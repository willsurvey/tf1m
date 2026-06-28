"""Telegram notification module for trade alerts and daily reports."""

from typing import Optional
from datetime import datetime, timezone
import os

import requests
from loguru import logger


class TelegramNotifier:
    """Send trade notifications via Telegram bot API.

    Uses synchronous requests to avoid async complexity.
    All methods fail gracefully — Telegram errors never crash the bot.
    """

    def __init__(self, config: dict):
        tg_cfg = config.get("notifications", {}).get("telegram", {})
        self.enabled = tg_cfg.get("enabled", False)
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

        if self.enabled and (not self.bot_token or not self.chat_id):
            logger.warning("Telegram enabled but token/chat_id not set")
            self.enabled = False

    def send_message(self, text: str) -> bool:
        """Send a plain text message to Telegram.

        Args:
            text: Message content (supports Markdown).

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.enabled:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Telegram send failed: {}", resp.text[:200])
                return False
            return True
        except Exception as e:
            logger.warning("Telegram error: {}", e)
            return False

    def send_trade_opened(
        self,
        direction: str,
        entry: float,
        tp: float,
        sl: float,
        lot: float,
        ticket: int,
        positions: int,
        max_positions: int,
    ) -> bool:
        """Send notification when a new trade is opened."""
        icon = "🟢" if direction == "LONG" else "🔴"
        tp_diff = abs(tp - entry)
        sl_diff = abs(sl - entry)
        msg = (
            f"📊 *TRADE OPENED*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Symbol: XAUUSD\n"
            f"Signal: {icon} {direction}\n"
            f"Ticket: `{ticket}`\n"
            f"Entry: `{entry:.3f}`\n"
            f"TP: `{tp:.3f}` (+{tp_diff:.3f})\n"
            f"SL: `{sl:.3f}` (-{sl_diff:.3f})\n"
            f"Lot: {lot}\n"
            f"Positions: {positions}/{max_positions}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
        )
        return self.send_message(msg)

    def send_trade_closed(
        self,
        direction: str,
        entry: float,
        exit_price: float,
        pnl: float,
        duration_min: int,
        exit_reason: str,
        daily_pnl: float = 0.0,
        daily_pct: float = 0.0,
    ) -> bool:
        """Send notification when a trade is closed."""
        icon = "✅" if pnl >= 0 else "❌"
        dir_icon = "🟢" if direction == "LONG" else "🔴"
        msg = (
            f"{icon} *TRADE CLOSED ({exit_reason})*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Direction: {dir_icon} {direction}\n"
            f"Entry: `{entry:.3f}` → Exit: `{exit_price:.3f}`\n"
            f"PnL: ${pnl:+.2f}\n"
            f"Duration: {duration_min} min\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 Today: ${daily_pnl:+.2f} ({daily_pct:+.2f}%)"
        )
        return self.send_message(msg)

    def send_alert(self, level: str, message: str) -> bool:
        """Send a warning or error alert."""
        icons = {"info": "ℹ️", "warning": "⚠️", "error": "🚨", "critical": "🔥"}
        icon = icons.get(level, "ℹ️")
        msg = (
            f"{icon} *{level.upper()} ALERT*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{message}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
        )
        return self.send_message(msg)

    def send_news_blackout(self, event_name: str, event_time: str, blackout_end: str) -> bool:
        """Send notification when news blackout is activated."""
        msg = (
            f"⚠️ *NEWS BLACKOUT ACTIVE*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Event: {event_name} 🔴\n"
            f"Time: {event_time} UTC\n"
            f"Blackout ends: {blackout_end} UTC\n"
            f"Action: All entries PAUSED\n"
            f"━━━━━━━━━━━━━━━"
        )
        return self.send_message(msg)

    def send_daily_summary(self, stats: dict) -> bool:
        """Send end-of-day performance summary."""
        msg = (
            f"📋 *DAILY SUMMARY*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Date: {stats.get('date', 'N/A')}\n"
            f"Trades: {stats.get('total_trades', 0)}\n"
            f"Won: {stats.get('wins', 0)} | Lost: {stats.get('losses', 0)}\n"
            f"Win Rate: {stats.get('win_rate', 0):.1f}%\n"
            f"PnL: ${stats.get('daily_pnl', 0):+.2f} ({stats.get('daily_pct', 0):+.2f}%)\n"
            f"Max DD: {stats.get('max_dd_pct', 0):.2f}%\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 Equity: ${stats.get('equity', 0):,.2f}"
        )
        return self.send_message(msg)
