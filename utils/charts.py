"""Reusable Plotly chart builders for ScrumBet pages."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import streamlit as st


# ── Palette ──────────────────────────────────────────────────────────────────────────────
WIN_COLOR  = "#22c55e"
DRAW_COLOR = "#f59e0b"
LOSS_COLOR = "#ef4444"
PRIMARY    = "#5a9e10"
SECONDARY  = "#7c3aed"


def _chart_theme() -> dict:
    """Return Plotly layout kwargs matching the active ScrumBet theme."""
    try:
        from themes import ALL_THEMES
        name = st.session_state.get("theme_name", "Night (Dark)")
        t = ALL_THEMES.get(name, next(iter(ALL_THEMES.values())))
    except Exception:
        return {}
    fc = t["text"]
    gc = t["border"]
    return dict(
        paper_bgcolor=t["main_bg"],
        plot_bgcolor=t["main_bg"],
        font=dict(color=fc),
        title_font_color=fc,
        legend=dict(font=dict(color=fc)),
        xaxis=dict(
            gridcolor=gc, zerolinecolor=gc,
            tickfont=dict(color=fc), title_font=dict(color=fc),
        ),
        yaxis=dict(
            gridcolor=gc, zerolinecolor=gc,
            tickfont=dict(color=fc), title_font=dict(color=fc),
        ),
    )


def form_badge_html(result: str) -> str:
    colors = {"W": WIN_COLOR, "D": DRAW_COLOR, "L": LOSS_COLOR}
    bg = colors.get(result, "#6b7280")
    return (
        f'<span style="background:{bg};color:#fff;padding:2px 9px;'
        f'border-radius:5px;font-weight:700;margin-right:3px;">{result}</span>'
    )


def radar_chart(
    categories: list[str],
    values: list[float],
    title: str = "",
    color: str = PRIMARY,
) -> go.Figure:
    cats = categories + [categories[0]]
    vals = values + [values[0]]
    fig = go.Figure(
        go.Scatterpolar(r=vals, theta=cats, fill="toself", line_color=color)
    )
    ct = _chart_theme()
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, max(vals) * 1.1 or 1])),
        showlegend=False,
        title=title,
        height=360,
        margin=dict(l=30, r=30, t=50, b=30),
        **ct,
    )
    return fig


def elo_line_chart(df: pd.DataFrame, team_name: str = "") -> go.Figure:
    fig = px.line(
        df.sort_values("date"),
        x="date",
        y="rating",
        title=f"Elo Rating — {team_name}",
        labels={"date": "", "rating": "Elo"},
    )
    fig.update_traces(line_color=PRIMARY, line_width=2)
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0), **_chart_theme())
    return fig


def scoreline_heatmap(matrix: np.ndarray, max_val: int = 50) -> go.Figure:
    z = matrix[:max_val, :max_val]
    fig = go.Figure(
        go.Heatmap(z=z, colorscale="Blues", showscale=True)
    )
    fig.update_layout(
        xaxis_title="Away Score",
        yaxis_title="Home Score",
        height=420,
        margin=dict(l=60, r=20, t=20, b=60),
        **_chart_theme(),
    )
    return fig


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    title: str = "",
    orientation: str = "v",
    height: int = 320,
) -> go.Figure:
    fig = px.bar(df, x=x, y=y, color=color, title=title, orientation=orientation)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=40, b=0), **_chart_theme())
    return fig


def scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    text: str | None = None,
    title: str = "",
) -> go.Figure:
    fig = px.scatter(df, x=x, y=y, text=text, title=title)
    if text:
        fig.update_traces(textposition="top center")
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=40, b=0), **_chart_theme())
    return fig


def stacked_bar(
    df: pd.DataFrame,
    x: str,
    y_cols: list[str],
    title: str = "",
) -> go.Figure:
    fig = go.Figure()
    colors = [PRIMARY, SECONDARY, "#0ea5e9", "#10b981", "#f59e0b"]
    for i, col in enumerate(y_cols):
        fig.add_trace(
            go.Bar(
                name=col,
                x=df[x],
                y=df[col],
                marker_color=colors[i % len(colors)],
            )
        )
    fig.update_layout(barmode="stack", title=title, height=320,
                      margin=dict(l=0, r=0, t=40, b=0), **_chart_theme())
    return fig


def probability_bar(labels: list[str], probs: list[float]) -> go.Figure:
    colors = [PRIMARY, "#6b7280", SECONDARY]
    fig = go.Figure(
        go.Bar(x=labels, y=[p * 100 for p in probs],
               marker_color=colors[:len(labels)],
               text=[f"{p:.1%}" for p in probs],
               textposition="auto")
    )
    fig.update_layout(
        yaxis_title="Probability (%)",
        height=260,
        margin=dict(l=0, r=0, t=20, b=0),
        **_chart_theme(),
    )
    return fig


def histogram(values: list[float], title: str = "", xaxis_title: str = "") -> go.Figure:
    fig = go.Figure(go.Histogram(x=values, marker_color=PRIMARY, nbinsx=40))
    fig.update_layout(
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title="Frequency",
        height=320,
        margin=dict(l=0, r=0, t=40, b=0),
        **_chart_theme(),
    )
    return fig


def radar_chart_compare(
    categories: list[str],
    values_a: list[float],
    values_b: list[float],
    label_a: str = "Player A",
    label_b: str = "Player B",
    title: str = "",
) -> go.Figure:
    """Overlay radar chart for comparing two players / teams."""
    cats = categories + [categories[0]]
    v_a = values_a + [values_a[0]]
    v_b = values_b + [values_b[0]]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=v_a, theta=cats, fill="toself",
            name=label_a, line_color=PRIMARY, opacity=0.75,
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=v_b, theta=cats, fill="toself",
            name=label_b, line_color=SECONDARY, opacity=0.75,
        )
    )
    max_val = max(max(values_a), max(values_b), 1)
    ct = _chart_theme()
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, max_val * 1.1])),
        showlegend=True,
        title=title,
        height=400,
        margin=dict(l=30, r=30, t=50, b=30),
        **ct,
    )
    return fig


def line_movement_chart(
    history: pd.DataFrame,
    home_name: str = "Home",
    away_name: str = "Away",
) -> go.Figure:
    """Plot home_ml and away_ml over time for odds line-movement tracking."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history["scraped_at"],
            y=history["home_ml"],
            name=f"{home_name} ML",
            mode="lines+markers",
            line=dict(color="#3b82f6", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=history["scraped_at"],
            y=history["away_ml"],
            name=f"{away_name} ML",
            mode="lines+markers",
            line=dict(color="#ef4444", width=2),
        )
    )
    fig.update_layout(
        yaxis_title="American Odds",
        hovermode="x unified",
        height=360,
        margin=dict(l=0, r=0, t=20, b=0),
        **_chart_theme(),
    )
    return fig
