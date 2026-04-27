from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR    = Path(__file__).parent.parent
DATA_DIR    = BASE_DIR / "data_files"
CSV_DIR     = DATA_DIR / "csv"
PARQUET_DIR = DATA_DIR / "parquet"

# Ensure directories exist on import
CSV_DIR.mkdir(parents=True, exist_ok=True)
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

# ── League metadata ────────────────────────────────────────────────────────
LEAGUES: dict[str, str] = {
    "six_nations":    "Six Nations",
    "premiership":    "Premiership Rugby",
    "top14":          "Top 14",
    "super_rugby":    "Super Rugby Pacific",
    "urc":            "United Rugby Championship",
    "champions_cup":  "European Champions Cup",
}

LEAGUE_LIST  = list(LEAGUES.keys())
LEAGUE_NAMES = list(LEAGUES.values())

# ── ESPN API ───────────────────────────────────────────────────────────────
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/rugby"

ESPN_LEAGUE_IDS: dict[str, str] = {
    "six_nations":   "180659",
    "premiership":   "267979",
    "top14":         "270557",
    "super_rugby":   "242041",
    "urc":           "270559",
    "champions_cup": "271937",
}

# ── SofaScore API ──────────────────────────────────────────────────────────
SOFASCORE_BASE = "https://api.sofascore.com/api/v1"

# ── Odds API ───────────────────────────────────────────────────────────────
ODDS_API_KEY  = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Only sport keys that actually exist in The Odds API.
# Rugby Union coverage is very limited — Six Nations only, and only when active.
# Premiership, Top14, Super Rugby, URC, Champions Cup have no API coverage.
ODDS_SPORT_MAP: dict[str, str] = {
    "six_nations": "rugbyunion_six_nations",
}

# ── Weather API (Open-Meteo — no key required) ────────────────────────────
OPEN_METEO_GEOCODING_BASE = "https://geocoding-api.open-meteo.com/v1"
OPEN_METEO_BASE           = "https://api.open-meteo.com/v1"

# WMO weather interpretation codes → human-readable descriptions
WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Heavy drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 99: "Thunderstorm with hail",
}

# ── Elo constants ──────────────────────────────────────────────────────────
ELO_K            = 32
ELO_HOME_ADV     = 50
ELO_DEFAULT      = 1500

# ── Current season (rugby seasons straddle calendar years) ────────────────
from datetime import datetime as _dt
CURRENT_SEASON = _dt.now().year if _dt.now().month > 6 else _dt.now().year - 1
