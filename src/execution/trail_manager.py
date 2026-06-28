"""Trailing stop manager: dynamically trail SL to lock in profits."""

from loguru import logger


class TrailManager:
    """Updates trailing stops for all open positions.

    Logic:
    - LONG: trail SL upward when price moves in favor
    - SHORT: trail SL downward when price moves in favor
    - Trail distance = 0.8 × ATR
    - Only move SL in profit direction (never widen SL)
    """

    def __init__(self, config: dict, mt5_connector, order_manager):
        ext = config["strategy"]["exit"]
        self.trail_atr_mult = ext["trail_atr_mult"]         # 0.8
        self.trail_offset_ratio = ext["trail_offset_ratio"] # 0.3
        self.mt5_conn = mt5_connector
        self.order_mgr = order_manager
        self.symbol = config["strategy"]["symbol"]
        self.magic = config["mt5"]["magic_number"]

    def update_trailing_stops(self, current_atr: float) -> int:
        """Update trailing stops for all open positions.

        For each position, calculates the ideal trailing SL based on
        current ATR and only moves SL if it would be more favorable.

        Args:
            current_atr: Current ATR value for trail distance calculation.

        Returns:
            Count of positions with modified SL.
        """
        if current_atr <= 0:
            return 0

        positions = self.mt5_conn.get_open_positions(
            symbol=self.symbol, magic=self.magic
        )
        if not positions:
            return 0

        trail_distance = current_atr * self.trail_atr_mult
        activation_distance = trail_distance * self.trail_offset_ratio
        modified = 0

        for pos in positions:
            try:
                prices = self.mt5_conn.get_current_price(self.symbol)
                if not prices:
                    continue
                bid, ask = prices

                if pos.type == 0:  # BUY position
                    # Current profit in price
                    profit_distance = bid - pos.price_open
                    # Only trail if position is in profit beyond activation
                    if profit_distance < activation_distance:
                        continue
                    # Ideal trailing SL
                    new_sl = round(bid - trail_distance, 3)
                    # Only move SL up, never down
                    if pos.sl == 0 or new_sl > pos.sl:
                        if self.order_mgr.modify_sl(pos.ticket, new_sl):
                            modified += 1
                            logger.debug(
                                "Trail LONG #{}: SL {:.3f} → {:.3f}",
                                pos.ticket, pos.sl, new_sl,
                            )

                elif pos.type == 1:  # SELL position
                    profit_distance = pos.price_open - ask
                    if profit_distance < activation_distance:
                        continue
                    new_sl = round(ask + trail_distance, 3)
                    # Only move SL down, never up
                    if pos.sl == 0 or new_sl < pos.sl:
                        if self.order_mgr.modify_sl(pos.ticket, new_sl):
                            modified += 1
                            logger.debug(
                                "Trail SHORT #{}: SL {:.3f} → {:.3f}",
                                pos.ticket, pos.sl, new_sl,
                            )

            except Exception as e:
                logger.warning("Trail error for #{}: {}", pos.ticket, e)

        if modified > 0:
            logger.info("Trailing stops updated: {}/{}", modified, len(positions))
        return modified
