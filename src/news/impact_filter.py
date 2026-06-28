"""News impact filter: evaluates blackout windows around high-impact events."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger

from src.news.calendar_fetcher import CalendarFetcher


class NewsImpactFilter:
    """Determines if current time falls within a news blackout window.

    Blackout window: [event_time - 15 min, event_time + 10 min]
    Only applies to HIGH impact USD events.
    """

    def __init__(self, config: dict, calendar_fetcher: CalendarFetcher):
        news_cfg = config["strategy"]["news"]
        self.blackout_before = timedelta(minutes=news_cfg["blackout_before_min"])  # 15
        self.blackout_after = timedelta(minutes=news_cfg["blackout_after_min"])    # 10
        self.calendar = calendar_fetcher
        self._blackout_windows: list = []
        self._last_refresh: Optional[datetime] = None

    def _refresh_windows(self) -> None:
        """Refresh blackout windows from calendar (cached internally)."""
        now = datetime.now(timezone.utc)

        # Only refresh every 30 minutes
        if self._last_refresh and (now - self._last_refresh).seconds < 1800:
            return

        events = self.calendar.fetch_today_events()
        self._blackout_windows = []

        for ev in events:
            try:
                ev_time = datetime.fromisoformat(ev["datetime_utc"])
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=timezone.utc)

                window_start = ev_time - self.blackout_before
                window_end = ev_time + self.blackout_after

                self._blackout_windows.append({
                    "name": ev["name"],
                    "event_time": ev_time,
                    "start": window_start,
                    "end": window_end,
                })
            except Exception as e:
                logger.debug("Failed to parse event: {} - {}", ev, e)

        self._last_refresh = now

        if self._blackout_windows:
            logger.info(
                "News blackout windows loaded: {} events",
                len(self._blackout_windows),
            )
            for w in self._blackout_windows:
                logger.info(
                    "  📰 {} | {} - {}",
                    w["name"],
                    w["start"].strftime("%H:%M"),
                    w["end"].strftime("%H:%M"),
                )

    def get_blackout_windows(self) -> list:
        """Get all blackout windows for today.

        Returns:
            List of dicts with name, event_time, start, end.
        """
        self._refresh_windows()
        return self._blackout_windows

    def is_in_blackout(self, utc_now: datetime) -> tuple:
        """Check if current time is within any blackout window.

        Args:
            utc_now: Current UTC datetime.

        Returns:
            Tuple of (is_blackout: bool, event_name: Optional[str]).
        """
        self._refresh_windows()

        for window in self._blackout_windows:
            if window["start"] <= utc_now <= window["end"]:
                return True, window["name"]

        return False, None

    def get_next_event(self, utc_now: datetime) -> Optional[dict]:
        """Get the next upcoming high-impact event.

        Args:
            utc_now: Current UTC datetime.

        Returns:
            Event dict or None if no upcoming events.
        """
        self._refresh_windows()

        upcoming = [
            w for w in self._blackout_windows
            if w["event_time"] > utc_now
        ]

        if not upcoming:
            return None

        upcoming.sort(key=lambda w: w["event_time"])
        return upcoming[0]
