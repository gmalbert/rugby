"""
Page 8 — Tournament Bracket Simulator
Monte Carlo knockout bracket simulation seeded by current Elo ratings.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from utils.cache import load_teams, load_elo_ratings
from utils.config import LEAGUES
import models.elo as elo_model
from models.season_sim import simulate_ko_bracket, simulate_ko_bracket_rounds
from footer import add_betting_oracle_footer

st.title("🎯 Tournament Bracket Simulator")
st.caption("Monte Carlo knockout bracket simulation seeded by current Elo ratings.")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df = load_teams()
elo_df   = load_elo_ratings()

if elo_df.empty or teams_df.empty:
    st.warning("Elo ratings required. Run `python scripts/pipeline.py` first.", icon="⚠️")
    st.stop()

_tmap = dict(zip(teams_df["id"], teams_df["name"])) if not teams_df.empty else {}

def tname(tid: str) -> str:
    return _tmap.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

ratings = elo_model.current_ratings(elo_df)

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.header("Tournament Simulator")
league_id = st.sidebar.selectbox(
    "Competition",
    options=list(LEAGUES.keys()),
    format_func=lambda x: LEAGUES[x],
)

bracket_size = st.sidebar.selectbox(
    "Bracket size",
    options=[2, 4, 8, 16],
    index=2,
    format_func=lambda x: f"{x} teams",
)

n_sims = st.sidebar.slider("Simulations", 1_000, 20_000, 10_000, step=1_000)

# ── Team selection ─────────────────────────────────────────────────────────
st.subheader("🏟️ Build Your Bracket")

league_team_ids = (
    teams_df[teams_df["league_id"] == league_id]["id"].tolist()
    if not teams_df.empty else []
)

# Default seeds: top N by Elo from the selected competition
default_ids = sorted(league_team_ids, key=lambda t: -ratings.get(t, 1500))[:bracket_size]
default_names = [tname(t) for t in default_ids]

all_team_names = sorted(_tmap.values())

selected_names = st.multiselect(
    f"Select exactly {bracket_size} teams (ordered = seeding: 1 vs 2, 3 vs 4, …)",
    options=all_team_names,
    default=default_names[:bracket_size],
    max_selections=bracket_size,
)

if len(selected_names) != bracket_size:
    st.warning(f"Select exactly {bracket_size} teams to continue.")
    st.stop()

# Resolve names → IDs
name_to_id = {v: k for k, v in _tmap.items()}
seeds = [name_to_id[n] for n in selected_names if n in name_to_id]

if len(seeds) != bracket_size:
    st.error("Could not resolve all team names to IDs. Try re-selecting teams.")
    st.stop()

# ── Show current Elo ratings for selected teams ────────────────────────────
seed_df = pd.DataFrame({
    "Seed": range(1, bracket_size + 1),
    "Team": selected_names,
    "Elo Rating": [int(ratings.get(name_to_id.get(n, ""), 1500)) for n in selected_names],
})
st.dataframe(seed_df, hide_index=True, width='stretch')

st.divider()

# ── Run simulation ─────────────────────────────────────────────────────────
if st.button(f"▶ Run {n_sims:,} Simulations", type="primary"):
    with st.spinner("Simulating…"):
        title_result = simulate_ko_bracket(seeds, ratings.to_dict(), n=n_sims)
        round_result = simulate_ko_bracket_rounds(seeds, ratings.to_dict(), n=n_sims)

    title_result["Team"]   = title_result["team_id"].apply(tname)
    title_result["Rating"] = title_result["team_id"].apply(
        lambda t: int(ratings.get(t, 1500))
    )
    title_result["Win %"]  = (title_result["title_prob"] * 100).round(1).astype(str) + "%"

    col_tbl, col_chart = st.columns([1, 2])

    with col_tbl:
        st.subheader("🏆 Title Probability")
        st.dataframe(
            title_result[["Team", "Rating", "Win %"]].reset_index(drop=True),
            hide_index=True,
            width='stretch',
        )

    with col_chart:
        fig = px.bar(
            title_result,
            x="Team",
            y="title_prob",
            labels={"title_prob": "Win Probability"},
            title=f"Tournament Win Probability — {n_sims:,} simulations",
            color="title_prob",
            color_continuous_scale="Greens",
        )
        fig.update_traces(
            text=(title_result["title_prob"] * 100).round(1).astype(str) + "%",
            textposition="auto",
        )
        fig.update_layout(height=360, margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
        st.plotly_chart(fig, width='stretch')

    # Round-by-round breakdown
    if not round_result.empty:
        st.subheader("📊 Round-by-Round Progression")
        round_result["Team"] = round_result["team_id"].apply(tname)
        round_cols = [c for c in round_result.columns if c not in ("team_id",)]
        st.dataframe(
            round_result[["Team"] + [c for c in round_cols if c != "Team"]],
            hide_index=True,
            width='stretch',
        )

add_betting_oracle_footer()
