"""Trade filters: session, ATR spike, and news blackout."""

from datetime import datetime, time, timezone
from typing import Optional

from loguru import logger


class TradeFilter:
    """Evaluates all pre-trade filters before allowing entries.

    Filters:
    1. Session filter — only trade 12:00–21:00 UTC, Mon–Fri
    2. ATR spike filter — skip if volatility abnormally high
    3. News blackout — skip around high-impact news events
    """

    def __init__(self, config: dict, news_filter=None):
        flt = config["strategy"]["filters"]
        h1, m1 = map(int, flt["session_start_utc"].split(":"))
        h2, m2 = map(int, flt["session_end_utc"].split(":"))
        h3, m3 = map(int, flt["force_close_utc"].split(":"))

        self.session_start = time(h1, m1)
        self.session_end = time(h2, m2)
        self.force_close_time = time(h3, m3)
        self.trading_days = flt["trading_days"]         # [0,1,2,3,4]
        self.spike_threshold = flt["atr_spike_threshold"]  # 2.0
        self.news_filter = news_filter
        self._last_blackout_log = None

    def is_session_active(self, utc_now: datetime) -> bool:
        """Check if current UTC time is within the trading session.

        Trading session: 12:00–21:00 UTC, Monday–Friday.
        """
        if utc_now.weekday() not in self.trading_days:
            return False
        current_time = utc_now.time()
        return self.session_start <= current_time < self.session_end

    def should_force_close(self, utc_now: datetime) -> bool:
        """Check if we should force-close all positions (20:55 UTC).

        Returns True during the force-close minute window.
        """
        current_time = utc_now.time()
        return current_time >= self.force_close_time and current_time < self.session_end

    def is_atr_spike(self, current_atr: float, avg_atr: float) -> bool:
        """Check if ATR indicates abnormal volatility (news proxy).

        Args:
            current_atr: Current ATR value.
            avg_atr: Average ATR over 100 bars.

        Returns:
            True if ATR exceeds threshold × average (skip trade).
        """
        if avg_atr <= 0:
            return False
        return current_atr > (avg_atr * self.spike_threshold)

    def is_news_blackout(self, utc_now: datetime) -> bool:
        """Check if current time falls within a news blackout window.

        Args:
            utc_now: Current UTC datetime.

        Returns:
            True if within blackout (skip trade).
        """
        if self.news_filter is None:
            return False
        try:
            is_blackout, event_name = self.news_filter.is_in_blackout(utc_now)
            if is_blackout and event_name != self._last_blackout_log:
                logger.warning("📰 News blackout: {}", event_name)
                self._last_blackout_log = event_name
            elif not is_blackout:
                self._last_blackout_log = None
            return is_blackout
        except Exception as e:
            logger.warning("News filter error (allowing trade): {}", e)
            return False

    def can_trade(
        self, utc_now: datetime, current_atr: float, avg_atr: float
    ) -> tuple:
        """Master filter — checks ALL conditions for trade eligibility.

        Args:
            utc_now: Current UTC datetime.
            current_atr: Current ATR value.
            avg_atr: Average ATR over 100 bars.

        Returns:
            Tuple of (can_trade: bool, reason: str).
            reason is empty if can_trade is True.
        """
        if not self.is_session_active(utc_now):
            return False, "Outside trading session"

        if self.is_atr_spike(current_atr, avg_atr):
            return False, f"ATR spike ({current_atr:.5f} > {avg_atr * self.spike_threshold:.5f})"

        if self.is_news_blackout(utc_now):
            return False, "News blackout active"

        return True, ""
