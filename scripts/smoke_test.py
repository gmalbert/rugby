"""Smoke test for the integrated odds_api_io client."""
import os
from pathlib import Path

for line in Path(".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from utils.odds_api_io import (
    get_events, get_odds, decimal_to_american, names_match
)

print("decimal_to_american(1.45):", decimal_to_american(1.45))   # -222
print("decimal_to_american(2.60):", decimal_to_american(2.60))   # +160
print("names_match exact:", names_match("Hurricanes", "Hurricanes"))
print("names_match partial:", names_match("Canterbury-Bankstown Bulldogs", "Canterbury-Bankstown Bulldogs"))

events = get_events("rugby", league="rugby-union-super-rugby", status="pending", limit=2)
print(f"\nSuper Rugby events: {len(events)}")
if events:
    ev = events[0]
    print(f"  {ev['home']} vs {ev['away']}  id={ev['id']}")
    odds = get_odds(ev["id"], ["DraftKings", "BetMGM BR"])
    bm = odds.get("bookmakers", {})
    print(f"  Bookmakers with odds: {list(bm.keys())}")
    for bname, mkts in bm.items():
        for m in mkts[:2]:
            first = m.get("odds", [{}])[0] if m.get("odds") else "empty"
            print(f"    {bname} | {m['name']} -> {first}")
