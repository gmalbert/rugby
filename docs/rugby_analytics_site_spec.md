# Rugby Betting & Analytics Site — Full Specification

> **Stack:** Python · Streamlit · CSV / Parquet · GitHub Actions  
> **Coverage:** Six Nations · Premiership Rugby · Top 14 · Super Rugby Pacific · United Rugby Championship · European Champions Cup  
> **Sportsbook Target:** DraftKings (primary)

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Data Sources & Scraping Pipeline](#2-data-sources--scraping-pipeline)
3. [Database Schema](#3-database-schema)
4. [Pages & Features](#4-pages--features)
5. [Models & Analytics](#5-models--analytics)
6. [DraftKings Integration](#6-draftkings-integration)
7. [Deployment & Scheduling](#7-deployment--scheduling)
8. [Rollout Phases](#8-rollout-phases)
9. [Risk & Caveats](#9-risk--caveats)

---

## 1. Project Structure

```
rugby-analytics/
├── predictions.py                        # Home / dashboard entry point
├── pages/
│   ├── 1_League_Overview.py
│   ├── 2_Team_Deep_Dive.py
│   ├── 3_Player_Stats.py
│   ├── 4_Match_Analysis.py
│   ├── 5_Betting_Edge.py
│   └── 6_Model_Lab.py
├── data/
│   ├── scrapers/
│   │   ├── espn_api.py           # ESPN hidden API ETL
│   │   ├── rugbypass.py          # RugbyPass JSON scraper
│   │   ├── worldrugby.py         # World Rugby fixtures/results
│   │   └── sofascore.py          # Live scores feed
│   ├── pipeline.py               # Orchestrates all scrapers → files
│   ├── csv/                      # Lightweight CSV snapshots (fixtures, odds)
│   │   ├── leagues.csv
│   │   ├── teams.csv
│   │   ├── matches.csv
│   │   └── odds_snapshots.csv
│   └── parquet/                  # Columnar Parquet for analytics
│       ├── player_match_stats.parquet
│       ├── team_season_stats.parquet
│       └── elo_ratings.parquet
├── models/
│   ├── elo.py                    # Elo rating system
│   ├── dixon_coles.py            # Score prediction model
│   ├── try_scorer.py             # Player prop model
│   └── value_finder.py           # Edge vs DK odds
├── utils/
│   ├── cache.py                  # st.cache_data wrappers
│   ├── odds.py                   # Odds format converters
│   └── charts.py                 # Reusable Altair/Plotly charts
├── .github/
│   └── workflows/
│       └── scrape.yml            # Nightly data refresh
├── requirements.txt
└── README.md
```

---

## 2. Data Sources & Scraping Pipeline

### Primary Sources

| Source | Method | Data Type | Leagues Covered | Freshness |
|---|---|---|---|---|
| **ESPN Hidden API** | Undocumented REST (JSON) | Match stats, player stats, standings, lineups | All 6 | Post-match (~1hr delay) |
| **RugbyPass** | JSON embedded in pages | Standings, fixtures, team stats, form | All 6 | Near real-time |
| **World Rugby** | HTML scrape / JSON feed | International fixtures, scorers, lineups | Six Nations, ECC | Near real-time |
| **SofaScore** | Reverse-engineered API | Live scores, match timelines, basic player stats | All 6 | Live |
| **ESPN StatsGuru** | HTML scrape (BeautifulSoup) | Deep historical player/team records | Internationals | Historical only |

### ESPN Hidden API — Key Endpoints

```python
BASE = "https://site.web.api.espn.com/apis/v2/sports/rugby"

# Leagues (use ESPN league IDs)
LEAGUE_IDS = {
    "six_nations":    "180659",
    "premiership":    "267979",
    "top14":          "270557",
    "super_rugby":    "242041",
    "urc":            "270559",
    "champions_cup":  "271937",
}

# Endpoints
/league/{id}/standings
/league/{id}/scoreboard          # fixtures + live scores
/league/{id}/teams
/event/{event_id}/summary        # full match stats + lineups
/athletes/{player_id}/stats
```

### RugbyPass — JSON Extraction

RugbyPass embeds structured JSON directly in its HTML responses (no JS rendering needed for most pages). Key pages:

```
https://www.rugbypass.com/{league}/standings/    → standings JSON in <script>
https://www.rugbypass.com/{league}/stats/        → team stats JSON
https://www.rugbypass.com/{league}/fixtures-results/ → fixtures/results
```

Extract with:
```python
import requests
from bs4 import BeautifulSoup
import json, re

resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(resp.text, "html.parser")
# RugbyPass inlines JSON in __NEXT_DATA__ script tag
raw = soup.find("script", {"id": "__NEXT_DATA__"}).string
data = json.loads(raw)
```

### SofaScore — Live Feed

SofaScore's internal API returns clean JSON and is widely reverse-engineered:

```python
BASE = "https://api.sofascore.com/api/v1"

/sport/rugby-union/scheduled-events/{date}   # fixtures by date
/event/{id}/statistics                        # match stats
/event/{id}/lineups                           # lineups
/team/{id}/performance                        # team form
```

### Scheduling — GitHub Actions Nightly Scrape

```yaml
# .github/workflows/scrape.yml
name: Nightly Data Refresh
on:
  schedule:
    - cron: "0 3 * * *"   # 3am UTC daily
  workflow_dispatch:        # manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python data/pipeline.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
```

---

## 3. Data Schema

### File Layout

Small, frequently-updated reference tables are stored as **CSV** (human-readable, easy to diff in Git). Large, analytics-heavy tables are stored as **Parquet** (columnar, fast reads, ~10× smaller than CSV).

```
data/
  csv/
    leagues.csv              # ~10 rows — hand-editable
    teams.csv                # ~150 rows
    matches.csv              # current-season fixtures + results
    odds_snapshots.csv       # rolling 14-day odds window
  parquet/
    player_match_stats.parquet   # all historical player rows
    team_season_stats.parquet    # aggregated per team/season
    elo_ratings.parquet          # full Elo history
```

### CSV Schemas

#### `leagues.csv`
| column | type | notes |
|--------|------|-------|
| id | str | e.g. `"premiership"` |
| name | str | |
| espn_id | str | |
| season | int | |

#### `teams.csv`
| column | type | notes |
|--------|------|-------|
| id | str | |
| league_id | str | FK → leagues.id |
| name | str | |
| short_name | str | |
| logo_url | str | |

#### `matches.csv`
| column | type | notes |
|--------|------|-------|
| id | str | |
| league_id | str | FK → leagues.id |
| home_team_id | str | FK → teams.id |
| away_team_id | str | FK → teams.id |
| kickoff_utc | datetime | ISO 8601 |
| home_score | int | |
| away_score | int | |
| home_tries | int | |
| away_tries | int | |
| status | str | `scheduled` \| `live` \| `final` |
| venue | str | |
| round | int | |

#### `odds_snapshots.csv`
| column | type | notes |
|--------|------|-------|
| match_id | str | FK → matches.id |
| scraped_at | datetime | ISO 8601 |
| home_ml | float | moneyline American odds |
| away_ml | float | |
| spread_home | float | handicap line |
| spread_home_odds | float | |
| total_line | float | |
| total_over_odds | float | |
| total_under_odds | float | |

### Parquet Schemas

#### `player_match_stats.parquet`
| column | type |
|--------|------|
| id | str |
| match_id | str |
| player_id | str |
| team_id | str |
| player_name | str |
| position | str |
| tries | int |
| assists | int |
| carries | int |
| metres_run | int |
| tackles | int |
| missed_tackles | int |
| linebreaks | int |
| minutes_played | int |

#### `team_season_stats.parquet`
| column | type |
|--------|------|
| team_id | str |
| league_id | str |
| season | int |
| played | int |
| won | int |
| lost | int |
| drawn | int |
| points_for | int |
| points_against | int |
| tries_for | int |
| tries_against | int |
| bonus_points | int |
| league_points | int |

#### `elo_ratings.parquet`
| column | type |
|--------|------|
| team_id | str |
| league_id | str |
| date | date |
| rating | float |

### Reading Data

```python
import pandas as pd

# CSV (reference tables)
leagues  = pd.read_csv("data/csv/leagues.csv")
teams    = pd.read_csv("data/csv/teams.csv")
matches  = pd.read_csv("data/csv/matches.csv", parse_dates=["kickoff_utc"])
odds     = pd.read_csv("data/csv/odds_snapshots.csv", parse_dates=["scraped_at"])

# Parquet (analytics tables)
player_stats    = pd.read_parquet("data/parquet/player_match_stats.parquet")
team_stats      = pd.read_parquet("data/parquet/team_season_stats.parquet")
elo             = pd.read_parquet("data/parquet/elo_ratings.parquet")
```

### Writing Data (pipeline.py)

```python
import pandas as pd

def save_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)

def append_parquet(new_rows: pd.DataFrame, path: str):
    """Merge new rows into existing Parquet file, deduplicating on primary key."""
    try:
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, new_rows]).drop_duplicates(
            subset=["id"], keep="last"
        )
    except FileNotFoundError:
        combined = new_rows
    combined.to_parquet(path, index=False)
```

---

## 4. Pages & Features

### `predictions.py` — Home Dashboard

**Purpose:** At-a-glance view of the rugby betting week.

**Features:**
- **This Week's Fixtures** — all 6 leagues, grouped by day, with kickoff times (local + UTC)
- **Live Match Ticker** — SofaScore feed showing in-progress matches with score + minute
- **Current Odds Snapshot** — DraftKings lines for next 7 days of fixtures (moneyline + spread)
- **Form Heatmap** — last 5 results for every team currently with an upcoming fixture (W/L/D color coded)
- **Try Scorer Leaderboard** — top 10 try scorers across all 6 leagues this season
- **League Selector Sidebar** — filter entire dashboard to one or more leagues

```python
# Key Streamlit components
st.set_page_config(layout="wide")
league_filter = st.sidebar.multiselect("Leagues", LEAGUES, default=LEAGUES)
col1, col2, col3 = st.columns([2, 1, 1])
# col1: fixtures table
# col2: live ticker
# col3: try scorer board
```

---

### `pages/1_League_Overview.py`

**Purpose:** Full season view for one selected league.

**Features:**
- League selector (dropdown)
- **Standings Table** — full table with P/W/L/D, points for/against, tries, bonus points, +/- form arrow
- **Points Per Game vs Tries Per Game scatter** — team efficiency quadrant chart
- **Home vs Away Performance** split bar chart
- **Round-by-Round Results Grid** — heatmap of scores across all rounds
- **Upcoming Fixtures** table with DraftKings odds inline
- **Season narrative** — auto-generated text ("Toulouse are 3 pts clear at the top, averaging 4.2 tries per game")

---

### `pages/2_Team_Deep_Dive.py`

**Purpose:** Everything about one team, across leagues if applicable (e.g. a club in both Premiership and ECC).

**Features:**
- Team selector (search by name)
- **Form Strip** — last 10 results as colored badges (W/L/D + score + opponent)
- **Attack vs Defence Radar Chart** — tries scored, tries conceded, metres made, linebreaks, turnovers won
- **Rolling Elo Rating Chart** — team strength over the season with match annotations
- **Scoring Breakdown** — tries vs penalties vs conversions vs drops (stacked bar)
- **Key Players** — top 5 performers by tries, metres, tackles this season
- **Head-to-Head Record** — vs any selected opponent, last 5 years
- **Venue Stats** — home/away split for points, tries, win %

---

### `pages/3_Player_Stats.py`

**Purpose:** Player-level analysis — the critical page for DraftKings try scorer props.

**Features:**
- **Try Scorer Rankings** by league — sortable table: player, team, tries, games, tries/game, last 3 games
- **Player Profile** — click any player:
  - Try scoring by round (bar chart)
  - Position heatmap on pitch (where they score from)
  - Minutes played trend
  - Opposition faced (try vs strong/weak defence)
- **Prop Bet Analyzer** — enter a DraftKings try scorer line (e.g. "Antoine Dupont anytime try scorer +150"), compare vs model probability
- **Consistency Score** — how reliable is this player at scoring (% of games with a try)
- **Injury/Availability Flag** — manual update field (v1) or scraped from team news (v2)

---

### `pages/4_Match_Analysis.py`

**Purpose:** Deep pre-match breakdown for a specific upcoming fixture.

**Features:**
- Fixture selector (filtered to upcoming matches in next 14 days)
- **Match Preview Card** — teams, venue, kickoff, referee, round
- **Last 5 Meetings** — H2H results table with scores
- **Current Form** — last 5 for each team side by side
- **Key Stats Comparison** — 10-metric horizontal bar comparison (tries/game, points/game, linebreaks, turnovers, scrum win %, lineout win %, etc.)
- **Predicted Score** — Dixon-Coles model output: most likely scoreline, win probabilities, expected tries
- **Predicted Try Scorers** — model's top 5 most likely anytime try scorers for each team with estimated probability
- **DraftKings Odds vs Model** — table showing where model disagrees with the market (edge column)
- **Weather Widget** — venue weather at kickoff (OpenWeatherMap API, free tier)

---

### `pages/5_Betting_Edge.py`

**Purpose:** The core value-add page — surfaces model-identified edges vs DraftKings lines.

**Features:**
- **Value Bets Table** — all upcoming fixtures where model probability diverges from DK implied probability by >5%
  - Columns: Match | Market | DK Odds | DK Implied % | Model % | Edge | Confidence
  - Color coded: green = back, red = lay (informational)
- **Try Scorer Value** — player props where model probability > DK implied probability
- **Totals Analysis** — over/under lines vs model's expected total points distribution
- **Parlay Builder** (informational) — combine value picks into a hypothetical same-game parlay, show combined probability vs DK parlay odds
- **Historical Edge Tracking** — past model picks vs outcomes: ROI chart, strike rate, by market type
- **Disclaimer banner** — responsible gambling notice, clearly informational not financial advice

---

### `pages/6_Model_Lab.py`

**Purpose:** Transparent, interactive view of the underlying models.

**Features:**
- **Elo Leaderboard** — all teams ranked by current Elo across all leagues, with trend arrow
- **Dixon-Coles Parameters** — attack/defence ratings table per team (editable for "what-if" scenarios)
- **Model Backtesting** — select a league + date range, see model accuracy: Brier score, calibration curve, % correct winner
- **Manual Override** — adjust team strength for injury news, home advantage etc. and see updated predictions
- **Simulation Tool** — run 10,000 Monte Carlo simulations for a match, show full scoreline distribution histogram

---

## 5. Models & Analytics

### 5.1 Elo Rating System

Simple, interpretable, and continuously updated. Ideal for match outcome probabilities.

```python
K = 32          # sensitivity (higher = faster adaptation)
HOME_ADV = 50   # Elo points added for home team

def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def update_elo(rating_a, rating_b, result_a, home=True):
    """result_a: 1=win, 0.5=draw, 0=loss"""
    ra = rating_a + (HOME_ADV if home else 0)
    exp = expected_score(ra, rating_b)
    new_a = rating_a + K * (result_a - exp)
    new_b = rating_b + K * ((1 - result_a) - (1 - exp))
    return new_a, new_b
```

**Outputs:** Win probability per match, team strength rankings, league-normalised ratings

**Enhancement:** Use margin-of-victory weighted Elo (common in rugby analytics) — a 30-point win moves the needle more than a 1-point win.

---

### 5.2 Dixon-Coles Score Prediction Model

Predicts the full scoreline distribution, enabling totals and handicap analysis.

**How it works:**
- Estimates attack (λ) and defence (μ) parameters per team using Poisson regression on historical points-scored data
- Includes a low-score correction factor (Dixon-Coles correction) for more accurate 0–0, 1–0 type scorelines
- Outputs: P(home wins), P(away wins), P(draw), expected total, most likely scoreline

```python
from scipy.optimize import minimize
from scipy.stats import poisson
import numpy as np

def expected_goals(attack_h, defence_h, attack_a, defence_a, home_adv):
    mu_home = np.exp(attack_h - defence_a + home_adv)
    mu_away = np.exp(attack_a - defence_h)
    return mu_home, mu_away

def scoreline_matrix(mu_home, mu_away, max_score=80):
    """Returns NxN matrix of scoreline probabilities"""
    return np.outer(
        [poisson.pmf(i, mu_home) for i in range(max_score)],
        [poisson.pmf(j, mu_away) for j in range(max_score)]
    )
```

> Note: Rugby scores aren't strictly Poisson (scoring is in 3s, 5s, 7s), so a rugby-specific version should bucket scoring events (tries, conversions, penalties) separately and combine.

---

### 5.3 Try Scorer Probability Model

Most directly maps to DraftKings' highest-margin prop markets.

**Features used:**
- Player's tries per 80 minutes (season average)
- Minutes played (starter vs impact sub)
- Position (wings/centres score more)
- Opposition defensive tries-against per game
- Home/away (marginal effect)
- Recent form (last 3 games weighted higher)

```python
# Logistic regression: P(player scores at least 1 try in match)
from sklearn.linear_model import LogisticRegression

features = [
    "tries_per_80",
    "avg_minutes",
    "opp_tries_conceded_pg",
    "is_starter",
    "is_home",
    "position_encoded",
    "form_last3",
]

model = LogisticRegression()
model.fit(X_train, y_train)   # y = 1 if scored in match, 0 if not
```

**Output:** P(anytime try scorer) per player per match → compare vs DK implied probability

---

### 5.4 Value Calculator

Converts model probabilities to expected value against DraftKings odds.

```python
def american_to_implied(american_odds):
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)

def expected_value(model_prob, american_odds):
    if american_odds > 0:
        profit_if_win = american_odds / 100
    else:
        profit_if_win = 100 / abs(american_odds)
    return (model_prob * profit_if_win) - ((1 - model_prob) * 1)

def has_edge(model_prob, american_odds, min_edge=0.05):
    implied = american_to_implied(american_odds)
    return (model_prob - implied) >= min_edge
```

---

### 5.5 Form & Momentum Score

Simple composite metric for UI display and model features.

```python
def form_score(results: list, weights=[1, 0.8, 0.6, 0.4, 0.2]) -> float:
    """
    results: list of 1 (win), 0.5 (draw), 0 (loss), most recent first
    Returns 0-100 weighted form score
    """
    weighted = sum(r * w for r, w in zip(results[:5], weights))
    return (weighted / sum(weights[:len(results)])) * 100
```

---

## 6. DraftKings Integration

DraftKings does not have a public API. Two options for pulling their odds:

### Option A: Manual Odds Entry (MVP)
Build an odds input table in `pages/5_Betting_Edge.py` where you paste in DK lines before each round. Simple, no scraping risk, works immediately.

### Option B: Odds Aggregator APIs (Recommended for v2)

Several free-tier APIs aggregate sportsbook odds including DraftKings:

| API | Free Tier | DK Included | Rugby Coverage |
|---|---|---|---|
| **The Odds API** | 500 req/month | ✅ | Premiership, Six Nations, Super Rugby |
| **OddsJam** | Limited free | ✅ | Good rugby coverage |
| **PropOdds API** | Free tier | ✅ | Player props including try scorers |

```python
# The Odds API example
import requests

ODDS_API_KEY = "your_key"
url = "https://api.the-odds-api.com/v4/sports/rugbyleague_uk_premiership/odds"
params = {
    "apiKey": ODDS_API_KEY,
    "regions": "us",
    "markets": "h2h,spreads,totals",
    "bookmakers": "draftkings",
}
resp = requests.get(url, params=params)
```

### DraftKings Market Map

| DK Market | Your Model | Page |
|---|---|---|
| Moneyline (match winner) | Elo / Dixon-Coles win prob | Match Analysis, Betting Edge |
| Spread (handicap) | Dixon-Coles scoreline distribution | Match Analysis, Betting Edge |
| Total Points O/U | Dixon-Coles expected total | Match Analysis, Betting Edge |
| Anytime Try Scorer | Try scorer logistic model | Player Stats, Betting Edge |
| First Try Scorer | Try scorer model + minutes adjustement | Player Stats |
| Half betting | First-half Elo variant | Match Analysis (v2) |
| Same Game Parlay | Combined probability from all models | Betting Edge |

---

## 7. Deployment & Scheduling

### Development

```bash
pip install streamlit pandas pyarrow requests beautifulsoup4 \
            scipy scikit-learn plotly altair

streamlit run preditions.py
```

### Production (Free Stack)

| Component | Tool | Cost |
|---|---|---|
| App hosting | Streamlit Community Cloud | Free |
| Data storage | CSV + Parquet files committed to repo | Free |
| Scraping scheduler | GitHub Actions (cron) | Free (2000 min/month) |
| Odds API | The Odds API | Free (500 req/mo) |
| Weather | OpenWeatherMap | Free (1000 req/day) |

### Caching Strategy

```python
import streamlit as st

@st.cache_data(ttl=3600)          # 1hr cache for standings/stats
def load_standings(league_id):
    ...

@st.cache_data(ttl=300)           # 5min cache for live scores
def load_live_scores():
    ...

@st.cache_data(ttl=86400)         # 24hr cache for historical player data
def load_player_history(player_id):
    ...
```

---

## 8. Rollout Phases

### Phase 1 — Data Foundation (Weeks 1–3)
- [ ] Set up ESPN hidden API scraper for 2 leagues (Premiership + Six Nations)
- [ ] Define CSV/Parquet file schemas, run initial historical data load
- [ ] Build `predictions.py` home dashboard with fixtures + standings
- [ ] Build `pages/1_League_Overview.py`

### Phase 2 — Core Analytics (Weeks 4–6)
- [ ] Implement Elo model, backfill ratings for all historical matches
- [ ] Build `pages/2_Team_Deep_Dive.py` and `pages/3_Player_Stats.py`
- [ ] Add RugbyPass scraper for current-season enrichment
- [ ] Expand to all 6 leagues

### Phase 3 — Betting Edge (Weeks 7–10)
- [ ] Implement Dixon-Coles score prediction model
- [ ] Implement try scorer logistic regression model
- [ ] Integrate The Odds API for DraftKings lines
- [ ] Build `pages/4_Match_Analysis.py` and `pages/5_Betting_Edge.py`

### Phase 4 — Polish & Model Lab (Weeks 11–14)
- [ ] Build `pages/6_Model_Lab.py` with backtesting and simulation
- [ ] Add historical edge tracking (model picks vs outcomes)
- [ ] Deploy to Streamlit Community Cloud
- [ ] Add SofaScore live score feed

### Phase 5 — Enhancements (Ongoing)
- [ ] Women's Six Nations and women's leagues
- [ ] NRL / Rugby League coverage (DK covers this too)
- [ ] Twitter/X integration for injury news scraping
- [ ] Player injury/availability tracker
- [ ] Email/notification alerts for high-value bet flags

---

## 9. Risk & Caveats

| Risk | Severity | Mitigation |
|---|---|---|
| ESPN hidden API structure changes | Medium | Monitor scraper logs, pin to working endpoint version |
| RugbyPass ToS / anti-scraping | Medium | Rate limit requests (1 req/3s), rotate user agents, cache responses to Parquet |
| DraftKings odds not via free API | Low | The Odds API covers DK for most rugby markets; PropOdds covers player props |
| Model accuracy early in season | High | Flag low-sample-size predictions (< 5 games), use prior-season Elo as starting point |
| Streamlit Community Cloud cold starts | Low | Use `@st.cache_data` aggressively, pre-compute heavy models in pipeline.py |
| Responsible gambling compliance | High | Prominent disclaimers on all betting pages, no real-money advice language |

---

## Key Libraries

```
# requirements.txt
streamlit>=1.51.0
pandas>=2.0.0
numpy>=1.26.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
scipy>=1.12.0
scikit-learn>=1.4.0
pyarrow>=15.0.0
plotly>=5.20.0
altair>=5.3.0
python-dotenv>=1.0.0
schedule>=1.2.0
```

---

*Last updated: April 2026 | Target sportsbook: DraftKings | Data sources: ESPN API, RugbyPass, World Rugby, SofaScore, The Odds API*
