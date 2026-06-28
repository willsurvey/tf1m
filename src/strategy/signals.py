"""Signal generation: technical indicators and entry signal logic."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class TradeSignal:
    """Represents a validated trade signal."""
    direction: str          # "LONG" or "SHORT"
    entry_price: float      # Current ask (LONG) or bid (SHORT)
    take_profit: float      # Calculated TP price
    stop_loss: float        # Calculated SL price
    trail_distance: float   # Trailing stop distance in price
    atr_value: float        # Current ATR value
    timestamp: datetime     # Signal generation time


class SignalGenerator:
    """Calculate technical indicators and generate LONG/SHORT signals.

    Implements AGGRO V6 strategy:
    - EMA crossover (5/13) for trend direction
    - RSI (7) for momentum confirmation
    - Donchian Channel (10) for breakout trigger
    - ATR (10) for dynamic TP/SL/Trail sizing
    """

    def __init__(self, config: dict):
        ind = config["strategy"]["indicators"]
        self.ema_fast_period = ind["ema_fast"]          # 5
        self.ema_slow_period = ind["ema_slow"]          # 13
        self.rsi_period = ind["rsi_period"]             # 7
        self.rsi_bull = ind["rsi_bull_threshold"]       # 60
        self.rsi_bear = ind["rsi_bear_threshold"]       # 40
        self.atr_period = ind["atr_period"]             # 10
        self.atr_avg_period = ind["atr_avg_period"]     # 100
        self.dc_period = ind["donchian_period"]         # 10

        ext = config["strategy"]["exit"]
        self.tp_mult = ext["tp_atr_mult"]               # 2.5
        self.sl_mult = ext["sl_atr_mult"]               # 1.2
        self.trail_mult = ext["trail_atr_mult"]         # 0.8

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators on OHLCV data.

        Adds columns: ema_fast, ema_slow, rsi, atr, atr_avg, dc_high, dc_low.

        Args:
            df: DataFrame with columns [time, open, high, low, close, tick_volume].

        Returns:
            DataFrame with added indicator columns.
        """
        df = df.copy()
        df["ema_fast"] = self._calc_ema(df["close"], self.ema_fast_period)
        df["ema_slow"] = self._calc_ema(df["close"], self.ema_slow_period)
        df["rsi"] = self._calc_rsi(df["close"], self.rsi_period)
        df["atr"] = self._calc_atr(df["high"], df["low"], df["close"], self.atr_period)
        df["atr_avg"] = df["atr"].rolling(window=self.atr_avg_period, min_periods=1).mean()
        df["dc_high"] = df["high"].rolling(window=self.dc_period).max()
        df["dc_low"] = df["low"].rolling(window=self.dc_period).min()
        return df

    def generate_signal(
        self, df: pd.DataFrame, bid: float, ask: float
    ) -> Optional[TradeSignal]:
        """Generate a LONG or SHORT signal from the latest bar.

        Args:
            df: DataFrame with indicator columns (from calculate_indicators).
            bid: Current bid price.
            ask: Current ask price.

        Returns:
            TradeSignal if conditions met, None otherwise.
        """
        if len(df) < 2:
            return None

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        # Validate required columns exist and have valid values
        required = ["ema_fast", "ema_slow", "rsi", "atr", "dc_high", "dc_low"]
        try:
            if any(pd.isna(curr[col]) for col in required):
                return None
        except KeyError:
            return None

        atr = curr["atr"]
        if atr <= 0:
            return None

        # === LONG conditions ===
        long_trend = curr["ema_fast"] > curr["ema_slow"]
        long_price = curr["close"] > curr["ema_fast"]
        long_momentum = curr["rsi"] > self.rsi_bull
        long_breakout = curr["high"] >= prev["dc_high"]
        is_long = long_trend and long_price and long_momentum and long_breakout

        # === SHORT conditions ===
        short_trend = curr["ema_fast"] < curr["ema_slow"]
        short_price = curr["close"] < curr["ema_fast"]
        short_momentum = curr["rsi"] < self.rsi_bear
        short_breakout = curr["low"] <= prev["dc_low"]
        is_short = short_trend and short_price and short_momentum and short_breakout

        if not is_long and not is_short:
            return None

        # Build signal
        if is_long:
            entry = ask
            tp = entry + (atr * self.tp_mult)
            sl = entry - (atr * self.sl_mult)
            direction = "LONG"
        else:
            entry = bid
            tp = entry - (atr * self.tp_mult)
            sl = entry + (atr * self.sl_mult)
            direction = "SHORT"

        trail_dist = atr * self.trail_mult

        signal = TradeSignal(
            direction=direction,
            entry_price=round(entry, 3),
            take_profit=round(tp, 3),
            stop_loss=round(sl, 3),
            trail_distance=round(trail_dist, 5),
            atr_value=round(atr, 5),
            timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "Signal: {} | entry={:.3f} | TP={:.3f} | SL={:.3f} | ATR={:.5f}",
            direction, entry, tp, sl, atr,
        )
        return signal

    # ── Indicator helpers ────────────────────────────────────

    @staticmethod
    def _calc_ema(series: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _calc_rsi(series: pd.Series, period: int) -> pd.Series:
        """Calculate RSI using Wilder's smoothing (EMA of gains/losses)."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _calc_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """Calculate Average True Range."""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
