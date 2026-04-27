# ParlayAPI Integration Reference

**API version:** 3.2.0  
**Docs:** https://parlay-api.com/docs  
**OpenAPI spec:** https://parlay-api.com/openapi.json  
**Tested:** April 27, 2026

---

## Overview

ParlayAPI aggregates real-time sports odds from **15 sources**, updated every 60–90 seconds.

| Dimension | Details |
|---|---|
| Sports | 66 total: MLB, NFL, NBA, NHL, MMA/UFC, Boxing, Tennis, Golf, Cricket, NRL rugby league, 51 soccer leagues |
| Sportsbooks | DraftKings, FanDuel, Caesars, Bovada, Pinnacle, Fliff |
| DFS/Props | PrizePicks, Underdog Fantasy, Betr, Pick6, Sleeper |
| Exchanges | Novig (bid/ask + volume), ProphetX |
| Historical archive | 1M+ odds records, 2005–present |

---

## Authentication

Pass the key as a header (preferred) or query parameter:

```http
X-API-Key: <your_key>
# OR
GET /v1/sports/baseball_mlb/odds?apiKey=<your_key>
```

**Critical:** Cloudflare blocks Python's default `urllib` user-agent with `403 Error 1010`. Always set a browser-like `User-Agent`:

```python
headers = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "X-API-Key": os.environ["PARLAY_API_KEY"],
}
```

**Environment variable:** `PARLAY_API_KEY`

---

## Credit Costs

| Endpoint | Credits |
|---|---|
| `GET /v1/sports` | **FREE** |
| `GET /v1/sports/{sport_key}/events` | **FREE** |
| `GET /v1/sports/{sport_key}/props/markets` | **FREE** |
| `GET /live/api/sports` | **FREE** (no auth) |
| `GET /v1/stats` | **FREE** (no auth) |
| `GET /v1/usage` | **FREE** |
| `GET /health` | **FREE** |
| `GET /v1/sports/{sport_key}/participants` | 1 |
| `GET /v1/prediction-markets/{sport_key}` | 1 |
| `GET /v1/sports/{sport_key}/scores` | 1–2 |
| `GET /v1/sports/{sport_key}/odds` | **markets × regions** (same formula as the-odds-api) |
| `GET /v1/sports/{sport_key}/events/{event_id}/odds` | markets × regions |
| `GET /v1/sports/{sport_key}/events/canonical` | 2 |
| `GET /v1/sports/{sport_key}/line-movement` | 2 |
| `GET /v1/sports/{sport_key}/props` | 3 |
| `GET /v1/sports/{sport_key}/live` | 3 |
| `GET /v1/exchange/{sport_key}/markets` | 3 |
| `GET /v1/sports/{sport_key}/consensus` | 3 |
| `GET /v1/sports/{sport_key}/futures` | 5 |
| `GET /v1/sports/{sport_key}/closing-lines` | 5 |
| `GET /v1/sports/{sport_key}/compare` | 5 |
| `GET /v1/inplay/arbs` | 5 |
| `GET /v1/sports/{sport_key}/arbitrage` | 10 |
| `GET /v1/sports/{sport_key}/ev` | 10 |
| `GET /v1/historical/sports/{sport_key}/odds` | 10 × markets × regions |
| `GET /v1/historical/sports/{sport_key}/closing-odds` | 10 |

**Free tier:** 1,000 credits/month. Check remaining credits:

```
GET /v1/usage
→ {credits_used, credits_remaining, credits_total, tier, period_start, period_end}
```

---

## All 66 Sport Keys

| Key | Group |
|---|---|
| `baseball_mlb` | Baseball |
| `americanfootball_nfl` | American Football |
| `americanfootball_ncaaf` | American Football |
| `basketball_nba` | Basketball |
| `basketball_ncaab` | Basketball |
| `basketball_euroleague` | Basketball |
| `icehockey_nhl` | Ice Hockey |
| `mma_mixed_martial_arts` | MMA |
| `boxing_boxing` | Boxing |
| `tennis_atp_french_open` | Tennis |
| `tennis_wta_french_open` | Tennis |
| `golf_pga_championship` | Golf |
| `cricket_ipl` | Cricket |
| `cricket_test_match` | Cricket |
| `rugbyleague_nrl` | Rugby League |
| `soccer_argentina_primera_division` | Soccer |
| `soccer_australia_aleague` | Soccer |
| `soccer_austria_bundesliga` | Soccer |
| `soccer_austria_2_liga` | Soccer |
| `soccer_belgium_first_div` | Soccer |
| `soccer_brazil_campeonato` | Soccer |
| `soccer_brazil_serie_b` | Soccer |
| `soccer_bulgaria_first_league` | Soccer |
| `soccer_chile_campeonato` | Soccer |
| `soccer_china_superleague` | Soccer |
| `soccer_colombia_primera_a` | Soccer |
| `soccer_costa_rica_primera_division` | Soccer |
| `soccer_croatia_prva_liga` | Soccer |
| `soccer_czech_football_league` | Soccer |
| `soccer_denmark_superliga` | Soccer |
| `soccer_ecuador_liga_pro` | Soccer |
| `soccer_england_championship` | Soccer |
| `soccer_england_league1` | Soccer |
| `soccer_england_league2` | Soccer |
| `soccer_epl` | Soccer |
| `soccer_finland_veikkausliiga` | Soccer |
| `soccer_france_ligue_one` | Soccer |
| `soccer_france_ligue_two` | Soccer |
| `soccer_germany_bundesliga` | Soccer |
| `soccer_germany_bundesliga2` | Soccer |
| `soccer_greece_super_league` | Soccer |
| `soccer_hungary_nb1` | Soccer |
| `soccer_ireland_premier_division` | Soccer |
| `soccer_italy_serie_a` | Soccer |
| `soccer_italy_serie_b` | Soccer |
| `soccer_japan_j_league` | Soccer |
| `soccer_japan_j2_league` | Soccer |
| `soccer_mexico_ligamx` | Soccer |
| `soccer_netherlands_eredivisie` | Soccer |
| `soccer_netherlands_eerste_divisie` | Soccer |
| `soccer_norway_eliteserien` | Soccer |
| `soccer_paraguay_primera_division` | Soccer |
| `soccer_poland_ekstraklasa` | Soccer |
| `soccer_portugal_primeira_liga` | Soccer |
| `soccer_romania_superliga` | Soccer |
| `soccer_saudi_professional_league` | Soccer |
| `soccer_scotland_championship` | Soccer |
| `soccer_scotland_premiership` | Soccer |
| `soccer_serbia_super_liga` | Soccer |
| `soccer_south_korea_kleague1` | Soccer |
| `soccer_spain_la_liga` | Soccer |
| `soccer_spain_segunda_division` | Soccer |
| `soccer_sweden_allsvenskan` | Soccer |
| `soccer_switzerland_superleague` | Soccer |
| `soccer_turkey_super_league` | Soccer |
| `soccer_ukraine_premier_league` | Soccer |

---

## Rugby Coverage Assessment

> **Tested April 27, 2026 — using this repo as the test subject.**

### Result: Not suitable for rugby union

| League | Key | Status |
|---|---|---|
| Six Nations | — | **Not listed** |
| Premiership Rugby | — | **Not listed** |
| Top 14 | — | **Not listed** |
| Super Rugby Pacific | — | **Not listed** |
| United Rugby Championship (URC) | — | **Not listed** |
| European Champions Cup | — | **Not listed** |
| NRL (Rugby League) | `rugbyleague_nrl` | Listed and active, but **0 events/scores returned** in testing |

The API currently covers only one rugby variant (`rugbyleague_nrl`) and has no data flowing for it. Rugby union (the sport this repo targets) has no coverage whatsoever. **Do not use ParlayAPI as a rugby odds source at this time.** Re-test at the start of each NRL season (typically March) to check if live data populates.

---

## Response Schema

### Events endpoint (free)

```json
{
  "id": "9a1aa99e19f3300e50c67efb7913b140",
  "canonical_event_id": "b98e3e59ff85b15f",
  "sport_key": "baseball_mlb",
  "sport_title": "MLB",
  "commence_time": "2026-04-27T19:00:00Z",
  "home_team": "Chicago White Sox",
  "away_team": "Los Angeles Angels"
}
```

### Odds endpoint

```json
{
  "id": "...",
  "canonical_event_id": "...",
  "sport_key": "baseball_mlb",
  "sport_title": "MLB",
  "commence_time": "2026-04-27T19:00:00Z",
  "home_team": "Arizona Diamondbacks",
  "away_team": "San Diego Padres",
  "bookmakers": [
    {
      "key": "draftkings",
      "title": "DraftKings",
      "last_update": "2026-04-27T04:40:18Z",
      "markets": [
        {
          "key": "h2h",
          "last_update": "2026-04-27T04:40:18Z",
          "outcomes": [
            {"name": "Arizona Diamondbacks", "price": 113},
            {"name": "San Diego Padres",     "price": -136}
          ]
        }
      ]
    }
  ]
}
```

`price` is in **American odds** when `oddsFormat=american` (default for most endpoints). Use `oddsFormat=decimal` or `oddsFormat=european` for other formats.

---

## Odds Parameters Reference

### `regions`
Controls which bookmakers are returned. Comma-separated.

| Region | Bookmakers |
|---|---|
| `us` | DraftKings, FanDuel, BetMGM, Caesars, Bovada |
| `us2` | Additional US regional books |
| `eu` | **Pinnacle**, Bet365, and European sportsbooks |
| `uk` | UK-licensed books |
| `au` | Australian sportsbooks (TAB, Sportsbet, etc.) |

Use `eu` for Pinnacle (the sharp book used as CLV baseline).

### `markets`
| Key | Description |
|---|---|
| `h2h` | Moneyline / 3-way (draw included for soccer) |
| `spreads` | Point spread / handicap |
| `totals` | Over/under total |

### Prop market keys (sport-dependent)
`player_points`, `player_rebounds`, `player_assists`, `player_three_pointers`, `player_strikeouts`, `player_hits`, `player_home_runs`, `player_total_bases`, `player_runs`, `player_rbis`, `player_goals`, `player_shots_on_goal`, `player_pts_rebs_asts` — and 50+ more. Use `list_prop_markets(sport_key)` (FREE) to enumerate available keys for a given sport.

---

## Reusable Python Client

The full client is at `utils/parlay_api.py`. It handles:
- Browser `User-Agent` to bypass Cloudflare
- `X-API-Key` header auth
- Consistent `(body, headers, status)` return from the internal helper
- Graceful empty-list/dict fallbacks

### Quick-start pattern for a new sport repo

```python
import os
from pathlib import Path
from utils.parlay_api import get_events, get_odds, get_usage

# Load .env if needed
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

SPORT = "soccer_epl"

# Free: list upcoming matches
events = get_events(SPORT)
print(f"{len(events)} upcoming events")

# 1 credit: moneyline odds from US books
odds = get_odds(SPORT, regions="us", markets="h2h")
for ev in odds:
    for bm in ev["bookmakers"]:
        for mkt in bm["markets"]:
            if mkt["key"] == "h2h":
                prices = {o["name"]: o["price"] for o in mkt["outcomes"]}
                print(ev["home_team"], "vs", ev["away_team"], "|", bm["key"], prices)

# Check credits remaining
usage = get_usage()
print(f"Credits remaining: {usage['credits_remaining']} / {usage['credits_total']}")
```

### Credit-efficient pattern: batch multiple markets in one call

```python
# 2 credits instead of 1+1 for separate calls
odds = get_odds(SPORT, regions="us", markets="h2h,spreads")

# 3 credits for us+eu in one call (Pinnacle + DK/FD side by side)
odds = get_odds(SPORT, regions="us,eu", markets="h2h")
```

### +EV finder (10 credits)

```python
from utils.parlay_api import find_ev

edges = find_ev("soccer_epl", sharp_book="pinnacle", min_edge=3.0)
for edge in edges:
    print(edge)
```

### Arbitrage scanner (10 credits)

```python
from utils.parlay_api import find_arbitrage

arbs = find_arbitrage("basketball_nba", min_profit=1.0)
for arb in arbs:
    print(arb)
```

---

## Credit Budget Guide (1,000/month free tier)

Assuming daily pipeline runs (30×/month):

| Use Case | Call | Cost/run | Monthly |
|---|---|---|---|
| Check coverage | `get_sports()` | 0 | 0 |
| Upcoming events | `get_events(sport)` | 0 | 0 |
| Daily moneylines | `get_odds(regions="us", markets="h2h")` | 1 | 30 |
| Daily moneylines + spreads | `get_odds(regions="us", markets="h2h,spreads")` | 2 | 60 |
| Add Pinnacle region | `get_odds(regions="us,eu", markets="h2h")` | 2 | 60 |
| Props snapshot | `get_props(sport)` | 3 | 90 |
| Line movement (1 event) | `get_line_movement(sport, event_id)` | 2 | 60 |
| +EV scan | `find_ev(sport)` | 10 | 300 |
| Closing lines | `get_closing_lines(sport)` | 5 | 150 |

A typical daily pipeline (events free + h2h odds + Pinnacle) uses **~60 credits/month**, leaving ~940 for ad-hoc queries.

---

## Best Sports for This API

Strongest coverage (live data confirmed April 2026):

1. **MLB** — 28 events with DraftKings odds observed live
2. **NBA** — 24 active events in live widget
3. **NHL** — 21 active events
4. **Soccer (EPL, La Liga, Bundesliga, Serie A, Ligue 1)** — confirmed live
5. **MMA/UFC** — 44 active events
6. **NFL** — active (off-season events present)

Moderate coverage (listed, not tested):
- Tennis, Golf, Cricket (IPL, Test Match), Boxing, Basketball EuroLeague/NCAAB
- 51 additional soccer leagues

Weak/no coverage (as of April 2026):
- **Rugby union** (no sport keys exist)
- NRL rugby league (key exists, 0 events returned)

---

## Deployment Checklist for a New Repo

- [ ] Add `PARLAY_API_KEY=<key>` to `.env` (never commit)
- [ ] Copy `utils/parlay_api.py` into the repo's `utils/` directory
- [ ] Call `get_sports(include_inactive=True)` first run to confirm your sport is listed
- [ ] Call `get_usage()` before heavy pipeline runs to verify remaining credits
- [ ] Use `X-API-Key` header — avoid `apiKey=` in URL (leaks key to server logs)
- [ ] Set `oddsFormat=american` explicitly; default is `decimal` on some endpoints
- [ ] For soccer: use `regions=eu` to include Pinnacle for CLV analysis
- [ ] Wrap all calls in try/except for `urllib.error.HTTPError` — the API returns structured JSON error bodies on 4xx
