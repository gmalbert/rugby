# ScrumBet — Copilot Instructions

## Project Summary
ScrumBet is a multi-page **Streamlit** rugby analytics app. The entry point is
`predictions.py`; all other pages live in `pages/`. Data is fetched by
`data/pipeline.py` and stored as CSV + Parquet in `data_files/`.

---

## Architecture Rules

### Streamlit page setup
- `st.set_page_config(...)` is called **once only**, at the top of `predictions.py`.
- Sub-pages in `pages/` must **never** call `st.set_page_config`.
- Navigation is declared in `predictions.py` via `st.navigation(...)` / `st.Page(...)`.
- The theme is stored in `st.session_state["theme_name"]` and applied via `themes.apply_theme(...)`.
  Initialise it before any widget renders.

### Charts
- All charts are created with factories in `utils/charts.py` (e.g. `scatter_chart`,
  `bar_chart`, `radar_chart`, `elo_line_chart`, `probability_bar`, `scoreline_heatmap`,
  `histogram`, `stacked_bar`).
- Render charts with `st.plotly_chart(fig, width='stretch')` — do **not** use the
  deprecated `use_container_width=True`.
- Render dataframes with `st.dataframe(..., width='stretch')` — same rule.

### Caching
- All data loading goes through `@st.cache_data` loaders in `utils/cache.py`.
- Available loaders: `load_leagues`, `load_teams`, `load_matches`, `load_odds`,
  `load_player_stats`, `load_team_season_stats`, `load_elo_ratings`.
- Clear the cache via `st.cache_data.clear()` (hooked to the sidebar refresh button).
- Do **not** read CSV/Parquet files directly in page code — always go through these loaders.

### Sidebar
- Shared sidebar items (logo, theme, refresh button, data-source caption) are rendered in
  `predictions.py` before `pg.run()`.
- Each page adds **page-specific** sidebar items (league selector, sliders, etc.) at the
  top of the page file.

---

## Data Model

### `data_files/csv/` (also mirrored in `parquet/`)

| File | Key columns |
|---|---|
| `leagues.csv` | `id`, `name` |
| `teams.csv` | `id`, `name`, `league_id` |
| `matches.csv` | `id`, `league_id`, `home_team_id`, `away_team_id`, `kickoff_utc`, `status` (`scheduled`/`live`/`final`), `home_score`, `away_score`, `home_tries`, `away_tries`, `round`, `venue` |
| `odds_snapshots.csv` | `match_id`, `scraped_at`, `home_ml`, `away_ml`, `total_line`, `total_over_odds`, `total_under_odds` |

Player stats are stored per match row with columns:
`player_id`, `player_name`, `team_id`, `match_id`, `position`, `tries`,
`metres_run`, `linebreaks`, `tackles`, `missed_tackles`, `minutes_played`.

### League IDs
```python
LEAGUES = {
    "six_nations":    "Six Nations",
    "premiership":    "Premiership Rugby",
    "top14":          "Top 14",
    "super_rugby":    "Super Rugby Pacific",
    "urc":            "United Rugby Championship",
    "champions_cup":  "European Champions Cup",
}
```

---

## Models

### Elo (`models/elo.py`)
- Constants: `ELO_K = 32`, `ELO_HOME_ADV = 50`, `ELO_DEFAULT = 1500` (from `utils/config.py`).
- Key functions: `build_elo_history(matches_df)`, `current_ratings(elo_df)`,
  `win_probability(r_home, r_away)` → `(p_home, p_draw, p_away)`,
  `update_elo(r_h, r_a, actual, home, point_diff)`.

### Dixon-Coles (`models/dixon_coles.py`)
- Requires ≥ 15 completed matches (`status == "final"`).
- Key functions: `fit(matches_df)` → model dict, `predict(home_id, away_id, model)` →
  `{p_home, p_draw, p_away, exp_home, exp_away, top_scorelines, matrix}`,
  `params_df(model, teams_df)` → attack/defence DataFrame.
- Model dict keys: `attack`, `defence`, `home_adv`, `rho`, `teams`.

### Try Scorer (`models/try_scorer.py`)
- Requires ≥ 20 completed matches and player stats.
- Key functions: `build_features(player_df, matches_df)`,
  `train(features_df)` → sklearn model,
  `top_try_scorers_for_match(home_id, away_id, player_df, model, n=5)` → DataFrame.

### Value Finder (`models/value_finder.py`)
- Key functions: `find_match_edges(upcoming, odds_df, elo_df, min_edge)`,
  `find_try_scorer_edges(...)`.
- Edge DataFrame columns: `home_team_id`, `away_team_id`, `league_id`, `market`,
  `dk_odds`, `dk_implied_pct`, `model_pct`, `edge_pct`, `ev`, `direction` (`back`/`fade`).

---

## Odds Utilities (`utils/odds.py`)
- `american_to_implied(odds: float) -> float` — converts American odds to implied probability.
- `expected_value(model_prob: float, dk_odds: float) -> float` — EV per $1 staked.
- `format_american(odds: float) -> str` — formats as `+150` or `-120`.

---

## Pipeline (`data/pipeline.py`)
- Run manually: `python data/pipeline.py`
- Scrapers: `data/scrapers/espn_api.py`, `sofascore.py`, `rugbypass.py`, `worldrugby.py`.
- Output: writes/updates CSV files in `data_files/csv/` and Parquet in `data_files/parquet/`.
- GitHub Actions cron: `.github/workflows/` — runs daily at 03:00 UTC.

---

## Environment Variables (`.env`)
```
ODDS_API_KEY=<The Odds API key>
OPENWEATHER_API_KEY=<OpenWeatherMap key>
```
Both are optional. The app degrades gracefully when they are absent.

---

## Coding Conventions

- Python 3.11+; type hints on function signatures.
- `_team_map` / `tname(tid)` pattern for resolving team IDs to names is used in every page —
  keep this consistent.
- Guard all data-dependent sections with `if df.empty: st.info(...); st.stop()` or conditional
  rendering; never let pandas operations run on empty DataFrames.
- Use `pd.Timestamp(...)` for datetime display formatting; all stored timestamps are UTC.
- Avoid importing `requests` at module level in page files — import inside the block that
  needs it (see weather widget in `pages/4_Match_Analysis.py`).
- Footer: call `from footer import add_betting_oracle_footer; add_betting_oracle_footer()`
  at the bottom of every page that has one.
- Do not add `st.set_page_config` to sub-pages.
- Prefer `@st.cache_data` over `@st.cache_resource` for DataFrames.
