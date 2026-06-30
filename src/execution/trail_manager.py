"""Trailing stop manager — identik dengan Pine Script strategy.exit().

Pine Script logic:
  strategy.exit("XL", "Long",
    profit      = tpTicks,              # TP = 1.2x ATR dari entry
    loss        = slTicks,              # SL = 3.0x ATR dari entry
    trail_points = trailTicks,          # Trail aktif saat profit >= 1.0x ATR
    trail_offset = trailTicks * 0.4     # SL ditempatkan 0.4x ATR dari extreme
  )

Implementasi bot:
  Phase 0 (profit < 0.8x ATR) → tidak ada perubahan SL
  Phase 1 (profit >= 0.8x ATR) → BREAKEVEN: SL digeser ke entry (ekstra safety)
  Phase 2 (profit >= 1.0x ATR) → TRAIL: SL = extreme_price ± (0.4x ATR)
"""

from loguru import logger


class TrailManager:
    """Updates trailing stops untuk semua open position.

    Identik dengan Pine Script strategy.exit() trailing logic:
    - trail_points = 1.0 * ATR  (profit minimum sebelum trail aktif)
    - trail_offset = 0.4 * ATR  (jarak SL dari extreme price)
    """

    def __init__(self, config: dict, mt5_connector, order_manager):
        ext = config["strategy"]["exit"]
        # trail_offset Pine: SL distance dari extreme = 0.4x ATR
        self.trail_atr_mult    = ext["trail_atr_mult"]       # 0.4
        # trail_points Pine: profit activation = 1.0x ATR
        self.trail_offset_ratio = ext["trail_offset_ratio"]  # 1.0
        # Extra safety — breakeven sebelum trail aktif
        self.breakeven_trigger  = ext.get("breakeven_trigger", 0.8)  # 0.8
        self.mt5_conn    = mt5_connector
        self.order_mgr   = order_manager
        self.symbol      = config["strategy"]["symbol"]
        self.magic       = config["mt5"]["magic_number"]

    def update_trailing_stops(self, current_atr: float) -> int:
        """Update trailing stops untuk semua open position.

        Phase 0 (profit < 0.8x ATR): tidak ada aksi
        Phase 1 (profit >= 0.8x ATR): BREAKEVEN — SL ke entry price
        Phase 2 (profit >= 1.0x ATR): TRAILING — SL = bid/ask ± 0.4 ATR

        Pine trail_offset = 0.4 * trail_atr * ATR dari extreme price.
        Kita approx dengan bid/ask saat ini (lebih konservatif).

        Args:
            current_atr: ATR saat ini untuk menghitung jarak trail.

        Returns:
            Jumlah posisi yang SL-nya diupdate.
        """
        if current_atr <= 0:
            return 0

        positions = self.mt5_conn.get_open_positions(
            symbol=self.symbol, magic=self.magic
        )
        if not positions:
            return 0

        # Jarak SL dari current price (Pine: trail_offset = 0.4x ATR)
        trail_distance      = current_atr * self.trail_atr_mult      # 0.4 ATR
        # Profit minimum untuk aktifkan trail (Pine: trail_points = 1.0x ATR)
        activation_distance = current_atr * self.trail_offset_ratio  # 1.0 ATR
        # Profit minimum untuk breakeven (extra safety, tidak ada di Pine)
        breakeven_distance  = current_atr * self.breakeven_trigger    # 0.8 ATR

        modified = 0

        for pos in positions:
            try:
                prices = self.mt5_conn.get_current_price(self.symbol)
                if not prices:
                    continue
                bid, ask = prices

                if pos.type == 0:  # BUY position
                    profit_distance = bid - pos.price_open

                    # Phase 2: TRAILING AKTIF (profit >= 1.0x ATR)
                    # Pine: SL = highestSeen - trail_offset
                    # Approx: SL = bid - 0.4 ATR (selalu gerak naik, tidak turun)
                    if profit_distance >= activation_distance:
                        new_sl = round(bid - trail_distance, 3)
                        # Hard floor: SL tidak boleh turun di bawah entry
                        new_sl = max(new_sl, round(pos.price_open, 3))
                        if pos.sl == 0 or new_sl > pos.sl:
                            if self.order_mgr.modify_sl(pos.ticket, new_sl):
                                modified += 1
                                logger.debug(
                                    "Trail LONG #{}: SL {:.3f} → {:.3f} "
                                    "(profit={:.3f}, trail_dist={:.3f})",
                                    pos.ticket, pos.sl, new_sl,
                                    profit_distance, trail_distance,
                                )

                    # Phase 1: BREAKEVEN (profit >= 0.8x ATR, belum trail)
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

                    # Phase 2: TRAILING AKTIF (profit >= 1.0x ATR)
                    # Pine: SL = lowestSeen + trail_offset
                    # Approx: SL = ask + 0.4 ATR (selalu gerak turun, tidak naik)
                    if profit_distance >= activation_distance:
                        new_sl = round(ask + trail_distance, 3)
                        # Hard ceiling: SL tidak boleh naik di atas entry
                        new_sl = min(new_sl, round(pos.price_open, 3))
                        if pos.sl == 0 or new_sl < pos.sl:
                            if self.order_mgr.modify_sl(pos.ticket, new_sl):
                                modified += 1
                                logger.debug(
                                    "Trail SHORT #{}: SL {:.3f} → {:.3f} "
                                    "(profit={:.3f}, trail_dist={:.3f})",
                                    pos.ticket, pos.sl, new_sl,
                                    profit_distance, trail_distance,
                                )

                    # Phase 1: BREAKEVEN (profit >= 0.8x ATR, belum trail)
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
