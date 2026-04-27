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

## 6. OpenWeatherMap — Already Integrated, Add Wind  ⭐ (Low effort)

Currently fetching temp + description. Extend to include:
- `wind_speed` (m/s) — affects kicking/lineouts significantly above 10 m/s
- `wind_deg` — end-to-end vs crossfield wind matters
- `precipitation` mm/h — affects handling errors

```python
def fetch_weather_extended(lat: float, lon: float) -> dict:
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            "lat": lat, "lon": lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
        },
        timeout=10,
    )
    d = r.json()
    return {
        "temp_c":       d["main"]["temp"],
        "description":  d["weather"][0]["description"],
        "wind_speed":   d["wind"]["speed"],          # m/s
        "wind_deg":     d["wind"].get("deg", 0),     # degrees
        "rain_1h":      d.get("rain", {}).get("1h", 0.0),  # mm
        "humidity":     d["main"]["humidity"],
    }

# Wind impact score (for kicking-game adjustment)
def wind_impact_score(wind_speed_ms: float) -> float:
    """0 = no impact, 1 = severe impact on kicking/lineouts."""
    return min(1.0, wind_speed_ms / 15.0)
```

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
| 8 | Weather extended | Low — extend existing | ⭐ |
| 9 | Twitter/X | High — rate limits | ⭐ |
