"""
Part 4: Test DraftKings + BetMGM BR odds for rugby events.
"""
import json
import os
import urllib.request
import urllib.error
import urllib.parse
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


def get(path, params=None):
    base_params = {"apiKey": API_KEY}
    if params:
        base_params.update(params)
    qs = "?" + urllib.parse.urlencode(base_params)
    req = urllib.request.Request(
        f"{BASE}/{path}{qs}", headers={"Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            hdrs = dict(resp.headers)
            body = json.loads(resp.read())
        return body, hdrs, 200
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        return body, dict(e.headers), e.code


def section(title):
    print(f"\n{'='*65}\n  {title}\n{'='*65}")


# ── Get rugby events and fetch odds with DraftKings + BetMGM BR
section("Odds with allowed bookmakers: DraftKings,BetMGM BR")
evs, _, _ = get("events", {"sport": "rugby", "status": "pending", "limit": "50"})

hits = 0
for ev in evs:
    data, hdrs, status = get("odds", {"eventId": ev["id"],
                                       "bookmakers": "DraftKings,BetMGM BR"})
    bm = data.get("bookmakers", {}) if isinstance(data, dict) else {}
    if bm:
        hits += 1
        print(f"\n  {ev['home']} vs {ev['away']}  ({ev.get('league',{}).get('name','')})")
        for bname, mkts in bm.items():
            for m in mkts:
                print(f"    {bname} | {m['name']} -> {m.get('odds', [])}")
        if hits >= 5:
            break
    else:
        pass  # no coverage

if hits == 0:
    print("  -> DraftKings and BetMGM BR have NO rugby odds coverage.")
    print("     Both are US-centric bookmakers that don't offer rugby markets.")

rl = hdrs.get("x-ratelimit-remaining", "?")
print(f"\nRate limit remaining: {rl}")

# ── Compare: Check American Football with DraftKings ────────
section("Control check: American Football with DraftKings (should have coverage)")
af_evs, _, _ = get("events", {"sport": "american-football", "status": "pending", "limit": "5"})
print(f"American football pending events: {len(af_evs)}")
for ev in af_evs[:3]:
    print(f"  [{ev['id']}] {ev.get('home','')} vs {ev.get('away','')}  "
          f"({ev.get('league',{}).get('name','')})  bms:{ev.get('bookmakerCount',0)}")

if af_evs:
    data, hdrs, status = get("odds", {"eventId": af_evs[0]["id"],
                                       "bookmakers": "DraftKings,BetMGM BR"})
    bm = data.get("bookmakers", {}) if isinstance(data, dict) else {}
    if bm:
        print("\n  DraftKings/BetMGM BR DO cover American Football:")
        for bname, mkts in list(bm.items())[:2]:
            for m in mkts[:2]:
                print(f"    {bname} | {m['name']} -> {m.get('odds', [])}")
    else:
        print(f"  No odds for American Football either. HTTP {status}: {data}")

print(f"\nFinal rate limit: {hdrs.get('x-ratelimit-remaining','?')} / {hdrs.get('x-ratelimit-limit','?')}")
print("Done.")
