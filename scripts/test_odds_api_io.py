"""
Quick coverage test for odds-api.io — rugby focus.
Run from repo root: python scripts/test_odds_api_io.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

# Load .env manually (avoid requiring python-dotenv for a one-off script)
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("ODDS_API_IO_KEY", "")
BASE = "https://api.odds-api.io/v3"

TARGET_LEAGUES = {
    "six_nations", "premiership", "top14",
    "super-rugby-pacific", "urc", "champions-cup",
}

OUR_LEAGUES = {
    "Six Nations":                    "six_nations",
    "Premiership Rugby":              "premiership",
    "Top 14":                         "top14",
    "Super Rugby Pacific":            "super-rugby-pacific",
    "United Rugby Championship":      "urc",
    "European Champions Cup":         "champions-cup",
}


def get(path: str, params: dict | None = None) -> tuple[any, dict]:
    qs = f"?apiKey={API_KEY}"
    if params:
        for k, v in params.items():
            qs += f"&{k}={v}"
    url = f"{BASE}/{path}{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        headers = dict(resp.headers)
        body = json.loads(resp.read())
    return body, headers


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("="*60)


# ── 1. Sports ────────────────────────────────────────────────
section("1. Available sports (no auth)")
req = urllib.request.Request(f"{BASE}/sports", headers={"Accept": "application/json"})
with urllib.request.urlopen(req, timeout=10) as r:
    sports = json.loads(r.read())

sport_slugs = {s["name"]: s["slug"] for s in sports}
print(f"Total sports: {len(sports)}")
rugby_slug = sport_slugs.get("Rugby")
print(f"Rugby slug: {rugby_slug!r}")
print("All sports:", ", ".join(sorted(sport_slugs.values())))


# ── 2. Rugby leagues ─────────────────────────────────────────
section("2. Rugby leagues (all=true)")
leagues, hdrs = get("leagues", {"sport": rugby_slug, "all": "true"})
print(f"Total rugby leagues returned: {len(leagues)}")
print(f"\nRate limit remaining: {hdrs.get('x-ratelimit-remaining', 'N/A')} / "
      f"{hdrs.get('x-ratelimit-limit', 'N/A')}  (resets {hdrs.get('x-ratelimit-reset', 'N/A')})")

print(f"\n{'Name':<55} {'Slug':<45} Events")
print("-" * 110)
for lg in sorted(leagues, key=lambda x: x.get("eventsCount", 0), reverse=True):
    marker = "  <<<" if any(t in lg["slug"] for t in [
        "six-nations", "premiership", "top-14", "super-rugby", "urc",
        "champions-cup", "six_nations", "top14"
    ]) else ""
    print(f"{lg['name']:<55} {lg['slug']:<45} {lg.get('eventsCount', 0):>5}{marker}")


# ── 3. Active rugby events (all bookmakers) ──────────────────
section("3. Active rugby events (pending + live, limit=20)")
events, _ = get("events", {"sport": rugby_slug, "status": "pending,live", "limit": "20"})
print(f"Events returned: {len(events)}")
if events:
    print(f"\n{'Home':<30} {'Away':<30} {'League':<35} Status   BookmakerCount")
    print("-" * 120)
    for ev in events[:20]:
        print(f"{ev.get('home',''):<30} {ev.get('away',''):<30} "
              f"{ev.get('league',{}).get('name',''):<35} "
              f"{ev.get('status',''):<8} {ev.get('bookmakerCount',0)}")


# ── 4. Odds for first available event ────────────────────────
if events:
    section("4. Sample odds for first event")
    first = events[0]
    print(f"Event: {first['home']} vs {first['away']}  ({first.get('league',{}).get('name','')})")

    # Try DraftKings and BetMGM (free-tier bookmakers)
    FREE_BM = "DraftKings,BetMGM"
    try:
        odds_data, hdrs2 = get("odds", {"eventId": first["id"], "bookmakers": FREE_BM})
        bm = odds_data.get("bookmakers", {})
        if bm:
            for bm_name, markets in bm.items():
                print(f"\n  Bookmaker: {bm_name}")
                for market in markets:
                    print(f"    Market: {market['name']}")
                    for o in market.get("odds", []):
                        print(f"      {o}")
        else:
            print("  No bookmaker odds returned (may not cover this event on free tier)")
        print(f"\nRate limit remaining: {hdrs2.get('x-ratelimit-remaining', 'N/A')}")
    except Exception as exc:
        print(f"  Odds fetch error: {exc}")
else:
    print("  No events to fetch odds for.")


# ── 5. Bookmakers list ───────────────────────────────────────
section("5. All bookmakers")
bm_list, _ = get("bookmakers")
print(f"Total bookmakers: {len(bm_list)}")
active = [b["name"] for b in bm_list if b.get("active")]
print(f"Active: {len(active)}")
print(", ".join(sorted(active)))


# ── 6. League mapping check ──────────────────────────────────
section("6. Our league name → API slug match check")
api_slugs = {lg["slug"] for lg in leagues}
api_names_lower = {lg["name"].lower(): lg["slug"] for lg in leagues}
for our_name, our_slug in OUR_LEAGUES.items():
    found_slug = None
    # exact slug match
    for lg in leagues:
        if our_slug.replace("_", "-") in lg["slug"] or our_name.lower() in lg["name"].lower():
            found_slug = lg["slug"]
            break
    status = "FOUND" if found_slug else "NOT FOUND"
    print(f"  [{status:9s}] {our_name:<35} -> {found_slug or '???'}")

print("\nDone.")
