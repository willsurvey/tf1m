"""Economic calendar fetcher: MT5 calendar -> FF JSON API -> hardcoded fallback."""

import json
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


# Hard-coded high-impact USD events for 2026 (FOMC, NFP, CPI)
# These serve as offline fallback when no live source is available.
# Dates sourced from federalreserve.gov and bls.gov.
HARDCODED_2026_EVENTS = [
    # FOMC Interest Rate Decisions
    {"name": "FOMC Interest Rate Decision", "date": "2026-01-29", "time": "19:00"},
    {"name": "FOMC Interest Rate Decision", "date": "2026-03-19", "time": "18:00"},
    {"name": "FOMC Interest Rate Decision", "date": "2026-05-07", "time": "18:00"},
    {"name": "FOMC Interest Rate Decision", "date": "2026-06-18", "time": "18:00"},
    {"name": "FOMC Interest Rate Decision", "date": "2026-07-30", "time": "18:00"},
    {"name": "FOMC Interest Rate Decision", "date": "2026-09-17", "time": "18:00"},
    {"name": "FOMC Interest Rate Decision", "date": "2026-11-05", "time": "19:00"},
    {"name": "FOMC Interest Rate Decision", "date": "2026-12-17", "time": "19:00"},
    # Non-Farm Payrolls — first Friday of each month at 12:30 UTC
    {"name": "Non-Farm Payrolls", "date": "2026-01-09", "time": "13:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-02-06", "time": "13:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-03-06", "time": "13:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-04-03", "time": "12:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-05-08", "time": "12:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-06-05", "time": "12:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-07-10", "time": "12:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-08-07", "time": "12:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-09-04", "time": "12:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-10-02", "time": "12:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-11-06", "time": "13:30"},
    {"name": "Non-Farm Payrolls", "date": "2026-12-04", "time": "13:30"},
    # US CPI — approx 2nd Wednesday each month
    {"name": "US CPI m/m", "date": "2026-01-14", "time": "13:30"},
    {"name": "US CPI m/m", "date": "2026-02-11", "time": "13:30"},
    {"name": "US CPI m/m", "date": "2026-03-11", "time": "12:30"},
    {"name": "US CPI m/m", "date": "2026-04-10", "time": "12:30"},
    {"name": "US CPI m/m", "date": "2026-05-13", "time": "12:30"},
    {"name": "US CPI m/m", "date": "2026-06-10", "time": "12:30"},
    {"name": "US CPI m/m", "date": "2026-07-15", "time": "12:30"},
    {"name": "US CPI m/m", "date": "2026-08-12", "time": "12:30"},
    {"name": "US CPI m/m", "date": "2026-09-09", "time": "12:30"},
    {"name": "US CPI m/m", "date": "2026-10-14", "time": "12:30"},
    {"name": "US CPI m/m", "date": "2026-11-12", "time": "13:30"},
    {"name": "US CPI m/m", "date": "2026-12-09", "time": "13:30"},
]


class CalendarFetcher:
    """Fetches high-impact economic events for news filtering.

    Data Sources (in priority order):
    1. MT5 built-in economic calendar (if available in terminal build 3290+)
    2. ForexFactory JSON API — nfs.faireconomy.media (no HTML scraping)
    3. Hard-coded known 2026 high-impact events (always available offline)
    4. Local JSON cache (6 hour TTL between refreshes)
    """

    # Official FF JSON endpoint — no scraping, no bot detection issues
    FF_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

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

        # 1. Check local cache first
        cached = self._load_cache()
        if cached is not None:
            logger.debug("Using cached news events ({} items)", len(cached))
            return cached

        events = []

        # 2. Try MT5 built-in calendar
        if HAS_MT5:
            events = self._fetch_from_mt5()
            if events:
                logger.info("Fetched {} events from MT5 calendar", len(events))
                self._save_cache(events)
                return events

        # 3. Try ForexFactory JSON API (fast, reliable, no scraping)
        events = self._fetch_from_ff_json()
        if events:
            logger.info("Fetched {} events from ForexFactory JSON API", len(events))
            self._save_cache(events)
            return events

        # 4. Final fallback: hard-coded known dates
        events = self._get_hardcoded_today()
        if events:
            logger.info(
                "Using hard-coded events ({} today) — no live calendar available",
                len(events),
            )
        else:
            logger.info("No high-impact USD events scheduled today")

        # Cache even empty result to avoid repeated failed fetches
        self._save_cache(events)
        return events

    def _fetch_from_mt5(self) -> list:
        """Fetch from MT5 built-in economic calendar (build 3290+)."""
        try:
            if not hasattr(mt5, "calendar_by_country"):
                return []

            now = datetime.now(timezone.utc)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

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

    def _fetch_from_ff_json(self) -> list:
        """Fetch from ForexFactory JSON endpoint — no HTML scraping required.

        Uses the official nfs.faireconomy.media endpoint provided by FF
        for their calendar widget. Reliable and does not trigger bot detection.
        """
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            }
            resp = requests.get(self.FF_JSON_URL, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.debug("FF JSON API returned status {}", resp.status_code)
                return []

            data = resp.json()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            events = []

            for item in data:
                currency = item.get("currency", "")
                impact = item.get("impact", "").lower()
                title = item.get("title", "")
                raw_date = item.get("date", "")

                if currency not in self.currencies:
                    continue
                if impact not in self.impact_levels:
                    continue

                try:
                    ev_time = datetime.fromisoformat(raw_date)
                    if ev_time.tzinfo is None:
                        # FF returns NY local time — assume UTC-4 (EDT)
                        ev_time = ev_time.replace(
                            tzinfo=timezone(timedelta(hours=-4))
                        ).astimezone(timezone.utc)
                    else:
                        ev_time = ev_time.astimezone(timezone.utc)

                    if ev_time.strftime("%Y-%m-%d") != today:
                        continue

                    events.append({
                        "name": title,
                        "currency": currency,
                        "impact": impact,
                        "datetime_utc": ev_time.isoformat(),
                    })
                except Exception:
                    continue

            return events

        except requests.exceptions.Timeout:
            logger.debug("FF JSON API timed out (10s)")
            return []
        except Exception as e:
            logger.debug("FF JSON fetch failed: {}", e)
            return []

    def _get_hardcoded_today(self) -> list:
        """Return hard-coded events scheduled for today (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        events = []
        for ev in HARDCODED_2026_EVENTS:
            if ev["date"] == today:
                ev_time_str = f"{ev['date']}T{ev['time']}:00+00:00"
                events.append({
                    "name": ev["name"],
                    "currency": "USD",
                    "impact": "high",
                    "datetime_utc": ev_time_str,
                })
        return events

    def _load_cache(self) -> Optional[list]:
        """Load cached events if still valid (within TTL and same day)."""
        if not self.cache_file.exists():
            return None
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("cached_at", ""))
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - cached_at > timedelta(hours=self.cache_ttl_hours):
                return None
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if data.get("date") != today:
                return None
            return data.get("events", [])
        except Exception:
            return None

    def _save_cache(self, events: list) -> None:
        """Save events list to local JSON cache file."""
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
