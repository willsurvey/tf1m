# 📐 Development Guidelines — XAUUSD AGGRO V6

> Dokumen ini berisi standar dan panduan pengembangan untuk proyek trading bot
> XAUUSD AGGRO V6. Semua kontributor **wajib** mengikuti guideline ini untuk
> menjaga konsistensi, kualitas, dan keamanan kode.

---

## 1. Code Style & Standards

### 1.1 PEP 8 Compliance

Semua kode Python **harus** mengikuti [PEP 8](https://peps.python.org/pep-0008/) secara ketat.

| Rule | Detail |
|---|---|
| Indentation | 4 spaces, **tanpa** tab |
| Max line length | 99 karakter (bukan 79, karena modern screen) |
| Imports | Grouped: stdlib → third-party → local, dipisah blank line |
| Naming | `snake_case` untuk fungsi/variabel, `PascalCase` untuk class, `UPPER_SNAKE` untuk konstanta |
| Trailing whitespace | **Tidak boleh** ada trailing whitespace |
| Blank lines | 2 blank lines antara top-level definitions, 1 blank line antara methods |

```python
# ✅ BENAR
import os
import sys
from pathlib import Path

import pandas as pd
import MetaTrader5 as mt5
from loguru import logger

from core.strategy import AggroV6Strategy
from utils.helpers import round_to_tick
```

### 1.2 Type Hints (Wajib di Semua Fungsi)

Gunakan type hints di **semua** parameter dan return value. Untuk struktur data kompleks,
gunakan `typing` module.

```python
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class TradeSignal:
    """Representasi sinyal trading yang dihasilkan strategi."""
    direction: str          # "BUY" atau "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    timestamp: datetime
    confidence: float       # 0.0 - 1.0

def calculate_atr(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    period: int = 10,
) -> pd.Series:
    """Hitung Average True Range."""
    ...
```

### 1.3 Google-Style Docstrings

Setiap fungsi, class, dan module **wajib** punya docstring format Google.

```python
def place_order(
    symbol: str,
    order_type: int,
    lot: float,
    price: float,
    sl: float,
    tp: float,
    magic: int = 20260629,
) -> Optional[mt5.OrderSendResult]:
    """Kirim order ke MT5 dengan retry mechanism.

    Fungsi ini mengirim market order ke MetaTrader 5 terminal dengan
    built-in retry logic untuk menangani slippage dan requote.

    Args:
        symbol: Trading symbol, contoh "XAUUSD".
        order_type: Tipe order (mt5.ORDER_TYPE_BUY atau mt5.ORDER_TYPE_SELL).
        lot: Volume lot yang akan di-trade.
        price: Harga entry yang diinginkan.
        sl: Level stop loss.
        tp: Level take profit.
        magic: Magic number untuk identifikasi EA. Default: 20260629.

    Returns:
        OrderSendResult jika berhasil, None jika gagal setelah semua retry.

    Raises:
        ConnectionError: Jika MT5 terminal tidak terkoneksi.
        ValueError: Jika parameter order tidak valid.

    Example:
        >>> result = place_order("XAUUSD", mt5.ORDER_TYPE_BUY, 0.02, 2650.50, 2645.00, 2662.50)
        >>> if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        ...     logger.info(f"Order berhasil: ticket={result.order}")
    """
    ...
```

### 1.4 Dataclasses untuk Structured Data

Gunakan `@dataclass` (bukan plain dict) untuk semua structured data:

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CircuitBreakerState:
    """State tracking untuk circuit breaker system."""
    daily_loss_pct: float = 0.0
    consecutive_losses: int = 0
    last_loss_time: Optional[datetime] = None
    is_halted: bool = False
    halt_reason: str = ""
    cooldown_until: Optional[datetime] = None
```

---

## 2. Git Workflow

### 2.1 Branching Strategy

Gunakan **Git Flow** yang disederhanakan:

```
main          ← Production-ready, hanya merge dari release/hotfix
├── develop   ← Integration branch, semua feature merge ke sini
│   ├── feature/mt5-connector
│   ├── feature/strategy-core
│   ├── feature/risk-manager
│   └── feature/telegram-notifier
├── release/v1.0.0  ← Pre-release testing
└── hotfix/fix-sl-calculation  ← Emergency fix di production
```

| Branch | Naming Convention | Merge Target |
|---|---|---|
| Feature | `feature/<nama-singkat>` | `develop` |
| Bugfix | `bugfix/<issue-id>-<deskripsi>` | `develop` |
| Release | `release/v<major>.<minor>.<patch>` | `main` + `develop` |
| Hotfix | `hotfix/<deskripsi-singkat>` | `main` + `develop` |

### 2.2 Commit Messages

Gunakan format [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <deskripsi singkat>

[body opsional - penjelasan lebih detail]

[footer opsional - breaking changes, issue references]
```

**Type yang digunakan:**

| Type | Kapan Digunakan |
|---|---|
| `feat` | Fitur baru |
| `fix` | Bug fix |
| `refactor` | Refactoring tanpa perubahan behavior |
| `test` | Menambah atau memperbaiki test |
| `docs` | Perubahan dokumentasi saja |
| `chore` | Maintenance (deps update, CI config, dll) |
| `perf` | Perbaikan performa |

```bash
# ✅ BENAR
git commit -m "feat(strategy): implement Donchian Channel breakout signal"
git commit -m "fix(risk): correct daily loss percentage calculation"
git commit -m "test(connector): add MT5 connection retry unit tests"

# ❌ SALAH
git commit -m "update code"
git commit -m "fix stuff"
git commit -m "wip"
```

### 2.3 Pull Request Rules

- Setiap PR **harus** punya deskripsi yang jelas
- Minimal 1 approval sebelum merge (jika tim > 1 orang)
- Semua tests **harus** pass
- Tidak boleh ada linting errors
- Squash merge ke `develop`, merge commit ke `main`

---

## 3. Testing Requirements

### 3.1 Framework & Tools

| Tool | Kegunaan |
|---|---|
| `pytest` | Test runner utama |
| `pytest-cov` | Coverage reporting |
| `pytest-mock` | Mocking MT5 dan external services |
| `pytest-asyncio` | Jika ada async code |

### 3.2 Minimum Coverage: 80%

```bash
# Jalankan tests dengan coverage report
pytest --cov=src --cov-report=term-missing --cov-fail-under=80

# Generate HTML coverage report
pytest --cov=src --cov-report=html
```

### 3.3 Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_indicators.py   # Test kalkulasi EMA, RSI, ATR, Donchian
│   ├── test_signals.py      # Test signal generation logic
│   ├── test_filters.py      # Test session, ATR spike, news filter
│   ├── test_risk.py         # Test circuit breakers, DD protection
│   └── test_helpers.py      # Test utility functions
├── integration/
│   ├── test_mt5_connector.py    # Test koneksi MT5 (mock)
│   ├── test_order_manager.py    # Test order placement (mock)
│   └── test_telegram.py        # Test notifikasi (mock)
└── fixtures/
    ├── sample_ohlcv.csv     # Data OHLCV untuk testing
    └── sample_config.yaml   # Config untuk testing
```

### 3.4 Test Naming Convention

```python
def test_ema_crossover_generates_buy_signal():
    """EMA(5) > EMA(13) dengan kondisi lain terpenuhi harus generate BUY."""
    ...

def test_circuit_breaker_halts_after_three_percent_loss():
    """Daily loss > 3% harus menghentikan trading."""
    ...

def test_atr_spike_filter_blocks_signal_when_atr_exceeds_threshold():
    """ATR > 2.0 * SMA(ATR, 100) harus memblokir sinyal."""
    ...
```

### 3.5 Critical Test Scenarios (Wajib Ada)

- [ ] Signal generation untuk semua kombinasi kondisi LONG/SHORT
- [ ] ATR spike filter blocking/allowing dengan benar
- [ ] Session filter (dalam/luar jam trading)
- [ ] Circuit breaker activation di setiap threshold
- [ ] TP/SL/Trail calculation accuracy
- [ ] Consecutive loss cooldown timing
- [ ] Force close di 20:55 UTC
- [ ] News filter blocking window (15 min before, 10 min after)
- [ ] Max pyramid enforcement (max 3 posisi)

---

## 4. Error Handling Patterns

### 4.1 Prinsip Umum

> **"Assume everything can fail."**
> Network bisa putus, MT5 bisa crash, API bisa timeout.
> Kode harus defensif dan graceful dalam menangani error.

### 4.2 Logging dengan Loguru

```python
from loguru import logger

# Setup logging (dilakukan SEKALI di main.py)
logger.add(
    "logs/aggro_v6_{time:YYYY-MM-DD}.log",
    rotation="00:00",        # Rotate setiap tengah malam
    retention="30 days",     # Simpan 30 hari
    compression="zip",       # Compress log lama
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
    backtrace=True,          # Full traceback
    diagnose=True,           # Variable values di traceback
)
```

### 4.3 Pattern: Try/Except dengan Context

```python
# ✅ BENAR — Spesifik exception, dengan logging yang informatif
def fetch_ohlcv(symbol: str, timeframe: int, count: int) -> Optional[pd.DataFrame]:
    """Fetch data OHLCV dari MT5."""
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            logger.warning(f"Tidak ada data OHLCV untuk {symbol}, count={count}")
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        logger.debug(f"Fetched {len(df)} bars untuk {symbol}")
        return df
    except Exception as e:
        logger.error(f"Gagal fetch OHLCV {symbol}: {e}")
        return None

# ❌ SALAH — Bare except, tanpa logging
def fetch_ohlcv_bad(symbol, timeframe, count):
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        return pd.DataFrame(rates)
    except:
        pass
```

### 4.4 Pattern: Retry Decorator

```python
import time
from functools import wraps

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator untuk retry logic dengan exponential backoff.

    Args:
        max_attempts: Jumlah maksimal percobaan.
        delay: Delay awal dalam detik.
        backoff: Multiplier untuk delay setiap retry.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} gagal setelah {max_attempts}x: {e}"
                        )
                        raise
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} "
                        f"gagal: {e}. Retry dalam {current_delay:.1f}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
```

### 4.5 Logging Levels — Kapan Pakai Apa

| Level | Kapan Digunakan | Contoh |
|---|---|---|
| `TRACE` | Detail sangat granular, biasanya off | Setiap tick price |
| `DEBUG` | Info untuk debugging | Nilai indicator per bar |
| `INFO` | Event operasional normal | "Order BUY executed", "Session started" |
| `SUCCESS` | Operasi berhasil yang penting | "TP hit +$25.00" |
| `WARNING` | Situasi tidak normal tapi recoverable | "Requote, retrying..." |
| `ERROR` | Error yang butuh perhatian | "Gagal place order" |
| `CRITICAL` | System-level failure | "MT5 disconnected", "Circuit breaker activated" |

---

## 5. MT5-Specific Patterns

### 5.1 Connection Management

```python
class MT5Connector:
    """Mengelola koneksi ke MetaTrader 5 terminal.

    Selalu gunakan context manager atau pastikan shutdown()
    dipanggil saat selesai.
    """

    def __init__(self, config: dict):
        self._config = config
        self._connected = False

    def connect(self) -> bool:
        """Establish koneksi ke MT5 terminal.

        Returns:
            True jika berhasil terkoneksi.
        """
        if not mt5.initialize(
            path=self._config.get("terminal_path"),
            login=self._config["login"],
            password=self._config["password"],
            server=self._config["server"],
            timeout=self._config.get("timeout", 10000),
        ):
            error = mt5.last_error()
            logger.critical(f"MT5 initialize gagal: {error}")
            return False

        self._connected = True
        account_info = mt5.account_info()
        logger.info(
            f"MT5 terkoneksi: {account_info.name} | "
            f"Balance: {account_info.balance} | "
            f"Server: {account_info.server}"
        )
        return True

    def ensure_connected(self) -> bool:
        """Pastikan koneksi aktif, reconnect jika perlu."""
        if not self._connected or mt5.account_info() is None:
            logger.warning("MT5 terputus, mencoba reconnect...")
            return self.connect()
        return True

    def shutdown(self):
        """Tutup koneksi MT5 dengan bersih."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 connection ditutup.")
```

### 5.2 Order Retry Pattern

```python
@retry(max_attempts=3, delay=0.5, backoff=2.0)
def send_market_order(
    symbol: str,
    order_type: int,
    lot: float,
    sl: float,
    tp: float,
    magic: int,
    comment: str = "",
) -> mt5.OrderSendResult:
    """Kirim market order dengan auto-retry untuk requote.

    Harga akan di-refresh setiap retry untuk menghindari
    stale price rejection.
    """
    # Selalu ambil harga terbaru sebelum kirim order
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise ConnectionError(f"Tidak bisa ambil tick untuk {symbol}")

    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        raise ConnectionError("order_send returned None")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(
            f"Order ditolak: retcode={result.retcode}, "
            f"comment={result.comment}"
        )

    return result
```

### 5.3 Data Fetching Best Practices

```python
# ✅ Selalu validasi data setelah fetch
def get_validated_bars(symbol: str, count: int) -> pd.DataFrame:
    """Fetch dan validasi OHLCV bars.

    Raises:
        ValueError: Jika data tidak mencukupi atau corrupt.
    """
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, count)

    if rates is None:
        raise ValueError(f"MT5 returned None untuk {symbol}")

    df = pd.DataFrame(rates)

    # Validasi minimum data
    if len(df) < count * 0.9:  # Toleransi 10% missing bars
        raise ValueError(
            f"Data tidak cukup: expected ~{count}, got {len(df)}"
        )

    # Validasi tidak ada NaN di kolom kritis
    critical_cols = ["open", "high", "low", "close"]
    if df[critical_cols].isna().any().any():
        raise ValueError("Data mengandung NaN di kolom OHLC")

    # Validasi OHLC consistency
    assert (df["high"] >= df["low"]).all(), "High < Low terdeteksi"
    assert (df["high"] >= df["open"]).all(), "High < Open terdeteksi"
    assert (df["high"] >= df["close"]).all(), "High < Close terdeteksi"

    return df
```

---

## 6. Security

### 6.1 Credential Management

> [!CAUTION]
> **JANGAN PERNAH** commit credentials, password, atau API key ke repository!

```yaml
# .env — FILE INI TIDAK BOLEH DI-COMMIT
MT5_LOGIN=12345678
MT5_PASSWORD=MySecretPassword123
MT5_SERVER=ICMarketsSC-Demo
TELEGRAM_BOT_TOKEN=6123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=-1001234567890
```

### 6.2 .gitignore (Wajib)

```gitignore
# Credentials & Secrets
.env
*.env
secrets/

# Logs
logs/
*.log

# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Data
data/*.csv
*.db

# MT5
*.ex5
*.set
```

### 6.3 Config Loading Pattern

```python
import os
from pathlib import Path
from dotenv import load_dotenv
import yaml

def load_config() -> dict:
    """Load konfigurasi dari settings.yaml dan .env.

    Settings.yaml berisi parameter strategi (non-sensitif).
    .env berisi credentials (sensitif).

    Returns:
        Dictionary gabungan konfigurasi.
    """
    # Load .env file
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    # Load settings.yaml
    config_path = Path(__file__).parent.parent / "settings.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Inject credentials dari environment
    config["mt5"]["login"] = int(os.getenv("MT5_LOGIN", "0"))
    config["mt5"]["password"] = os.getenv("MT5_PASSWORD", "")
    config["mt5"]["server"] = os.getenv("MT5_SERVER", "")

    config["telegram"]["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "")
    config["telegram"]["chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "")

    # Validasi credentials
    if config["mt5"]["login"] == 0:
        raise ValueError("MT5_LOGIN tidak di-set di .env")

    return config
```

---

## 7. Performance

### 7.1 Hindari Blocking Calls

```python
# ❌ SALAH — Blocking sleep di main loop
import time
while True:
    check_signals()
    time.sleep(60)  # Block seluruh thread 60 detik

# ✅ BENAR — Event-driven dengan schedule
import schedule
import time

schedule.every(1).minutes.do(check_signals)
schedule.every(5).seconds.do(check_trailing_stops)
schedule.every(30).seconds.do(monitor_circuit_breakers)

while is_running:
    schedule.run_pending()
    time.sleep(0.1)  # Small sleep, non-blocking feel
```

### 7.2 Efficient Data Handling

```python
# ❌ SALAH — Fetch semua data setiap loop
def bad_check():
    df = fetch_10000_bars()  # Fetch ulang 10K bars setiap menit
    ema = df["close"].ewm(span=5).mean()

# ✅ BENAR — Incremental update, fetch hanya yang diperlukan
class DataManager:
    """Mengelola data OHLCV secara efisien dengan incremental update."""

    def __init__(self, lookback: int = 200):
        self._buffer: Optional[pd.DataFrame] = None
        self._lookback = lookback

    def update(self, symbol: str) -> pd.DataFrame:
        """Update buffer dengan bar terbaru saja.

        Hanya fetch bar baru, bukan seluruh history.
        """
        if self._buffer is None:
            # Initial fetch
            self._buffer = fetch_bars(symbol, self._lookback)
        else:
            # Fetch hanya 5 bar terakhir (buffer untuk missed bars)
            new_bars = fetch_bars(symbol, 5)
            self._buffer = pd.concat(
                [self._buffer, new_bars]
            ).drop_duplicates(subset=["time"]).tail(self._lookback)

        return self._buffer
```

### 7.3 Memory Management

```python
# Gunakan dtypes yang tepat untuk hemat memory
df["close"] = df["close"].astype("float32")    # Bukan float64
df["tick_volume"] = df["tick_volume"].astype("int32")  # Bukan int64

# Hapus variabel besar setelah tidak diperlukan
del large_dataframe
import gc
gc.collect()
```

---

## 8. Deployment Checklist

### 8.1 Pre-Deployment

- [ ] **Semua tests pass** — `pytest --cov=src --cov-fail-under=80`
- [ ] **Linting clean** — Tidak ada PEP 8 violations
- [ ] **Type checking** — `mypy src/` tanpa error
- [ ] **Settings.yaml** — Semua parameter sudah sesuai production
- [ ] **.env file** — Credentials production sudah di-set
- [ ] **Magic number** — Unik, tidak konflik dengan EA lain (20260629)
- [ ] **Lot size** — Dikonfirmasi 0.02 (sesuai risk management)
- [ ] **Demo test** — Sudah jalan minimal 1 minggu di demo account
- [ ] **Logs directory** — `logs/` sudah dibuat dan writable
- [ ] **Timezone** — Server time dan UTC offset sudah dikonfirmasi

### 8.2 Go-Live

- [ ] Jalankan di **VPS** (bukan PC personal) — uptime 99.9%
- [ ] **MT5 terminal** sudah login dan auto-start enabled
- [ ] **Algorithmic trading** enabled di MT5 settings
- [ ] **Telegram bot** sudah ditest kirim pesan
- [ ] **Circuit breakers** semua threshold sudah di-set
- [ ] **Session time** dikonfirmasi 12:00-21:00 UTC
- [ ] **News calendar** sumber data sudah bisa di-fetch

### 8.3 Post-Deployment Monitoring

- [ ] Cek **log files** setiap hari untuk error/warning
- [ ] Monitor **equity curve** vs expected drawdown
- [ ] Verifikasi **trailing stop** berjalan dengan benar
- [ ] Pastikan **force close 20:55 UTC** berfungsi
- [ ] Review **circuit breaker activations** weekly
- [ ] Backup **trade journal** dan performance data

### 8.4 Emergency Procedures

| Situasi | Tindakan |
|---|---|
| Bot crash / unresponsive | Restart script, cek logs, close manual jika ada posisi terbuka |
| MT5 disconnect > 5 menit | Kill script, login manual ke MT5, close posisi jika perlu |
| Equity < 70% | **SHUTDOWN OTOMATIS** — Jangan restart tanpa review |
| Daily loss > 5% | **EMERGENCY STOP** — Review strategy, adjust params |
| VPS down | Gunakan MT5 mobile untuk close posisi, investigate VPS |

---

> **Last Updated:** 2026-06-29
> **Version:** 1.0.0
> **Author:** AGGRO V6 Development Team
