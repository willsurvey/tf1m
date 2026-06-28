"""Main trading bot orchestrator — the heart of AGGRO V6."""

import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from src.mt5_connector import MT5Connector
from src.strategy.signals import SignalGenerator, TradeSignal
from src.strategy.filters import TradeFilter
from src.strategy.risk_manager import RiskManager
from src.execution.order_manager import OrderManager
from src.execution.trail_manager import TrailManager
from src.news.calendar_fetcher import CalendarFetcher
from src.news.impact_filter import NewsImpactFilter
from src.utils.notifier import TelegramNotifier
from src.utils.helpers import utc_now


class TradingBot:
    """XAUUSD AGGRO V6 Automated Trading Bot.

    Orchestrates the full trading lifecycle:
    1. Connect to MT5
    2. Fetch M1 data and calculate indicators
    3. Apply filters (session, ATR spike, news)
    4. Generate and execute signals
    5. Manage trailing stops
    6. Enforce risk limits and circuit breakers
    7. Send notifications via Telegram
    """

    def __init__(self, config: dict, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.symbol = config["strategy"]["symbol"]
        self.timeframe = config["strategy"]["timeframe"]
        self._running = False
        self._last_bar_time: Optional[datetime] = None
        self._current_day: Optional[int] = None

        # Initialize all components
        logger.info("Initializing AGGRO V6 bot | dry_run={}", dry_run)

        self.mt5 = MT5Connector(config)
        self.signal_gen = SignalGenerator(config)
        self.calendar = CalendarFetcher(config)
        self.news_filter = NewsImpactFilter(config, self.calendar)
        self.trade_filter = TradeFilter(config, self.news_filter)
        self.risk_mgr = RiskManager(config, self.mt5)
        self.order_mgr = OrderManager(config, self.mt5)
        self.trail_mgr = TrailManager(config, self.mt5, self.order_mgr)
        self.notifier = TelegramNotifier(config)

        # Trade journal
        self.journal_path = Path("data/trade_journal.csv")
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_journal()

    def run(self) -> None:
        """Main run loop. Runs indefinitely until Ctrl+C or fatal error."""
        # Step 1: Connect to MT5
        if not self.mt5.connect():
            logger.critical("Cannot connect to MT5. Aborting.")
            return

        self._running = True
        self.risk_mgr.reset_daily()
        self._current_day = utc_now().day

        # Startup notification
        account = self.mt5.get_account_info()
        self.notifier.send_alert(
            "info",
            f"🚀 Bot started\n"
            f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}\n"
            f"Balance: ${account.get('balance', 0):,.2f}\n"
            f"Leverage: 1:{account.get('leverage', 0)}",
        )

        logger.info("=" * 50)
        logger.info("AGGRO V6 BOT STARTED")
        logger.info("Symbol: {} | TF: {}", self.symbol, self.timeframe)
        logger.info("Mode: {}", "DRY RUN" if self.dry_run else "LIVE")
        logger.info("=" * 50)

        # Step 2: Main loop
        try:
            while self._running:
                try:
                    self._tick()
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error("Tick error: {}", e, exc_info=True)
                time.sleep(1)  # 1 second between ticks

        except KeyboardInterrupt:
            logger.info("Shutdown requested (Ctrl+C)")
        except Exception as e:
            logger.critical("Fatal error: {}", e, exc_info=True)
            self.notifier.send_alert("critical", f"Fatal error: {e}")
        finally:
            self._shutdown()

    def _tick(self) -> None:
        """Single iteration of the main trading loop."""
        now = utc_now()

        # ── 1. Check MT5 connection ─────────────────────────
        if not self.mt5.is_connected():
            logger.warning("MT5 disconnected, attempting reconnect...")
            if not self.mt5.reconnect():
                self.notifier.send_alert("error", "MT5 reconnection failed!")
                time.sleep(10)
                return

        # ── 2. Check for new day ────────────────────────────
        if now.day != self._current_day:
            self._on_new_day()
            self._current_day = now.day

        # ── 3. Fetch OHLCV data ─────────────────────────────
        df = self.mt5.get_ohlcv(self.symbol, self.timeframe, count=120)
        if df is None or len(df) < 20:
            return

        # ── 4. Check for new bar (avoid duplicate signals) ──
        latest_bar_time = df.iloc[-1]["time"]
        if self._last_bar_time is not None and latest_bar_time <= self._last_bar_time:
            # Same bar — only update trailing stops
            indicators = self.signal_gen.calculate_indicators(df)
            current_atr = float(indicators.iloc[-1]["atr"])
            if current_atr > 0:
                self.trail_mgr.update_trailing_stops(current_atr)
            return
        self._last_bar_time = latest_bar_time

        # ── 5. Calculate indicators ─────────────────────────
        df = self.signal_gen.calculate_indicators(df)
        curr = df.iloc[-1]
        current_atr = float(curr["atr"])
        avg_atr = float(curr["atr_avg"])

        # ── 6. Force close check (20:55 UTC) ────────────────
        if self.trade_filter.should_force_close(now):
            positions = self.mt5.get_open_positions(
                symbol=self.symbol, magic=self.config["mt5"]["magic_number"]
            )
            if positions:
                logger.info("⏰ Force close time — closing {} positions", len(positions))
                closed = self.order_mgr.close_all_positions(dry_run=self.dry_run)
                self.notifier.send_alert(
                    "info", f"⏰ Force close: {closed} positions closed"
                )
            return

        # ── 7. Check circuit breakers ───────────────────────
        cb_ok, cb_reason = self.risk_mgr.check_circuit_breakers()
        if not cb_ok:
            logger.warning("Circuit breaker: {}", cb_reason)
            if "EMERGENCY" in cb_reason:
                self.order_mgr.close_all_positions(dry_run=self.dry_run)
                self.notifier.send_alert("critical", f"🔥 {cb_reason}")
                self._running = False
            return

        # ── 8. Check all filters ────────────────────────────
        can_trade, filter_reason = self.trade_filter.can_trade(
            now, current_atr, avg_atr
        )
        if not can_trade:
            logger.debug("Filter blocked: {}", filter_reason)
            # Still update trailing stops
            self.trail_mgr.update_trailing_stops(current_atr)
            return

        # ── 9. Check if can open position ───────────────────
        can_open, risk_reason = self.risk_mgr.can_open_position()
        if not can_open:
            logger.debug("Risk blocked: {}", risk_reason)
            self.trail_mgr.update_trailing_stops(current_atr)
            return

        # ── 10. Generate signal ─────────────────────────────
        prices = self.mt5.get_current_price(self.symbol)
        if not prices:
            return
        bid, ask = prices

        signal = self.signal_gen.generate_signal(df, bid, ask)
        if signal is None:
            self.trail_mgr.update_trailing_stops(current_atr)
            return

        # ── 11. Execute order ───────────────────────────────
        ticket = self.order_mgr.open_position(signal, dry_run=self.dry_run)
        if ticket:
            positions = self.mt5.get_open_positions(
                symbol=self.symbol,
                magic=self.config["mt5"]["magic_number"],
            )
            self._log_trade(ticket, signal)
            self.notifier.send_trade_opened(
                direction=signal.direction,
                entry=signal.entry_price,
                tp=signal.take_profit,
                sl=signal.stop_loss,
                lot=self.config["risk"]["lot_size"],
                ticket=ticket,
                positions=len(positions),
                max_positions=self.config["risk"]["max_pyramiding"],
            )
        else:
            logger.warning("Order execution failed for {} signal", signal.direction)

        # ── 12. Update trailing stops ───────────────────────
        self.trail_mgr.update_trailing_stops(current_atr)

    def _on_new_day(self) -> None:
        """Called when a new trading day starts (midnight UTC)."""
        logger.info("=" * 40)
        logger.info("📅 NEW TRADING DAY")
        logger.info("=" * 40)

        # Send previous day summary
        try:
            stats = self.risk_mgr.get_daily_stats()
            if stats.get("total_trades", 0) > 0:
                self.notifier.send_daily_summary(stats)
        except Exception as e:
            logger.warning("Failed to send daily summary: {}", e)

        # Reset daily counters
        self.risk_mgr.reset_daily()

        # Refresh news calendar
        try:
            events = self.calendar.fetch_today_events()
            if events:
                logger.info("Loaded {} news events for today", len(events))
                for ev in events:
                    logger.info("  📰 {} @ {}", ev["name"], ev["datetime_utc"])
        except Exception as e:
            logger.warning("News calendar refresh failed: {}", e)

    def _init_journal(self) -> None:
        """Initialize trade journal CSV with headers if not exists."""
        if not self.journal_path.exists():
            with open(self.journal_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "ticket", "symbol", "direction",
                    "entry", "tp", "sl", "lot", "atr",
                    "comment",
                ])

    def _log_trade(self, ticket: int, signal: TradeSignal) -> None:
        """Write trade entry to CSV journal."""
        try:
            with open(self.journal_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    signal.timestamp.isoformat(),
                    ticket,
                    self.symbol,
                    signal.direction,
                    f"{signal.entry_price:.3f}",
                    f"{signal.take_profit:.3f}",
                    f"{signal.stop_loss:.3f}",
                    self.config["risk"]["lot_size"],
                    f"{signal.atr_value:.5f}",
                    f"AGGRO_V6_{signal.direction}",
                ])
        except Exception as e:
            logger.warning("Journal write error: {}", e)

    def _shutdown(self) -> None:
        """Graceful shutdown procedure."""
        logger.info("Shutting down bot...")
        self._running = False

        # Close all positions
        try:
            positions = self.mt5.get_open_positions(
                symbol=self.symbol,
                magic=self.config["mt5"]["magic_number"],
            )
            if positions:
                logger.info("Closing {} open positions...", len(positions))
                self.order_mgr.close_all_positions(dry_run=self.dry_run)
        except Exception as e:
            logger.error("Error closing positions: {}", e)

        # Send final stats
        try:
            stats = self.risk_mgr.get_daily_stats()
            self.notifier.send_alert(
                "info",
                f"🛑 Bot stopped\nToday's PnL: ${stats.get('daily_pnl', 0):+.2f}"
            )
        except Exception:
            pass

        # Disconnect
        self.mt5.disconnect()
        logger.info("Bot shutdown complete")
