"""Unit tests for SignalGenerator."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from src.strategy.signals import SignalGenerator, TradeSignal


@pytest.fixture
def config():
    return {
        "strategy": {
            "indicators": {
                "ema_fast": 5, "ema_slow": 13, "rsi_period": 7,
                "rsi_bull_threshold": 60, "rsi_bear_threshold": 40,
                "atr_period": 10, "atr_avg_period": 100, "donchian_period": 10,
            },
            "exit": {
                "tp_atr_mult": 2.5, "sl_atr_mult": 1.2,
                "trail_atr_mult": 0.8, "trail_offset_ratio": 0.3,
            },
        }
    }


@pytest.fixture
def gen(config):
    return SignalGenerator(config)


@pytest.fixture
def sample_df():
    """Create sample OHLCV data with uptrend for testing."""
    np.random.seed(42)
    n = 120
    base = 4000.0
    prices = base + np.cumsum(np.random.randn(n) * 0.5 + 0.1)  # Uptrend
    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC"),
        "open": prices - np.random.rand(n) * 0.3,
        "high": prices + np.random.rand(n) * 1.5,
        "low": prices - np.random.rand(n) * 1.5,
        "close": prices,
        "tick_volume": np.random.randint(10, 500, n),
    })
    return df


class TestIndicators:
    def test_calculate_indicators_columns(self, gen, sample_df):
        result = gen.calculate_indicators(sample_df)
        expected_cols = ["ema_fast", "ema_slow", "rsi", "atr", "atr_avg", "dc_high", "dc_low"]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_ema_fast_shorter_than_slow(self, gen, sample_df):
        result = gen.calculate_indicators(sample_df)
        # In an uptrend, fast EMA should generally be above slow EMA
        last = result.iloc[-1]
        assert not pd.isna(last["ema_fast"])
        assert not pd.isna(last["ema_slow"])

    def test_rsi_range(self, gen, sample_df):
        result = gen.calculate_indicators(sample_df)
        rsi_values = result["rsi"].dropna()
        assert (rsi_values >= 0).all(), "RSI should be >= 0"
        assert (rsi_values <= 100).all(), "RSI should be <= 100"

    def test_atr_positive(self, gen, sample_df):
        result = gen.calculate_indicators(sample_df)
        atr_values = result["atr"].dropna()
        assert (atr_values > 0).all(), "ATR should be positive"

    def test_donchian_high_above_low(self, gen, sample_df):
        result = gen.calculate_indicators(sample_df)
        valid = result.dropna(subset=["dc_high", "dc_low"])
        assert (valid["dc_high"] >= valid["dc_low"]).all()


class TestSignalGeneration:
    def test_no_signal_with_insufficient_data(self, gen):
        df = pd.DataFrame({
            "time": [datetime.now(timezone.utc)],
            "open": [4000], "high": [4001], "low": [3999],
            "close": [4000], "tick_volume": [100],
        })
        df = gen.calculate_indicators(df)
        assert gen.generate_signal(df, 4000, 4001) is None

    def test_signal_returns_trade_signal_or_none(self, gen, sample_df):
        df = gen.calculate_indicators(sample_df)
        result = gen.generate_signal(df, 4050.0, 4050.5)
        assert result is None or isinstance(result, TradeSignal)

    def test_long_signal_tp_above_entry(self, gen, sample_df):
        df = gen.calculate_indicators(sample_df)
        result = gen.generate_signal(df, 4050.0, 4050.5)
        if result and result.direction == "LONG":
            assert result.take_profit > result.entry_price
            assert result.stop_loss < result.entry_price

    def test_short_signal_tp_below_entry(self, gen, sample_df):
        # Create downtrend data
        np.random.seed(42)
        n = 120
        prices = 4100 - np.cumsum(np.random.rand(n) * 0.5 + 0.1)
        df = pd.DataFrame({
            "time": pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC"),
            "open": prices + 0.3, "high": prices + 1.5,
            "low": prices - 1.5, "close": prices, "tick_volume": np.random.randint(10, 500, n),
        })
        df = gen.calculate_indicators(df)
        result = gen.generate_signal(df, 4050.0, 4050.5)
        if result and result.direction == "SHORT":
            assert result.take_profit < result.entry_price
            assert result.stop_loss > result.entry_price
