# 📋 Task Breakdown — XAUUSD AGGRO V6

> Dokumen ini berisi breakdown lengkap semua task yang harus dikerjakan untuk
> membangun trading bot XAUUSD AGGRO V6. Setiap task memiliki checkbox untuk
> tracking progress.

**Strategy:** AGGRO V6 — XAUUSD M1 Scalping with Donchian Breakout
**Magic Number:** 20260629
**Target:** Automated trading pada session 12:00–21:00 UTC

---

## 📊 Progress Overview

| Phase | Deskripsi | Status |
|---|---|---|
| Phase 1 | Project Setup | 🔲 Not Started |
| Phase 2 | MT5 Connection | 🔲 Not Started |
| Phase 3 | Strategy Core | 🔲 Not Started |
| Phase 4 | Filters | 🔲 Not Started |
| Phase 5 | Execution | 🔲 Not Started |
| Phase 6 | Risk Management | 🔲 Not Started |
| Phase 7 | Notifications | 🔲 Not Started |
| Phase 8 | Testing & Validation | 🔲 Not Started |
| Phase 9 | Deployment & Monitoring | 🔲 Not Started |

---

## Phase 1: Project Setup 🏗️

> Fondasi proyek — struktur folder, konfigurasi, dan environment.

### 1.1 Project Structure

- [ ] Buat folder structure sesuai arsitektur:
  ```
  xauusd-aggro-v6/
  ├── src/
  │   ├── __init__.py
  │   ├── main.py              # Entry point
  │   ├── core/
  │   │   ├── __init__.py
  │   │   ├── strategy.py      # Strategi AGGRO V6
  │   │   ├── indicators.py    # Kalkulasi EMA, RSI, ATR, Donchian
  │   │   └── signals.py       # Signal generation logic
  │   ├── connectors/
  │   │   ├── __init__.py
  │   │   └── mt5_connector.py # MT5 connection manager
  │   ├── execution/
  │   │   ├── __init__.py
  │   │   ├── order_manager.py # Order placement & management
  │   │   └── trailing.py      # Trailing stop logic
  │   ├── filters/
  │   │   ├── __init__.py
  │   │   ├── session.py       # Session time filter
  │   │   ├── atr_spike.py     # ATR spike filter
  │   │   └── news.py          # News filter
  │   ├── risk/
  │   │   ├── __init__.py
  │   │   ├── circuit_breaker.py   # Circuit breaker system
  │   │   └── position_sizer.py    # Lot sizing & pyramid control
  │   ├── notifications/
  │   │   ├── __init__.py
  │   │   └── telegram.py      # Telegram bot notifier
  │   └── utils/
  │       ├── __init__.py
  │       ├── config.py        # Config loader
  │       ├── helpers.py       # Utility functions
  │       └── constants.py     # Magic number, enums, dll
  ├── tests/
  │   ├── conftest.py
  │   ├── unit/
  │   └── integration/
  ├── logs/
  ├── data/
  ├── settings.yaml
  ├── .env.example
  ├── .gitignore
  ├── requirements.txt
  ├── README.md
  └── Guideline.md
  ```

### 1.2 Configuration

- [ ] Buat `settings.yaml` dengan semua parameter strategi:
  - [ ] EMA periods: fast=5, slow=13
  - [ ] RSI: period=7, bull_threshold=60, bear_threshold=40
  - [ ] ATR: period=10, average_period=100
  - [ ] Donchian: period=10
  - [ ] TP multiplier: 2.5, SL multiplier: 1.2
  - [ ] Trail distance: 0.8×ATR, Trail offset: 0.3×trail
  - [ ] Session: start=12:00, end=21:00, force_close=20:55 (UTC)
  - [ ] Lot: 0.02, Max pyramid: 3
  - [ ] Magic number: 20260629
  - [ ] ATR spike threshold: 2.0
  - [ ] News filter: pre_minutes=15, post_minutes=10
  - [ ] Circuit breaker thresholds: daily_loss=3%, emergency=5%, equity_shutdown=70%
  - [ ] Cooldown: consecutive_losses=3, cooldown_minutes=30
- [ ] Buat `.env.example` (tanpa actual credentials)
- [ ] Buat `src/utils/config.py` — config loader dari YAML + .env

### 1.3 Dependencies & Environment

- [ ] Buat `requirements.txt` dengan pinned versions
- [ ] Setup virtual environment: `python -m venv venv`
- [ ] Install semua dependencies: `pip install -r requirements.txt`
- [ ] Verifikasi MT5 library bisa di-import

### 1.4 Development Tooling

- [ ] Setup `.gitignore` (exclude .env, logs, __pycache__, dll)
- [ ] Setup loguru logging configuration di `main.py`
- [ ] Buat `src/utils/constants.py` dengan semua konstanta
- [ ] Init git repository dan buat initial commit

---

## Phase 2: MT5 Connection 🔌

> Koneksi ke MetaTrader 5 terminal — data fetching dan account management.

### 2.1 MT5 Connector

- [ ] Implement `MT5Connector` class di `src/connectors/mt5_connector.py`:
  - [ ] `connect()` — Initialize dan login ke MT5
  - [ ] `disconnect()` — Shutdown MT5 connection dengan bersih
  - [ ] `ensure_connected()` — Auto-reconnect jika terputus
  - [ ] `get_account_info()` — Ambil info akun (balance, equity, margin)
  - [ ] `is_market_open()` — Cek apakah market XAUUSD sedang buka
- [ ] Implement connection health check (heartbeat setiap 30 detik)
- [ ] Implement auto-reconnect dengan exponential backoff
- [ ] Handle MT5 error codes dengan proper logging

### 2.2 Data Fetching

- [ ] Implement `fetch_ohlcv()` — Fetch OHLCV data M1 timeframe
- [ ] Implement `fetch_tick()` — Fetch tick data real-time (bid/ask)
- [ ] Implement data validation (NaN check, OHLC consistency)
- [ ] Implement `DataManager` class untuk efficient buffer management:
  - [ ] Circular buffer untuk menyimpan N bars terakhir
  - [ ] Incremental update (fetch hanya bar baru)
  - [ ] Minimum lookback: 200 bars (untuk ATR SMA 100)

### 2.3 Account Monitoring

- [ ] Implement `get_balance()` — Return current balance
- [ ] Implement `get_equity()` — Return current equity
- [ ] Implement `get_open_positions()` — Daftar posisi terbuka (filtered by magic)
- [ ] Implement `get_daily_profit()` — Hitung profit/loss hari ini
- [ ] Implement `get_position_count()` — Count posisi aktif (untuk pyramid check)

---

## Phase 3: Strategy Core 📈

> Kalkulasi indikator teknikal dan logic pembuatan sinyal.

### 3.1 Indicators (`src/core/indicators.py`)

- [ ] Implement `calculate_ema(series, period)`:
  - [ ] EMA Fast: period = 5
  - [ ] EMA Slow: period = 13
  - [ ] Validasi input series tidak kosong
- [ ] Implement `calculate_rsi(series, period=7)`:
  - [ ] Gunakan Wilder's smoothing method (bukan SMA)
  - [ ] Handle edge case: semua gain atau semua loss
  - [ ] Return RSI value 0-100
- [ ] Implement `calculate_atr(high, low, close, period=10)`:
  - [ ] True Range = max(H-L, |H-C_prev|, |L-C_prev|)
  - [ ] ATR = EMA/SMA of True Range
  - [ ] Return ATR series
- [ ] Implement `calculate_donchian(high, low, period=10)`:
  - [ ] Upper = Highest High dari N period sebelumnya
  - [ ] Lower = Lowest Low dari N period sebelumnya
  - [ ] Middle = (Upper + Lower) / 2
  - [ ] Return tuple (upper, lower, middle)
- [ ] Implement `calculate_atr_sma(atr_series, period=100)`:
  - [ ] SMA dari ATR values
  - [ ] Digunakan untuk ATR spike filter

### 3.2 Signal Generation (`src/core/signals.py`)

- [ ] Implement `check_long_signal()`:
  - [ ] Kondisi 1: EMA(5) > EMA(13) — Trend bullish
  - [ ] Kondisi 2: Close > EMA(5) — Price above fast EMA
  - [ ] Kondisi 3: RSI > 60 — Momentum bullish
  - [ ] Kondisi 4: High >= DonchianHigh[1] — Breakout ke atas
  - [ ] **Semua 4 kondisi harus terpenuhi** untuk generate BUY signal
- [ ] Implement `check_short_signal()`:
  - [ ] Kondisi 1: EMA(5) < EMA(13) — Trend bearish
  - [ ] Kondisi 2: Close < EMA(5) — Price below fast EMA
  - [ ] Kondisi 3: RSI < 40 — Momentum bearish
  - [ ] Kondisi 4: Low <= DonchianLow[1] — Breakout ke bawah
  - [ ] **Semua 4 kondisi harus terpenuhi** untuk generate SELL signal
- [ ] Implement `calculate_tp_sl_trail()`:
  - [ ] Take Profit = entry ± (2.5 × ATR)
  - [ ] Stop Loss = entry ∓ (1.2 × ATR)
  - [ ] Trail Distance = 0.8 × ATR
  - [ ] Trail Offset = 0.3 × trail_distance
- [ ] Buat `TradeSignal` dataclass untuk output signal

### 3.3 Strategy Orchestrator (`src/core/strategy.py`)

- [ ] Implement `AggroV6Strategy` class:
  - [ ] `evaluate()` — Main method, panggil semua indicator → signal check
  - [ ] `get_current_indicators()` — Return snapshot semua indicator values
  - [ ] Store last signal untuk anti-duplicate check
  - [ ] Log semua indicator values setiap evaluasi (level DEBUG)

---

## Phase 4: Filters 🚦

> Filter untuk mencegah entry di kondisi yang tidak menguntungkan.

### 4.1 Session Filter (`src/filters/session.py`)

- [ ] Implement `SessionFilter` class:
  - [ ] `is_trading_allowed()` — Cek apakah waktu saat ini dalam 12:00-21:00 UTC
  - [ ] `should_force_close()` — Return True jika waktu >= 20:55 UTC
  - [ ] `time_until_session_start()` — Waktu tunggu sampai session buka
  - [ ] `time_until_force_close()` — Waktu tersisa sebelum force close
  - [ ] Handle timezone conversion dengan benar (server time → UTC)
  - [ ] Handle edge case: pergantian hari / weekend

### 4.2 ATR Spike Filter (`src/filters/atr_spike.py`)

- [ ] Implement `ATRSpikeFilter` class:
  - [ ] `is_spike()` — Return True jika current ATR > 2.0 × SMA(ATR, 100)
  - [ ] `get_spike_ratio()` — Return rasio ATR/SMA untuk logging
  - [ ] Log warning ketika spike terdeteksi
  - [ ] Spike = volatilitas abnormal, sinyal sebaiknya di-skip

### 4.3 News Filter (`src/filters/news.py`)

- [ ] Implement `NewsFilter` class:
  - [ ] `fetch_news_calendar()` — Fetch jadwal news high-impact USD
  - [ ] Sumber data: ForexFactory, Investing.com, atau API lain
  - [ ] Parse HTML/JSON dari sumber berita
  - [ ] `is_news_blackout()` — Return True jika dalam window:
    - [ ] 15 menit SEBELUM high-impact news
    - [ ] 10 menit SETELAH high-impact news
  - [ ] `get_next_news_event()` — Return waktu news terdekat
  - [ ] Cache jadwal news (refresh 1x per hari atau per session)
  - [ ] Fallback: jika fetch gagal, **tetap izinkan trading** (dengan warning)

### 4.4 Filter Aggregator

- [ ] Implement `FilterManager` class:
  - [ ] `can_trade()` — Cek SEMUA filter, return (bool, reason)
  - [ ] Aggregate results dari session + ATR spike + news filter
  - [ ] Log filter yang memblokir sinyal (dengan alasan)
  - [ ] Return human-readable reason jika blocked

---

## Phase 5: Execution ⚡

> Order management, trailing stop, dan posisi management.

### 5.1 Order Manager (`src/execution/order_manager.py`)

- [ ] Implement `OrderManager` class:
  - [ ] `place_buy()` — Kirim market BUY order dengan TP/SL
  - [ ] `place_sell()` — Kirim market SELL order dengan TP/SL
  - [ ] `close_position()` — Tutup posisi spesifik by ticket
  - [ ] `close_all_positions()` — Tutup semua posisi (untuk force close)
  - [ ] `modify_sl()` — Update stop loss (untuk trailing)
  - [ ] `get_open_positions()` — Daftar posisi aktif (by magic number)
- [ ] Implement retry logic untuk setiap operasi order:
  - [ ] Max 3 attempts dengan exponential backoff
  - [ ] Refresh harga setiap retry (hindari stale price)
  - [ ] Handle requote, off-quotes, dan error lainnya
- [ ] Implement pyramid control:
  - [ ] Cek jumlah posisi aktif sebelum buka posisi baru
  - [ ] Max 3 posisi simultan (sesuai settings)
  - [ ] Log rejection jika melebihi limit
- [ ] Implement slippage protection:
  - [ ] Max deviation parameter di order request
  - [ ] Log actual vs expected fill price

### 5.2 Trailing Stop (`src/execution/trailing.py`)

- [ ] Implement `TrailingStopManager` class:
  - [ ] `update_trailing_stops()` — Update SL untuk semua posisi aktif
  - [ ] Logic trailing:
    - [ ] Trail distance = 0.8 × ATR
    - [ ] Trail offset = 0.3 × trail_distance
    - [ ] BUY: new_sl = current_price - trail_distance
    - [ ] SELL: new_sl = current_price + trail_distance
    - [ ] Hanya update jika new_sl lebih baik dari current SL
    - [ ] Aktivasi trailing setelah profit >= trail_offset
  - [ ] `should_trail()` — Cek apakah posisi sudah qualify untuk trailing
  - [ ] Run setiap 5 detik (bukan setiap tick, untuk efisiensi)

### 5.3 Force Close Handler

- [ ] Implement logika force close di 20:55 UTC:
  - [ ] Close semua posisi aktif (by magic number)
  - [ ] Log semua posisi yang di-close beserta P&L
  - [ ] Kirim notifikasi ke Telegram
  - [ ] Pastikan tidak ada posisi tertinggal (double-check)

---

## Phase 6: Risk Management 🛡️

> Circuit breakers, drawdown protection, dan safety nets.

### 6.1 Circuit Breaker System (`src/risk/circuit_breaker.py`)

- [ ] Implement `CircuitBreaker` class:
  - [ ] **Daily Loss Stop (3%)**:
    - [ ] Hitung total loss hari ini vs balance awal hari
    - [ ] Jika loss > 3%: STOP trading, tunggu besok
    - [ ] Log: "Circuit breaker activated: daily loss {pct}%"
    - [ ] Notifikasi Telegram
  - [ ] **Emergency Stop (5%)**:
    - [ ] Jika loss > 5%: STOP + close semua posisi
    - [ ] Log level CRITICAL
    - [ ] Notifikasi Telegram urgent
    - [ ] **Butuh manual restart** setelah review
  - [ ] **Equity Shutdown (70%)**:
    - [ ] Jika equity < 70% dari balance awal
    - [ ] **SHUTDOWN bot completely**
    - [ ] Close semua posisi
    - [ ] Log level CRITICAL
    - [ ] Notifikasi Telegram urgent
    - [ ] **Butuh manual intervention** untuk restart

### 6.2 Consecutive Loss Cooldown

- [ ] Track jumlah consecutive losses:
  - [ ] Reset counter setelah 1 win
  - [ ] Jika 3 consecutive losses → cooldown 30 menit
  - [ ] Log: "Cooldown activated: 3 consecutive losses, resume at {time}"
  - [ ] `is_in_cooldown()` — Return True jika masih dalam cooldown period
  - [ ] `get_cooldown_remaining()` — Sisa waktu cooldown

### 6.3 Position Sizer (`src/risk/position_sizer.py`)

- [ ] Implement `PositionSizer` class:
  - [ ] `get_lot_size()` — Return lot size (fixed 0.02 untuk V6)
  - [ ] `can_open_position()` — Cek margin, pyramid limit
  - [ ] `check_pyramid_limit()` — Max 3 posisi simultan
  - [ ] Validasi free margin cukup sebelum buka posisi

### 6.4 Daily State Management

- [ ] Track daily stats:
  - [ ] `start_of_day_balance` — Balance saat session dimulai
  - [ ] `daily_trades_count` — Jumlah trade hari ini
  - [ ] `daily_wins` / `daily_losses` — Win/loss count
  - [ ] `daily_pnl` — Total P&L hari ini
- [ ] Reset semua counters di awal session baru
- [ ] Persist state ke file (survive restart)

---

## Phase 7: Notifications 📱

> Telegram bot untuk monitoring dan alert.

### 7.1 Telegram Notifier (`src/notifications/telegram.py`)

- [ ] Implement `TelegramNotifier` class:
  - [ ] `send_message()` — Kirim text message ke chat
  - [ ] `send_trade_alert()` — Format dan kirim alert trade:
    ```
    🟢 BUY XAUUSD
    Entry: 2650.50
    SL: 2645.30 (-5.20)
    TP: 2661.35 (+10.85)
    Lot: 0.02
    ATR: 4.34
    RSI: 65.2
    Time: 2026-06-29 14:32:01 UTC
    ```
  - [ ] `send_close_alert()` — Alert saat posisi ditutup:
    ```
    🔴 CLOSED BUY XAUUSD
    Ticket: 12345678
    P&L: +$12.50
    Reason: TP Hit
    Duration: 23 min
    ```
  - [ ] `send_daily_report()` — Laporan harian:
    ```
    📊 Daily Report — 2026-06-29
    Trades: 8 (5W / 3L)
    Win Rate: 62.5%
    Net P&L: +$45.20
    Max DD: -1.2%
    Balance: $10,045.20
    ```
  - [ ] `send_circuit_breaker_alert()` — Alert circuit breaker
  - [ ] `send_startup_message()` — Konfirmasi bot mulai berjalan
  - [ ] `send_shutdown_message()` — Konfirmasi bot berhenti

### 7.2 Message Queue & Rate Limiting

- [ ] Implement message queue (hindari Telegram rate limit)
- [ ] Max 30 pesan per detik (Telegram limit)
- [ ] Retry pengiriman jika gagal (max 3x)
- [ ] Fallback: log ke file jika Telegram unreachable

---

## Phase 8: Testing & Validation 🧪

> Comprehensive testing untuk memastikan semua komponen bekerja dengan benar.

### 8.1 Unit Tests

- [ ] `test_indicators.py`:
  - [ ] Test EMA calculation dengan known values
  - [ ] Test RSI calculation (edge cases: all up, all down, flat)
  - [ ] Test ATR calculation accuracy
  - [ ] Test Donchian Channel upper/lower bands
  - [ ] Test ATR SMA calculation
- [ ] `test_signals.py`:
  - [ ] Test LONG signal — semua kondisi terpenuhi → BUY
  - [ ] Test LONG signal — 1 kondisi gagal → No signal
  - [ ] Test SHORT signal — semua kondisi terpenuhi → SELL
  - [ ] Test SHORT signal — 1 kondisi gagal → No signal
  - [ ] Test TP/SL/Trail calculation accuracy
  - [ ] Test edge case: RSI tepat di threshold (60/40)
- [ ] `test_filters.py`:
  - [ ] Test session filter — dalam jam trading → allowed
  - [ ] Test session filter — luar jam trading → blocked
  - [ ] Test session filter — force close time → True
  - [ ] Test ATR spike — normal ATR → allowed
  - [ ] Test ATR spike — spike detected → blocked
  - [ ] Test news filter — during blackout → blocked
  - [ ] Test news filter — outside blackout → allowed
- [ ] `test_risk.py`:
  - [ ] Test circuit breaker — loss < 3% → continue
  - [ ] Test circuit breaker — loss > 3% → halt
  - [ ] Test circuit breaker — loss > 5% → emergency
  - [ ] Test equity shutdown — equity < 70% → shutdown
  - [ ] Test consecutive losses — 3 losses → cooldown
  - [ ] Test consecutive losses — win resets counter
  - [ ] Test pyramid limit — reject if positions >= 3
- [ ] `test_helpers.py`:
  - [ ] Test config loader
  - [ ] Test utility functions
  - [ ] Test data validation

### 8.2 Integration Tests

- [ ] `test_mt5_connector.py` (dengan mock):
  - [ ] Test successful connection
  - [ ] Test connection failure → retry
  - [ ] Test auto-reconnect
  - [ ] Test data fetching dengan mock responses
- [ ] `test_order_manager.py` (dengan mock):
  - [ ] Test order placement → success
  - [ ] Test order placement → requote → retry → success
  - [ ] Test order modification (trailing SL)
  - [ ] Test close position
  - [ ] Test pyramid limit enforcement
- [ ] `test_telegram.py` (dengan mock):
  - [ ] Test message sending
  - [ ] Test rate limiting
  - [ ] Test failure → retry

### 8.3 End-to-End Validation

- [ ] Jalankan bot di **demo account** minimal 5 hari trading
- [ ] Verifikasi:
  - [ ] Signal generation sesuai rules
  - [ ] TP/SL placement benar
  - [ ] Trailing stop berjalan
  - [ ] Force close di 20:55 UTC
  - [ ] Circuit breakers trigger di threshold yang benar
  - [ ] Telegram notifikasi terkirim
  - [ ] No memory leaks setelah 24+ jam running
- [ ] Compare hasil dengan manual backtest
- [ ] Document semua discrepancies

### 8.4 Coverage & Quality

- [ ] Minimum code coverage: **80%**
- [ ] Jalankan: `pytest --cov=src --cov-report=term-missing --cov-fail-under=80`
- [ ] Fix semua uncovered critical paths
- [ ] Semua fungsi punya docstrings
- [ ] Tidak ada TODO/FIXME/HACK di kode production

---

## Phase 9: Deployment & Monitoring 🚀

> Deploy ke production dan setup monitoring berkelanjutan.

### 9.1 VPS Setup

- [ ] Sewa VPS (recommended: Windows VPS, 2GB RAM, SSD)
- [ ] Install MetaTrader 5 terminal
- [ ] Install Python 3.10+
- [ ] Clone repository ke VPS
- [ ] Setup virtual environment dan install dependencies
- [ ] Copy `.env` file dengan production credentials
- [ ] Verifikasi MT5 terminal login berhasil
- [ ] Test jalankan bot secara manual

### 9.2 Auto-Start Configuration

- [ ] Buat Windows Task Scheduler untuk auto-start bot
- [ ] Buat startup script (`start_bot.bat` atau `start_bot.ps1`)
- [ ] Setup auto-restart jika crash (watchdog script)
- [ ] Verifikasi auto-start setelah VPS reboot

### 9.3 Monitoring Setup

- [ ] Setup log rotation (loguru: daily, 30 days retention)
- [ ] Buat daily report automation (Telegram, setiap 21:05 UTC)
- [ ] Setup health check endpoint (opsional: simple HTTP server)
- [ ] Buat performance tracking spreadsheet/dashboard
- [ ] Setup alert jika bot tidak kirim heartbeat > 5 menit

### 9.4 Backup & Recovery

- [ ] Backup strategy: daily backup trade logs
- [ ] Backup `.env` dan `settings.yaml` secara terpisah
- [ ] Dokumentasikan recovery procedure jika VPS gagal
- [ ] Test full recovery dari backup

### 9.5 Post-Launch Review Schedule

- [ ] **Daily**: Cek logs, review trades, verify circuit breakers
- [ ] **Weekly**: Review win rate, P&L, max drawdown, adjust params jika perlu
- [ ] **Monthly**: Full performance review, compare dengan backtest expectations
- [ ] **Quarterly**: Strategy review, consider parameter optimization

---

## 🏷️ Priority Legend

| Priority | Meaning |
|---|---|
| 🔴 P0 | Critical — Must have, blocking other tasks |
| 🟠 P1 | High — Important, needed for core functionality |
| 🟡 P2 | Medium — Needed but not blocking |
| 🟢 P3 | Low — Nice to have, can defer |

### Suggested Build Order (Critical Path)

```
Phase 1 (Setup) → Phase 2 (MT5) → Phase 3 (Strategy) → Phase 5 (Execution)
                                  → Phase 4 (Filters) ↗
                                  → Phase 6 (Risk) ↗
                                                        → Phase 7 (Telegram)
                                                        → Phase 8 (Testing)
                                                        → Phase 9 (Deploy)
```

> Phase 3, 4, dan 6 bisa dikerjakan secara paralel setelah Phase 2 selesai.

---

> **Last Updated:** 2026-06-29
> **Version:** 1.0.0
> **Author:** AGGRO V6 Development Team
