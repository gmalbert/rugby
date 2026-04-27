"""
Page 3 — Player Stats
Try scorer rankings, player profiles, prop bet analyzer.
"""

import streamlit as st
import pandas as pd

from utils.cache import load_teams, load_matches, load_player_stats
from utils.config import LEAGUES
from utils.charts import bar_chart
from utils.odds import american_to_implied, expected_value

st.title("👤 Player Stats & Try Scorer Props")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
player_df  = load_player_stats()

if player_df.empty:
    st.warning(
        "No player stats loaded. Run `python scripts/pipeline.py` to fetch match data.",
        icon="⚠️",
    )
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────
league_filter = st.sidebar.multiselect(
    "Leagues",
    options=list(LEAGUES.keys()),
    default=list(LEAGUES.keys()),
    format_func=lambda x: LEAGUES[x],
)
position_filter = st.sidebar.multiselect(
    "Positions",
    options=sorted(player_df["position"].dropna().unique()),
    default=[],
)

_tmap = dict(zip(teams_df["id"], teams_df["name"])) if not teams_df.empty else {}
def tname(tid: str) -> str:
    return _tmap.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

# ── Merge match league info into player stats ──────────────────────────────
if not matches_df.empty:
    _mdf = matches_df[["id", "league_id"]].copy()
    _mdf["id"] = _mdf["id"].astype(str)
    _pdf = player_df.drop(columns=["league_id"], errors="ignore").copy()
    _pdf["match_id"] = _pdf["match_id"].astype(str)
    ps = _pdf.merge(_mdf, left_on="match_id", right_on="id", how="left")
else:
    ps = player_df.copy()
    ps["league_id"] = ""

if league_filter:
    ps = ps[ps["league_id"].isin(league_filter)]
if position_filter:
    ps = ps[ps["position"].isin(position_filter)]

# ── Try Scorer Rankings ────────────────────────────────────────────────────
st.subheader("🏆 Try Scorer Rankings")

try_ranks = (
    ps.groupby(["player_id", "player_name", "team_id", "position"])
      .agg(
          tries=("tries", "sum"),
          games=("match_id", "nunique"),
          metres=("metres_run", "sum"),
          tackles=("tackles", "sum"),
      )
      .reset_index()
)
try_ranks = try_ranks[try_ranks["tries"] > 0].copy()
try_ranks["tries_per_game"] = (try_ranks["tries"] / try_ranks["games"].clip(1)).round(2)
try_ranks["Team"]  = try_ranks["team_id"].apply(tname)

# Last 3 games tries
last3 = (
    ps.sort_values("match_id")
      .groupby("player_id")
      .tail(3)
      .groupby("player_id")["tries"]
      .sum()
      .rename("last3_tries")
)
try_ranks = try_ranks.merge(last3, on="player_id", how="left").fillna({"last3_tries": 0})
try_ranks["last3_tries"] = try_ranks["last3_tries"].astype(int)

disp = try_ranks.sort_values("tries", ascending=False).reset_index(drop=True)
disp.index += 1
st.dataframe(
    disp[["player_name", "Team", "position", "tries", "games", "tries_per_game", "last3_tries"]].rename(columns={
        "player_name": "Player", "position": "Pos",
        "tries": "Tries", "games": "Games",
        "tries_per_game": "T/Game", "last3_tries": "Last 3"
    }),
    width='stretch',
)

st.divider()

# ── Player Profile ─────────────────────────────────────────────────────────
st.subheader("👤 Player Profile")
all_players = sorted(ps["player_name"].dropna().unique())
if not all_players:
    st.info("No players available for selected filters.")
else:
    selected_player = st.selectbox("Select Player", all_players)
    player_rows = ps[ps["player_name"] == selected_player].copy()

    if not player_rows.empty:
        pid = player_rows["player_id"].iloc[0]
        team = tname(player_rows["team_id"].iloc[0])
        pos  = player_rows["position"].iloc[0]
        total_tries = int(player_rows["tries"].sum())
        total_games = player_rows["match_id"].nunique()
        tpg = round(total_tries / max(total_games, 1), 2)
        consistency = round((player_rows.groupby("match_id")["tries"].sum() >= 1).mean() * 100, 1)
        avg_mins = round(player_rows["minutes_played"].mean(), 0)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Team", team)
        c2.metric("Position", pos)
        c3.metric("Tries This Season", total_tries)
        c4.metric("Tries per Game", tpg)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown(f"**Consistency Score:** {consistency}% of games with ≥1 try")
            st.markdown(f"**Avg Minutes Played:** {avg_mins:.0f}")

            # Try scoring by round/match
            if not matches_df.empty:
                _rdf = matches_df[["id", "round"]].copy()
                _rdf["id"] = _rdf["id"].astype(str)
                _prows = player_rows.copy()
                _prows["match_id"] = _prows["match_id"].astype(str)
                round_tries = _prows.merge(_rdf, left_on="match_id", right_on="id", how="left")
            else:
                round_tries = player_rows
            if "round" in round_tries.columns:
                rt = round_tries.groupby("round")["tries"].sum().reset_index()
                fig = bar_chart(rt, x="round", y="tries",
                                title=f"{selected_player} — Tries by Round")
                st.plotly_chart(fig, width='stretch')

        with col_b:
            # Minutes played trend
            mp = player_rows.sort_values("match_id")[["match_id", "minutes_played"]].copy()
            mp["Game #"] = range(1, len(mp) + 1)
            fig = bar_chart(mp, x="Game #", y="minutes_played",
                            title=f"{selected_player} — Minutes Played")
            st.plotly_chart(fig, width='stretch')

st.divider()

# ── Prop Bet Analyzer ──────────────────────────────────────────────────────
st.subheader("💰 Prop Bet Analyzer")
st.caption("Enter a DraftKings try scorer line and compare against model probability.")

col_pa, col_pb = st.columns([1, 1])
with col_pa:
    prop_player = st.selectbox("Player", all_players, key="prop_player")
    dk_odds_input = st.number_input(
        "DraftKings Odds (American, e.g. +150 or -120)",
        value=150, step=5,
    )
with col_pb:
    if prop_player and not ps.empty:
        prop_rows = ps[ps["player_name"] == prop_player]
        if not prop_rows.empty:
            # Simple model: historical scoring rate as probability
            games_with_try = (
                prop_rows.groupby("match_id")["tries"].sum() >= 1
            ).sum()
            total_prop_games = prop_rows["match_id"].nunique()
            model_prob = games_with_try / max(total_prop_games, 1)
            dk_implied = american_to_implied(dk_odds_input)
            edge       = model_prob - dk_implied
            ev_val     = expected_value(model_prob, dk_odds_input)

            st.metric("Model Probability", f"{model_prob:.1%}")
            st.metric("DK Implied Probability", f"{dk_implied:.1%}")
            st.metric("Edge", f"{edge:+.1%}", delta_color="normal")
            st.metric("Expected Value (per $1)", f"${ev_val:.2f}")

            if edge >= 0.05:
                st.success(f"✅ +Edge detected — model gives {edge:.1%} advantage over DK line.")
            elif edge <= -0.05:
                st.error(f"🔴 Negative edge — DK line is {-edge:.1%} better than model.")
            else:
                st.info("Roughly fair value — edge within 5%.")
        else:
            st.info("No stats for selected player.")
from footer import add_betting_oracle_footer
add_betting_oracle_footer()