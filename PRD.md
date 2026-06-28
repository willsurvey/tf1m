# PRD: XAUUSD AGGRO V6 — Automated Trading Bot (MT5 + Python)

## 1. Overview

**Nama Produk:** XAUUSD AGGRO V6 Trading Bot  
**Versi:** 1.0.0  
**Platform:** MetaTrader 5 (MT5) via Python API  
**Bahasa:** Python 3.10+  
**Symbol:** XAUUSD (Gold / US Dollar)  
**Timeframe:** M1 (1 Menit)

### 1.1 Latar Belakang

Strategi ini dikembangkan melalui iterasi backtest intensif di TradingView (V1–V6).
AGGRO V6 terpilih sebagai versi final dengan performa terbaik:

| Metrik | Nilai |
|---|---|
| Total PnL (5 hari) | +289,37 USD (+2,89%) |
| Profit Factor | 1,316 |
| Win Rate | 58,87% (229/389) |
| Drawdown Maks | 91,83 USD (0,89%) |
| Return per Hari | ~0,58% |

### 1.2 Tujuan

Mengimplementasikan strategi AGGRO V6 ke dalam bot Python yang:
1. Terhubung ke MT5 secara real-time
2. Mengeksekusi sinyal otomatis pada timeframe M1
3. Menyaring berita ekonomi berdampak tinggi (News Filter)
4. Mengelola risiko dengan anti margin-call protection
5. Mengirim notifikasi real-time via Telegram

---

## 2. Strategy Specification

### 2.1 Indikator yang Digunakan

| Indikator | Parameter | Fungsi |
|---|---|---|
| **EMA Fast** | Period: 5 | Trend jangka sangat pendek |
| **EMA Slow** | Period: 13 | Trend jangka pendek |
| **RSI** | Period: 7, Bull: 60, Bear: 40 | Konfirmasi momentum |
| **ATR** | Period: 10 | Volatilitas untuk sizing TP/SL/Trail |
| **ATR Average** | SMA(ATR, 100) | Baseline volatilitas untuk spike detection |
| **Donchian Channel** | Period: 10 | Breakout confirmation |

### 2.2 Sinyal Entry

#### LONG Entry (semua kondisi harus TRUE):
```
1. EMA(5) > EMA(13)                    # Trend bullish
2. Close > EMA(5)                       # Harga di atas fast EMA
3. RSI(7) > 60                          # Momentum bullish kuat
4. High >= Donchian_High[1]             # Breakout konfirmasi
5. Session filter = TRUE                # Dalam jam trading aktif
6. ATR spike filter = FALSE             # Tidak ada volatilitas abnormal
7. News filter = TRUE (no news nearby)  # Tidak ada berita berdampak tinggi
8. Jumlah posisi terbuka < 3            # Pyramiding belum penuh
```

#### SHORT Entry (semua kondisi harus TRUE):
```
1. EMA(5) < EMA(13)                    # Trend bearish
2. Close < EMA(5)                       # Harga di bawah fast EMA
3. RSI(7) < 40                          # Momentum bearish kuat
4. Low <= Donchian_Low[1]               # Breakout konfirmasi
5. Session filter = TRUE
6. ATR spike filter = FALSE
7. News filter = TRUE (no news nearby)
8. Jumlah posisi terbuka < 3
```

### 2.3 Exit Rules

| Tipe | Formula | Keterangan |
|---|---|---|
| **Take Profit** | Entry ± (2.5 × ATR) | Arah sesuai posisi |
| **Stop Loss** | Entry ∓ (1.2 × ATR) | Proteksi kerugian |
| **Trailing Stop** | 0.8 × ATR dari highest profit | Kunci profit yang sudah berjalan |
| **Trail Offset** | 0.3 × Trail distance | Jarak aktivasi trailing |

### 2.4 Session Filter

| Parameter | Nilai | Keterangan |
|---|---|---|
| **Sesi Aktif** | 12:00–21:00 UTC | London open → NY close |
| **Hari Aktif** | Senin–Jumat | Skip weekend |
| **Force Close** | 20:55 UTC | Tutup semua posisi 5 menit sebelum sesi berakhir |

### 2.5 ATR Spike Filter (News Proxy)

```python
is_spike = current_atr > (average_atr_100 * spike_threshold)
# spike_threshold = 2.0
# Jika is_spike = True → SKIP semua entry baru
# Posisi yang sudah terbuka TIDAK ditutup (trailing stop tetap jalan)
```

### 2.6 News Filter

#### Sumber Data:
1. **Primary:** MT5 Economic Calendar (`calendar_by_country`)
2. **Fallback:** ForexFactory RSS / Investing.com scraping
3. **Manual Override:** File JSON lokal untuk custom blackout periods

#### Logic:
```python
BLACKOUT_MINUTES_BEFORE = 15  # Jangan entry 15 menit sebelum news
BLACKOUT_MINUTES_AFTER  = 10  # Jangan entry 10 menit setelah news
IMPACT_LEVELS = ["high"]      # Hanya filter berita HIGH impact

# Mata uang yang difilter: USD (karena XAUUSD)
# Event yang difilter: NFP, FOMC, CPI, PPI, GDP, Unemployment, ISM, Fed Speech
```

#### Daftar Event High-Impact yang Di-filter:
| Event | Frequency | Typical Volatility |
|---|---|---|
| Non-Farm Payrolls (NFP) | Monthly (1st Friday) | ±$30–50 |
| FOMC Rate Decision | 8x/year | ±$20–40 |
| CPI (Consumer Price Index) | Monthly | ±$15–30 |
| PPI (Producer Price Index) | Monthly | ±$10–20 |
| GDP | Quarterly | ±$10–20 |
| Unemployment Claims | Weekly (Thursday) | ±$5–15 |
| ISM Manufacturing/Services | Monthly | ±$5–15 |
| Fed Chair Speech | Irregular | ±$10–25 |
| PCE Price Index | Monthly | ±$10–20 |
| Retail Sales | Monthly | ±$5–15 |

---

## 3. Risk Management

### 3.1 Posisi & Lot Sizing

| Parameter | Nilai | Keterangan |
|---|---|---|
| **Lot per Entry** | 0.02 | Fixed lot berdasarkan modal $1.000 |
| **Max Pyramiding** | 3 | Max 3 posisi terbuka bersamaan |
| **Max Total Lot** | 0.06 | 3 × 0.02 |
| **Leverage** | 1:100 | Minimum yang direkomendasikan |

### 3.2 Circuit Breakers (Kill Switches)

| Trigger | Action | Recovery |
|---|---|---|
| **Daily Loss > 3%** | Stop trading hari ini | Reset keesokan hari |
| **Daily Loss > 5%** | Stop trading + notifikasi darurat | Manual reset |
| **Equity < 70% modal awal** | Tutup semua posisi, stop bot | Manual restart |
| **3 loss berturut-turut** | Cooldown 30 menit | Auto-resume |
| **MT5 disconnect > 30 detik** | Tutup semua posisi | Auto-reconnect |

### 3.3 Max Drawdown Protection

```python
# Monitor real-time
max_equity_today = max(equity_history_today)
current_drawdown = (max_equity_today - current_equity) / max_equity_today * 100

if current_drawdown > MAX_DAILY_DD_PERCENT:  # 3%
    close_all_positions()
    pause_trading_until_tomorrow()
    send_alert("⚠️ Daily DD limit reached!")
```

---

## 4. Arsitektur Sistem

### 4.1 Project Structure

```
xauusd-aggro-v6/
├── README.md                    # Dokumentasi utama
├── PRD.md                       # Product Requirements (file ini)
├── Guideline.md                 # Development guidelines
├── Task.md                      # Task breakdown
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
├── .env                         # Environment variables (JANGAN commit)
│
├── config/
│   └── settings.yaml            # Semua parameter strategi & konfigurasi
│
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point aplikasi
│   ├── bot.py                   # Orchestrator utama (main loop)
│   │
│   ├── mt5_connector.py         # MT5 connection & data fetching
│   │
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── signals.py           # Kalkulasi indikator & sinyal entry
│   │   ├── filters.py           # Session, ATR spike, news filter
│   │   └── risk_manager.py      # Lot sizing, DD protection, circuit breaker
│   │
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_manager.py     # Kirim, modifikasi, tutup order ke MT5
│   │   └── trail_manager.py     # Trailing stop management loop
│   │
│   ├── news/
│   │   ├── __init__.py
│   │   ├── calendar_fetcher.py  # Ambil kalender ekonomi
│   │   └── impact_filter.py     # Evaluasi dampak berita pada trading
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py            # Setup logging (file + console)
│       ├── notifier.py          # Telegram notification
│       └── helpers.py           # Fungsi utilitas umum
│
├── tests/
│   ├── __init__.py
│   ├── test_signals.py          # Unit test sinyal entry/exit
│   ├── test_filters.py          # Unit test semua filter
│   ├── test_risk_manager.py     # Unit test risk management
│   └── test_order_manager.py    # Unit test order execution
│
├── logs/                        # Log files (auto-generated)
│   └── .gitkeep
│
└── data/                        # Data files (auto-generated)
    ├── .gitkeep
    ├── news_cache.json           # Cache kalender ekonomi
    └── trade_journal.csv         # Log semua trade yang dieksekusi
```

### 4.2 Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│                    MAIN LOOP (setiap 1 detik)       │
│                                                     │
│  1. Cek koneksi MT5 ─── Reconnect jika putus       │
│  2. Ambil data M1 terbaru (100 bar terakhir)        │
│  3. Hitung indikator (EMA, RSI, ATR, Donchian)      │
│  4. Cek filter:                                     │
│     ├── Session filter (12:00-21:00 UTC?)            │
│     ├── ATR spike filter (volatilitas normal?)       │
│     ├── News filter (tidak ada berita 15 min?)       │
│     └── Circuit breaker (DD/loss limit OK?)          │
│  5. Generate sinyal (LONG / SHORT / NO_SIGNAL)       │
│  6. Jika sinyal valid:                               │
│     ├── Cek pyramiding (< 3 posisi?)                 │
│     ├── Hitung TP/SL/Trail dari ATR                  │
│     └── Kirim order ke MT5                           │
│  7. Update trailing stop posisi yang ada              │
│  8. Cek force close (20:55 UTC?)                     │
│  9. Log & monitor performa                           │
│ 10. Kirim notifikasi jika ada trade/alert            │
└─────────────────────────────────────────────────────┘
```

---

## 5. Dependensi Python

### 5.1 Core Dependencies

| Package | Versi | Fungsi |
|---|---|---|
| `MetaTrader5` | ≥5.0.45 | MT5 Python API |
| `pandas` | ≥2.0 | Manipulasi data OHLCV |
| `numpy` | ≥1.24 | Kalkulasi numerik |
| `pyyaml` | ≥6.0 | Baca config YAML |
| `python-dotenv` | ≥1.0 | Load .env file |
| `loguru` | ≥0.7 | Advanced logging |
| `schedule` | ≥1.2 | Task scheduling |
| `requests` | ≥2.28 | HTTP requests (news API) |

### 5.2 Optional Dependencies

| Package | Versi | Fungsi |
|---|---|---|
| `python-telegram-bot` | ≥20.0 | Telegram notifikasi |
| `beautifulsoup4` | ≥4.12 | Scraping ForexFactory (fallback news) |
| `lxml` | ≥4.9 | Parser HTML (untuk BS4) |
| `pytest` | ≥7.0 | Unit testing |
| `pytest-cov` | ≥4.0 | Test coverage |

---

## 6. Konfigurasi (settings.yaml)

```yaml
strategy:
  symbol: "XAUUSD"
  timeframe: "M1"
  
  indicators:
    ema_fast: 5
    ema_slow: 13
    rsi_period: 7
    rsi_bull_threshold: 60
    rsi_bear_threshold: 40
    atr_period: 10
    atr_avg_period: 100
    donchian_period: 10
  
  exit:
    tp_atr_mult: 2.5
    sl_atr_mult: 1.2
    trail_atr_mult: 0.8
    trail_offset_ratio: 0.3
  
  filters:
    session_start_utc: "12:00"
    session_end_utc: "21:00"
    force_close_utc: "20:55"
    trading_days: [0, 1, 2, 3, 4]  # Mon-Fri
    atr_spike_threshold: 2.0
    
  news:
    enabled: true
    blackout_before_min: 15
    blackout_after_min: 10
    impact_levels: ["high"]
    currencies: ["USD"]
    cache_ttl_hours: 6

risk:
  lot_size: 0.02
  max_pyramiding: 3
  max_daily_loss_pct: 3.0
  max_total_loss_pct: 30.0
  consecutive_loss_cooldown: 3
  cooldown_minutes: 30
  disconnect_timeout_sec: 30

mt5:
  login: ${MT5_LOGIN}
  password: ${MT5_PASSWORD}
  server: ${MT5_SERVER}
  path: ${MT5_PATH}
  magic_number: 20260629
  deviation: 20
  type_filling: "ioc"

notifications:
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}
  
logging:
  level: "INFO"
  file_rotation: "10 MB"
  file_retention: "30 days"
  console: true
```

---

## 7. API Functions Reference

### 7.1 Core Functions

| Module | Function | Input | Output | Deskripsi |
|---|---|---|---|---|
| `signals` | `calculate_indicators(df)` | DataFrame OHLCV | DataFrame + kolom indikator | Hitung semua indikator |
| `signals` | `generate_signal(df)` | DataFrame + indikator | `"LONG"` / `"SHORT"` / `None` | Generate sinyal trading |
| `filters` | `is_session_active(utc_now)` | datetime UTC | bool | Cek jam trading |
| `filters` | `is_atr_spike(atr, avg_atr)` | float, float | bool | Cek volatilitas abnormal |
| `filters` | `is_news_blackout(utc_now)` | datetime UTC | bool | Cek apakah ada berita dekat |
| `risk_manager` | `can_open_position()` | - | bool | Cek semua kondisi risiko |
| `risk_manager` | `check_circuit_breakers()` | - | bool | Cek kill switches |
| `order_manager` | `open_position(signal, tp, sl)` | str, float, float | int (ticket) | Buka posisi baru |
| `order_manager` | `close_position(ticket)` | int | bool | Tutup posisi spesifik |
| `order_manager` | `close_all_positions()` | - | int (count) | Tutup semua posisi |
| `trail_manager` | `update_trailing_stops()` | - | int (modified) | Update trailing stop |
| `calendar_fetcher` | `fetch_today_events()` | - | List[NewsEvent] | Ambil berita hari ini |
| `impact_filter` | `get_blackout_windows()` | - | List[TimeWindow] | Daftar window blackout |
| `notifier` | `send_trade_alert(msg)` | str | bool | Kirim notifikasi Telegram |

### 7.2 Data Models

```python
@dataclass
class TradeSignal:
    direction: str          # "LONG" or "SHORT"
    entry_price: float      # Current ask/bid price
    take_profit: float      # Calculated TP
    stop_loss: float        # Calculated SL
    trail_distance: float   # Trailing stop distance in points
    atr_value: float        # Current ATR value
    timestamp: datetime     # Signal generation time

@dataclass
class NewsEvent:
    name: str               # "Non-Farm Payrolls"
    currency: str           # "USD"
    impact: str             # "high", "medium", "low"
    datetime_utc: datetime  # Event scheduled time
    actual: Optional[str]   # Actual value (after release)
    forecast: Optional[str] # Forecasted value
    previous: Optional[str] # Previous value

@dataclass  
class RiskStatus:
    can_trade: bool
    reason: str             # Why trading is blocked (if any)
    daily_pnl: float
    daily_pnl_pct: float
    open_positions: int
    consecutive_losses: int
    max_equity_today: float
    current_drawdown_pct: float
```

---

## 8. Notifikasi Telegram

### 8.1 Format Pesan

```
📊 TRADE OPENED
━━━━━━━━━━━━━━━
Symbol: XAUUSD
Signal: 🟢 LONG
Entry: 4088.530
TP: 4093.280 (+4.750)
SL: 4085.050 (-3.480)
Lot: 0.02
Positions: 1/3
━━━━━━━━━━━━━━━
⏰ 2026-06-29 14:32 UTC
```

```
✅ TRADE CLOSED (TP HIT)
━━━━━━━━━━━━━━━
Symbol: XAUUSD
Direction: 🟢 LONG
Entry: 4088.530 → Exit: 4093.280
PnL: +$9.50 (+0.95%)
Duration: 12 min
━━━━━━━━━━━━━━━
📊 Today: +$38.20 (+3.82%)
```

```
⚠️ NEWS BLACKOUT ACTIVE
━━━━━━━━━━━━━━━
Event: Non-Farm Payrolls 🔴
Time: 14:30 UTC (in 12 min)
Blackout: 14:15 - 14:40 UTC
Action: All entries PAUSED
━━━━━━━━━━━━━━━
```

---

## 9. Monitoring & Logging

### 9.1 Log Levels

| Level | Contoh |
|---|---|
| `DEBUG` | Setiap kalkulasi indikator, setiap tick |
| `INFO` | Trade opened/closed, filter status, session start/end |
| `WARNING` | News blackout active, consecutive losses, high DD |
| `ERROR` | MT5 disconnect, order rejection, API failure |
| `CRITICAL` | Circuit breaker triggered, emergency close |

### 9.2 Trade Journal (CSV)

Setiap trade dicatat ke `data/trade_journal.csv`:
```csv
timestamp,ticket,symbol,direction,entry,exit,tp,sl,lot,pnl_usd,pnl_pct,duration_min,exit_reason
```

---

## 10. Deployment

### 10.1 Requirements
- Windows 10/11 (MT5 hanya tersedia di Windows)
- MetaTrader 5 terminal terinstall dan login
- Python 3.10+ (64-bit)
- Koneksi internet stabil

### 10.2 Startup
```bash
# Install dependencies
pip install -r requirements.txt

# Copy dan isi environment variables
cp .env.example .env
# Edit .env dengan login MT5 dan token Telegram

# Jalankan bot
python -m src.main

# Atau jalankan dalam mode dry-run (tanpa eksekusi order)
python -m src.main --dry-run
```

### 10.3 Proses Operasional Harian
1. **Sebelum market open:** Bot auto-start, fetch news calendar
2. **12:00 UTC:** Mulai scan sinyal & entry
3. **20:55 UTC:** Force close semua posisi
4. **21:00 UTC:** Session end, generate daily report
5. **Kirim daily summary via Telegram**
