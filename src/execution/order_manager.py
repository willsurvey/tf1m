"""Order execution: open, close, and modify positions via MT5."""

from typing import Optional

import MetaTrader5 as mt5
from loguru import logger

from src.strategy.signals import TradeSignal


class OrderManager:
    """Handles all order operations with MT5.

    Features:
    - Open LONG/SHORT with TP and SL
    - Close individual or all positions
    - Modify SL for trailing stop updates
    - Retry logic on transient failures
    """

    def __init__(self, config: dict, mt5_connector):
        self.lot_size = config["risk"]["lot_size"]          # 0.02
        self.magic = config["mt5"]["magic_number"]          # 20260629
        self.deviation = config["mt5"]["deviation"]         # 20
        self.symbol = config["strategy"]["symbol"]          # XAUUSD
        self.mt5_conn = mt5_connector

        # Map fill type
        fill_type = config["mt5"].get("type_filling", "ioc")
        self.filling_type = {
            "ioc": mt5.ORDER_FILLING_IOC,
            "fok": mt5.ORDER_FILLING_FOK,
            "return": mt5.ORDER_FILLING_RETURN,
        }.get(fill_type, mt5.ORDER_FILLING_IOC)

    def open_position(self, signal: TradeSignal, dry_run: bool = False) -> Optional[int]:
        """Open a new position based on trade signal.

        Args:
            signal: TradeSignal with direction, TP, SL, etc.
            dry_run: If True, log but don't execute.

        Returns:
            Order ticket number, or None on failure.
        """
        if signal.direction == "LONG":
            order_type = mt5.ORDER_TYPE_BUY
            price = signal.entry_price
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = signal.entry_price

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot_size,
            "type": order_type,
            "price": price,
            "sl": signal.stop_loss,
            "tp": signal.take_profit,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": f"AGGRO_V6_{signal.direction}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self.filling_type,
        }

        if dry_run:
            logger.info(
                "[DRY RUN] Would open {} {} @ {:.3f} | TP={:.3f} SL={:.3f}",
                self.lot_size, signal.direction, price,
                signal.take_profit, signal.stop_loss,
            )
            return -1  # Dummy ticket

        # Retry up to 3 times
        for attempt in range(1, 4):
            # Refresh price before each attempt
            prices = self.mt5_conn.get_current_price(self.symbol)
            if prices:
                if signal.direction == "LONG":
                    request["price"] = prices[1]  # ask
                else:
                    request["price"] = prices[0]  # bid

            result = mt5.order_send(request)
            if result is None:
                logger.error("Order send returned None (attempt {})", attempt)
                continue

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(
                    "✅ Order filled | ticket={} | {} {:.2f} @ {:.3f}",
                    result.order, signal.direction, self.lot_size, result.price,
                )
                return result.order

            logger.warning(
                "Order failed (attempt {}): retcode={} comment={}",
                attempt, result.retcode, result.comment,
            )

            # Don't retry on permanent errors
            permanent_errors = {
                mt5.TRADE_RETCODE_INVALID,
                mt5.TRADE_RETCODE_INVALID_VOLUME,
                mt5.TRADE_RETCODE_MARKET_CLOSED,
                mt5.TRADE_RETCODE_NO_MONEY,
            }
            if result.retcode in permanent_errors:
                logger.error("Permanent error, not retrying: {}", result.comment)
                break

        return None

    def close_position(self, ticket: int, dry_run: bool = False) -> bool:
        """Close a specific position by ticket number.

        Args:
            ticket: Position ticket to close.
            dry_run: If True, log but don't execute.

        Returns:
            True if closed successfully.
        """
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.warning("Position {} not found", ticket)
            return False

        pos = positions[0]
        # Position type: 0 = BUY, 1 = SELL
        if pos.type == 0:  # BUY position → close with SELL
            close_type = mt5.ORDER_TYPE_SELL
            prices = self.mt5_conn.get_current_price(pos.symbol)
            price = prices[0] if prices else pos.price_current  # bid
        else:              # SELL position → close with BUY
            close_type = mt5.ORDER_TYPE_BUY
            prices = self.mt5_conn.get_current_price(pos.symbol)
            price = prices[1] if prices else pos.price_current  # ask

        if dry_run:
            logger.info("[DRY RUN] Would close ticket {} @ {:.3f}", ticket, price)
            return True

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": "AGGRO_V6_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self.filling_type,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info("✅ Position {} closed @ {:.3f}", ticket, result.price)
            return True

        logger.error(
            "Failed to close {}: {}",
            ticket, result.comment if result else "no result",
        )
        return False

    def close_all_positions(self, dry_run: bool = False) -> int:
        """Close all open positions for this bot's magic number.

        Returns:
            Count of successfully closed positions.
        """
        positions = self.mt5_conn.get_open_positions(
            symbol=self.symbol, magic=self.magic
        )
        if not positions:
            return 0

        closed = 0
        for pos in positions:
            if self.close_position(pos.ticket, dry_run=dry_run):
                closed += 1

        logger.info("Closed {}/{} positions", closed, len(positions))
        return closed

    def modify_sl(self, ticket: int, new_sl: float) -> bool:
        """Modify the stop loss of an existing position.

        Args:
            ticket: Position ticket.
            new_sl: New stop loss price.

        Returns:
            True if modification succeeded.
        """
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False

        pos = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": ticket,
            "sl": round(new_sl, 3),
            "tp": pos.tp,
            "magic": self.magic,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return True

        logger.debug(
            "SL modify failed for {}: {}",
            ticket, result.comment if result else "no result",
        )
        return False
