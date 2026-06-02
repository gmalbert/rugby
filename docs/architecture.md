# ScrumBet — Architecture

## Overview
Multi-page Streamlit rugby analytics app. Data is fetched by a nightly pipeline, stored as CSV + Parquet, and displayed via cached loaders. Models include Elo, Dixon-Coles, and a Try Scorer probability model.

## Data Flow
```
ESPN API / SofaScore / RugbyPass / WorldRugby
        ↓
scripts/pipeline.py
    scripts/scrapers/espn_api.py
    scripts/scrapers/sofascore.py
    scripts/scrapers/rugbypass.py
    scripts/scrapers/worldrugby.py
        ↓
data_files/csv/ (leagues, teams, matches, odds_snapshots, player_stats)
data_files/parquet/ (mirrored from CSV)
        ↓
utils/cache.py → @st.cache_data loaders
        ↓
predictions.py (entry) → st.navigation → pages/
        ↓
scripts/export_best_bets.py → data_files/best_bets_today.json
```

## ML / Prediction Models

### Elo (`models/elo.py`)
- Constants: `ELO_K=32`, `ELO_HOME_ADV=50`, `ELO_DEFAULT=1500`
- `build_elo_history(matches_df)`, `current_ratings(elo_df)`, `win_probability(r_home, r_away)`, `update_elo(...)`

### Dixon-Coles (`models/dixon_coles.py`)
- Requires ≥15 completed matches
- `fit(matches_df)` → model dict; `predict(home_id, away_id, model)` → `{p_home, p_draw, p_away, exp_home, exp_away, top_scorelines, matrix}`

### Try Scorer (`models/try_scorer.py`)
- Requires ≥20 completed matches + player stats
- `build_features(player_df, matches_df)`, `train(features_df)` → sklearn model

### Value Finder (`models/value_finder.py`)
- `find_match_edges(upcoming, odds_df, elo_df, min_edge)` → edge DataFrame
- `find_try_scorer_edges(...)` — player prop edges
- Edge columns: `market`, `dk_odds`, `dk_implied_pct`, `model_pct`, `edge_pct`, `ev`, `direction`

## Cache Loaders (`utils/cache.py`)
`load_leagues`, `load_teams`, `load_matches`, `load_odds`, `load_player_stats`, `load_team_season_stats`, `load_elo_ratings`
- All wrapped in `@st.cache_data`
- Do NOT read CSV/Parquet directly in page code
- Clear via `st.cache_data.clear()` (sidebar refresh button)

## API Integrations
| Source | Purpose | Key |
|--------|---------|-----|
| ESPN API | Scores, schedules | None (public) |
| SofaScore | Stats, lineups | None (scraped) |
| RugbyPass | Advanced stats | None (scraped) |
| WorldRugby | Official results | None (public) |
| The Odds API | Match odds | `ODDS_API_KEY` |
| OpenWeatherMap | Match weather | `OPENWEATHER_API_KEY` |

## Data Model (CSV files)
| File | Key Columns |
|------|-------------|
| `matches.csv` | id, league_id, home/away_team_id, kickoff_utc, status, home/away_score |
| `odds_snapshots.csv` | match_id, home_ml, away_ml, total_line, total_over/under_odds |

## Charts (`utils/charts.py`)
All charts via factories: `scatter_chart`, `bar_chart`, `radar_chart`, `elo_line_chart`, `probability_bar`, `scoreline_heatmap`, `histogram`, `stacked_bar`. Render with `st.plotly_chart(fig, width='stretch')`.

## Nightly Automation
GitHub Actions (`.github/workflows/`) runs `python scripts/pipeline.py` at 03:00 UTC daily.
