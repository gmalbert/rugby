"""
Page 2 — Team Deep Dive
Everything about one team: form, radar, Elo trend, H2H, venue stats.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from utils.cache import load_teams, load_matches, load_player_stats, load_elo_ratings
from utils.config import LEAGUES
from utils.charts import form_badge_html, radar_chart, elo_line_chart, stacked_bar, bar_chart

st.title("🔍 Team Deep Dive")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
player_df  = load_player_stats()
elo_df     = load_elo_ratings()

if matches_df.empty or teams_df.empty:
    st.warning("No data loaded. Run `python data/pipeline.py` first.", icon="⚠️")
    st.stop()

# ── Team selector ──────────────────────────────────────────────────────────
all_teams  = sorted(teams_df["name"].dropna().unique())
team_name  = st.sidebar.selectbox("Select Team", all_teams)

team_row = teams_df[teams_df["name"] == team_name].iloc[0]
team_id  = team_row["id"]
league_id = team_row["league_id"]

# Opponent selector for H2H
all_others = [n for n in all_teams if n != team_name]
opp_name   = st.sidebar.selectbox("H2H vs Opponent", all_others)
opp_row    = teams_df[teams_df["name"] == opp_name].iloc[0]
opp_id     = opp_row["id"]

_tmap = dict(zip(teams_df["id"], teams_df["name"]))
def tname(tid: str) -> str:
    return _tmap.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

st.header(f"{team_name}  ·  {LEAGUES.get(league_id, league_id)}")

# ── Form strip ─────────────────────────────────────────────────────────────
st.subheader("📊 Form Strip — Last 10 Results")
team_matches = matches_df[
    ((matches_df["home_team_id"] == team_id) | (matches_df["away_team_id"] == team_id))
    & (matches_df["status"] == "final")
].sort_values("kickoff_utc", ascending=False).head(10)

if team_matches.empty:
    st.info("No completed matches found for this team.")
else:
    badges_html = ""
    for _, row in team_matches.iterrows():
        is_home = row["home_team_id"] == team_id
        ts = row["home_score"] if is_home else row["away_score"]
        os = row["away_score"] if is_home else row["home_score"]
        result = "W" if ts > os else ("D" if ts == os else "L")
        opp    = tname(row["away_team_id"] if is_home else row["home_team_id"])
        badge  = form_badge_html(result)
        score  = f"{ts}–{os}"
        badges_html += f'{badge} <small style="color:#94a3b8">{opp} {score}</small> &nbsp; '

    st.markdown(badges_html, unsafe_allow_html=True)

st.divider()
col1, col2 = st.columns(2)

# ── Radar chart ────────────────────────────────────────────────────────────
with col1:
    st.subheader("⚡ Attack vs Defence Radar")
    final = matches_df[matches_df["status"] == "final"]
    if not final.empty:
        h_agg = final[final["home_team_id"] == team_id].agg(
            tries_for=("home_tries", "sum"),
            pts_for=("home_score", "sum"),
        )
        a_agg = final[final["away_team_id"] == team_id].agg(
            tries_away=("away_tries", "sum"),
            pts_away=("away_score", "sum"),
        )
        h_conc = final[final["home_team_id"] == team_id].agg(tries_against=("away_tries", "sum"))
        a_conc = final[final["away_team_id"] == team_id].agg(tries_against=("home_tries", "sum"))

        tries_scored   = int(h_agg.get("tries_for", 0))   + int(a_agg.get("tries_away", 0))
        tries_conceded = int(h_conc.get("tries_against", 0)) + int(a_conc.get("tries_against", 0))

        if not player_df.empty:
            tm_player = player_df[player_df["team_id"] == team_id]
            metres     = int(tm_player["metres_run"].sum())
            linebreaks = int(tm_player["linebreaks"].sum())
            tackles    = int(tm_player["tackles"].sum())
        else:
            metres, linebreaks, tackles = 0, 0, 0

        n = max(len(team_matches), 1)
        vals = [
            round(tries_scored / n, 1),
            round(max(10 - tries_conceded / n, 0), 1),
            round(metres / n / 100, 1),
            round(linebreaks / n, 1),
            round(tackles / n / 10, 1),
        ]
        fig = radar_chart(
            ["Tries Scored", "Tries Def", "Metres (×100)", "Linebreaks", "Tackles (×10)"],
            vals,
            title=team_name,
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Match data required for radar chart.")

# ── Elo rating chart ───────────────────────────────────────────────────────
with col2:
    st.subheader("📈 Elo Rating History")
    if not elo_df.empty:
        team_elo = elo_df[elo_df["team_id"] == team_id].sort_values("date")
        if not team_elo.empty:
            fig = elo_line_chart(team_elo, team_name)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No Elo history yet for this team.")
    else:
        st.info("Elo ratings load after first pipeline run.")

st.divider()

# ── Scoring breakdown ──────────────────────────────────────────────────────
st.subheader("🎯 Scoring Breakdown")
if not final.empty:
    home_pts   = final[final["home_team_id"] == team_id]["home_score"].sum()
    away_pts   = final[final["away_team_id"] == team_id]["away_score"].sum()
    home_tries = final[final["home_team_id"] == team_id]["home_tries"].sum()
    away_tries = final[final["away_team_id"] == team_id]["away_tries"].sum()
    total_tries = int(home_tries + away_tries)
    total_pts   = int(home_pts + away_pts)
    # Points from tries (5 pts + avg 2pt conversion = ~7 per try)
    try_pts   = total_tries * 7
    other_pts = max(total_pts - try_pts, 0)

    breakdown = pd.DataFrame({
        "Category": ["Try Points (est.)", "Penalties / Drops / Conv (est.)"],
        "Points":   [try_pts, other_pts],
    })
    fig = bar_chart(breakdown, x="Category", y="Points",
                    title=f"{team_name} — Points Origin (season total)")
    st.plotly_chart(fig, width='stretch')

# ── Key players ────────────────────────────────────────────────────────────
st.subheader("⭐ Key Players This Season")
if not player_df.empty:
    tm = player_df[player_df["team_id"] == team_id]
    if not tm.empty:
        top_try = tm.groupby(["player_id", "player_name"])["tries"].sum().nlargest(5).reset_index()
        top_met = tm.groupby(["player_id", "player_name"])["metres_run"].sum().nlargest(5).reset_index()
        top_tac = tm.groupby(["player_id", "player_name"])["tackles"].sum().nlargest(5).reset_index()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Top Try Scorers**")
            st.dataframe(top_try[["player_name", "tries"]].rename(
                columns={"player_name": "Player", "tries": "Tries"}),
                hide_index=True, width='stretch')
        with c2:
            st.markdown("**Top Metres Carriers**")
            st.dataframe(top_met[["player_name", "metres_run"]].rename(
                columns={"player_name": "Player", "metres_run": "Metres"}),
                hide_index=True, width='stretch')
        with c3:
            st.markdown("**Top Tacklers**")
            st.dataframe(top_tac[["player_name", "tackles"]].rename(
                columns={"player_name": "Player", "tackles": "Tackles"}),
                hide_index=True, width='stretch')
    else:
        st.info("No player stats for this team yet.")
else:
    st.info("Player data loads after first pipeline run.")

st.divider()

# ── Head-to-Head ───────────────────────────────────────────────────────────
st.subheader(f"⚔️ Head-to-Head vs {opp_name}")
h2h = matches_df[
    (
        ((matches_df["home_team_id"] == team_id) & (matches_df["away_team_id"] == opp_id)) |
        ((matches_df["home_team_id"] == opp_id)  & (matches_df["away_team_id"] == team_id))
    ) & (matches_df["status"] == "final")
].sort_values("kickoff_utc", ascending=False).head(10)

if h2h.empty:
    st.info(f"No head-to-head history found between {team_name} and {opp_name}.")
else:
    rows = []
    for _, row in h2h.iterrows():
        is_home = row["home_team_id"] == team_id
        ts = row["home_score"] if is_home else row["away_score"]
        os = row["away_score"] if is_home else row["home_score"]
        result = "W" if ts > os else ("D" if ts == os else "L")
        rows.append({
            "Date":   pd.Timestamp(row["kickoff_utc"]).strftime("%d %b %Y"),
            "Home":   tname(row["home_team_id"]),
            "Score":  f"{row['home_score']}–{row['away_score']}",
            "Away":   tname(row["away_team_id"]),
            "Result": result,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')

# ── Venue stats ────────────────────────────────────────────────────────────
st.subheader("🏟️ Venue Stats — Home vs Away Split")
if not final.empty:
    h_games = final[final["home_team_id"] == team_id]
    a_games = final[final["away_team_id"] == team_id]

    h_wins  = (h_games["home_score"] > h_games["away_score"]).sum()
    a_wins  = (a_games["away_score"] > a_games["home_score"]).sum()

    venue_data = pd.DataFrame({
        "Split":      ["Home", "Away"],
        "Games":      [len(h_games), len(a_games)],
        "Wins":       [h_wins, a_wins],
        "Avg Pts For": [
            round(h_games["home_score"].mean(), 1) if not h_games.empty else 0,
            round(a_games["away_score"].mean(), 1) if not a_games.empty else 0,
        ],
        "Avg Pts Against": [
            round(h_games["away_score"].mean(), 1) if not h_games.empty else 0,
            round(a_games["home_score"].mean(), 1) if not a_games.empty else 0,
        ],
    })
    st.dataframe(venue_data, hide_index=True, width='stretch')

from footer import add_betting_oracle_footer
add_betting_oracle_footer()
