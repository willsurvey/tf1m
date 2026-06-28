"""Unit tests for TradeFilter."""

import pytest
from datetime import datetime, time, timezone

from src.strategy.filters import TradeFilter


@pytest.fixture
def config():
    return {
        "strategy": {
            "filters": {
                "session_start_utc": "12:00",
                "session_end_utc": "21:00",
                "force_close_utc": "20:55",
                "trading_days": [0, 1, 2, 3, 4],
                "atr_spike_threshold": 2.0,
            }
        }
    }


@pytest.fixture
def trade_filter(config):
    return TradeFilter(config, news_filter=None)


class TestSessionFilter:
    def test_active_during_session(self, trade_filter):
        # Wednesday 14:30 UTC
        dt = datetime(2026, 6, 24, 14, 30, tzinfo=timezone.utc)
        assert trade_filter.is_session_active(dt) is True

    def test_inactive_before_session(self, trade_filter):
        # Wednesday 08:00 UTC
        dt = datetime(2026, 6, 24, 8, 0, tzinfo=timezone.utc)
        assert trade_filter.is_session_active(dt) is False

    def test_inactive_after_session(self, trade_filter):
        # Wednesday 22:00 UTC
        dt = datetime(2026, 6, 24, 22, 0, tzinfo=timezone.utc)
        assert trade_filter.is_session_active(dt) is False

    def test_inactive_on_saturday(self, trade_filter):
        # Saturday 14:00 UTC
        dt = datetime(2026, 6, 27, 14, 0, tzinfo=timezone.utc)
        assert trade_filter.is_session_active(dt) is False

    def test_inactive_on_sunday(self, trade_filter):
        # Sunday 14:00 UTC
        dt = datetime(2026, 6, 28, 14, 0, tzinfo=timezone.utc)
        assert trade_filter.is_session_active(dt) is False

    def test_active_at_session_start(self, trade_filter):
        dt = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
        assert trade_filter.is_session_active(dt) is True

    def test_inactive_at_session_end(self, trade_filter):
        dt = datetime(2026, 6, 24, 21, 0, tzinfo=timezone.utc)
        assert trade_filter.is_session_active(dt) is False


class TestForceClose:
    def test_force_close_at_2055(self, trade_filter):
        dt = datetime(2026, 6, 24, 20, 55, tzinfo=timezone.utc)
        assert trade_filter.should_force_close(dt) is True

    def test_no_force_close_at_2050(self, trade_filter):
        dt = datetime(2026, 6, 24, 20, 50, tzinfo=timezone.utc)
        assert trade_filter.should_force_close(dt) is False

    def test_force_close_at_2059(self, trade_filter):
        dt = datetime(2026, 6, 24, 20, 59, tzinfo=timezone.utc)
        assert trade_filter.should_force_close(dt) is True


class TestATRSpike:
    def test_spike_detected(self, trade_filter):
        assert trade_filter.is_atr_spike(5.0, 2.0) is True  # 5 > 2*2

    def test_normal_atr(self, trade_filter):
        assert trade_filter.is_atr_spike(3.0, 2.0) is False  # 3 < 2*2

    def test_atr_at_threshold(self, trade_filter):
        assert trade_filter.is_atr_spike(4.0, 2.0) is False  # 4 == 2*2 (not >)

    def test_zero_avg_atr(self, trade_filter):
        assert trade_filter.is_atr_spike(5.0, 0.0) is False


class TestCanTrade:
    def test_all_pass(self, trade_filter):
        dt = datetime(2026, 6, 24, 15, 0, tzinfo=timezone.utc)
        can, reason = trade_filter.can_trade(dt, 2.0, 2.0)
        assert can is True
        assert reason == ""

    def test_blocked_by_session(self, trade_filter):
        dt = datetime(2026, 6, 24, 8, 0, tzinfo=timezone.utc)
        can, reason = trade_filter.can_trade(dt, 2.0, 2.0)
        assert can is False
        assert "session" in reason.lower()

    def test_blocked_by_atr_spike(self, trade_filter):
        dt = datetime(2026, 6, 24, 15, 0, tzinfo=timezone.utc)
        can, reason = trade_filter.can_trade(dt, 10.0, 2.0)
        assert can is False
        assert "ATR" in reason
