# Additional Data Sources

Ranked by implementation effort vs expected data value for ScrumBet.



## 2. World Rugby Official API  ⭐⭐⭐ (High value, already partial)

World Rugby's Pulse Live API (already used for Six Nations fixtures) also exposes:
- Full player rankings and ratings
- International match results going back decades
- Try-scorer data per match

```python
PULSE_BASE = "https://api.wr-rims-prod.pulselive.com/rugby/v3"

endpoints = {
    "rankings":      f"{PULSE_BASE}/rankings/mru",          # world rankings
    "match_events":  f"{PULSE_BASE}/match/{match_id}/stats", # try scorers, cards
    "player_career": f"{PULSE_BASE}/player/{player_id}/career",
    "team_squad":    f"{PULSE_BASE}/team/{team_id}/squad",
}

def fetch_try_events(match_id: str) -> pd.DataFrame:
    """Fetch scoring events (tries, conversions, pens) for an international."""
    r = requests.get(
        f"{PULSE_BASE}/match/{match_id}/stats",
        headers={"Accept": "application/json"},
        timeout=15,
    )
    data = r.json()
    events = data.get("match", {}).get("matchEvents", [])
    return pd.DataFrame([{
        "type":   e.get("type"),
        "player": e.get("player", {}).get("name", ""),
        "team":   e.get("team", {}).get("name", ""),
        "minute": e.get("minute"),
        "half":   e.get("half"),
    } for e in events if e.get("type") in ("T", "C", "PG", "DG")])
```

---

## 3. Sky Sports / BBC Sport Injury Feeds  ⭐⭐ (Medium value)

Injury and selection news is the single biggest mover of match outcome probability that
model parameters don't capture. RSS feeds provide near-real-time updates.

```python
# data/scrapers/injury_feed.py
import feedparser

FEEDS = {
    "premiership": "https://www.bbc.co.uk/sport/rugby-union/rss.xml",
    "all":         "https://www.skysports.com/rss/11889",
}

INJURY_KEYWORDS = [
    "injured", "injury", "ruled out", "doubt", "fitness test",
    "suspended", "banned", "unavailable", "withdrawn", "pulled out",
]

def fetch_injury_news(league_id: str = "all", max_age_hours: int = 48) -> pd.DataFrame:
    """Scrape RSS feeds for injury/selection news."""
    feed = feedparser.parse(FEEDS.get(league_id, FEEDS["all"]))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    records = []
    for entry in feed.entries:
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if published < cutoff:
            continue
        title = entry.title.lower()
        summary = entry.get("summary", "").lower()
        text = title + " " + summary
        if any(kw in text for kw in INJURY_KEYWORDS):
            records.append({
                "headline":   entry.title,
                "url":        entry.link,
                "published":  published,
                "source":     feed.feed.title,
                "league_id":  league_id,
            })
    return pd.DataFrame(records)
```

**Add to requirements.txt:** `feedparser>=6.0.0`

---

## 4. The Odds API — Additional Markets  ⭐⭐ (Already integrated, extend)

Currently only fetching `h2h`, `spreads`, `totals`. Extend to:

```python
EXTRA_MARKETS = [
    "player_tries",        # anytime try scorer props
    "team_totals",         # per-team point totals
    "alternate_spreads",   # wider spread ladder
    "h2h_3_way",           # home/draw/away (rugby-specific)
]

# In _fetch_odds(), change the markets param:
params = {
    "markets": "h2h,spreads,totals,player_tries,h2h_3_way",
    ...
}
```

Try scorer props are particularly valuable for the Player Stats page edge calculator.

---

## 5. SofaScore Extended — Head to Head & Lineups  ⭐⭐ (Already partial)

SofaScore's undocumented API (already used for live scores) also provides:

```python
SOFA_BASE = "https://api.sofascore.com/api/v1"

def fetch_h2h(home_team_id: str, away_team_id: str) -> pd.DataFrame:
    """Last 10 H2H meetings between two teams."""
    r = requests.get(
        f"{SOFA_BASE}/team/{home_team_id}/near-events",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    # Filter events where opponent == away_team_id
    ...

def fetch_player_image(player_id: str) -> str:
    """Return CDN URL for player headshot."""
    return f"https://api.sofascore.com/api/v1/player/{player_id}/image"

def fetch_pre_match_odds(event_id: str) -> dict:
    """Pre-match opening odds from SofaScore aggregator."""
    r = requests.get(
        f"{SOFA_BASE}/event/{event_id}/odds/1/all",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    return r.json() if r.status_code == 200 else {}
```

---

## 6. Open-Meteo — Replace OpenWeatherMap (No API Key)  ⭐ (Low effort)

Open-Meteo is a free, open-source weather API with no key required. Replace the current
OpenWeatherMap integration to fetch extended conditions via two calls: geocoding (venue
name → lat/lon) then the forecast endpoint.

Data available:
- `temperature_2m` (°C)
- `wind_speed_10m` (km/h) — affects kicking/lineouts significantly above 36 km/h (~10 m/s)
- `wind_direction_10m` (°) — end-to-end vs crossfield wind matters
- `precipitation` (mm/h) — affects handling errors
- `relative_humidity_2m` (%)
- `weather_code` (WMO code) — maps to a human-readable description

```python
OPEN_METEO_GEOCODING_BASE = "https://geocoding-api.open-meteo.com/v1"
OPEN_METEO_BASE           = "https://api.open-meteo.com/v1"

# Subset of WMO weather interpretation codes
WMO_DESCRIPTIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Heavy drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 99: "Thunderstorm with hail",
}

def geocode_venue(venue: str) -> tuple[float, float] | None:
    """Resolve a venue/city name to (latitude, longitude) via Open-Meteo geocoding."""
    r = requests.get(
        f"{OPEN_METEO_GEOCODING_BASE}/search",
        params={"name": venue, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    results = r.json().get("results", [])
    if not results:
        return None
    return results[0]["latitude"], results[0]["longitude"]

def fetch_weather_extended(venue: str) -> dict | None:
    """Return current weather for a venue name. No API key required."""
    coords = geocode_venue(venue)
    if coords is None:
        return None
    lat, lon = coords
    r = requests.get(
        f"{OPEN_METEO_BASE}/forecast",
        params={
            "latitude":  lat,
            "longitude": lon,
            "current":   "temperature_2m,weather_code,wind_speed_10m,"
                         "wind_direction_10m,precipitation,relative_humidity_2m",
            "wind_speed_unit": "ms",  # return in m/s for consistency
            "forecast_days": 1,
        },
        timeout=10,
    )
    if r.status_code != 200:
        return None
    c = r.json().get("current", {})
    code = c.get("weather_code", 0)
    return {
        "temp_c":       c.get("temperature_2m"),
        "description":  WMO_DESCRIPTIONS.get(code, f"Code {code}"),
        "wind_speed":   c.get("wind_speed_10m"),      # m/s
        "wind_deg":     c.get("wind_direction_10m"),  # degrees
        "rain_1h":      c.get("precipitation", 0.0),  # mm
        "humidity":     c.get("relative_humidity_2m"),
    }

# Wind impact score (for kicking-game adjustment)
def wind_impact_score(wind_speed_ms: float) -> float:
    """0 = no impact, 1 = severe impact on kicking/lineouts."""
    return min(1.0, wind_speed_ms / 15.0)
```

**No change to requirements.txt needed** — `requests` is already a dependency.
Remove `OPENWEATHER_API_KEY` and `OPENWEATHER_BASE` from `utils/config.py` and
`.env`; replace with the two constants above.

---

## 7. Referee Statistics Database  ⭐⭐ (Under-exploited edge)

Referee tendencies (penalty rate, cards per game, advantage play style) are
significant predictors — some referees systematically advantage certain playing styles.

```python
# data/scrapers/referee_stats.py
# Source: rugbypy match details include referee name
# Build internal database from historical matches

def build_referee_stats(matches_with_details: pd.DataFrame) -> pd.DataFrame:
    """Compute per-referee statistics from historical match details."""
    return (
        matches_with_details
        .groupby("referee")
        .agg(
            games=("match_id", "count"),
            avg_home_pens=("home_penalties", "mean"),
            avg_away_pens=("away_penalties", "mean"),
            avg_total_pens=("total_penalties", "mean"),
            avg_cards=("cards", "mean"),
            home_win_rate=("home_win", "mean"),
            avg_total_points=("total_points", "mean"),
        )
        .reset_index()
    )
```

---

## Priority order for implementation

| Priority | Source | Effort | Value |
|---|---|---|---|
| 1 | rugbypy (historical) | Low — pip install | ⭐⭐⭐ |
| 2 | World Rugby Pulse (match events/tries) | Low — extend existing | ⭐⭐⭐ |
| 3 | The Odds API (try scorer props) | Low — add markets | ⭐⭐ |
| 4 | SofaScore (H2H + lineups) | Medium | ⭐⭐ |
| 5 | Injury RSS feeds | Medium | ⭐⭐ |
| 6 | Referee stats DB | Medium — rugbypy source | ⭐⭐ |
| 7 | Betfair Exchange | High — auth required | ⭐⭐⭐ |
| 8 | Open-Meteo (extended wind/rain) | Low — no key, extend existing | ⭐ |
| 9 | Twitter/X | High — rate limits | ⭐ |
