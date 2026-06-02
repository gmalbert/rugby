# ScrumBet (Rugby) — Next 5 Features to Implement

> **Based on:** Codebase gap analysis as of July 2025

---

## Feature 1: Form-Weighted Dixon-Coles (Time Decay)

**Why:** The current Dixon-Coles implementation weights all historical matches equally. Adding the standard time-decay parameter `xi` (weight = `exp(-xi × days_ago)`, typical `xi = 0.0065`) down-weights older matches and makes the model more responsive to in-season form changes — the most impactful model upgrade available.

**How:**
1. In `models/dixon_coles.py`, modify `fit(matches_df)` to accept a `xi` parameter (default `0.0065`)
2. Compute `weight = exp(-xi × (today - match_date).days)` for each historical match
3. Apply weights in the log-likelihood optimization loop
4. Add a `xi` slider to the Models page in the UI for experimentation
5. Compare predicted vs actual results with and without decay over a holdout season

**Complexity:** Medium

---

## Feature 2: Try Scorer Value Bet Comparison

**Why:** `models/try_scorer.py` computes top predicted try scorers per match but this output is not compared against DraftKings first/anytime try scorer odds. Surfacing model probability vs market odds with an edge column is the most actionable output for bettors.

**How:**
1. Extend `models/value_finder.py` with `find_try_scorer_edges(home_id, away_id, player_df, model, odds_df)`
2. For each predicted top-5 try scorer, look up their DK anytime/first scorer odds in `odds_snapshots.csv`
3. Compute: `model_prob`, `dk_implied_pct`, `edge_pct`, `ev`
4. Add a "Try Scorer Value" section to `pages/3_Value_Finder.py` below match-level edges

**Complexity:** Medium

---

## Feature 3: Referee Impact Features

**Why:** World Rugby referee tendencies (scrum penalty rate, high tackle consistency, home bias) are publicly documentable from historical match data. Referee assignment is known days before the match and is a signal that most sportsbooks fail to price efficiently.

**How:**
1. Add a `referee` column to `data_files/csv/matches.csv` (scrape from rugbypass.com or espn fixture pages)
2. Compute per-referee stats from historical matches: home team win%, scrums won by visiting team%, yellow cards per game
3. Add `ref_home_win_pct` and `ref_fouls_per_game` as features in `models/elo.py` update function
4. Display assigned referee + stats on `pages/4_Match_Analysis.py`

**Complexity:** Medium

---

## Feature 4: League Table Dashboard with Elo Projections

**Why:** The app models individual match outcomes but has no league standings visualization. Adding a standings table (URC, Premiership, Top14) with current Elo ratings and projected final positions based on remaining fixtures would be a flagship navigation page.

**How:**
1. Add `pages/5_League_Table.py`
2. Compute current standings from `data_files/csv/matches.csv` (results only, `status == "final"`)
3. Load `data_files/csv/leagues.csv` and `teams.csv` for team metadata
4. For each remaining fixture, use Elo win probability to compute projected points (expected value)
5. Render with `st.dataframe(width='stretch')`: Pos | Team | P | W | D | L | Points | Elo | Projected Finish

**Complexity:** Low

---

## Feature 5: Best Bets JSON Export for Sports-Picks-Grid

**Why:** `rugby` is listed in the sports-picks-grid aggregator REPOS mapping. A consistent `data_files/best_bets_today.json` export with the unified schema would bring rugby picks into the dashboard.

**How:**
1. Add `scripts/export_best_bets.py` that calls `models/value_finder.py` for upcoming fixtures
2. Filter to `edge_pct >= 0.03` (Strong tier and above)
3. Write `data_files/best_bets_today.json` per the unified schema (`meta` + `bets` array)
4. Add to GitHub Actions nightly pipeline as the final step
5. Validate schema against sports-picks-grid `docs/02-unified-schema.md`

**Complexity:** Low
