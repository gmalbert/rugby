"""
Coverage test for ParlayAPI — rugby focus, with broader sport validation.

Run from repo root:
    python scripts/test_parlay_api.py

Uses 3 credits total (1 for MLB odds schema check, 0 for all rugby tests).
Checks usage before and after so you can see the exact cost.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

if not os.environ.get("PARLAY_API_KEY"):
    sys.exit("ERROR: PARLAY_API_KEY not set in .env")

# Import after env is loaded
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.parlay_api import (
    american_to_implied,
    find_ev,
    format_american,
    get_events,
    get_live_sports,
    get_odds,
    get_public_stats,
    get_scores,
    get_sports,
    get_usage,
)

RUGBY_UNION_LEAGUES = [
    "Six Nations",
    "Premiership Rugby",
    "Top 14",
    "Super Rugby Pacific",
    "United Rugby Championship",
    "European Champions Cup",
]

RUGBY_UNION_SPORT_KEYS = [
    "rugby_union",
    "rugbyunion",
    "rugby_six_nations",
    "rugby_premiership",
    "rugby_top14",
    "rugby_super_rugby",
    "rugby_urc",
    "rugby_champions_cup",
]


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


# ── 0. Credits before ─────────────────────────────────────────
section("0. Credits before test")
usage_before = get_usage()
print(
    f"  Used: {usage_before['credits_used']}  "
    f"Remaining: {usage_before['credits_remaining']}  "
    f"Tier: {usage_before['tier']}"
)


# ── 1. Health / public stats ───────────────────────────────────
section("1. Public stats (no credits)")
stats = get_public_stats()
print(f"  Odds snapshots:  {stats.get('odds_snapshots', 'n/a')}")
print(f"  Prop snapshots:  {stats.get('prop_snapshots', 'n/a')}")
print(f"  Earliest date:   {stats.get('earliest_date', 'n/a')}")
print(f"  Latest date:     {stats.get('latest_date', 'n/a')}")


# ── 2. All sports – rugby scan ─────────────────────────────────
section("2. All sports — rugby coverage check (FREE)")
all_sports = get_sports(include_inactive=True)
print(f"  Total sports listed: {len(all_sports)}")

rugby_sports = [s for s in all_sports if "rugby" in s.get("key", "").lower()]
print(f"  Rugby sport keys found: {len(rugby_sports)}")
if rugby_sports:
    for s in rugby_sports:
        print(
            f"    key={s['key']}  active={s['active']}  "
            f"group={s.get('group', '')}  title={s.get('title', '')}"
        )
else:
    print("    NONE — ParlayAPI has no rugby sports listed.")

# Check known rugby union key candidates
missing = []
for key in RUGBY_UNION_SPORT_KEYS:
    if not any(s["key"] == key for s in all_sports):
        missing.append(key)
if missing:
    print(f"\n  Rugby union keys tested but absent: {missing}")


# ── 3. NRL events and odds ─────────────────────────────────────
section("3. NRL rugbyleague_nrl — events + odds (FREE + up to 1 credit)")
nrl = next((s for s in all_sports if s["key"] == "rugbyleague_nrl"), None)
if not nrl:
    print("  rugbyleague_nrl not found in sports list.")
else:
    print(f"  NRL active={nrl['active']}")
    events = get_events("rugbyleague_nrl")
    print(f"  Upcoming events: {len(events)}")
    if events:
        e0 = events[0]
        print(f"  Sample: {e0['home_team']} vs {e0['away_team']} @ {e0['commence_time']}")

        # Odds — costs 1 credit
        odds = get_odds("rugbyleague_nrl", regions="au,us", markets="h2h")
        print(f"  Events with odds: {len(odds)}")
        if odds:
            bm_keys = {bm["key"] for ev in odds for bm in ev.get("bookmakers", [])}
            print(f"  Bookmakers seen: {sorted(bm_keys)}")
    else:
        print("  No upcoming events — zero odds data available.")

    scores = get_scores("rugbyleague_nrl", days_from=3)
    print(f"  Recent scores (daysFrom=3): {len(scores)}")


# ── 4. Live widget — is rugby in live feed? ────────────────────
section("4. Live sports widget (FREE, no auth)")
live = get_live_sports()
rugby_live = [s for s in live if "rugby" in s.get("key", "").lower()]
print(f"  Active live sports: {len(live)}")
print(f"  Rugby in live feed: {len(rugby_live)}")
for s in rugby_live:
    print(f"    {s}")


# ── 5. Reference: confirmed working sport (MLB) ────────────────
section("5. MLB reference test — confirms API is working (1 credit)")
try:
    mlb_events = get_events("baseball_mlb")
    print(f"  MLB upcoming events (free): {len(mlb_events)}")

    mlb_odds = get_odds("baseball_mlb", regions="us", markets="h2h")
    print(f"  MLB events with odds (1 credit): {len(mlb_odds)}")
    if mlb_odds:
        e0 = mlb_odds[0]
        bm = e0["bookmakers"][0] if e0.get("bookmakers") else {}
        mkt = bm["markets"][0] if bm.get("markets") else {}
        outcomes = mkt.get("outcomes", [])
        print(f"  Sample: {e0['home_team']} vs {e0['away_team']} @ {bm.get('key', '?')}")
        for o in outcomes:
            prob = american_to_implied(o["price"])
            print(f"    {o['name']}: {format_american(o['price'])} (implied {prob:.1%})")
except urllib.error.HTTPError as exc:
    print(f"  MLB test failed: HTTP {exc.code}")


# ── 6. Summary ─────────────────────────────────────────────────
section("6. Summary")
usage_after = get_usage()
credits_spent = usage_after["credits_used"] - usage_before["credits_used"]
print(f"  Credits spent this run: {credits_spent}")
print(f"  Credits remaining:      {usage_after['credits_remaining']}")
print()
print("  RUGBY VERDICT:")
if rugby_sports:
    if any(ev for ev in (events if nrl else [])):
        print("  ✓ NRL events found — limited but present. Test odds/scores.")
    else:
        print(
            "  ✗ NRL key exists but 0 events returned. "
            "API has no live rugby data at this time."
        )
else:
    print("  ✗ No rugby sport keys at all — not suitable for rugby union.")
print()
print(
    "  RECOMMENDATION: ParlayAPI is best suited for MLB/NBA/NHL/NFL/Soccer/MMA.\n"
    "  Rugby union (Six Nations, Premiership, Top 14, URC, Champions Cup) is\n"
    "  NOT covered. Monitor at start of NRL season (~March) for league rugby."
)
