"""Signal generation — 100% identik dengan Pine Script XAUUSD M1 AGGRO V6.

Pine Script reference:
  strategy("XAUUSD M1 AGGRO V6", pyramiding=3)

Entry LONG:
  bullMomentum = fastMA > slowMA AND close > fastMA AND rsi > 60
  bullBreak    = high >= dcHigh[1]
  → Entry jika canTrade AND bullMomentum AND bullBreak

Entry SHORT:
  bearMomentum = fastMA < slowMA AND close < fastMA AND rsi < 40
  bearBreak    = low <= dcLow[1]
  → Entry jika canTrade AND bearMomentum AND bearBreak

TP = 2.5x ATR | SL = 1.2x ATR | Trail = 0.8x ATR | Trail offset = 30%
"""

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
    """Calculate technical indicators dan generate LONG/SHORT signals.

    EXACT replica of Pine Script XAUUSD M1 AGGRO V6:
    - EMA(5) dan EMA(13) untuk trend direction   → Pine: ta.ema(close, 5/13)
    - RSI(7) untuk momentum confirmation          → Pine: ta.rsi(close, 7)
    - Donchian Channel(10) untuk breakout trigger → Pine: ta.highest/lowest(high/low, 10)
    - ATR(10) untuk TP/SL/Trail sizing            → Pine: ta.atr(10)
    """

    def __init__(self, config: dict):
        ind = config["strategy"]["indicators"]
        # EMA — Pine: emaFast=5, emaSlow=13
        self.ema_fast_period = ind["ema_fast"]       # 5
        self.ema_slow_period = ind["ema_slow"]       # 13
        # RSI — Pine: rsiLen=7, rsiOB=60, rsiOS=40
        self.rsi_period = ind["rsi_period"]          # 7
        self.rsi_ob     = ind["rsi_ob"]              # 60 (bull threshold)
        self.rsi_os     = ind["rsi_os"]              # 40 (bear threshold)
        # ATR — Pine: atrLen=10
        self.atr_period     = ind["atr_period"]      # 10
        self.atr_avg_period = ind["atr_avg_period"]  # 100
        # Donchian — Pine: dcLen=10
        self.dc_period = ind["donchian_period"]      # 10

        ext = config["strategy"]["exit"]
        self.tp_mult    = ext["tp_atr_mult"]    # 2.5  — Pine: tpMult=2.5
        self.sl_mult    = ext["sl_atr_mult"]    # 1.2  — Pine: slMult=1.2
        self.trail_mult = ext["trail_atr_mult"] # 0.8  — Pine: trailMult=0.8

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators on OHLCV data.

        Semua identik dengan Pine internals:
        - ta.ema   → ewm(span=period, adjust=False)
        - ta.rsi   → Wilder's RMA (ewm alpha=1/period)
        - ta.atr   → Wilder's RMA true range
        - ta.highest/lowest → rolling max/min

        Args:
            df: DataFrame dengan kolom [time, open, high, low, close, tick_volume].

        Returns:
            DataFrame dengan kolom indikator tambahan.
        """
        df = df.copy()

        # EMA — Pine: fastMA = ta.ema(close, 5)
        df["ema_fast"] = self._calc_ema(df["close"], self.ema_fast_period)
        df["ema_slow"] = self._calc_ema(df["close"], self.ema_slow_period)

        # RSI — Pine: rsi = ta.rsi(close, 7) → Wilder's RMA
        df["rsi"] = self._calc_rsi(df["close"], self.rsi_period)

        # ATR — Pine: atr = ta.atr(10) → Wilder's RMA
        df["atr"]     = self._calc_atr(df["high"], df["low"], df["close"], self.atr_period)
        df["atr_avg"] = df["atr"].rolling(window=self.atr_avg_period, min_periods=1).mean()

        # Donchian Channel — Pine: dcHigh=ta.highest(high,10), dcLow=ta.lowest(low,10)
        # Pine pakai dcHigh[1] dan dcLow[1] → kita shift(1) untuk match [1]
        df["dc_high"] = df["high"].rolling(window=self.dc_period).max().shift(1)
        df["dc_low"]  = df["low"].rolling(window=self.dc_period).min().shift(1)

        return df

    def generate_signal(
        self, df: pd.DataFrame, bid: float, ask: float
    ) -> Optional[TradeSignal]:
        """Generate LONG atau SHORT signal.

        100% identik dengan Pine Script AGGRO V6:

          bullMomentum = fastMA > slowMA and close > fastMA and rsi > rsiOB
          bearMomentum = fastMA < slowMA and close < fastMA and rsi < rsiOS
          bullBreak    = high >= dcHigh[1]
          bearBreak    = low  <= dcLow[1]

          if canTrade and bullMomentum and bullBreak → Entry Long
          if canTrade and bearMomentum and bearBreak → Entry Short

        (Filter canTrade = session + ATR spike dihandle di TradeFilter)

        Args:
            df: DataFrame dengan indicator columns dari calculate_indicators.
            bid: Current bid price.
            ask: Current ask price.

        Returns:
            TradeSignal jika kondisi terpenuhi, None jika tidak.
        """
        if len(df) < self.dc_period + 2:
            return None

        curr = df.iloc[-1]

        # Validasi semua kolom ada dan tidak NaN
        required = ["ema_fast", "ema_slow", "rsi", "atr", "dc_high", "dc_low"]
        try:
            if any(pd.isna(curr[col]) for col in required):
                return None
        except KeyError:
            return None

        atr = float(curr["atr"])
        if atr <= 0:
            return None

        fast_ma  = float(curr["ema_fast"])
        slow_ma  = float(curr["ema_slow"])
        rsi      = float(curr["rsi"])
        close    = float(curr["close"])
        high     = float(curr["high"])
        low      = float(curr["low"])
        dc_high  = float(curr["dc_high"])  # sudah shift(1) = dcHigh[1] di Pine
        dc_low   = float(curr["dc_low"])   # sudah shift(1) = dcLow[1] di Pine

        # === LONG — Pine: bullMomentum AND bullBreak ===
        bull_momentum = (fast_ma > slow_ma) and (close > fast_ma) and (rsi > self.rsi_ob)
        bull_break    = (high >= dc_high)
        is_long       = bull_momentum and bull_break

        # === SHORT — Pine: bearMomentum AND bearBreak ===
        bear_momentum = (fast_ma < slow_ma) and (close < fast_ma) and (rsi < self.rsi_os)
        bear_break    = (low <= dc_low)
        is_short      = bear_momentum and bear_break

        if not is_long and not is_short:
            return None

        # Build signal — exit sizing identik Pine
        # tpTicks = atr*tpMult/mintick → dalam price: atr*tpMult
        if is_long:
            entry = ask
            tp    = entry + (atr * self.tp_mult)  # +2.5 ATR
            sl    = entry - (atr * self.sl_mult)  # -1.2 ATR
            direction = "LONG"
        else:
            entry = bid
            tp    = entry - (atr * self.tp_mult)  # -2.5 ATR
            sl    = entry + (atr * self.sl_mult)  # +1.2 ATR
            direction = "SHORT"

        # trail_points = atr * 0.8 (aktivasi trail)
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
            "Signal: {} | entry={:.3f} | TP={:.3f} | SL={:.3f} | "
            "ATR={:.3f} | EMA[{:.3f}/{:.3f}] | RSI={:.1f} | "
            "DC[{:.3f}/{:.3f}]",
            direction, entry, tp, sl, atr,
            fast_ma, slow_ma, rsi, dc_low, dc_high,
        )
        return signal

    # ── Indicator helpers (identik dengan Pine internals) ─────────────────────

    @staticmethod
    def _calc_ema(series: pd.Series, period: int) -> pd.Series:
        """EMA — Pine: ta.ema() → ewm span=period, adjust=False."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _calc_rsi(series: pd.Series, period: int) -> pd.Series:
        """RSI — Pine: ta.rsi() pakai Wilder's RMA (alpha=1/period).

        Identik dengan ta.rma() internal Pine.
        """
        delta    = series.diff()
        gain     = delta.clip(lower=0)
        loss     = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _calc_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """ATR — Pine: ta.atr() pakai Wilder's RMA (alpha=1/period).

        True Range = max(H-L, |H-prevC|, |L-prevC|), lalu RMA.
        """
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low  - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
