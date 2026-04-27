"""
ScrumBet — Home Dashboard
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

from utils.cache import (
    load_leagues, load_teams, load_matches,
    load_odds, load_player_stats,
)
from utils.config import LEAGUES
from utils.charts import form_badge_html
from scripts.scrapers.sofascore import fetch_live_scores
from footer import add_betting_oracle_footer
from themes import apply_theme

# ── Called ONCE here — sub-pages must NOT call set_page_config ───────────
st.set_page_config(
    page_title="ScrumBet — Rugby Analytics",
    page_icon="🏉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auto theme: Emerald Isle 06:00–20:00, Night (Dark) 20:00–06:00 ─────────
# JS injects ?hour=N via window.parent (st.iframe renders in a real iframe).
# Guard: only redirects when the value is absent or stale — no infinite loop.
st.iframe(
    """
    <script>
    const h = new Date().getHours();
    const url = new URL(window.parent.location.href);
    const existing = url.searchParams.get('hour');
    if (existing === null || parseInt(existing, 10) !== h) {
        url.searchParams.set('hour', h);
        window.parent.location.replace(url.toString());
    }
    </script>
    """,
    height=10,
)

_hour_param = st.query_params.get("hour", None)
if _hour_param is not None:
    try:
        _browser_hour = int(_hour_param)
    except ValueError:
        _browser_hour = 12
else:
    _browser_hour = 12

_theme_name = "Emerald Isle" if 6 <= _browser_hour < 20 else "Night (Dark)"
st.session_state["theme_name"] = _theme_name

# ── Shared sidebar items (visible on every page) ───────────────────────────
logo_path = "data_files/logo.png"
try:
    st.sidebar.image(logo_path, width='stretch')
except Exception:
    st.sidebar.title("🏉 ScrumBet")

apply_theme(_theme_name)

st.sidebar.divider()
if st.sidebar.button("🔄 Refresh cache"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.caption("Data: ESPN API · RugbyPass · SofaScore · The Odds API")


def home_page() -> None:
    """Landing page — fixtures, live scores, odds snapshot, form."""

    # ── Home-specific sidebar ──────────────────────────────────────────────
    league_filter = st.sidebar.multiselect(
        "Filter Leagues",
        options=list(LEAGUES.keys()),
        default=list(LEAGUES.keys()),
        format_func=lambda x: LEAGUES[x],
    )

    # ── Header ────────────────────────────────────────────────────────────
    st.title("ScrumBet")
    st.caption("European rugby analytics & DraftKings betting intelligence")

# ── Load data ──────────────────────────────────────────────────────────────
    # ── Load data ──────────────────────────────────────────────────────────
    teams_df   = load_teams()
    matches_df = load_matches()
    odds_df    = load_odds()
    player_df  = load_player_stats()

    if matches_df.empty:
        st.warning(
            "No match data loaded yet. Run `python scripts/pipeline.py` to populate the database.",
            icon="⚠️",
        )
        st.info("Once the pipeline has run, this dashboard will show live fixtures, odds, form, and try scorer stats.")
        st.stop()

    # Apply league filter
    if league_filter:
        matches_df = matches_df[matches_df["league_id"].isin(league_filter)]

    # ── Helper: team name lookup ───────────────────────────────────────────
    _team_map: dict[str, str] = (
        dict(zip(teams_df["id"], teams_df["name"]))
        if not teams_df.empty else {}
    )

    def team_name(tid: str) -> str:
        return _team_map.get(tid, tid.split("-", 1)[-1].replace("-", " ").title())

    # ── Helper: last-N form ────────────────────────────────────────────────
    def team_form(team_id: str, n: int = 5) -> list[str]:
        m = matches_df[
            ((matches_df["home_team_id"] == team_id) | (matches_df["away_team_id"] == team_id))
            & (matches_df["status"] == "final")
        ].sort_values("kickoff_utc", ascending=False).head(n)
        results = []
        for _, row in m.iterrows():
            is_home = row["home_team_id"] == team_id
            ts = row["home_score"] if is_home else row["away_score"]
            os = row["away_score"] if is_home else row["home_score"]
            results.append("W" if ts > os else ("D" if ts == os else "L"))
        return results

    # ── Time bounds ────────────────────────────────────────────────────────
    now        = datetime.now(timezone.utc)
    week_ahead = now + timedelta(days=7)

    upcoming = matches_df[
        (matches_df["kickoff_utc"] >= now) &
        (matches_df["kickoff_utc"] <= week_ahead) &
        (matches_df["status"] == "scheduled")
    ].sort_values("kickoff_utc")

    live_matches = matches_df[matches_df["status"] == "live"].sort_values("kickoff_utc")

    # ── Latest odds per match ──────────────────────────────────────────────
    latest_odds = pd.DataFrame()
    if not odds_df.empty:
        latest_odds = (
            odds_df.sort_values("scraped_at")
                   .groupby("match_id")
                   .last()
                   .reset_index()
        )

    # ── Layout ────────────────────────────────────────────────────────────
    col_fix, col_live, col_scorers = st.columns([2.5, 1.1, 1.4])

    # ── Column 1: Upcoming fixtures ────────────────────────────────────────
    with col_fix:
        st.subheader("📅 This Week's Fixtures")
        if upcoming.empty:
            st.info("No fixtures in the next 7 days for selected leagues.")
        else:
            if not latest_odds.empty:
                upcoming = upcoming.merge(
                    latest_odds[["match_id", "home_ml", "away_ml"]],
                    left_on="id", right_on="match_id", how="left",
                )

            for day_ts, day_df in upcoming.groupby(
                upcoming["kickoff_utc"].dt.floor("D")
            ):
                st.markdown(f"**{pd.Timestamp(day_ts).strftime('%A, %d %b')}**")
                rows = []
                for _, m in day_df.iterrows():
                    home = team_name(m["home_team_id"])
                    away = team_name(m["away_team_id"])
                    ko   = pd.Timestamp(m["kickoff_utc"]).strftime("%H:%M")
                    row  = {
                        "League":   LEAGUES.get(m["league_id"], m["league_id"]),
                        "KO (UTC)": ko,
                        "Home":     home,
                        "Away":     away,
                        "Venue":    str(m.get("venue", "") or ""),
                    }
                    if "home_ml" in m and pd.notna(m.get("home_ml")):
                        row["Home ML"] = f"{int(m['home_ml']):+d}"
                        row["Away ML"] = f"{int(m['away_ml']):+d}" if pd.notna(m.get("away_ml")) else "—"
                    rows.append(row)
                st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
                st.write("")

    # ── Column 2: Live ticker ──────────────────────────────────────────────
    with col_live:
        st.subheader("🔴 Live")

        try:
            sofa_live = fetch_live_scores()
        except Exception:
            sofa_live = pd.DataFrame()

        if not sofa_live.empty:
            for _, m in sofa_live.iterrows():
                label = f"{m['home_team']} v {m['away_team']}"
                score = f"{m['home_score']} – {m['away_score']}"
                st.metric(label, score, delta=m.get("minute", ""))
        elif not live_matches.empty:
            for _, m in live_matches.iterrows():
                label = f"{team_name(m['home_team_id'])} v {team_name(m['away_team_id'])}"
                score = f"{m['home_score']} – {m['away_score']}"
                st.metric(label, score)
        else:
            st.info("No live matches.")

        if not upcoming.empty and not latest_odds.empty:
            st.subheader("💰 DK Odds (Next 7 Days)")
            snap = upcoming.merge(
                latest_odds[["match_id", "home_ml", "away_ml", "total_line"]],
                left_on="id", right_on="match_id", how="inner",
            )
            if not snap.empty:
                snap_rows = []
                for _, m in snap.iterrows():
                    snap_rows.append({
                        "Match": f"{team_name(m['home_team_id'])} v {team_name(m['away_team_id'])}",
                        "H ML":  f"{int(m['home_ml']):+d}" if pd.notna(m.get("home_ml")) else "—",
                        "A ML":  f"{int(m['away_ml']):+d}" if pd.notna(m.get("away_ml")) else "—",
                        "O/U":   m.get("total_line", "—"),
                    })
                st.dataframe(pd.DataFrame(snap_rows), hide_index=True, width='stretch')

    # ── Column 3: Try scorer leaderboard ──────────────────────────────────
    with col_scorers:
        st.subheader("🏆 Top Try Scorers")
        if not player_df.empty and not matches_df.empty:
            _mdf = matches_df[["id", "league_id"]].copy()
            _mdf["id"] = _mdf["id"].astype(str)
            # Drop league_id from player_df first — the parquet may already carry it,
            # which would cause pandas to suffix both copies and lose the plain name.
            _pdf = player_df.drop(columns=["league_id"], errors="ignore").copy()
            _pdf["match_id"] = _pdf["match_id"].astype(str)
            ps = _pdf.merge(_mdf, left_on="match_id", right_on="id", how="left")
            if league_filter:
                ps = ps[ps["league_id"].isin(league_filter)]

            top = (
                ps.groupby(["player_id", "player_name", "team_id"])["tries"]
                  .sum()
                  .reset_index()
                  .sort_values("tries", ascending=False)
                  .head(10)
            )
            top["Team"] = top["team_id"].apply(team_name)
            st.dataframe(
                top[["player_name", "Team", "tries"]].rename(
                    columns={"player_name": "Player", "tries": "Tries"}
                ),
                hide_index=True,
                width='stretch',
            )
        else:
            st.info("Player stats load after first pipeline run.")

    # ── Form heatmap ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Team Form — Last 5 Results")

    teams_in_view: set[str] = set()
    if not upcoming.empty:
        teams_in_view = set(upcoming["home_team_id"]) | set(upcoming["away_team_id"])

    if teams_in_view:
        form_data = {team_name(tid): team_form(tid) for tid in sorted(teams_in_view)}
        cols_per_row = 4
        items = list(form_data.items())
        for i in range(0, len(items), cols_per_row):
            row_cols = st.columns(cols_per_row)
            for j, (name, results) in enumerate(items[i : i + cols_per_row]):
                with row_cols[j]:
                    badges = "".join(form_badge_html(r) for r in results) if results else "<em>No data</em>"
                    st.markdown(f"**{name}**<br>{badges}", unsafe_allow_html=True)
    else:
        st.info("Form data will appear here once fixtures are loaded.")

    add_betting_oracle_footer()


# ── Navigation ─────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "": [
            st.Page(home_page, title="Home", icon="🏉", default=True),
        ],
        "Analytics": [
            st.Page("pages/1_League_Overview.py", title="League Overview", icon="🏆"),
            st.Page("pages/2_Team_Deep_Dive.py",  title="Team Deep Dive",  icon="📊"),
            st.Page("pages/3_Player_Stats.py",    title="Player Stats",    icon="👟"),
            st.Page("pages/4_Match_Analysis.py",  title="Match Analysis",  icon="🔍"),
            st.Page("pages/9_Player_Compare.py",  title="Player Compare",  icon="🔬"),
        ],
        "Betting": [
            st.Page("pages/5_Betting_Edge.py",    title="Betting Edge",    icon="⚡"),
            st.Page("pages/7_Line_Movement.py",   title="Line Movement",   icon="📉"),
        ],
        "Models": [
            st.Page("pages/6_Model_Lab.py",       title="Model Lab",       icon="🧪"),
            st.Page("pages/8_Tournament_Sim.py",  title="Tournament Sim",  icon="🎯"),
        ],
    }
)
pg.run()

