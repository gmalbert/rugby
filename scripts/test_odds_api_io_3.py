"""
Part 3: Probe plan restrictions and bookmaker filter behavior.
"""
import json
import os
import urllib.request
import urllib.error
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


def get(path: str, params: dict | None = None, method: str = "GET"):
    qs = f"?apiKey={API_KEY}"
    if params:
        for k, v in params.items():
            qs += f"&{k}={v}"
    url = f"{BASE}/{path}{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            hdrs = dict(resp.headers)
            body = json.loads(resp.read())
        return body, hdrs, resp.status
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            body = json.loads(body_bytes)
        except Exception:
            body = {"raw": body_bytes.decode(errors="replace")}
        return body, dict(e.headers), e.code


def section(title):
    print(f"\n{'='*65}\n  {title}\n{'='*65}")


# ── Filter events by bookmaker ───────────────────────────────
section("Events filtered by DraftKings")
data, hdrs, status = get("events", {"sport": "rugby", "bookmaker": "DraftKings", "limit": "10"})
print(f"HTTP {status}  |  rate-limit remaining: {hdrs.get('x-ratelimit-remaining','?')}")
if isinstance(data, list):
    print(f"Events returned: {len(data)}")
    for ev in data[:5]:
        print(f"  {ev.get('home','')} vs {ev.get('away','')}  bms:{ev.get('bookmakerCount',0)}")
else:
    print(f"Response: {data}")


section("Events filtered by Bet365")
data, hdrs, status = get("events", {"sport": "rugby", "bookmaker": "Bet365", "limit": "5"})
print(f"HTTP {status}")
if isinstance(data, list):
    print(f"Events returned: {len(data)}")
    for ev in data[:5]:
        print(f"  {ev.get('home','')} vs {ev.get('away','')}  bms:{ev.get('bookmakerCount',0)}")
else:
    print(f"Response: {data}")


section("Events filtered by Sportsbet.com.au (Australian bookmaker)")
data, hdrs, status = get("events", {"sport": "rugby", "bookmaker": "Sportsbet.com.au", "limit": "5"})
print(f"HTTP {status}")
if isinstance(data, list):
    print(f"Events returned: {len(data)}")
    for ev in data[:5]:
        print(f"  {ev.get('home','')} vs {ev.get('away','')}  bms:{ev.get('bookmakerCount',0)}")
else:
    print(f"Response: {data}")


# ── Try to fetch odds (403 on free tier?) ────────────────────
section("Odds fetch for known event (403 check)")
# Use Hurricanes vs Crusaders from test 2
EVENT_IDS = [65892838, 66349386, 62382510]
for eid in EVENT_IDS:
    data, hdrs, status = get("odds", {"eventId": eid, "bookmakers": "Bet365"})
    print(f"  Event {eid}: HTTP {status}  -> {data}")

# ── Value bets ───────────────────────────────────────────────
section("Value bets endpoint (rugby)")
data, hdrs, status = get("value-bets", {"sport": "rugby"})
print(f"HTTP {status}")
print(f"Response: {str(data)[:300]}")

# ── Account / me endpoint ────────────────────────────────────
section("Account info (get me)")
data, hdrs, status = get("me")
print(f"HTTP {status}")
print(f"Response: {data}")

# ── Selected bookmakers ──────────────────────────────────────
section("Get selected bookmakers")
data, hdrs, status = get("bookmakers/selected")
print(f"HTTP {status}")
print(f"Response: {data}")

print(f"\nFinal rate limit: {hdrs.get('x-ratelimit-remaining','?')} / {hdrs.get('x-ratelimit-limit','?')}")
print("Done.")
