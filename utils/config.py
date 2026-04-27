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

ODDS_SPORT_MAP: dict[str, str] = {
    "premiership":   "rugbyunion_gallagher_premiership",
    "six_nations":   "rugbyunion_six_nations",
    "super_rugby":   "rugbyunion_super_rugby",
    "urc":           "rugbyunion_urc",
    "top14":         "rugbyunion_top14",
    "champions_cup": "rugbyunion_ecc",
}

# ── Weather API ────────────────────────────────────────────────────────────
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_BASE    = "https://api.openweathermap.org/data/2.5"

# ── Elo constants ──────────────────────────────────────────────────────────
ELO_K            = 32
ELO_HOME_ADV     = 50
ELO_DEFAULT      = 1500

# ── Current season (rugby seasons straddle calendar years) ────────────────
from datetime import datetime as _dt
CURRENT_SEASON = _dt.now().year if _dt.now().month > 6 else _dt.now().year - 1
