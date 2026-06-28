"""
Quick test script untuk verifikasi news filter logic.
Jalankan: python test_news.py
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Tambahkan root project ke path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from src.utils.helpers import load_config
from src.news.calendar_fetcher import CalendarFetcher
from src.news.impact_filter import NewsImpactFilter

print("=" * 55)
print("  NEWS FILTER — VERIFICATION TEST")
print("=" * 55)

config = load_config("config/settings.yaml")

# ── 1. Test CalendarFetcher ──────────────────────────────
print("\n[1] Fetching today's news events...")
fetcher = CalendarFetcher(config)
events = fetcher.fetch_today_events()

if events:
    print(f"    ✅ {len(events)} event(s) loaded:")
    for ev in events:
        print(f"       📰 [{ev['impact'].upper()}] {ev['name']} @ {ev['datetime_utc']}")
else:
    print("    ℹ️  No high-impact events found today (or news source unavailable)")
    print("    → Bot will trade normally without any blackout window")

# ── 2. Test NewsImpactFilter ─────────────────────────────
print("\n[2] Loading blackout windows...")
news_filter = NewsImpactFilter(config, fetcher)
windows = news_filter.get_blackout_windows()

if windows:
    print(f"    ✅ {len(windows)} blackout window(s):")
    for w in windows:
        print(f"       ⏰ {w['name']}")
        print(f"          Block: {w['start'].strftime('%H:%M')} – {w['end'].strftime('%H:%M')} UTC")
else:
    print("    ℹ️  No blackout windows active today")

# ── 3. Test is_in_blackout (sekarang) ───────────────────
print("\n[3] Checking current time vs blackout...")
now = datetime.now(timezone.utc)
is_blackout, event_name = news_filter.is_in_blackout(now)
print(f"    Current UTC time : {now.strftime('%Y-%m-%d %H:%M:%S')}")
if is_blackout:
    print(f"    🔴 BLACKOUT ACTIVE: {event_name}")
    print(f"    → Bot would PAUSE entries right now")
else:
    print(f"    ✅ No blackout — bot is free to trade (if in session)")

# ── 4. Simulasi blackout manual ──────────────────────────
print("\n[4] Simulating a news blackout (manual test)...")

# Buat event palsu 5 menit dari sekarang
fake_event_time = now + timedelta(minutes=5)
test_windows = [{
    "name": "FOMC Interest Rate Decision [TEST]",
    "event_time": fake_event_time,
    "start": fake_event_time - timedelta(minutes=15),
    "end": fake_event_time + timedelta(minutes=10),
}]

# Inject langsung ke filter
news_filter._blackout_windows = test_windows
news_filter._last_refresh = now  # prevent re-fetch

# Test waktu saat ini (harus DALAM blackout karena start = now - 15 min = sebelum now)
test_time_inside = now  # sekarang ada di dalam window (start sudah lewat, end belum)
is_block, name = news_filter.is_in_blackout(test_time_inside)

# Waktu sebelum blackout
test_time_before = fake_event_time - timedelta(minutes=20)
is_before, _ = news_filter.is_in_blackout(test_time_before)

# Waktu setelah blackout
test_time_after = fake_event_time + timedelta(minutes=15)
is_after, _ = news_filter.is_in_blackout(test_time_after)

print(f"    Fake event: '{test_windows[0]['name']}'")
print(f"    Blackout window: {test_windows[0]['start'].strftime('%H:%M')} – {test_windows[0]['end'].strftime('%H:%M')} UTC")
print()
print(f"    20 min BEFORE event  → blocked={is_before}  (expected: False) {'✅' if not is_before else '❌'}")
print(f"    DURING blackout (now)→ blocked={is_block}   (expected: True)  {'✅' if is_block else '❌'}")
print(f"    15 min AFTER event   → blocked={is_after}   (expected: False) {'✅' if not is_after else '❌'}")

# ── 5. Test next event lookup ────────────────────────────
print("\n[5] Next upcoming event...")
# Reset ke real windows
news_filter._blackout_windows = windows
next_ev = news_filter.get_next_event(now)
if next_ev:
    mins_away = int((next_ev["event_time"] - now).total_seconds() / 60)
    print(f"    ⏭️  Next: {next_ev['name']}")
    print(f"       In {mins_away} minutes @ {next_ev['event_time'].strftime('%H:%M')} UTC")
    print(f"       Blackout: {next_ev['start'].strftime('%H:%M')} – {next_ev['end'].strftime('%H:%M')} UTC")
else:
    print(f"    ℹ️  No upcoming events today")

print("\n" + "=" * 55)
print("  TEST COMPLETE")
print("=" * 55)
