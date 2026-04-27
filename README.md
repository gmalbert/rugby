# ScrumBet 🏉

European rugby analytics and DraftKings betting intelligence, built with Streamlit.

## Overview

ScrumBet is a multi-page Streamlit app that combines live scraped data from five sources with
three predictive models (Elo, Dixon-Coles, Try Scorer) to surface match previews, player
stats, and value-bet opportunities across six major European and international rugby
competitions.

## Pages

### Home (`predictions.py`)
- **This Week's Fixtures** — upcoming matches grouped by day with kickoff time, venue, and DK moneylines
- **Live Ticker** — real-time scores via SofaScore; falls back to pipeline data when unavailable
- **DK Odds Snapshot** — compact moneyline + total table for next 7 days
- **Top Try Scorers** — league-filtered season leaderboard across all competitions
- **Team Form Strip** — last-5 result badges (W/D/L) for every team in the current fixture list
- Global sidebar: logo, theme selector, cache-refresh button, data-source credits

### 1 – League Overview (`pages/1_League_Overview.py`)
- **Standings table** — P/W/L/D, points for/against, try diff, bonus points, league points, form arrow
- **Attack Efficiency scatter** — Points per Game vs Tries per Game with quadrant lines at the mean
- **Home vs Away bar charts** — average points scored at home and away per team
- **Round-by-Round Results grid** — pivot table of scores by round
- **Upcoming Fixtures** — date, teams, venue, round, and DK odds (ML + O/U) when available
- **Season Snapshot** — auto-generated narrative (leader, gap at top, top attacker, best defence)

### 2 – Team Deep Dive (`pages/2_Team_Deep_Dive.py`)
- **Form Strip** — last 10 results with colour-coded badges and opponent/score labels
- **Attack vs Defence Radar** — five-axis radar: tries scored, tries conceded, metres, linebreaks, tackles
- **Elo Rating History** — line chart of the team's Elo trajectory across all recorded matches
- **Scoring Breakdown** — bar chart splitting season points into try-derived vs penalties/drops
- **Key Players** — top 5 try scorers, metres carriers, and tacklers in three side-by-side tables
- **Head-to-Head** — last 10 meetings vs any selected opponent with W/D/L result column
- **Venue Stats** — home/away split: games, wins, average points for/against

### 3 – Player Stats (`pages/3_Player_Stats.py`)
- **Try Scorer Rankings** — sortable table: tries, games, tries-per-game, last-3 tries; filterable by league and position
- **Player Profile** — metrics card (team, position, season tries, T/game, consistency %, avg minutes); tries-by-round bar chart; minutes-played trend
- **Prop Bet Analyzer** — enter a DraftKings American-odds line; model computes historical scoring rate, implied probability, expected value, and Kelly Criterion stake recommendation

### 4 – Match Analysis (`pages/4_Match_Analysis.py`)
- **Win Probabilities** — horizontal probability bar chart from Dixon-Coles (primary) or Elo (fallback)
- **Predicted Scoreline** — expected points for each team and top-5 most likely scorelines with probabilities
- **Scoreline Distribution Heatmap** — Dixon-Coles joint Poisson matrix up to 40 pts per side
- **Head-to-Head** — last 5 meetings between the two selected teams
- **Key Stats Comparison** — 8-metric side-by-side table: win%, pts/game, tries/game, tries conceded/game, metres, linebreaks, tackles, missed tackles
- **Predicted Try Scorers** — top-5 anytime try scorer probabilities from the logistic regression model
- **DK Odds vs Model** — edge table for home ML, away ML, and total line with signal (✅ Back / 🔴 Under / 🔴 Fade)
- **Venue Weather** — current conditions at kickoff venue via OpenWeatherMap (optional, requires `OPENWEATHER_API_KEY`)

### 5 – Betting Edge (`pages/5_Betting_Edge.py`)
- **Value Bets** — Elo-implied vs DK-implied probability for every upcoming fixture; colour-coded rows (green = back, red = fade); configurable minimum edge threshold
- **Try Scorer Value** — model probability and fair-value American odds for anytime try scorer across all upcoming games
- **Totals Analysis** — Dixon-Coles expected total vs DK O/U line with Over/Under signal
- **Parlay Builder** — select any combination of Elo-ranked match-winner legs; displays combined model probability and fair-value American parlay odds
- **Historical Edge Tracking** — placeholder section; will show ROI, strike rate, and calibration by market type as results accumulate

### 6 – Model Lab (`pages/6_Model_Lab.py`)
- **Elo Leaderboard** — current ratings for all teams with league, 3-match trend arrow, and sortable table; per-team Elo history line chart
- **Dixon-Coles Parameters** — home advantage and ρ (low-scoring correction) values; attack/defence rating table; attack-vs-defence scatter plot
- **Backtesting** — walk-forward evaluation: % correct winner, Brier score, number of test matches, calibration scatter (predicted vs actual home win rate)
- **Manual Override** — adjust any two teams' Elo ratings by ±200 points to simulate injury news; re-runs win probability instantly
- **Monte Carlo Simulation** — Poisson draws (1 000–10 000); outputs win/draw/loss %, total-points histogram, and winning-margin histogram

## Data Sources

| Source | Used For |
|---|---|
| ESPN API | Fixtures, results, scores, league standings |
| RugbyPass | Supplementary match metadata |
| SofaScore | Live scores, player statistics (tries, metres, tackles, linebreaks, minutes) |
| World Rugby | Official rankings |
| The Odds API | DraftKings moneylines, totals, and try scorer props |

## Models

| Model | Details |
|---|---|
| **Elo** | K = 32, home advantage = +50, margin-weighted updates. Ratings stored per match in `data_files/`. Used for win probability, backtesting, and parlay builder. |
| **Dixon-Coles** | Bivariate Poisson with low-scoring correction (ρ). Fitted via `scipy.optimize.minimize`. Requires ≥ 15 completed matches. Outputs attack/defence ratings, win/draw/loss probabilities, and full scoreline matrix. |
| **Try Scorer** | Random Forest on player features: tries-per-game, position, home/away, minutes. Trained on all completed match data; requires ≥ 20 matches. |
| **Value Finder** | Compares Elo/DC model probabilities to DK implied probabilities; identifies edges above a configurable threshold. |

## Leagues Covered

Six Nations · Premiership Rugby · Top 14 · Super Rugby Pacific · United Rugby Championship · European Champions Cup

## Tech Stack

| Layer | Library |
|---|---|
| Frontend | Streamlit (multi-page, wide layout, dark/light themes) |
| Data | pandas, pyarrow (Parquet + CSV dual-write) |
| Models | scipy, scikit-learn, numpy |
| Charts | Plotly Express |
| Scrapers | requests, ESPN API, SofaScore API, The Odds API |
| Pipeline | Python script + GitHub Actions cron (daily 03:00 UTC) |
| Config | python-dotenv (`.env` for API keys) |


## Disclaimer

ScrumBet is an informational analytics tool only. Nothing here constitutes financial or gambling advice.
