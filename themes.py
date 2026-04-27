"""
ScrumBet — Theme system

10 Night (dark) themes + 10 complementary day themes derived from the ScrumBet logo
palette: dark forest green · bright lime green · white.

Usage
-----
    from themes import apply_theme, THEME_NAMES, plotly_theme, render_table

    # Sidebar selector (call at module level so all pages get the CSS)
    st.sidebar.selectbox("🎨 Theme", THEME_NAMES, key="theme_name")
    apply_theme(st.session_state.get("theme_name", "Night (Dark)"))

    # In any page that uses Plotly
    fig.update_layout(**plotly_theme())

La Liga learnings applied here:
- Every Streamlit CSS selector is covered with !important
- Dropdown/portal menus receive their own rules (they render outside .stApp)
- Sidebar text, inputs, and alert boxes all have explicit overrides
- Use render_table() for HTML tables instead of bare st.dataframe() so row
  colours actually respond to the active theme
"""

import streamlit as st

# ── 10 Night (dark) themes ────────────────────────────────────────────────
# Sidebars use non-green, lighter colours so the logo reads clearly.
_NIGHT_THEMES: dict[str, dict] = {

    "Night (Dark)": dict(                       # refreshed – charcoal navy sidebar
        main_bg="#0e1117",   sidebar_bg="#1a2840",  sidebar_text="#d8eaf8",
        text="#f0f8e8",      accent="#7dc918",
        df_header_bg="#1a3a0d", df_header_text="#e8f5d0",
        card_bg="#1a2e10",   input_bg="#253d18",    input_text="#e8f5d0",
        btn_bg="#5a9e10",    btn_text="#ffffff",
        cell_bg="#141f0e",   cell_text="#e8f5d0",
        border="#3a6a10",    alert_bg="#1a3010",
    ),

    "Midnight": dict(                           # deep navy blue
        main_bg="#0a0f1e",   sidebar_bg="#0f1d3a",  sidebar_text="#c0d0e8",
        text="#d0e0f8",      accent="#4da6ff",
        df_header_bg="#162040", df_header_text="#c0d0e8",
        card_bg="#141e36",   input_bg="#1a2848",    input_text="#c0d0e8",
        btn_bg="#1a5fa0",    btn_text="#ffffff",
        cell_bg="#0d1428",   cell_text="#c0d0e8",
        border="#2a4a7a",    alert_bg="#162040",
    ),

    "Charcoal": dict(                           # neutral dark gray
        main_bg="#111111",   sidebar_bg="#202020",  sidebar_text="#dddddd",
        text="#e0e0e0",      accent="#7dc918",
        df_header_bg="#282828", df_header_text="#dddddd",
        card_bg="#1c1c1c",   input_bg="#282828",    input_text="#dddddd",
        btn_bg="#5a9e10",    btn_text="#ffffff",
        cell_bg="#161616",   cell_text="#e0e0e0",
        border="#383838",    alert_bg="#242424",
    ),

    "Deep Space": dict(                         # dark indigo / purple
        main_bg="#0d0b1a",   sidebar_bg="#1a1535",  sidebar_text="#d0c8f0",
        text="#d8d0f8",      accent="#a78bfa",
        df_header_bg="#221e40", df_header_text="#d0c8f0",
        card_bg="#181530",   input_bg="#221e40",    input_text="#d0c8f0",
        btn_bg="#7c3aed",    btn_text="#ffffff",
        cell_bg="#100d20",   cell_text="#d8d0f8",
        border="#4a3888",    alert_bg="#1e1840",
    ),

    "Storm": dict(                              # dark blue-gray
        main_bg="#0f1419",   sidebar_bg="#1a2535",  sidebar_text="#c8d8e8",
        text="#d0e0ec",      accent="#38bdf8",
        df_header_bg="#1e2d3e", df_header_text="#c8d8e8",
        card_bg="#162030",   input_bg="#1e2d3e",    input_text="#c8d8e8",
        btn_bg="#0284c7",    btn_text="#ffffff",
        cell_bg="#0d1520",   cell_text="#d0e0ec",
        border="#2a4560",    alert_bg="#1e2d3e",
    ),

    "Forge": dict(                              # dark warm, amber / gold accent
        main_bg="#0f0d0a",   sidebar_bg="#2a2018",  sidebar_text="#e8d8b0",
        text="#f0e0c0",      accent="#f59e0b",
        df_header_bg="#352a1e", df_header_text="#e8d8b0",
        card_bg="#1e1a14",   input_bg="#2a2018",    input_text="#e8d8b0",
        btn_bg="#b45309",    btn_text="#ffffff",
        cell_bg="#141008",   cell_text="#f0e0c0",
        border="#5a4020",    alert_bg="#352a1e",
    ),

    "Carbon": dict(                             # pure charcoal, teal accent
        main_bg="#0a0a0a",   sidebar_bg="#181818",  sidebar_text="#d0e8e8",
        text="#d8d8d8",      accent="#22d3ee",
        df_header_bg="#202020", df_header_text="#d0e8e8",
        card_bg="#161616",   input_bg="#202020",    input_text="#d0e8e8",
        btn_bg="#0891b2",    btn_text="#ffffff",
        cell_bg="#101010",   cell_text="#d8d8d8",
        border="#303030",    alert_bg="#1e1e1e",
    ),

    "Eclipse": dict(                            # dark purple / violet
        main_bg="#0d0a14",   sidebar_bg="#1e1530",  sidebar_text="#d8c8f0",
        text="#e8d8f8",      accent="#c084fc",
        df_header_bg="#281e3e", df_header_text="#d8c8f0",
        card_bg="#1a1228",   input_bg="#281e3e",    input_text="#d8c8f0",
        btn_bg="#9333ea",    btn_text="#ffffff",
        cell_bg="#120f1e",   cell_text="#e8d8f8",
        border="#4a2878",    alert_bg="#281e3e",
    ),

    "Cosmos": dict(                             # deep dark navy, electric blue
        main_bg="#080a10",   sidebar_bg="#151a2e",  sidebar_text="#c0d0e8",
        text="#d0ddf0",      accent="#60a5fa",
        df_header_bg="#1e2440", df_header_text="#c0d0e8",
        card_bg="#121824",   input_bg="#1a2038",    input_text="#c0d0e8",
        btn_bg="#2563eb",    btn_text="#ffffff",
        cell_bg="#0c0e18",   cell_text="#d0ddf0",
        border="#2a3860",    alert_bg="#1a2038",
    ),

    "Iron": dict(                               # dark steel blue-gray
        main_bg="#0e1118",   sidebar_bg="#1c2333",  sidebar_text="#ccd6e0",
        text="#d8e4ec",      accent="#94a3b8",
        df_header_bg="#232d3e", df_header_text="#ccd6e0",
        card_bg="#1a2230",   input_bg="#222c3c",    input_text="#ccd6e0",
        btn_bg="#475569",    btn_text="#ffffff",
        cell_bg="#101520",   cell_text="#d8e4ec",
        border="#374558",    alert_bg="#1e2a3a",
    ),
}

# ── 10 Day themes ──────────────────────────────────────────────────────────
# Every theme is complementary to the logo's forest-green / lime / white
# palette. Accents pull directly from the logo's lime (#7dc918) or adjacent
# greens; sidebars use dark-green tones so the logo sits comfortably on them.
_DAY_THEMES: dict[str, dict] = {

    "Pitch": dict(                              # clean white + lime
        main_bg="#f8fff4",   sidebar_bg="#1c3a0d",  sidebar_text="#ffffff",
        text="#0d1f05",      accent="#7dc918",
        df_header_bg="#c8e8a0", df_header_text="#0d1f05",
        card_bg="#edf7e0",   input_bg="#ffffff",    input_text="#0d1f05",
        btn_bg="#5a9e10",    btn_text="#ffffff",
        cell_bg="#f8fff4",   cell_text="#0d1f05",
        border="#9cc858",    alert_bg="#dff0c0",
    ),

    "Chalk": dict(                              # crisp off-white
        main_bg="#fafaf8",   sidebar_bg="#2d5016",  sidebar_text="#ffffff",
        text="#1a2e0a",      accent="#5a9e10",
        df_header_bg="#d4e8b0", df_header_text="#1a2e0a",
        card_bg="#f0f5e8",   input_bg="#ffffff",    input_text="#1a2e0a",
        btn_bg="#4a8c0f",    btn_text="#ffffff",
        cell_bg="#fafaf8",   cell_text="#1a2e0a",
        border="#a0c870",    alert_bg="#e0efcc",
    ),

    "Highland": dict(                           # misty Scottish sage
        main_bg="#f0f5ec",   sidebar_bg="#4a6e2a",  sidebar_text="#ffffff",
        text="#1a2e0a",      accent="#7dc918",
        df_header_bg="#cce0a8", df_header_text="#1a2e0a",
        card_bg="#e5f0d8",   input_bg="#f8fcf0",    input_text="#1a2e0a",
        btn_bg="#5a8c1a",    btn_text="#ffffff",
        cell_bg="#f0f5ec",   cell_text="#1a2e0a",
        border="#90b860",    alert_bg="#d8ecc0",
    ),

    "Mint": dict(                               # fresh cool mint
        main_bg="#f0fdf4",   sidebar_bg="#166534",  sidebar_text="#ffffff",
        text="#052e16",      accent="#16a34a",
        df_header_bg="#bbf7d0", df_header_text="#052e16",
        card_bg="#dcfce7",   input_bg="#ffffff",    input_text="#052e16",
        btn_bg="#16a34a",    btn_text="#ffffff",
        cell_bg="#f0fdf4",   cell_text="#052e16",
        border="#86efac",    alert_bg="#d1fae5",
    ),

    "Emerald Isle": dict(                       # deep rich emerald
        main_bg="#ecfdf5",   sidebar_bg="#064e3b",  sidebar_text="#d1fae5",
        text="#022c22",      accent="#10b981",
        df_header_bg="#a7f3d0", df_header_text="#022c22",
        card_bg="#d1fae5",   input_bg="#ffffff",    input_text="#022c22",
        btn_bg="#059669",    btn_text="#ffffff",
        cell_bg="#ecfdf5",   cell_text="#022c22",
        border="#6ee7b7",    alert_bg="#ccfbf1",
    ),

    "Clover": dict(                             # light lime-yellow
        main_bg="#f7fef0",   sidebar_bg="#3a6b0f",  sidebar_text="#ffffff",
        text="#1a3005",      accent="#84cc16",
        df_header_bg="#d9f99d", df_header_text="#1a3005",
        card_bg="#ecfccb",   input_bg="#ffffff",    input_text="#1a3005",
        btn_bg="#65a30d",    btn_text="#ffffff",
        cell_bg="#f7fef0",   cell_text="#1a3005",
        border="#a3e635",    alert_bg="#e8f9c0",
    ),

    "Sand & Grass": dict(                       # warm outdoor
        main_bg="#fdf9f0",   sidebar_bg="#5a7a1a",  sidebar_text="#ffffff",
        text="#2a1a05",      accent="#7dc918",
        df_header_bg="#e8d8a0", df_header_text="#2a1a05",
        card_bg="#f5efe0",   input_bg="#ffffff",    input_text="#2a1a05",
        btn_bg="#6a8c1a",    btn_text="#ffffff",
        cell_bg="#fdf9f0",   cell_text="#2a1a05",
        border="#c0a860",    alert_bg="#f0e8c0",
    ),

    "Pearl": dict(                              # minimal clean white
        main_bg="#fefefe",   sidebar_bg="#234012",  sidebar_text="#e8f5d0",
        text="#0d2008",      accent="#5a9e1a",
        df_header_bg="#d0e8b0", df_header_text="#0d2008",
        card_bg="#f5faf0",   input_bg="#ffffff",    input_text="#0d2008",
        btn_bg="#4a8c10",    btn_text="#ffffff",
        cell_bg="#fefefe",   cell_text="#0d2008",
        border="#98c860",    alert_bg="#e0f0c8",
    ),

    "Morning Mist": dict(                       # cool blue-gray + forest green
        main_bg="#f4f8f5",   sidebar_bg="#2e5038",  sidebar_text="#e0f0e5",
        text="#0f2418",      accent="#4ade80",
        df_header_bg="#b8d8c0", df_header_text="#0f2418",
        card_bg="#e4f0e8",   input_bg="#ffffff",    input_text="#0f2418",
        btn_bg="#4a8c5a",    btn_text="#ffffff",
        cell_bg="#f4f8f5",   cell_text="#0f2418",
        border="#78b888",    alert_bg="#d0e8d8",
    ),

    "Lush": dict(                               # deep green-washed bg
        main_bg="#e8f5e2",   sidebar_bg="#1a4a0a",  sidebar_text="#c8f0a0",
        text="#0a2005",      accent="#7dc918",
        df_header_bg="#c0e098", df_header_text="#0a2005",
        card_bg="#d8f0c8",   input_bg="#f0f9e8",    input_text="#0a2005",
        btn_bg="#5a9e10",    btn_text="#ffffff",
        cell_bg="#e8f5e2",   cell_text="#0a2005",
        border="#88c850",    alert_bg="#c8e8a8",
    ),
}

# ── Public exports ─────────────────────────────────────────────────────────
ALL_THEMES: dict[str, dict] = {**_NIGHT_THEMES, **_DAY_THEMES}
THEME_NAMES: list[str] = list(ALL_THEMES.keys())

# ── CSS template ───────────────────────────────────────────────────────────
# Double-braces {{ }} are literal braces in the output; single-brace
# {tokens} are substituted by .format(**theme_dict).
_CSS = """
/* ── Top header bar ─────────────────────────────────────────────────────── */
[data-testid="stHeader"],
header[data-testid="stHeader"],
[data-testid="stHeader"] > div,
[data-testid="stDecoration"] {{
    background-color: {main_bg} !important;
}}

/* ── App background & base text ─────────────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMainBlockContainer"],
[data-testid="stBottom"],
section.main > div {{
    background-color: {main_bg} !important;
    color: {text} !important;
}}

/* ── Global text cascade ────────────────────────────────────────────────── */
.stApp p, .stApp li, .stApp span, .stApp div,
.stApp h1, .stApp h2, .stApp h3,
.stApp h4, .stApp h5, .stApp h6,
.stApp label, .stApp caption, .stApp small,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] * {{
    color: {text} !important;
}}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
    background-color: {sidebar_bg} !important;
}}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] caption,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] * {{
    color: {sidebar_text} !important;
}}

/* ── Sidebar selectbox field ────────────────────────────────────────────── */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] [data-baseweb="select-container"] {{
    background-color: {input_bg} !important;
    border-color: {border} !important;
}}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-testid="stSidebar"] [data-baseweb="select"] p,
[data-testid="stSidebar"] [data-baseweb="select"] * {{
    color: {input_text} !important;
    background-color: transparent !important;
}}

/* ── Dropdown menus / portals (global + sidebar) ────────────────────────── */
/* Portals render outside .stApp so we need stand-alone selectors            */
[data-baseweb="menu"],
[data-baseweb="popover"] ul,
[role="listbox"] {{
    background-color: {input_bg} !important;
    border-color: {border} !important;
}}
[data-baseweb="menu"] li,
[data-baseweb="option"] {{
    background-color: {input_bg} !important;
    color: {input_text} !important;
}}
/* Force ALL child text in every option to be readable */
[data-baseweb="menu"] li *,
[data-baseweb="option"] *,
[role="listbox"] li,
[role="listbox"] li *,
[role="option"],
[role="option"] * {{
    color: {input_text} !important;
    background-color: transparent !important;
}}
/* Hover state */
[data-baseweb="option"]:hover,
[role="option"]:hover {{
    background-color: {border} !important;
}}
[data-baseweb="option"]:hover *,
[role="option"]:hover * {{
    color: {input_text} !important;
}}
/* Selected / focused / highlighted state */
[data-baseweb="option"][aria-selected="true"],
[data-baseweb="option"][data-highlighted],
[role="option"][aria-selected="true"] {{
    background-color: {accent} !important;
}}
[data-baseweb="option"][aria-selected="true"] *,
[data-baseweb="option"][data-highlighted] *,
[role="option"][aria-selected="true"] * {{
    color: #ffffff !important;
    background-color: transparent !important;
}}
/* Sidebar variants (same rules scoped to sidebar) */
[data-testid="stSidebar"] [data-baseweb="menu"],
[data-testid="stSidebar"] [role="listbox"],
[data-testid="stSidebar"] [data-baseweb="popover"] ul {{
    background-color: {input_bg} !important;
}}
[data-testid="stSidebar"] [data-baseweb="option"],
[data-testid="stSidebar"] [data-baseweb="menu"] li {{
    background-color: {input_bg} !important;
    color: {input_text} !important;
}}
[data-testid="stSidebar"] [data-baseweb="option"] *,
[data-testid="stSidebar"] [data-baseweb="menu"] li * {{
    color: {input_text} !important;
    background-color: transparent !important;
}}
[data-testid="stSidebar"] [data-baseweb="option"]:hover {{
    background-color: {border} !important;
}}
[data-testid="stSidebar"] [data-baseweb="option"][aria-selected="true"] {{
    background-color: {accent} !important;
}}
[data-testid="stSidebar"] [data-baseweb="option"][aria-selected="true"] * {{
    color: #ffffff !important;
    background-color: transparent !important;
}}

/* ── Metric values ──────────────────────────────────────────────────────── */
[data-testid="stMetricValue"] {{
    color: {accent} !important;
    font-weight: 700;
}}
[data-testid="stMetricLabel"] > div,
[data-testid="stMetricDelta"] {{
    color: {text} !important;
}}

/* ── Buttons ────────────────────────────────────────────────────────────── */
.stButton > button,
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"],
[data-testid="stDownloadButton"] > button {{
    background-color: {btn_bg} !important;
    color: {btn_text} !important;
    border-color: {btn_bg} !important;
}}
.stButton > button:hover,
[data-testid="stDownloadButton"] > button:hover {{
    filter: brightness(1.12);
}}

/* ── Dataframe / chart element toolbar — transparent, no box ────────────── */
[data-testid="stElementToolbar"],
[data-testid="stElementToolbar"] > div {{
    background-color: transparent !important;
    border-color: transparent !important;
    box-shadow: none !important;
}}
[data-testid="stElementToolbar"] button,
[data-testid="stElementToolbar"] [data-testid="stElementToolbarButton"] {{
    background-color: transparent !important;
    color: {text} !important;
    border-color: transparent !important;
    box-shadow: none !important;
}}
[data-testid="stElementToolbar"] button:hover {{
    background-color: {border} !important;
    border-radius: 4px;
}}

/* ── Text / number / date inputs ────────────────────────────────────────── */
[data-baseweb="input"],
[data-baseweb="input"] input,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
textarea,
[data-baseweb="textarea"] {{
    background-color: {input_bg} !important;
    color: {input_text} !important;
    border-color: {border} !important;
}}

/* ── Main-area selectbox / multiselect ──────────────────────────────────── */
[data-baseweb="select"] > div,
[data-baseweb="select"] [data-baseweb="select-container"],
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
    background-color: {input_bg} !important;
    color: {input_text} !important;
    border-color: {border} !important;
}}
[data-baseweb="select"] * {{ color: {input_text} !important; }}
[data-baseweb="tag"] {{
    background-color: {btn_bg} !important;
    color: {btn_text} !important;
}}

/* ── Sidebar alert / info boxes ─────────────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stAlert"],
[data-testid="stSidebar"] [data-testid="stNotification"],
[data-testid="stSidebar"] [data-baseweb="notification"] {{
    background-color: rgba(255,255,255,0.18) !important;
    border-color: rgba(255,255,255,0.35) !important;
    border-left-color: rgba(255,255,255,0.35) !important;
    border-left-width: 4px !important;
    outline: none !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] [data-testid="stAlert"] *,
[data-testid="stSidebar"] [data-testid="stNotification"] *,
[data-testid="stSidebar"] [data-baseweb="notification"] * {{
    color: {sidebar_text} !important;
    background-color: transparent !important;
}}

/* ── st.dataframe (Glide Data Grid) ─────────────────────────────────────── */
[data-testid="stDataFrame"] {{ border-radius: 4px; }}

/* ── HTML tables (.sb-tbl) — used by render_table() ────────────────────── */
.sb-tbl {{ overflow-x: auto; border-radius: 4px; }}
.sb-tbl table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    color: {text};
    background-color: {cell_bg};
}}
.sb-tbl th {{
    background-color: {df_header_bg} !important;
    color: {df_header_text} !important;
    padding: 7px 12px;
    text-align: left;
    border-bottom: 2px solid {border};
    white-space: nowrap;
    font-weight: 600;
}}
.sb-tbl td {{
    background-color: {cell_bg};
    color: {text};
    padding: 5px 12px;
    border-bottom: 1px solid {border};
    white-space: nowrap;
}}
.sb-tbl tbody tr:nth-child(even) td {{ background-color: {df_header_bg}; }}
.sb-tbl tbody tr:hover td {{ filter: brightness(0.95); }}

/* ── st.table() ─────────────────────────────────────────────────────────── */
[data-testid="stTable"] table {{
    background-color: {cell_bg} !important;
    color: {cell_text} !important;
}}
[data-testid="stTable"] thead th {{
    background-color: {df_header_bg} !important;
    color: {df_header_text} !important;
    border-bottom: 2px solid {border} !important;
}}
[data-testid="stTable"] tbody td {{
    background-color: {cell_bg} !important;
    color: {cell_text} !important;
    border-color: {border} !important;
}}
[data-testid="stTable"] tbody tr:nth-child(even) td {{
    background-color: {df_header_bg} !important;
}}

/* ── Expander ───────────────────────────────────────────────────────────── */
details[data-testid="stExpander"],
[data-testid="stExpander"] {{
    background-color: {card_bg} !important;
    border-color: {border} !important;
}}
details[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary {{
    background-color: {df_header_bg} !important;
    border-radius: 4px;
    padding: 6px 10px;
}}
details[data-testid="stExpander"] summary *,
[data-testid="stExpander"] summary *,
[data-testid="stExpanderHeader"],
[data-testid="stExpanderHeader"] *,
.streamlit-expanderHeader,
.streamlit-expanderHeader * {{
    color: {df_header_text} !important;
    background-color: transparent !important;
}}
[data-testid="stExpanderDetails"],
[data-testid="stExpanderDetails"] > div {{
    background-color: {card_bg} !important;
}}

/* ── Cards / bordered containers ────────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: {card_bg} !important;
    border-color: {border} !important;
}}

/* ── Alert / notification boxes ─────────────────────────────────────────── */
[data-testid="stAlert"],
[data-testid="stNotification"],
div[class*="stInfo"],
div[class*="stWarning"],
div[class*="stSuccess"],
div[class*="stError"] {{
    background-color: {alert_bg} !important;
    color: {text} !important;
    border-color: {border} !important;
}}
[data-testid="stAlert"] *,
[data-testid="stNotification"] * {{ color: {text} !important; }}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px;
    background-color: {main_bg} !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 4px 4px 0 0;
    padding: 8px 14px;
    color: {text} !important;
    background-color: {card_bg} !important;
}}
.stTabs [aria-selected="true"][data-baseweb="tab"] {{
    background-color: {btn_bg} !important;
    color: {btn_text} !important;
}}
.stTabs [data-baseweb="tab-panel"],
.stTabs [data-baseweb="tab-border"] {{
    background-color: {main_bg} !important;
}}

/* ── Progress bar ───────────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {{
    background-color: {accent} !important;
}}

/* ── Checkbox / radio labels ────────────────────────────────────────────── */
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label {{ color: {text} !important; }}

/* ── Divider ────────────────────────────────────────────────────────────── */
[data-testid="stDivider"] hr {{ border-color: {border} !important; }}
"""


def apply_theme(theme_name: str = "Night (Dark)") -> None:
    """Inject CSS for the selected theme into the current page."""
    t = ALL_THEMES.get(theme_name, _NIGHT_THEMES["Night (Dark)"])
    st.markdown(f"<style>{_CSS.format(**t)}</style>", unsafe_allow_html=True)


def plotly_theme(theme_name: str = "Night (Dark)") -> dict:
    """Return Plotly ``update_layout`` kwargs matching the active theme."""
    t = ALL_THEMES.get(theme_name, _NIGHT_THEMES["Night (Dark)"])
    fc = t["text"]
    gc = t["border"]
    return dict(
        paper_bgcolor=t["card_bg"],
        plot_bgcolor=t["card_bg"],
        font=dict(color=fc),
        title_font_color=fc,
        legend_font_color=fc,
        xaxis=dict(
            gridcolor=gc, zerolinecolor=gc,
            tickfont=dict(color=fc), title_font=dict(color=fc),
        ),
        yaxis=dict(
            gridcolor=gc, zerolinecolor=gc,
            tickfont=dict(color=fc), title_font=dict(color=fc),
        ),
    )


def render_table(df, hide_index: bool = True) -> None:
    """Render a DataFrame as a theme-aware HTML table (.sb-tbl class).

    Use this instead of a bare st.dataframe() call when you need row colours
    to follow the active theme — mirrors the render_table() pattern from
    the La Liga project that fixed daytime mode table readability.
    """
    if df.empty:
        st.info("No data to display.")
        return
    html = df.to_html(index=not hide_index, classes="sb-tbl", border=0, escape=True)
    st.markdown(f'<div class="sb-tbl">{html}</div>', unsafe_allow_html=True)
