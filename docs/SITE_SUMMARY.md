> **AI Onboarding Guide** — See also `.github/copilot-instructions.md` for full coding conventions.

# ScrumBet (Rugby) — Site Summary

## What This App Does

Streamlit multi-page rugby analytics app covering major leagues (Six Nations, Premiership, Top14, Super Rugby, URC, Champions Cup). Uses Elo ratings, Dixon-Coles match prediction, and a try-scorer model to identify value bets and player prop opportunities across all six competitions.

## Quick Start

```bash
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1        # Windows
source .venv/bin/activate           # macOS/Linux

# 2. (Optional) Refresh data
python scripts/pipeline.py

# 3. Run the app
streamlit run predictions.py
```

GitHub Actions runs `scripts/pipeline.py` daily at 03:00 UTC.

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit (multi-page, `st.navigation`) |
| Models | Elo + Dixon-Coles + Try Scorer (sklearn) |
| Data storage | CSV + Parquet (`data_files/`) |
| Visualization | Plotly (via `utils/charts.py` factories) |
| Caching | `@st.cache_data` loaders in `utils/cache.py` |
| Config | python-dotenv (`.env` file) |

## Key Files

| File | Purpose |
|---|---|
| `predictions.py` | Entry point — `st.set_page_config`, sidebar, theme, `st.navigation`, `pg.run()` |
| `pages/*.py` | Individual pages — **never** call `st.set_page_config` here |
| `models/elo.py` | Elo rating system: K=32, home advantage=50 points |
| `models/dixon_coles.py` | Dixon-Coles match prediction (requires ≥15 completed matches) |
| `models/try_scorer.py` | Try scorer probability model (requires ≥20 matches + player stats) |
| `models/value_finder.py` | `find_match_edges()` — model probability vs DraftKings implied odds |
| `utils/cache.py` | All `@st.cache_data` loaders: `load_leagues`, `load_teams`, `load_matches`, etc. |
| `utils/charts.py` | Chart factory functions — always use these, never create Plotly figures directly in pages |
| `utils/odds.py` | `american_to_implied()`, `expected_value()`, `format_american()` |
| `scripts/pipeline.py` | Nightly data pipeline: runs all scrapers, writes CSV/Parquet |
| `footer.py` | `add_betting_oracle_footer()` |

## Data Flow

1. **Scraping**: `scripts/scrapers/` (ESPN, SofaScore, RugbyPass, WorldRugby) → raw match data
2. **Storage**: `scripts/pipeline.py` writes `data_files/csv/` + `data_files/parquet/`
3. **Caching**: `utils/cache.py` loaders read Parquet → `@st.cache_data` for all pages
4. **Models**: `models/elo.py` → current Elo ratings; `models/dixon_coles.py` → match predictions; `models/try_scorer.py` → player prop probabilities
5. **Value finding**: `models/value_finder.py` → edge = model probability vs DK implied odds

## League IDs

```python
LEAGUES = {
    "six_nations": "Six Nations",    "premiership": "Premiership Rugby",
    "top14": "Top 14",               "super_rugby": "Super Rugby Pacific",
    "urc": "United Rugby Championship",  "champions_cup": "European Champions Cup"
}
```

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `ODDS_API_KEY` | The Odds API — DraftKings lines | Optional |
| `OPENWEATHER_API_KEY` | OpenWeatherMap — match-day weather | Optional |

## Critical Conventions

- **All data loading** goes through `@st.cache_data` loaders in `utils/cache.py` — never read CSV/Parquet directly in page code
- **All charts** are created with factory functions in `utils/charts.py` (e.g., `scatter_chart`, `elo_line_chart`, `radar_chart`)
- Render charts with `st.plotly_chart(fig, width='stretch')` — `use_container_width` is deprecated
- Guard all data sections with `if df.empty: st.info(...); st.stop()` — never run pandas operations on empty DataFrames
- Use `_team_map` / `tname(tid)` pattern for resolving team IDs to names (consistent across all pages)
- Dixon-Coles requires ≥15 completed matches; Try Scorer requires ≥20 — check before calling

## Common Gotchas

- Dixon-Coles `fit()` will fail with fewer than 15 completed matches — add a check at the start of each season
- Scrapers may be fragile to site layout changes (SofaScore, RugbyPass) — monitor after each site update
- Weather widget in `pages/4_Match_Analysis.py` imports `requests` inside the block (not at module level) — keep this pattern
