"""
Page 9 — Player Comparison Tool
Side-by-side radar comparison of any two players using season stats.
"""

import streamlit as st
import pandas as pd

from utils.cache import load_teams, load_matches, load_player_stats
from utils.config import LEAGUES
from utils.charts import radar_chart_compare, bar_chart
from footer import add_betting_oracle_footer

st.title("🔬 Player Comparison")
st.caption("Side-by-side radar comparison of any two players across all tracked stats.")

# ── Load data ──────────────────────────────────────────────────────────────
teams_df   = load_teams()
matches_df = load_matches()
player_df  = load_player_stats()

if player_df.empty:
    st.warning(
        "No player stats loaded yet. Run `python data/pipeline.py` to populate.",
        icon="⚠️",
    )
    st.stop()

_tmap = dict(zip(teams_df["id"], teams_df["name"])) if not teams_df.empty else {}

def tname(tid: str) -> str:
    return _tmap.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

# ── Merge league info ──────────────────────────────────────────────────────
if not matches_df.empty:
    _mdf = matches_df[["id", "league_id"]].copy()
    _mdf["id"] = _mdf["id"].astype(str)
    _pdf = player_df.drop(columns=["league_id"], errors="ignore").copy()
    _pdf["match_id"] = _pdf["match_id"].astype(str)
    ps = _pdf.merge(_mdf, left_on="match_id", right_on="id", how="left")
else:
    ps = player_df.copy()
    ps["league_id"] = ""

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.header("Player Comparison")
league_filter = st.sidebar.multiselect(
    "Filter by League",
    options=list(LEAGUES.keys()),
    default=list(LEAGUES.keys()),
    format_func=lambda x: LEAGUES[x],
)
position_filter = st.sidebar.multiselect(
    "Filter by Position",
    options=sorted(ps["position"].dropna().unique()),
    default=[],
)

if league_filter:
    ps = ps[ps["league_id"].isin(league_filter)]
if position_filter:
    ps = ps[ps["position"].isin(position_filter)]

# ── Build per-player aggregates ────────────────────────────────────────────
COMPARE_STATS = ["tries", "metres_run", "tackles", "missed_tackles", "linebreaks"]
if "carries" in ps.columns:
    COMPARE_STATS.insert(1, "carries")
if "assists" in ps.columns:
    COMPARE_STATS.append("assists")

agg_dict = {s: "sum" for s in COMPARE_STATS if s in ps.columns}
agg_dict["match_id"] = "nunique"
agg_dict["minutes_played"] = "sum"

player_agg = (
    ps.groupby(["player_id", "player_name", "team_id", "position"])
      .agg(agg_dict)
      .reset_index()
      .rename(columns={"match_id": "games"})
)
player_agg["Team"] = player_agg["team_id"].apply(tname)
player_agg = player_agg[player_agg["games"] > 0]

all_players = sorted(player_agg["player_name"].dropna().unique())
if len(all_players) < 2:
    st.info("Not enough players for comparison with the current filters.")
    st.stop()

# ── Player selectors ───────────────────────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    player_a = st.selectbox("🔵 Player A", all_players, index=0)
with col_b:
    default_b = 1 if len(all_players) > 1 else 0
    player_b  = st.selectbox("🔴 Player B", all_players, index=default_b)

row_a = player_agg[player_agg["player_name"] == player_a].iloc[0]
row_b = player_agg[player_agg["player_name"] == player_b].iloc[0]

# ── Top-line metrics ───────────────────────────────────────────────────────
st.divider()
ca, cb = st.columns(2)
with ca:
    st.subheader(f"🔵 {player_a}")
    st.caption(f"{row_a['Team']}  ·  {row_a['position']}")
    st.metric("Games",   int(row_a["games"]))
    st.metric("Tries",   int(row_a.get("tries", 0)))
    st.metric("Metres",  int(row_a.get("metres_run", 0)))
    st.metric("Tackles", int(row_a.get("tackles", 0)))
with cb:
    st.subheader(f"🔴 {player_b}")
    st.caption(f"{row_b['Team']}  ·  {row_b['position']}")
    st.metric("Games",   int(row_b["games"]))
    st.metric("Tries",   int(row_b.get("tries", 0)))
    st.metric("Metres",  int(row_b.get("metres_run", 0)))
    st.metric("Tackles", int(row_b.get("tackles", 0)))

st.divider()

# ── Build per-game averages for radar ─────────────────────────────────────
stat_labels = {
    "tries":          "Tries/Game",
    "carries":        "Carries/Game",
    "metres_run":     "Metres/Game (÷10)",
    "linebreaks":     "Linebreaks/Game",
    "tackles":        "Tackles/Game",
    "missed_tackles": "Miss Tackles/Game",
    "assists":        "Assists/Game",
}
available = [s for s in COMPARE_STATS if s in player_agg.columns]

def _per_game(row: pd.Series, stat: str) -> float:
    games = max(int(row.get("games", 1)), 1)
    raw   = float(row.get(stat, 0) or 0)
    val   = raw / games
    # Scale metres so it's on a comparable axis with other stats
    if stat == "metres_run":
        val /= 10
    return round(val, 2)

vals_a = [_per_game(row_a, s) for s in available]
vals_b = [_per_game(row_b, s) for s in available]
labels = [stat_labels.get(s, s) for s in available]

# ── Radar chart ────────────────────────────────────────────────────────────
st.subheader("⚡ Radar Comparison (per-game averages)")
fig = radar_chart_compare(labels, vals_a, vals_b, label_a=player_a, label_b=player_b)
st.plotly_chart(fig, width='stretch')

st.divider()

# ── Bar chart comparison ───────────────────────────────────────────────────
st.subheader("📊 Season Totals — Side by Side")
stat_select = st.selectbox(
    "Choose stat",
    options=available,
    format_func=lambda s: stat_labels.get(s, s),
)

bar_data = pd.DataFrame({
    "Player": [player_a, player_b],
    stat_select: [
        float(row_a.get(stat_select, 0) or 0),
        float(row_b.get(stat_select, 0) or 0),
    ],
    "Color": ["#3b82f6", "#ef4444"],
})
fig_bar = bar_chart(bar_data, x="Player", y=stat_select, color="Color",
                    title=f"Season {stat_labels.get(stat_select, stat_select)}")
st.plotly_chart(fig_bar, width='stretch')

# ── Per-game stat table ────────────────────────────────────────────────────
st.subheader("📋 Full Stats Table")
compare_rows = []
for stat in available:
    compare_rows.append({
        "Stat":                  stat_labels.get(stat, stat),
        f"{player_a} (total)":   int(row_a.get(stat, 0) or 0),
        f"{player_a} (per game)": _per_game(row_a, stat),
        f"{player_b} (total)":   int(row_b.get(stat, 0) or 0),
        f"{player_b} (per game)": _per_game(row_b, stat),
    })
st.dataframe(pd.DataFrame(compare_rows), hide_index=True, width='stretch')

# ── CSV download ───────────────────────────────────────────────────────────
import io
buf = io.StringIO()
pd.DataFrame(compare_rows).to_csv(buf, index=False)
st.download_button(
    "Download Comparison CSV",
    data=buf.getvalue(),
    file_name=f"{player_a}_vs_{player_b}_comparison.csv",
    mime="text/csv",
)

add_betting_oracle_footer()
