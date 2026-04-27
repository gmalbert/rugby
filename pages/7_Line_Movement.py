"""
Page 7 — Line Movement Tracker
Track how DraftKings moneylines move from first scrape to kick-off.
Sharp money leaves a trail in the line.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

from utils.cache import load_teams, load_matches, load_odds, load_live_rugby_odds
from utils.config import LEAGUES, ODDS_API_KEY, ODDS_API_IO_KEY
from utils.charts import line_movement_chart
from footer import add_betting_oracle_footer

st.title("📉 Line Movement")
st.caption("Track how DraftKings odds shift from opening to kick-off — sharp money leaves a trail.")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
odds_df    = load_odds()

if odds_df.empty or matches_df.empty:
    if not ODDS_API_KEY and not ODDS_API_IO_KEY:
        st.info(
            "Set `ODDS_API_IO_KEY` in `.env` and run the pipeline to populate odds snapshots. "
            "odds-api.io covers **Super Rugby**, **NRL**, and **international rugby** "
            "(DraftKings / BetMGM BR). Club rugby (Premiership, Top 14, URC) requires a paid plan."
        )
    elif odds_df.empty:
        st.info(
            "No odds snapshots yet. Run `python scripts/pipeline.py` to fetch the first snapshot. "
            "\n\n**Coverage with odds-api.io (free tier):**\n"
            "- DraftKings: Super Rugby Union ML, NRL Premiership ML\n"
            "- BetMGM BR: International rugby — ML, Spread, Totals\n\n"
            "Line movement charts populate once the pipeline has run at least twice."
        )
    st.stop()

_tmap = dict(zip(teams_df["id"], teams_df["name"])) if not teams_df.empty else {}

def tname(tid: str) -> str:
    return _tmap.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.header("Line Movement")
league_filter = st.sidebar.multiselect(
    "Leagues",
    options=list(LEAGUES.keys()),
    default=list(LEAGUES.keys()),
    format_func=lambda x: LEAGUES[x],
)

# ── Filter matches to a rolling window ────────────────────────────────────
now          = datetime.now(timezone.utc)
window_start = now - timedelta(days=3)
window_end   = now + timedelta(days=14)

relevant = matches_df[
    (matches_df["kickoff_utc"] >= window_start) &
    (matches_df["kickoff_utc"] <= window_end)
].copy()

if league_filter:
    relevant = relevant[relevant["league_id"].isin(league_filter)]

if relevant.empty:
    st.info("No fixtures in the current window for selected leagues.")
    st.stop()

relevant["label"] = (
    relevant["home_team_id"].apply(tname) + " vs " +
    relevant["away_team_id"].apply(tname) + "  (" +
    relevant["kickoff_utc"].dt.strftime("%d %b") + ")"
)

# Identify matches with multiple odds snapshots (needed for movement)
snap_counts   = odds_df.groupby("match_id")["scraped_at"].nunique()
multi_snap_ids = snap_counts[snap_counts >= 2].index

# Sort: multi-snapshot matches first, then singles
relevant["has_movement"] = relevant["id"].isin(multi_snap_ids)
relevant = relevant.sort_values(["has_movement", "kickoff_utc"], ascending=[False, True])

selected_label = st.sidebar.selectbox(
    "Fixture",
    options=relevant["label"].tolist(),
    help="★ = multiple snapshots available (movement visible)",
)
match = relevant[relevant["label"] == selected_label].iloc[0]
match_id  = match["id"]
home_name = tname(match["home_team_id"])
away_name = tname(match["away_team_id"])

# ── Load odds history ──────────────────────────────────────────────────────
history = odds_df[odds_df["match_id"] == match_id].sort_values("scraped_at").copy()

st.header(f"{home_name}  vs  {away_name}")
ko_str = pd.Timestamp(match["kickoff_utc"]).strftime("%d %b %Y %H:%M UTC")
st.caption(f"{LEAGUES.get(match['league_id'], match['league_id'])}  ·  Kickoff {ko_str}")

if history.empty:
    st.info("No odds have been scraped for this fixture yet.")
    st.stop()

# ── Summary metrics ────────────────────────────────────────────────────────
def _fmt(v) -> str:
    try:
        return f"{int(v):+d}"
    except Exception:
        return "—"

if len(history) >= 2:
    first = history.iloc[0]
    last  = history.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Opening Home ML", _fmt(first.get("home_ml")))
    c2.metric(
        "Current Home ML",
        _fmt(last.get("home_ml")),
        delta=(
            _fmt(int(last.get("home_ml", 0)) - int(first.get("home_ml", 0)))
            if pd.notna(first.get("home_ml")) and pd.notna(last.get("home_ml"))
            else None
        ),
    )
    c3.metric("Opening Away ML", _fmt(first.get("away_ml")))
    c4.metric(
        "Current Away ML",
        _fmt(last.get("away_ml")),
        delta=(
            _fmt(int(last.get("away_ml", 0)) - int(first.get("away_ml", 0)))
            if pd.notna(first.get("away_ml")) and pd.notna(last.get("away_ml"))
            else None
        ),
    )
else:
    st.info("Only one snapshot available — more scrapes are needed to show movement.")

st.divider()

# ── Moneyline chart ────────────────────────────────────────────────────────
st.subheader("💲 Moneyline Movement")
fig_ml = line_movement_chart(history, home_name, away_name)
st.plotly_chart(fig_ml, width='stretch')

# ── Total line chart ───────────────────────────────────────────────────────
if history["total_line"].notna().any():
    import plotly.graph_objects as go
    from utils.charts import _chart_theme

    st.subheader("➕ Total (O/U) Line Movement")
    fig_tot = go.Figure()
    fig_tot.add_trace(
        go.Scatter(
            x=history["scraped_at"],
            y=history["total_line"],
            name="O/U Line",
            mode="lines+markers",
            line=dict(color="#f59e0b", width=2),
        )
    )
    fig_tot.update_layout(
        yaxis_title="Total Points Line",
        hovermode="x unified",
        height=260,
        margin=dict(l=0, r=0, t=20, b=0),
        **_chart_theme(),
    )
    st.plotly_chart(fig_tot, width='stretch')

st.divider()

# ── Raw snapshot table ─────────────────────────────────────────────────────
st.subheader("📋 All Snapshots")
disp = history[
    ["scraped_at", "home_ml", "away_ml", "total_line", "total_over_odds", "total_under_odds"]
].copy()
disp["scraped_at"] = disp["scraped_at"].dt.strftime("%d %b %H:%M UTC")
disp = disp.rename(columns={
    "scraped_at": "Scraped At",
    "home_ml": "Home ML", "away_ml": "Away ML",
    "total_line": "O/U Line",
    "total_over_odds": "Over Odds", "total_under_odds": "Under Odds",
})
st.dataframe(disp, hide_index=True, width='stretch')

# ── Implied probability movement ───────────────────────────────────────────
from utils.odds import american_to_implied

if history["home_ml"].notna().any():
    st.subheader("📊 Implied Probability Movement")
    impl = history[["scraped_at", "home_ml", "away_ml"]].dropna(subset=["home_ml"]).copy()
    impl["Home Impl %"] = (impl["home_ml"].apply(american_to_implied) * 100).round(1)
    impl["Away Impl %"] = (impl["away_ml"].apply(american_to_implied) * 100).round(1)
    impl["scraped_at"] = impl["scraped_at"].dt.strftime("%d %b %H:%M")
    st.dataframe(
        impl[["scraped_at", "Home Impl %", "Away Impl %"]].rename(
            columns={"scraped_at": "Scraped At"}
        ),
        hide_index=True,
        width='stretch',
    )

add_betting_oracle_footer()
