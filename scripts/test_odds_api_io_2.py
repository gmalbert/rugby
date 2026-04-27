"""
Part 2: Deep coverage test for odds-api.io - bookmaker odds for rugby events.
"""
import json
import os
import urllib.request
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("ODDS_API_IO_KEY", "")
BASE = "https://api.odds-api.io/v3"


def get(path: str, params: dict | None = None):
    qs = f"?apiKey={API_KEY}"
    if params:
        for k, v in params.items():
            qs += f"&{k}={v}"
    req = urllib.request.Request(
        f"{BASE}/{path}{qs}", headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        hdrs = dict(resp.headers)
        body = json.loads(resp.read())
    return body, hdrs


def section(title):
    print(f"\n{'='*65}\n  {title}\n{'='*65}")


# ── English Premiership events ───────────────────────────────
section("English Premiership events")
evs, h = get("events", {"sport": "rugby", "league": "rugby-union-english-premiership",
                         "status": "pending,live", "limit": "10"})
print(f"Count: {len(evs)}")
for ev in evs:
    print(f"  [{ev['id']}] {ev['home']} vs {ev['away']}  "
          f"bms:{ev.get('bookmakerCount', 0)}  date:{ev['date'][:10]}")
print(f"\nRate limit: {h.get('x-ratelimit-remaining','?')} / {h.get('x-ratelimit-limit','?')}")

# ── All pending events sorted by bookmakerCount ──────────────
section("Top pending events by bookmaker coverage")
all_evs, _ = get("events", {"sport": "rugby", "status": "pending", "limit": "100"})
best = sorted(all_evs, key=lambda x: x.get("bookmakerCount", 0), reverse=True)[:10]
for ev in best:
    print(f"  [{ev['id']}] {ev['home']} vs {ev['away']}  "
          f"({ev.get('league',{}).get('name','')})  bms:{ev.get('bookmakerCount',0)}")

# ── Try fetching odds for the best-covered event ─────────────
if best and best[0].get("bookmakerCount", 0) > 0:
    ev = best[0]
    section(f"Odds for event {ev['id']} ({ev['home']} vs {ev['away']})")
    # Try popular international bookmakers first
    BM_GROUPS = [
        "DraftKings,BetMGM",
        "Bet365,Unibet,William Hill",
        "Sportsbet.com.au,TABtouch AU",
        "Betway,BetWinner",
    ]
    for bm_str in BM_GROUPS:
        try:
            od, h2 = get("odds", {"eventId": ev["id"], "bookmakers": bm_str})
            bm = od.get("bookmakers", {})
            if bm:
                print(f"\nBookmakers requested: {bm_str}")
                for bname, mkts in bm.items():
                    for m in mkts:
                        print(f"  {bname} | {m['name']} -> {m.get('odds', [])}")
            else:
                print(f"  No odds returned for bookmakers: {bm_str}")
            print(f"  Rate limit: {h2.get('x-ratelimit-remaining','?')}")
        except Exception as e:
            print(f"  Error for {bm_str}: {e}")
else:
    section("NOTE: All pending rugby events have 0 bookmakers")
    print("  DraftKings and BetMGM likely do not cover rugby markets.")
    print("  Checking football (soccer) as comparison:")
    fb_evs, _ = get("events", {"sport": "football", "status": "pending", "limit": "5"})
    for ev in fb_evs:
        print(f"  [{ev['id']}] {ev['home']} vs {ev['away']}  bms:{ev.get('bookmakerCount', 0)}")

print("\nDone.")
