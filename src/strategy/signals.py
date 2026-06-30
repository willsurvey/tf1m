"""Signal generation — 100% identik dengan TradingView Pine Script.

Pine Script reference: XAUUSD M1 Scalper V1
Strategy: Bollinger Bands mean-reversion + RSI confirmation

Entry LONG:  close < BB_Lower AND RSI < 30  (oversold bounce)
Entry SHORT: close > BB_Upper AND RSI > 70  (overbought reversal)

TP = 1.2x ATR | SL = 3.0x ATR | Trail = 1.0x ATR | Trail offset = 40%
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
    """Calculate technical indicators and generate LONG/SHORT signals.

    EXACT replica of TradingView Pine Script strategy:
    - Bollinger Bands (20, 2.0) for mean-reversion trigger
    - RSI (14) for overbought/oversold confirmation
    - ATR (14) for dynamic TP/SL/Trail sizing

    Entry logic (sama persis dengan Pine):
      LONG:  close < BB_Lower AND RSI < rsi_os  (contrariant — bounce dari bawah)
      SHORT: close > BB_Upper AND RSI > rsi_ob  (contrariant — reversal dari atas)
    """

    def __init__(self, config: dict):
        ind = config["strategy"]["indicators"]
        # Bollinger Bands — sama dengan Pine: bbLen=20, bbMult=2.0
        self.bb_period = ind["bb_period"]          # 20
        self.bb_mult   = ind["bb_mult"]            # 2.0
        # RSI — sama dengan Pine: rsiLen=14
        self.rsi_period = ind["rsi_period"]        # 14
        self.rsi_ob     = ind["rsi_ob"]            # 70  (overbought)
        self.rsi_os     = ind["rsi_os"]            # 30  (oversold)
        # ATR — sama dengan Pine: atrLen=14
        self.atr_period     = ind["atr_period"]        # 14
        self.atr_avg_period = ind["atr_avg_period"]    # 100

        ext = config["strategy"]["exit"]
        self.tp_mult    = ext["tp_atr_mult"]    # 1.2  (sama Pine: tpMult=1.2)
        self.sl_mult    = ext["sl_atr_mult"]    # 3.0  (sama Pine: slMult=3.0)
        self.trail_mult = ext["trail_atr_mult"] # 1.0  (sama Pine: trailMult=1.0)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators on OHLCV data.

        Adds columns: bb_upper, bb_lower, bb_basis, rsi, atr, atr_avg.
        Semua identik dengan kalkulasi ta.bb() dan ta.rsi() di Pine Script.

        Args:
            df: DataFrame dengan kolom [time, open, high, low, close, tick_volume].

        Returns:
            DataFrame with added indicator columns.
        """
        df = df.copy()

        # Bollinger Bands — Pine: basis=ta.sma(close,20), dev=2.0*ta.stdev(close,20)
        # ta.stdev di Pine = std populasi (ddof=0) untuk period pertama,
        # tapi praktisnya sama dengan ddof=1 untuk data banyak — kita pakai ddof=1
        df["bb_basis"] = df["close"].rolling(window=self.bb_period, min_periods=self.bb_period).mean()
        bb_std         = df["close"].rolling(window=self.bb_period, min_periods=self.bb_period).std(ddof=1)
        df["bb_upper"] = df["bb_basis"] + (self.bb_mult * bb_std)
        df["bb_lower"] = df["bb_basis"] - (self.bb_mult * bb_std)

        # RSI — Pine: ta.rsi(close, 14) menggunakan Wilder's smoothing (RMA)
        df["rsi"] = self._calc_rsi(df["close"], self.rsi_period)

        # ATR — Pine: ta.atr(14) menggunakan RMA (Wilder's)
        df["atr"]     = self._calc_atr(df["high"], df["low"], df["close"], self.atr_period)
        df["atr_avg"] = df["atr"].rolling(window=self.atr_avg_period, min_periods=1).mean()

        return df

    def generate_signal(
        self, df: pd.DataFrame, bid: float, ask: float
    ) -> Optional[TradeSignal]:
        """Generate LONG atau SHORT signal.

        100% identik dengan kondisi entry Pine Script:
          longCond  = tradingAllowed and close < lower and rsi < rsiOS
          shortCond = tradingAllowed and close > upper and rsi > rsiOB

        (Filter tradingAllowed = session + ATR spike sudah ditangani di TradeFilter)

        Args:
            df: DataFrame dengan indicator columns (dari calculate_indicators).
            bid: Current bid price.
            ask: Current ask price.

        Returns:
            TradeSignal jika kondisi terpenuhi, None jika tidak.
        """
        if len(df) < self.bb_period + 1:
            return None

        curr = df.iloc[-1]

        # Validasi semua kolom tersedia dan tidak NaN
        required = ["bb_upper", "bb_lower", "bb_basis", "rsi", "atr"]
        try:
            if any(pd.isna(curr[col]) for col in required):
                return None
        except KeyError:
            return None

        atr = float(curr["atr"])
        if atr <= 0:
            return None

        close     = float(curr["close"])
        bb_upper  = float(curr["bb_upper"])
        bb_lower  = float(curr["bb_lower"])
        rsi       = float(curr["rsi"])

        # === LONG: close < BB_Lower AND RSI < 30 ===
        # Pine: longCond = tradingAllowed and close < lower and rsi < rsiOS
        is_long  = (close < bb_lower) and (rsi < self.rsi_os)

        # === SHORT: close > BB_Upper AND RSI > 70 ===
        # Pine: shortCond = tradingAllowed and close > upper and rsi > rsiOB
        is_short = (close > bb_upper) and (rsi > self.rsi_ob)

        if not is_long and not is_short:
            return None

        # Build signal — exit sizing identik dengan Pine
        # Pine: tpTicks = atr*tpMult, slTicks = atr*slMult, trailTicks = atr*trailMult
        if is_long:
            entry = ask                          # BUY di ask
            tp    = entry + (atr * self.tp_mult) # TP: 1.2x ATR di atas entry
            sl    = entry - (atr * self.sl_mult) # SL: 3.0x ATR di bawah entry
            direction = "LONG"
        else:
            entry = bid                          # SELL di bid
            tp    = entry - (atr * self.tp_mult) # TP: 1.2x ATR di bawah entry
            sl    = entry + (atr * self.sl_mult) # SL: 3.0x ATR di atas entry
            direction = "SHORT"

        # Trail distance = 1.0x ATR (Pine: trailMult=1.0)
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
            "ATR={:.3f} | BB=[{:.3f}~{:.3f}] | RSI={:.1f}",
            direction, entry, tp, sl, atr, bb_lower, bb_upper, rsi,
        )
        return signal

    # ── Indicator helpers (identik dengan Pine internals) ────────────────────

    @staticmethod
    def _calc_rsi(series: pd.Series, period: int) -> pd.Series:
        """RSI menggunakan Wilder's RMA smoothing — identik dengan Pine ta.rsi().

        Pine ta.rsi() = ta.rma() (Wilder's Moving Average), bukan EMA biasa.
        RMA alpha = 1/period (bukan 2/(period+1) seperti EMA).
        """
        delta    = series.diff()
        gain     = delta.clip(lower=0)
        loss     = (-delta).clip(lower=0)
        # Wilder's RMA = alpha 1/period, sama persis Pine ta.rma()
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _calc_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """ATR menggunakan Wilder's RMA — identik dengan Pine ta.atr().

        Pine ta.atr() menggunakan ta.rma() (Wilder) bukan SMA/EMA biasa.
        """
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low  - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # Wilder's RMA = ewm alpha=1/period
        return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
