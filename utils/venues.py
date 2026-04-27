"""
Static (lat, lon) coordinates for all known rugby venues in the dataset.
Used by the weather widget to avoid geocoding API calls for well-known stadia.
The geocoding API (Open-Meteo) is used as a fallback for any venue not listed here.
"""

from typing import Optional

# ── Venue coordinate table ──────────────────────────────────────────────────
# All coordinates are (latitude, longitude) in decimal degrees.
VENUE_COORDS: dict[str, tuple[float, float]] = {

    # ── British Isles — modern stadia ──────────────────────────────────────
    "Aviva Stadium":           ( 53.3352,  -6.2284),  # Dublin, Ireland
    "Lansdowne Road":          ( 53.3352,  -6.2284),  # Dublin (former name of Aviva)
    "Principality Stadium":    ( 51.4782,  -3.1826),  # Cardiff, Wales
    "Cardiff Arms Park":       ( 51.4784,  -3.1826),  # Cardiff, Wales
    "Kingsholm":               ( 51.8712,  -2.2408),  # Gloucester, England
    "Scotstoun Stadium":       ( 55.8870,  -4.3547),  # Glasgow, Scotland
    "Rodney Parade":           ( 51.5929,  -2.9924),  # Newport, Wales
    "Rectory Field":           ( 51.4651,   0.0107),  # Blackheath, London
    "Athletic Ground":         ( 51.4619,  -0.3079),  # Richmond, London
    "St Helen's":              ( 51.6193,  -3.9395),  # Swansea, Wales
    "Stradey Park":            ( 51.6815,  -4.1628),  # Llanelli, Wales
    "Birkenhead Park":         ( 53.3856,  -3.0638),  # Merseyside, England
    "Crown Flatt":             ( 53.6893,  -1.6349),  # Dewsbury, England
    "Affidea Stadium":         ( 54.57639, -5.90444),  # Belfast, North Ireland (current name of Crown Flatt)

    # ── Historic Edinburgh ──────────────────────────────────────────────────
    "Raeburn Place":           ( 55.9616,  -3.2028),  # Edinburgh — first international 1871

    # ── Historic Glasgow ────────────────────────────────────────────────────
    "Hamilton Crescent":       ( 55.8858,  -4.2843),  # Glasgow — first football international 1872

    # ── Historic London ─────────────────────────────────────────────────────
    "Kennington Oval":         ( 51.4832,  -0.1149),  # London — The Oval cricket ground

    # ── Historic Ireland ────────────────────────────────────────────────────
    "Leinster Cricket Ground": ( 53.3575,  -6.2591),  # Dublin, Ireland
    "Ormeau":                  ( 54.5879,  -5.9256),  # Belfast, N. Ireland
    "Ballynafeigh":            ( 54.5856,  -5.9249),  # Belfast, N. Ireland

    # ── Historic England ────────────────────────────────────────────────────
    "Whalley Range":           ( 53.4476,  -2.2423),  # Manchester, England

    # ── France ─────────────────────────────────────────────────────────────
    "Stade de France":         ( 48.9244,   2.3601),  # Saint-Denis, France
    "Stadium de Toulouse":     ( 43.6297,   1.4009),  # Toulouse — Stade Ernest-Wallon

    # ── New Zealand ────────────────────────────────────────────────────────
    "One NZ Stadium":          (-43.5369, 172.5900),  # Christchurch, NZ

    # ── South Africa ───────────────────────────────────────────────────────
    "Newlands Stadium":        (-33.9788,  18.4614),  # Cape Town
    "Port Elizabeth Cricket Ground": (-33.9618, 25.6053),  # Gqeberha (Port Elizabeth)
}


def get_coords(venue: str) -> Optional[tuple[float, float]]:
    """Return ``(lat, lon)`` for a known venue name, or ``None`` if unlisted."""
    return VENUE_COORDS.get(venue)
