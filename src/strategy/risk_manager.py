"""Risk management: position sizing, circuit breakers, drawdown protection."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger


@dataclass
class RiskStatus:
    """Snapshot of current risk state."""
    can_trade: bool
    reason: str
    daily_pnl: float
    daily_pnl_pct: float
    open_positions: int
    consecutive_losses: int
    max_equity_today: float
    current_drawdown_pct: float


class RiskManager:
    """Manages position limits, drawdown protection, and circuit breakers.

    Circuit Breakers:
    1. Daily loss > 3% → stop trading for the day
    2. Daily loss > 5% → emergency stop + alert
    3. Equity < 70% of initial → shutdown bot
    4. 3 consecutive losses → 30 min cooldown
    """

    def __init__(self, config: dict, mt5_connector):
        risk = config["risk"]
        self.lot_size = risk["lot_size"]                             # 0.02
        self.max_pyramiding = risk["max_pyramiding"]                 # 3
        self.max_daily_loss_pct = risk["max_daily_loss_pct"]         # 3.0
        self.max_total_loss_pct = risk["max_total_loss_pct"]         # 30.0
        self.consec_loss_limit = risk["consecutive_loss_cooldown"]   # 3
        self.cooldown_minutes = risk["cooldown_minutes"]             # 30

        self.mt5 = mt5_connector
        self.symbol = config["strategy"]["symbol"]
        self.magic = config["mt5"]["magic_number"]

        # Daily tracking
        self._start_balance: float = 0.0
        self._max_equity_today: float = 0.0
        self._daily_pnl: float = 0.0
        self._consecutive_losses: int = 0
        self._cooldown_until: Optional[datetime] = None
        self._daily_stopped: bool = False
        self._emergency_stopped: bool = False
        self._trade_count: int = 0
        self._win_count: int = 0

    def reset_daily(self) -> None:
        """Reset all daily counters. Call at start of each trading day."""
        account = self.mt5.get_account_info()
        self._start_balance = account.get("equity", 10000.0)
        self._max_equity_today = self._start_balance
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._cooldown_until = None
        self._daily_stopped = False
        self._trade_count = 0
        self._win_count = 0
        logger.info(
            "Risk manager reset | start_balance={:.2f}", self._start_balance
        )

    def record_trade_result(self, pnl: float) -> None:
        """Record a trade result and update risk counters.

        Args:
            pnl: Profit/loss amount in account currency.
        """
        self._daily_pnl += pnl
        self._trade_count += 1

        if pnl >= 0:
            self._consecutive_losses = 0
            self._win_count += 1
            logger.info("Trade result: +{:.2f} | streak reset", pnl)
        else:
            self._consecutive_losses += 1
            logger.info(
                "Trade result: {:.2f} | consecutive losses: {}",
                pnl, self._consecutive_losses,
            )

            # Cooldown after N consecutive losses
            if self._consecutive_losses >= self.consec_loss_limit:
                self._cooldown_until = datetime.now(timezone.utc).replace(
                    second=0, microsecond=0
                )
                self._cooldown_until += timedelta(minutes=self.cooldown_minutes)
                logger.warning(
                    "⏸️ Cooldown activated: {} consecutive losses → paused until {}",
                    self._consecutive_losses,
                    self._cooldown_until.strftime("%H:%M UTC"),
                )

    def can_open_position(self) -> tuple:
        """Check if a new position can be opened.

        Returns:
            Tuple of (allowed: bool, reason: str).
        """
        # Check emergency stop
        if self._emergency_stopped:
            return False, "Emergency stop active"

        # Check daily stop
        if self._daily_stopped:
            return False, "Daily loss limit reached"

        # Check cooldown
        now = datetime.now(timezone.utc)
        if self._cooldown_until and now < self._cooldown_until:
            remaining = (self._cooldown_until - now).seconds // 60
            return False, f"Cooldown: {remaining}min remaining"

        # Clear expired cooldown
        if self._cooldown_until and now >= self._cooldown_until:
            self._cooldown_until = None
            self._consecutive_losses = 0
            logger.info("Cooldown expired, trading resumed")

        # Check pyramiding limit
        positions = self.mt5.get_open_positions(
            symbol=self.symbol, magic=self.magic
        )
        if len(positions) >= self.max_pyramiding:
            return False, f"Max pyramiding ({self.max_pyramiding}) reached"

        return True, ""

    def check_circuit_breakers(self) -> tuple:
        """Check all circuit breaker conditions.

        Returns:
            Tuple of (is_ok: bool, reason: str).
            is_ok=True means trading can continue.
        """
        account = self.mt5.get_account_info()
        if not account:
            return False, "Cannot get account info"

        equity = account.get("equity", 0)
        balance = account.get("balance", 0)

        # Update max equity tracking
        if equity > self._max_equity_today:
            self._max_equity_today = equity

        # Calculate daily P&L percentage
        if self._start_balance > 0:
            daily_pnl_pct = ((equity - self._start_balance) / self._start_balance) * 100
        else:
            daily_pnl_pct = 0.0

        # Circuit Breaker 1: Daily loss > 3%
        if daily_pnl_pct < -self.max_daily_loss_pct:
            self._daily_stopped = True
            logger.critical(
                "🔴 CIRCUIT BREAKER: Daily loss {:.2f}% > {:.1f}% limit",
                daily_pnl_pct, self.max_daily_loss_pct,
            )
            return False, f"Daily loss {daily_pnl_pct:.2f}% exceeded limit"

        # Circuit Breaker 2: Daily loss > 5% (emergency)
        if daily_pnl_pct < -(self.max_daily_loss_pct + 2.0):
            self._emergency_stopped = True
            logger.critical("🔥 EMERGENCY STOP: Daily loss {:.2f}%", daily_pnl_pct)
            return False, f"EMERGENCY: Daily loss {daily_pnl_pct:.2f}%"

        # Circuit Breaker 3: Equity < 70% of initial capital
        if self._start_balance > 0:
            equity_ratio = equity / self._start_balance * 100
            if equity_ratio < (100 - self.max_total_loss_pct):
                self._emergency_stopped = True
                logger.critical(
                    "🔥 EQUITY PROTECTION: Equity={:.2f} ({:.1f}% of start)",
                    equity, equity_ratio,
                )
                return False, f"Equity dropped to {equity_ratio:.1f}% of start"

        return True, ""

    def get_status(self) -> RiskStatus:
        """Get current risk status snapshot."""
        account = self.mt5.get_account_info()
        equity = account.get("equity", 0) if account else 0
        positions = self.mt5.get_open_positions(symbol=self.symbol, magic=self.magic)

        daily_pnl_pct = 0.0
        dd_pct = 0.0
        if self._start_balance > 0:
            daily_pnl_pct = ((equity - self._start_balance) / self._start_balance) * 100
        if self._max_equity_today > 0:
            dd_pct = ((self._max_equity_today - equity) / self._max_equity_today) * 100

        can, reason = self.can_open_position()

        return RiskStatus(
            can_trade=can,
            reason=reason,
            daily_pnl=equity - self._start_balance,
            daily_pnl_pct=daily_pnl_pct,
            open_positions=len(positions),
            consecutive_losses=self._consecutive_losses,
            max_equity_today=self._max_equity_today,
            current_drawdown_pct=max(0, dd_pct),
        )

    def get_daily_stats(self) -> dict:
        """Get daily performance stats for reporting."""
        account = self.mt5.get_account_info()
        equity = account.get("equity", 0) if account else 0
        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_trades": self._trade_count,
            "wins": self._win_count,
            "losses": self._trade_count - self._win_count,
            "win_rate": (self._win_count / self._trade_count * 100) if self._trade_count > 0 else 0,
            "daily_pnl": equity - self._start_balance,
            "daily_pct": ((equity - self._start_balance) / self._start_balance * 100) if self._start_balance > 0 else 0,
            "max_dd_pct": ((self._max_equity_today - equity) / self._max_equity_today * 100) if self._max_equity_today > 0 else 0,
            "equity": equity,
        }
