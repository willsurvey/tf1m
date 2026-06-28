"""MT5 connection management and market data fetching."""

import os
import time
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger


class MT5Connector:
    """Manages connection to MetaTrader 5 terminal.

    Handles initialization, login, reconnection, and all data queries.
    """

    # MT5 timeframe mapping
    TIMEFRAMES = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }

    def __init__(self, config: dict):
        """Initialize MT5 connector with config.

        Args:
            config: Full configuration dictionary.
        """
        self.login = int(os.environ.get("MT5_LOGIN", 0))
        self.password = os.environ.get("MT5_PASSWORD", "")
        self.server = os.environ.get("MT5_SERVER", "")
        self.path = os.environ.get("MT5_PATH", "")
        self.magic = config["mt5"]["magic_number"]
        self.deviation = config["mt5"]["deviation"]
        self._connected = False

    def connect(self) -> bool:
        """Initialize MT5 terminal and login.

        Returns:
            True if connection and login succeed.
        """
        logger.info("Connecting to MT5 | server={}", self.server)

        init_kwargs = {}
        if self.path:
            init_kwargs["path"] = self.path

        if not mt5.initialize(**init_kwargs):
            logger.error("MT5 initialize failed: {}", mt5.last_error())
            return False

        if self.login and self.password and self.server:
            if not mt5.login(self.login, password=self.password, server=self.server):
                logger.error("MT5 login failed: {}", mt5.last_error())
                mt5.shutdown()
                return False

        self._connected = True
        info = mt5.account_info()
        if info:
            logger.info(
                "MT5 connected | account={} | balance={:.2f} | server={}",
                info.login, info.balance, info.server,
            )
        return True

    def disconnect(self) -> None:
        """Shutdown MT5 connection."""
        mt5.shutdown()
        self._connected = False
        logger.info("MT5 disconnected")

    def is_connected(self) -> bool:
        """Check if MT5 is connected and responsive.

        Returns:
            True if terminal is alive and responsive.
        """
        try:
            info = mt5.terminal_info()
            return info is not None and info.connected
        except Exception:
            return False

    def reconnect(self, max_attempts: int = 3, delay: float = 5.0) -> bool:
        """Attempt reconnection with retry logic.

        Args:
            max_attempts: Maximum reconnection attempts.
            delay: Seconds between attempts.

        Returns:
            True if reconnection succeeds.
        """
        for attempt in range(1, max_attempts + 1):
            logger.warning("Reconnecting to MT5 (attempt {}/{})", attempt, max_attempts)
            self.disconnect()
            time.sleep(delay)
            if self.connect():
                logger.info("Reconnected successfully on attempt {}", attempt)
                return True
        logger.error("Failed to reconnect after {} attempts", max_attempts)
        return False

    def get_ohlcv(
        self, symbol: str, timeframe: str = "M1", count: int = 100
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV candle data.

        Args:
            symbol: Trading symbol (e.g. 'XAUUSD').
            timeframe: Timeframe string ('M1', 'M5', 'H1', etc.).
            count: Number of bars to fetch.

        Returns:
            DataFrame with columns [time, open, high, low, close, tick_volume]
            or None on failure.
        """
        tf = self.TIMEFRAMES.get(timeframe, mt5.TIMEFRAME_M1)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

        if rates is None or len(rates) == 0:
            logger.warning("No OHLCV data for {} {}", symbol, timeframe)
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df[["time", "open", "high", "low", "close", "tick_volume"]]

    def get_current_price(self, symbol: str) -> Optional[tuple]:
        """Get current bid and ask price.

        Args:
            symbol: Trading symbol.

        Returns:
            Tuple of (bid, ask) or None on failure.
        """
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.warning("Cannot get price for {}", symbol)
            return None
        return (tick.bid, tick.ask)

    def get_symbol_info(self, symbol: str):
        """Get symbol information (point, digits, etc.).

        Args:
            symbol: Trading symbol.

        Returns:
            MT5 SymbolInfo object or None.
        """
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning("Symbol info not found: {}", symbol)
            # Ensure symbol is visible in MarketWatch
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
        return info

    def get_open_positions(
        self, symbol: Optional[str] = None, magic: Optional[int] = None
    ) -> list:
        """Get list of open positions filtered by symbol and/or magic number.

        Args:
            symbol: Filter by symbol (optional).
            magic: Filter by magic number (optional).

        Returns:
            List of position objects.
        """
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        result = list(positions)
        if magic is not None:
            result = [p for p in result if p.magic == magic]
        return result

    def get_account_info(self) -> dict:
        """Get account balance, equity, margin info.

        Returns:
            Dictionary with balance, equity, margin, free_margin, margin_level.
        """
        info = mt5.account_info()
        if info is None:
            logger.error("Cannot get account info")
            return {}
        return {
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "margin_level": info.margin_level if info.margin_level else 0.0,
            "profit": info.profit,
            "login": info.login,
            "leverage": info.leverage,
            "currency": info.currency,
        }
