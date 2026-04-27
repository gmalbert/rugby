"""
Page 1 — League Overview
Full season view for one selected league: standings, charts, fixtures.
"""

import streamlit as st
import pandas as pd

from utils.cache import load_teams, load_matches, load_team_season_stats, load_odds
from utils.config import LEAGUES
from utils.charts import scatter_chart, bar_chart, stacked_bar

st.title("📋 League Overview")

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.header("League Overview")
league_id = st.sidebar.selectbox(
    "Select League",
    options=list(LEAGUES.keys()),
    format_func=lambda x: LEAGUES[x],
)

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
tss_df     = load_team_season_stats()
odds_df    = load_odds()

if matches_df.empty:
    st.warning("No data loaded. Run `python data/pipeline.py` first.", icon="⚠️")
    st.stop()

# Filter
league_matches = matches_df[matches_df["league_id"] == league_id].copy()
league_teams   = teams_df[teams_df["league_id"] == league_id] if not teams_df.empty else pd.DataFrame()
league_tss     = tss_df[tss_df["league_id"] == league_id] if not tss_df.empty else pd.DataFrame()

_team_map = dict(zip(league_teams["id"], league_teams["name"])) if not league_teams.empty else {}

def tname(tid: str) -> str:
    return _team_map.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

st.header(LEAGUES[league_id])

# ── Standings table ────────────────────────────────────────────────────────
st.subheader("🏅 Standings")
if not league_tss.empty:
    standings = league_tss.copy()
    standings["Team"]  = standings["team_id"].apply(tname)
    standings["Diff"]  = standings["points_for"] - standings["points_against"]
    standings["Try Diff"] = standings["tries_for"] - standings["tries_against"]

    # Form arrows (simple: net wins)
    def form_arrow(row):
        if row["won"] > row["lost"]:
            return "↑"
        if row["won"] < row["lost"]:
            return "↓"
        return "→"

    standings["Form"] = standings.apply(form_arrow, axis=1)

    disp = standings[[
        "Team", "played", "won", "lost", "drawn",
        "points_for", "points_against", "Diff",
        "tries_for", "tries_against", "bonus_points", "league_points", "Form"
    ]].rename(columns={
        "played": "P", "won": "W", "lost": "L", "drawn": "D",
        "points_for": "PF", "points_against": "PA",
        "tries_for": "TF", "tries_against": "TA",
        "bonus_points": "BP", "league_points": "Pts",
    }).sort_values("Pts", ascending=False).reset_index(drop=True)

    disp.index += 1
    st.dataframe(disp, width='stretch')
else:
    st.info("Standings load after first pipeline run.")

# ── Efficiency scatter: PPG vs Tries PG ────────────────────────────────────
if not league_tss.empty and (league_tss["played"] > 0).any():
    st.subheader("⚡ Attack Efficiency — Points per Game vs Tries per Game")
    eff = league_tss.copy()
    eff = eff[eff["played"] > 0]
    eff["Team"]   = eff["team_id"].apply(tname)
    eff["PPG"]    = (eff["points_for"] / eff["played"]).round(1)
    eff["TPG"]    = (eff["tries_for"]  / eff["played"]).round(2)
    fig = scatter_chart(eff, x="TPG", y="PPG", text="Team",
                        title="Points per Game vs Tries per Game")
    # Add quadrant lines
    fig.add_hline(y=eff["PPG"].mean(), line_dash="dot", line_color="gray", opacity=0.5)
    fig.add_vline(x=eff["TPG"].mean(), line_dash="dot", line_color="gray", opacity=0.5)
    st.plotly_chart(fig, width='stretch')

# ── Home vs Away ────────────────────────────────────────────────────────────
st.subheader("🏠 Home vs Away Performance")
final = league_matches[league_matches["status"] == "final"]
if not final.empty:
    home_stats = final.groupby("home_team_id").agg(
        home_pts=("home_score", "mean"),
        home_tries=("home_tries", "mean"),
    ).reset_index().rename(columns={"home_team_id": "team_id"})

    away_stats = final.groupby("away_team_id").agg(
        away_pts=("away_score", "mean"),
        away_tries=("away_tries", "mean"),
    ).reset_index().rename(columns={"away_team_id": "team_id"})

    ha = home_stats.merge(away_stats, on="team_id", how="outer").fillna(0)
    ha["Team"] = ha["team_id"].apply(tname)

    col1, col2 = st.columns(2)
    with col1:
        fig = bar_chart(ha, x="Team", y="home_pts",
                        title="Avg Points Scored at Home")
        st.plotly_chart(fig, width='stretch')
    with col2:
        fig = bar_chart(ha, x="Team", y="away_pts",
                        title="Avg Points Scored Away")
        st.plotly_chart(fig, width='stretch')
else:
    st.info("Results will appear here once matches are completed.")

# ── Round-by-round results grid ────────────────────────────────────────────
st.subheader("📅 Round-by-Round Results")
if not final.empty and "round" in final.columns and final["round"].max() > 0:
    pivot = final.copy()
    pivot["Home"] = pivot["home_team_id"].apply(tname)
    pivot["Score"] = pivot["home_score"].astype(str) + "–" + pivot["away_score"].astype(str)
    rounds_df = pivot[["round", "Home", "Score"]].sort_values("round")
    st.dataframe(rounds_df.rename(columns={"round": "Round", "Home": "Home Team"}),
                 hide_index=True, width='stretch')
else:
    st.info("Round results will appear here once matches are completed.")

# ── Upcoming fixtures with odds ────────────────────────────────────────────
st.subheader("📆 Upcoming Fixtures")
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
upcoming = league_matches[
    (league_matches["kickoff_utc"] >= now) &
    (league_matches["status"] == "scheduled")
].sort_values("kickoff_utc")

if upcoming.empty:
    st.info("No upcoming fixtures in this league.")
else:
    if not odds_df.empty:
        lo = odds_df.sort_values("scraped_at").groupby("match_id").last().reset_index()
        upcoming = upcoming.merge(
            lo[["match_id", "home_ml", "away_ml", "total_line"]],
            left_on="id", right_on="match_id", how="left"
        )
    rows = []
    for _, m in upcoming.iterrows():
        row = {
            "Date":  pd.Timestamp(m["kickoff_utc"]).strftime("%d %b %H:%M"),
            "Home":  tname(m["home_team_id"]),
            "Away":  tname(m["away_team_id"]),
            "Venue": str(m.get("venue", "") or ""),
            "Rnd":   int(m.get("round", 0) or 0),
        }
        if "home_ml" in m and pd.notna(m.get("home_ml")):
            row["H ML"] = f"{int(m['home_ml']):+d}"
            row["A ML"] = f"{int(m['away_ml']):+d}" if pd.notna(m.get("away_ml")) else "—"
            row["O/U"]  = m.get("total_line", "—")
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')

# ── Season narrative ────────────────────────────────────────────────────────
if not league_tss.empty and (league_tss["played"] > 0).any():
    st.subheader("📰 Season Snapshot")
    top_team = league_tss.sort_values("league_points", ascending=False).iloc[0]
    t_name   = tname(top_team["team_id"])
    tpg      = round(top_team["tries_for"] / max(top_team["played"], 1), 1)
    ppg      = round(top_team["points_for"] / max(top_team["played"], 1), 1)

    if len(league_tss) > 1:
        second = league_tss.sort_values("league_points", ascending=False).iloc[1]
        gap    = int(top_team["league_points"] - second["league_points"])
        gap_str = f", {gap} pts clear at the top" if gap > 0 else " at the top"
    else:
        gap_str = " at the top"

    st.info(
        f"**{t_name}** lead {LEAGUES[league_id]}{gap_str}, "
        f"averaging {tpg} tries and {ppg} points per game."
    )

from footer import add_betting_oracle_footer
add_betting_oracle_footer()
