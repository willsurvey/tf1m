"""Trailing stop manager: dynamically trail SL to lock in profits."""

from loguru import logger


class TrailManager:
    """Updates trailing stops for all open positions.

    Logic (3 phases):
    1. BREAKEVEN LOCK: Saat profit >= 1.0x ATR → pindah SL ke entry price
    2. ACTIVATION: Trail baru aktif saat profit >= 1.5x ATR (trail_offset_ratio)
    3. TRAILING: SL digeser dengan jarak 1.5x ATR dari harga saat ini

    Untuk XAUUSD M1:
    - ATR rata-rata ~2-3 pts
    - Breakeven aktif saat profit ~2-3 pts
    - Trail aktif saat profit ~3-4.5 pts, jarak SL ~3-4.5 pts dari harga
    - Normal M1 noise ~1-2 pts → SL tidak kena dari bounce biasa
    """

    def __init__(self, config: dict, mt5_connector, order_manager):
        ext = config["strategy"]["exit"]
        self.trail_atr_mult = ext["trail_atr_mult"]         # 1.5
        self.trail_offset_ratio = ext["trail_offset_ratio"] # 1.5
        self.breakeven_trigger = ext.get("breakeven_trigger", 1.0)  # 1.0
        self.mt5_conn = mt5_connector
        self.order_mgr = order_manager
        self.symbol = config["strategy"]["symbol"]
        self.magic = config["mt5"]["magic_number"]

    def update_trailing_stops(self, current_atr: float) -> int:
        """Update trailing stops for all open positions.

        Phase 1 — Breakeven: pindah SL ke entry saat profit >= 1x ATR
        Phase 2 — Trail: geser SL mengikuti harga saat profit >= 1.5x ATR

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
        # Phase 1: breakeven saat profit >= 1x ATR
        breakeven_distance = current_atr * self.breakeven_trigger
        # Phase 2: trail aktif saat profit >= 1.5x ATR
        activation_distance = current_atr * self.trail_offset_ratio
        modified = 0

        for pos in positions:
            try:
                prices = self.mt5_conn.get_current_price(self.symbol)
                if not prices:
                    continue
                bid, ask = prices

                if pos.type == 0:  # BUY position
                    profit_distance = bid - pos.price_open

                    # Phase 2: Full trail (profit >= 1.5x ATR)
                    if profit_distance >= activation_distance:
                        new_sl = round(bid - trail_distance, 3)
                        # Jangan pernah turunkan SL (selalu lock ke atas)
                        # Jangan biarkan SL turun di bawah entry
                        new_sl = max(new_sl, pos.price_open)
                        if pos.sl == 0 or new_sl > pos.sl:
                            if self.order_mgr.modify_sl(pos.ticket, new_sl):
                                modified += 1
                                logger.debug(
                                    "Trail LONG #{}: SL {:.3f} → {:.3f} (trail)",
                                    pos.ticket, pos.sl, new_sl,
                                )

                    # Phase 1: Breakeven lock (profit >= 1x ATR)
                    elif profit_distance >= breakeven_distance:
                        breakeven_sl = round(pos.price_open, 3)
                        if pos.sl < breakeven_sl:
                            if self.order_mgr.modify_sl(pos.ticket, breakeven_sl):
                                modified += 1
                                logger.info(
                                    "Breakeven LONG #{}: SL {:.3f} → {:.3f} (entry lock)",
                                    pos.ticket, pos.sl, breakeven_sl,
                                )

                elif pos.type == 1:  # SELL position
                    profit_distance = pos.price_open - ask

                    # Phase 2: Full trail (profit >= 1.5x ATR)
                    if profit_distance >= activation_distance:
                        new_sl = round(ask + trail_distance, 3)
                        # Jangan pernah naikkan SL (selalu lock ke bawah)
                        # Jangan biarkan SL naik di atas entry
                        new_sl = min(new_sl, pos.price_open)
                        if pos.sl == 0 or new_sl < pos.sl:
                            if self.order_mgr.modify_sl(pos.ticket, new_sl):
                                modified += 1
                                logger.debug(
                                    "Trail SHORT #{}: SL {:.3f} → {:.3f} (trail)",
                                    pos.ticket, pos.sl, new_sl,
                                )

                    # Phase 1: Breakeven lock (profit >= 1x ATR)
                    elif profit_distance >= breakeven_distance:
                        breakeven_sl = round(pos.price_open, 3)
                        if pos.sl > breakeven_sl:
                            if self.order_mgr.modify_sl(pos.ticket, breakeven_sl):
                                modified += 1
                                logger.info(
                                    "Breakeven SHORT #{}: SL {:.3f} → {:.3f} (entry lock)",
                                    pos.ticket, pos.sl, breakeven_sl,
                                )

            except Exception as e:
                logger.warning("Trail error for #{}: {}", pos.ticket, e)

        if modified > 0:
            logger.info("Trailing stops updated: {}/{}", modified, len(positions))
        return modified
