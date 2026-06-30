"""Trailing stop manager — identik dengan Pine Script XAUUSD M1 AGGRO V6.

Pine Script logic:
  trailTicks = atr * trailMult / syminfo.mintick   = atr * 0.8 / mintick
  trail_offset = trailTicks * 0.3                  = atr * 0.24 / mintick

  strategy.exit("XL", "Long",
    profit       = tpTicks,       # TP: 2.5x ATR dari entry
    loss         = slTicks,       # SL: 1.2x ATR dari entry
    trail_points = trailTicks,    # Trail aktif saat profit >= 0.8x ATR
    trail_offset = trailTicks*0.3 # SL ditempatkan 0.24x ATR dari extreme
  )

Implementasi bot (3 phase):
  Phase 0 (profit < 0.5x ATR) → tidak ada perubahan SL
  Phase 1 (profit >= 0.5x ATR) → BREAKEVEN: SL ke entry (extra safety vs Pine)
  Phase 2 (profit >= 0.8x ATR) → TRAIL: SL = extreme ± (0.24x ATR)
"""

from loguru import logger


class TrailManager:
    """Update trailing stop untuk semua open position.

    Identik dengan Pine strategy.exit() AGGRO V6:
    - trail_points  = 0.8 * ATR  → profit minimum untuk aktifkan trail
    - trail_offset  = 0.24 * ATR → jarak SL dari extreme price seen
    """

    def __init__(self, config: dict, mt5_connector, order_manager):
        ext = config["strategy"]["exit"]
        # SL distance dari extreme price — Pine: trail_offset = trailMult*0.3 = 0.24 ATR
        self.trail_atr_mult     = ext["trail_atr_mult"]      # 0.24
        # Profit minimum untuk trail aktif — Pine: trail_points = trailMult = 0.8 ATR
        self.trail_offset_ratio = ext["trail_offset_ratio"]  # 0.8
        # Breakeven sebelum trail — extra safety (tidak ada di Pine)
        self.breakeven_trigger  = ext.get("breakeven_trigger", 0.5)  # 0.5

        self.mt5_conn  = mt5_connector
        self.order_mgr = order_manager
        self.symbol    = config["strategy"]["symbol"]
        self.magic     = config["mt5"]["magic_number"]

    def update_trailing_stops(self, current_atr: float) -> int:
        """Update trailing stops untuk semua open position.

        Pine: trail aktif saat profit >= 0.8 ATR, SL = extreme ± 0.24 ATR

        Phase 0 (profit < 0.5x ATR): tidak ada aksi
        Phase 1 (profit >= 0.5x ATR): BREAKEVEN — SL ke entry price
        Phase 2 (profit >= 0.8x ATR): TRAILING — SL = bid/ask ± 0.24 ATR

        Args:
            current_atr: ATR saat ini.

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

        # Pine: trail_offset = 0.24x ATR (SL distance dari extreme)
        trail_distance = current_atr * self.trail_atr_mult        # 0.24 ATR

        # Pine: trail_points = 0.8x ATR (profit minimum untuk aktifkan trail)
        activation_distance = current_atr * self.trail_offset_ratio  # 0.8 ATR

        # Extra: breakeven sebelum trail aktif
        breakeven_distance = current_atr * self.breakeven_trigger    # 0.5 ATR

        modified = 0

        for pos in positions:
            try:
                prices = self.mt5_conn.get_current_price(self.symbol)
                if not prices:
                    continue
                bid, ask = prices

                if pos.type == 0:  # BUY / LONG position
                    profit_distance = bid - pos.price_open

                    # Phase 2: TRAILING (profit >= 0.8x ATR)
                    # Pine: SL = highestSeen - trail_offset = bid - 0.24 ATR
                    if profit_distance >= activation_distance:
                        new_sl = round(bid - trail_distance, 3)
                        # Hard floor: SL tidak boleh turun di bawah entry
                        new_sl = max(new_sl, round(pos.price_open, 3))
                        if pos.sl == 0 or new_sl > pos.sl:
                            if self.order_mgr.modify_sl(pos.ticket, new_sl):
                                modified += 1
                                logger.debug(
                                    "Trail LONG #{}: SL {:.3f} → {:.3f} "
                                    "(profit={:.3f} >= act={:.3f}, dist={:.3f})",
                                    pos.ticket, pos.sl, new_sl,
                                    profit_distance, activation_distance, trail_distance,
                                )

                    # Phase 1: BREAKEVEN (profit >= 0.5x ATR, belum trail)
                    elif profit_distance >= breakeven_distance:
                        be_sl = round(pos.price_open, 3)
                        if pos.sl < be_sl:
                            if self.order_mgr.modify_sl(pos.ticket, be_sl):
                                modified += 1
                                logger.info(
                                    "Breakeven LONG #{}: SL {:.3f} → {:.3f}",
                                    pos.ticket, pos.sl, be_sl,
                                )

                elif pos.type == 1:  # SELL / SHORT position
                    profit_distance = pos.price_open - ask

                    # Phase 2: TRAILING (profit >= 0.8x ATR)
                    # Pine: SL = lowestSeen + trail_offset = ask + 0.24 ATR
                    if profit_distance >= activation_distance:
                        new_sl = round(ask + trail_distance, 3)
                        # Hard ceiling: SL tidak boleh naik di atas entry
                        new_sl = min(new_sl, round(pos.price_open, 3))
                        if pos.sl == 0 or new_sl < pos.sl:
                            if self.order_mgr.modify_sl(pos.ticket, new_sl):
                                modified += 1
                                logger.debug(
                                    "Trail SHORT #{}: SL {:.3f} → {:.3f} "
                                    "(profit={:.3f} >= act={:.3f}, dist={:.3f})",
                                    pos.ticket, pos.sl, new_sl,
                                    profit_distance, activation_distance, trail_distance,
                                )

                    # Phase 1: BREAKEVEN (profit >= 0.5x ATR, belum trail)
                    elif profit_distance >= breakeven_distance:
                        be_sl = round(pos.price_open, 3)
                        if pos.sl > be_sl:
                            if self.order_mgr.modify_sl(pos.ticket, be_sl):
                                modified += 1
                                logger.info(
                                    "Breakeven SHORT #{}: SL {:.3f} → {:.3f}",
                                    pos.ticket, pos.sl, be_sl,
                                )

            except Exception as e:
                logger.warning("Trail error for #{}: {}", pos.ticket, e)

        if modified > 0:
            logger.info("Trailing stops updated: {}/{}", modified, len(positions))
        return modified
