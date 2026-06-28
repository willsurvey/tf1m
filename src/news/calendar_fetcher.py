"""Economic calendar fetcher: MT5 calendar + ForexFactory fallback."""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    HAS_MT5 = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class CalendarFetcher:
    """Fetches high-impact economic events for news filtering.

    Data Sources (in priority order):
    1. MT5 built-in economic calendar
    2. ForexFactory HTML scraping (fallback)
    3. Local JSON cache
    """

    # Known high-impact USD events (manual fallback)
    KNOWN_HIGH_IMPACT = [
        "Non-Farm Payrolls", "NFP", "FOMC", "Fed Interest Rate",
        "CPI", "Consumer Price Index", "PPI", "Producer Price Index",
        "GDP", "Gross Domestic Product", "Unemployment Claims",
        "ISM Manufacturing", "ISM Services", "Fed Chair",
        "PCE Price Index", "Retail Sales", "Durable Goods",
    ]

    def __init__(self, config: dict):
        news_cfg = config["strategy"]["news"]
        self.enabled = news_cfg.get("enabled", True)
        self.cache_ttl_hours = news_cfg.get("cache_ttl_hours", 6)
        self.currencies = news_cfg.get("currencies", ["USD"])
        self.impact_levels = news_cfg.get("impact_levels", ["high"])
        self.cache_file = Path("data/news_cache.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def fetch_today_events(self) -> list:
        """Fetch today's high-impact economic events.

        Returns:
            List of dicts with keys: name, currency, impact, datetime_utc.
        """
        if not self.enabled:
            return []

        # 1. Check cache
        cached = self._load_cache()
        if cached is not None:
            logger.debug("Using cached news events ({} items)", len(cached))
            return cached

        events = []

        # 2. Try MT5 calendar
        if HAS_MT5:
            events = self._fetch_from_mt5()
            if events:
                logger.info("Fetched {} events from MT5 calendar", len(events))
                self._save_cache(events)
                return events

        # 3. Fallback: ForexFactory
        if HAS_BS4:
            events = self._fetch_from_forexfactory()
            if events:
                logger.info("Fetched {} events from ForexFactory", len(events))
                self._save_cache(events)
                return events

        logger.warning("No news source available, using empty calendar")
        return []

    def _fetch_from_mt5(self) -> list:
        """Fetch from MT5 built-in economic calendar."""
        try:
            now = datetime.now(timezone.utc)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            # MT5 calendar functions (available in newer builds)
            if not hasattr(mt5, "calendar_by_country"):
                return []

            events_raw = mt5.calendar_by_country("US")
            if not events_raw:
                return []

            events = []
            for ev in events_raw:
                ev_time = datetime.fromtimestamp(ev.time, tz=timezone.utc)
                if day_start <= ev_time < day_end:
                    importance = {1: "low", 2: "medium", 3: "high"}.get(
                        ev.importance, "low"
                    )
                    if importance in self.impact_levels:
                        events.append({
                            "name": ev.name,
                            "currency": "USD",
                            "impact": importance,
                            "datetime_utc": ev_time.isoformat(),
                        })
            return events

        except Exception as e:
            logger.debug("MT5 calendar fetch failed: {}", e)
            return []

    def _fetch_from_forexfactory(self) -> list:
        """Fallback: scrape ForexFactory calendar."""
        try:
            url = "https://www.forexfactory.com/calendar"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )
            }
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "lxml")
            events = []
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            rows = soup.select("tr.calendar__row")
            for row in rows:
                currency_el = row.select_one(".calendar__currency")
                impact_el = row.select_one(".calendar__impact span")
                event_el = row.select_one(".calendar__event-title")
                time_el = row.select_one(".calendar__time")

                if not all([currency_el, event_el]):
                    continue

                currency = currency_el.get_text(strip=True)
                if currency not in self.currencies:
                    continue

                # Determine impact from CSS class
                impact = "low"
                if impact_el:
                    classes = impact_el.get("class", [])
                    class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                    if "high" in class_str or "red" in class_str:
                        impact = "high"
                    elif "medium" in class_str or "orange" in class_str:
                        impact = "medium"

                if impact not in self.impact_levels:
                    continue

                event_name = event_el.get_text(strip=True)
                time_str = time_el.get_text(strip=True) if time_el else "00:00"

                # Parse time (ForexFactory uses ET)
                try:
                    if ":" in time_str:
                        # Convert approximate time — just capture the event
                        events.append({
                            "name": event_name,
                            "currency": currency,
                            "impact": impact,
                            "datetime_utc": f"{today_str}T{time_str}:00+00:00",
                        })
                except Exception:
                    pass

            return events

        except Exception as e:
            logger.debug("ForexFactory fetch failed: {}", e)
            return []

    def _load_cache(self) -> Optional[list]:
        """Load cached events if still valid."""
        if not self.cache_file.exists():
            return None
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("cached_at", ""))
            if datetime.now(timezone.utc) - cached_at > timedelta(hours=self.cache_ttl_hours):
                return None
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if data.get("date") != today:
                return None
            return data.get("events", [])
        except Exception:
            return None

    def _save_cache(self, events: list) -> None:
        """Save events to cache file."""
        try:
            data = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "events": events,
            }
            self.cache_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Cache save failed: {}", e)
