# rugbypy Integration Guide

**Verdict: Use it.** `rugbypy` is a pip-installable Python package backed by a live
database of 8 000+ players, 250+ teams, 6 000+ games (2022–2025 seasons) across 23+
competitions. It provides clean, normalised DataFrames with richer historical depth than
the ESPN scraper alone, making it the primary source for model training and player analytics.

---

## Install

```bash
pip install rugbypy
# already added to requirements.txt
```

Python ≥ 3.11 required (matches our venv).

---

## What it covers

| Entity | Volume |
|---|---|
| Matches | 6 000+ (2022–2026, ongoing) |
| Teams | 289 (club + international + 7s) |
| Players | 8 444 with per-game stat rows |
| Competitions | 23 (see list below) |
| Venues | 350+ |

### Competition IDs relevant to ScrumBet

| ID | Competition |
|---|---|
| `2c3df351` | Gallagher Premiership |
| `2f0de05a` | French Top 14 |
| `ee0c6883` | European Rugby Champions Cup |
| `83d92007` | European Rugby Challenge Cup |
| `877aa127` | Super Rugby |
| `23df32a1` | International Test Match |
| `0fad1a69` | Premiership Women's Rugby |
| `822142db` | Pro D2 |
| `0ab9177f` | Major League Rugby |

---

## API Reference

### Matches

```python
from rugbypy.match import (
    fetch_all_matches,          # all 6 000+ matches, returns: match_id, home_team, away_team, date
    fetch_matches_by_date,      # matches on a specific date
    fetch_match_details,        # full detail row (22 columns) for one match_id
)

# All matches ever
all_matches = fetch_all_matches()
# → columns: match_id, home_team, away_team, date

# Matches on a date
day_matches = fetch_matches_by_date(date="20260101")
# → columns: match_id, competition_id, home_team_id, home_team, away_team_id, away_team

# Full match detail
detail = fetch_match_details(match_id="35e0b16d")
# → columns: match_id, date, season, competition_id, competition, venue_id, venue,
#            city_played, home_team, away_team, home_team_id, away_team_id,
#            completed, is_tournament, played_on_grass, attendance,
#            home_team_form, away_team_form, kickoff_time, home_score, away_score, referee
```

### Teams

```python
from rugbypy.team import fetch_all_teams, fetch_team_stats

all_teams  = fetch_all_teams()
# → team_id, team_name

team_games = fetch_team_stats(team_id="93542906")
# → team, game_date, team_id, team_vs, team_vs_id, match_id, players,
#   22m_entries, 22m_conversion, line_breaks, clean_breaks, carries,
#   metres_carried, rucks_won, mauls_won, tackles, missed_tackles,
#   turnovers_conceded, turnover_knock_on, turnovers_won, offload,
#   passes, kicks_from_hand, territory, scrums_won, total_lineouts,
#   lineouts_won, penalty_goals, total_free_kicks_conceded,
#   yellow_cards, red_cards, tries, points   (59 cols total)

# With date filter (returns single row):
one_game = fetch_team_stats(team_id="93542906", date="20251213")
```

### Players

```python
from rugbypy.player import (
    fetch_all_players,   # player_id, player_name registry
    fetch_player_id,     # fuzzy search by name
    fetch_player_stats,  # per-game rows for a player
)

# Fuzzy name search
matches = fetch_player_id("josh van der flier")

# Full career stats
career = fetch_player_stats(player_id="24717f78")
# → player_id, name, team, team_id, position, carries, line_breaks,
#   tackles_completed, turnovers_lost, turnovers_won, clean_breaks,
#   defenders_beaten, metres, offload, passes, kicks, penalty_goals, points,
#   rucks_won, runs, tackles, total_free_kicks_conceded, total_lineouts,
#   tries, try_assists, turnover_knock_on, turnovers_conceded,
#   yellow_cards, red_cards, missed_tackles  (54 cols)

# On a specific date (returns row for that match)
one_game = fetch_player_stats(player_id="24717f78", date="20250101")
```

### Competitions & Venues

```python
from rugbypy.competition import fetch_all_competitions
from rugbypy.venue import fetch_all_venues

competitions = fetch_all_competitions()  # competition_id, competition_name
venues       = fetch_all_venues()        # venue_id, venue_name
```

---

## Integration Plan for ScrumBet

### 1. Replace CSV seed data with live registry

```python
# data/scrapers/rugbypy_source.py
from rugbypy.team import fetch_all_teams
from rugbypy.competition import fetch_all_competitions

def sync_teams_from_rugbypy() -> pd.DataFrame:
    """Pull the full team registry and map to our league_id system."""
    raw = fetch_all_teams()
    COMP_TO_LEAGUE = {
        "2c3df351": "premiership",
        "2f0de05a": "top14",
        "ee0c6883": "champions_cup",
        "877aa127": "super_rugby",
    }
    # Cross-reference via match history to assign league_id
    return raw
```

### 2. Use rugbypy as the primary historical match source

```python
# In data/pipeline.py — add rugbypy match pull
from rugbypy.match import fetch_all_matches, fetch_match_details

def _run_rugbypy_history() -> pd.DataFrame:
    """Pull full historical match list (6 000+ games) for model training."""
    all_m = fetch_all_matches()
    # Filter to our 6 competitions by joining against competition IDs
    target_comps = {
        "2c3df351", "2f0de05a", "ee0c6883", "83d92007", "877aa127",
    }
    # Enrich with scores via fetch_match_details for recent N matches
    ...
```

### 3. Enrich player stats with full career data

rugbypy has 54 per-player columns vs ESPN's 12. Key additions:
- `territory` — % territory controlled (predictive for match outcomes)
- `22m_entries` / `22m_conversion` — attacking efficiency
- `clean_breaks` vs `line_breaks` distinction
- `defenders_beaten` — individual carrying threat score
- `scrums_won` / `lineouts_won` — set-piece dominance
- `passes` / `kicks_from_hand` — game-management style

### 4. Build player similarity index

```python
from rugbypy.player import fetch_all_players, fetch_player_stats
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

STAT_COLS = [
    "carries", "metres", "clean_breaks", "defenders_beaten",
    "tackles", "missed_tackles", "turnovers_won", "offload",
]

def build_player_similarity(player_ids: list[str]) -> pd.DataFrame:
    """Return cosine-similarity matrix across STAT_COLS."""
    rows = []
    for pid in player_ids:
        s = fetch_player_stats(pid)
        if s.empty:
            continue
        avg = s[STAT_COLS].mean()
        avg["player_id"] = pid
        rows.append(avg)
    df = pd.DataFrame(rows).set_index("player_id")
    scaled = StandardScaler().fit_transform(df.fillna(0))
    sim = pd.DataFrame(
        cosine_similarity(scaled), index=df.index, columns=df.index
    )
    return sim
```

### 5. Form string parsing (already in rugbypy match details)

rugbypy provides `home_team_form` / `away_team_form` as `"WLWWL"` strings directly —
no need to compute from match history. Use these in:
- `models/elo.py` — weight recent form vs Elo for blended prediction
- `utils/charts.py` `form_badge_html()` — already consumes this format

### 6. Venue & attendance features

```python
# Merge venue attendance into match rows for home advantage calibration
venues = fetch_all_venues()
details = fetch_match_details(match_id)
attendance = details["attendance"].iloc[0]  # integer or None
```

Attendance is a strong proxy for home atmosphere pressure — include as a feature
in Dixon-Coles home_adv parameter fitting.

---

## Requirements.txt addition

```
rugbypy>=3.0.0
```

---

## Data freshness

rugbypy updates are triggered by the maintainer — typically within 24–48 h of matches
completing. For live/same-day data continue using ESPN + SofaScore scrapers.
Use rugbypy for: historical model training, player career stats, competition registries.
Use ESPN/SofaScore for: today's fixtures, live scores, current-season scoreboard.
