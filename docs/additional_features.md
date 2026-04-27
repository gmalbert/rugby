# Additional Features Roadmap

UI pages, tools, and capabilities to add to ScrumBet beyond the current 6-page build.

---

## Page: Line Movement Tracker

Track how odds move from opening to kick-off. Sharp money leaves a trail.

```python
# pages/7_Line_Movement.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.cache import load_odds, load_teams

"""
Visualise DraftKings odds movement for each upcoming fixture.

A line that moves from +200 → +140 means heavy money came in on that side.
Reverse line movement (public % contradicts line movement) = sharp action.
"""

def line_movement_chart(odds_history: pd.DataFrame, match_label: str) -> go.Figure:
    """Plot home_ml and away_ml over time for a single match."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=odds_history["scraped_at"],
        y=odds_history["home_ml"],
        name="Home ML",
        mode="lines+markers",
        line=dict(color="#3b82f6"),
    ))
    fig.add_trace(go.Scatter(
        x=odds_history["scraped_at"],
        y=odds_history["away_ml"],
        name="Away ML",
        mode="lines+markers",
        line=dict(color="#ef4444"),
    ))
    fig.update_layout(
        title=match_label,
        yaxis_title="American Odds",
        template="plotly_dark",
        hovermode="x unified",
    )
    return fig
```

---

## Page: Tournament Bracket Simulator

Run Monte Carlo simulations for knockout tournaments (Champions Cup quarters onward).

```python
# pages/8_Tournament_Sim.py
"""
Select the remaining bracket of a knockout tournament, set team seeds by
current Elo rating, and simulate 10 000 paths to produce win probabilities
for each possible outcome.
"""

import streamlit as st
import pandas as pd
import numpy as np
from models.elo import win_probability, current_ratings

def simulate_ko_bracket(
    seeds: list[str],
    ratings: dict[str, float],
    n: int = 10_000,
) -> pd.DataFrame:
    """
    seeds: ordered list of team_ids (1v8, 2v7, 3v6, 4v5 in QFs)
    Returns per-team win probability for each round.
    """
    assert len(seeds) in (2, 4, 8, 16)
    round_names = {16: "R16", 8: "QF", 4: "SF", 2: "Final"}
    win_counts  = {t: 0 for t in seeds}
    rng         = np.random.default_rng(42)

    for _ in range(n):
        bracket = list(seeds)
        while len(bracket) > 1:
            next_round = []
            for i in range(0, len(bracket), 2):
                h, a = bracket[i], bracket[i+1]
                ph, _, _ = win_probability(ratings.get(h, 1500), ratings.get(a, 1500))
                winner = h if rng.random() < ph else a
                next_round.append(winner)
            bracket = next_round
        win_counts[bracket[0]] += 1

    return pd.DataFrame([
        {"team_id": t, "title_prob": win_counts[t] / n}
        for t in seeds
    ]).sort_values("title_prob", ascending=False)
```

---

## Page: Player Comparison Tool

Side-by-side radar comparison of any two players from the rugbypy database.

```python
# pages/9_Player_Compare.py
"""
Select two players, choose stat categories, render radar overlay.
Useful for: replacement analysis, transfer value, prop bet comparison.
"""

import streamlit as st
from rugbypy.player import fetch_player_id, fetch_player_stats
from utils.charts import radar_chart

COMPARE_STATS = [
    "carries", "metres", "clean_breaks", "defenders_beaten",
    "tackles", "turnovers_won", "offload", "tries",
]

def player_radar(player_a_id: str, player_b_id: str) -> None:
    stats_a = fetch_player_stats(player_a_id)[COMPARE_STATS].mean()
    stats_b = fetch_player_stats(player_b_id)[COMPARE_STATS].mean()
    fig = radar_chart(
        categories=COMPARE_STATS,
        values_a=stats_a.tolist(),
        values_b=stats_b.tolist(),
        label_a=player_a_id,
        label_b=player_b_id,
    )
    st.plotly_chart(fig, use_container_width=True)
```

---

## Page: Referee Analysis

Each referee has measurable tendencies that affect match outcomes.

```python
# pages/10_Referee_Stats.py
"""
- Penalties per game (home vs away split)
- Cards per game
- Home win rate under this referee
- Average total points per game
- Style profile: advantage-player vs whistle-happy
"""

import streamlit as st
import pandas as pd
from rugbypy.match import fetch_all_matches, fetch_match_details

@st.cache_data(ttl=86400)
def build_referee_db() -> pd.DataFrame:
    """Build referee statistics from rugbypy match details."""
    all_m = fetch_all_matches()
    records = []
    for mid in all_m["match_id"].tolist():
        det = fetch_match_details(mid)
        if det.empty or not det.iloc[0].get("referee"):
            continue
        row = det.iloc[0]
        records.append({
            "referee":       row["referee"],
            "home_score":    row["home_score"],
            "away_score":    row["away_score"],
            "total_points":  row["home_score"] + row["away_score"],
            "home_win":      int(row["home_score"] > row["away_score"]),
            "competition":   row["competition"],
        })
    df = pd.DataFrame(records)
    return df.groupby("referee").agg(
        games=("home_win", "count"),
        avg_total_pts=("total_points", "mean"),
        home_win_rate=("home_win", "mean"),
    ).reset_index().sort_values("games", ascending=False)
```

---

## Feature: Smart Injury Banner

Scan RSS/team news for injuries to players who appear in upcoming fixture predictions.
Highlight which model predictions may be stale.

```python
# utils/injury_alert.py
from data.scrapers.injury_feed import fetch_injury_news
import pandas as pd

def get_injury_alerts(player_predictions: pd.DataFrame) -> list[str]:
    """
    Cross-reference predicted try scorers against recent injury news.
    Returns list of alert strings for st.warning() display.
    """
    news = fetch_injury_news()
    alerts = []
    for _, player in player_predictions.iterrows():
        name = player["player_name"].lower()
        hits = news[news["headline"].str.lower().str.contains(name.split()[-1])]
        if not hits.empty:
            alerts.append(
                f"⚠️ {player['player_name']}: injury news detected — "
                f"'{hits.iloc[0]['headline']}'"
            )
    return alerts
```

---

## Feature: Odds Alert System

Persist a "target odds" threshold per bet. When odds reach the target, surface a banner.

```python
# utils/odds_alerts.py
import json
from pathlib import Path
import pandas as pd

ALERTS_PATH = Path("data_files/odds_alerts.json")

def save_alert(match_id: str, market: str, target_odds: int, note: str = "") -> None:
    alerts = _load_raw()
    alerts.append({
        "match_id": match_id,
        "market":   market,
        "target":   target_odds,
        "note":     note,
        "triggered": False,
    })
    ALERTS_PATH.write_text(json.dumps(alerts, indent=2))

def check_alerts(current_odds_df: pd.DataFrame) -> list[dict]:
    """Return alerts where current odds have reached or exceeded target."""
    alerts  = _load_raw()
    triggered = []
    for a in alerts:
        if a.get("triggered"):
            continue
        row = current_odds_df[current_odds_df["match_id"] == a["match_id"]]
        if row.empty:
            continue
        current = row.iloc[0].get(a["market"])
        if current is not None and current >= a["target"]:
            triggered.append(a)
    return triggered

def _load_raw() -> list:
    if ALERTS_PATH.exists():
        return json.loads(ALERTS_PATH.read_text())
    return []
```

---

## Feature: Historical Bet Tracker (P&L)

Track every model recommendation and its outcome. Compute ROI by market, league, and model.

```python
# data/csv/bet_log.csv  (schema)
# columns: date, match_id, market, selection, model_prob, dk_odds, stake, result, pnl

import pandas as pd
from pathlib import Path

BET_LOG = Path("data_files/csv/bet_log.csv")

def log_bet(match_id, market, selection, model_prob, dk_odds, stake):
    row = pd.DataFrame([{
        "date": pd.Timestamp.now().date(),
        "match_id": match_id, "market": market,
        "selection": selection, "model_prob": model_prob,
        "dk_odds": dk_odds, "stake": stake,
        "result": None, "pnl": None,
    }])
    if BET_LOG.exists():
        existing = pd.read_csv(BET_LOG)
        row = pd.concat([existing, row], ignore_index=True)
    row.to_csv(BET_LOG, index=False)

def compute_roi(bet_log: pd.DataFrame) -> dict:
    settled = bet_log.dropna(subset=["pnl"])
    return {
        "total_bets":  len(settled),
        "total_staked": settled["stake"].sum(),
        "total_pnl":   settled["pnl"].sum(),
        "roi_pct":     settled["pnl"].sum() / settled["stake"].sum() * 100,
        "strike_rate": (settled["pnl"] > 0).mean(),
    }
```

---

## Feature: st.navigation Grouped Sidebar

Organise pages into semantic groups with icons (see `macos-emoji-filename-fix.md` for the
full migration guide):

```python
# predictions.py  (entry point structure)
pg = st.navigation({
    "": [
        st.Page(home_page, title="Home",              icon="🏉", default=True),
    ],
    "Analytics": [
        st.Page("pages/1_League_Overview.py",  title="League Overview",  icon="🏆"),
        st.Page("pages/2_Team_Deep_Dive.py",   title="Team Deep Dive",   icon="📊"),
        st.Page("pages/3_Player_Stats.py",     title="Player Stats",     icon="👟"),
        st.Page("pages/4_Match_Analysis.py",   title="Match Analysis",   icon="🔍"),
    ],
    "Betting": [
        st.Page("pages/5_Betting_Edge.py",     title="Betting Edge",     icon="⚡"),
        st.Page("pages/7_Line_Movement.py",    title="Line Movement",    icon="📉"),
    ],
    "Models": [
        st.Page("pages/6_Model_Lab.py",        title="Model Lab",        icon="🧪"),
        st.Page("pages/8_Tournament_Sim.py",   title="Tournament Sim",   icon="🎯"),
    ],
    "Research": [
        st.Page("pages/9_Player_Compare.py",   title="Player Compare",   icon="🔬"),
        st.Page("pages/10_Referee_Stats.py",   title="Referee Stats",    icon="🟨"),
    ],
})
pg.run()
```

---

## Feature: Export & Share

```python
# In any data table page, add:
import io

def download_button(df: pd.DataFrame, filename: str, label: str = "Download CSV") -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    st.download_button(
        label=label,
        data=buf.getvalue(),
        file_name=filename,
        mime="text/csv",
    )
```

---

## Backlog Summary

| # | Feature | Page | Effort | Priority |
|---|---|---|---|---|
| 7 | Line Movement Tracker | new page | M | High |
| 8 | Tournament Bracket Simulator | new page | M | High |
| 9 | Player Comparison Tool | new page | L | Medium |
| 10 | Referee Analysis | new page | M | Medium |
| — | Injury Alert Banner | existing pages | M | High |
| — | Odds Alert System | utils + sidebar | M | High |
| — | Bet Tracker P&L | new page | L | Medium |
| — | Kelly Criterion stake sizing | Betting Edge | L | High |
| — | XGBoost win model | Model Lab tab | H | Medium |
| — | Season Table Simulator | Model Lab tab | M | Medium |
| — | Bradley-Terry model | Model Lab tab | L | Medium |
| — | rugbypy historical pull | pipeline | L | High |
