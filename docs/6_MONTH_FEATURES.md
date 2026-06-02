# ScrumBet — 6-Month Feature Roadmap

## Month 1: Match Day

- **Today's fixtures** — All upcoming matches across 6 leagues with model win %, Dixon-Coles expected score, and DraftKings line.
- **Match countdown timer** — Days/hours to kickoff for the next Top 14 and Premiership games.
- **Head-to-head preview** — Last 5 meetings for tonight's matchup with scorelines.
- **Live score banner** — Auto-refresh for in-play matches.

## Month 2: Team Analytics

- **Team profile page** — Elo history chart, season stats, Dixon-Coles attack/defence parameters.
- **League standings** — Live points tables for all 6 leagues pulled from ESPN/Rugby-Reference.
- **Elo leaderboard** — All-time highest Elo by league; current rankings.

## Month 3: Betting Intelligence

- **Value finder** — Edge > 3% vs. bookmaker odds; ranked by EV.
- **Handicap market analysis** — Win-by-7+ probability vs. DraftKings spread line.
- **Totals model** — Over/under probability for each match.

## Month 4: Player Stats

- **Top try scorer tracker** — Season tries leaders across all six leagues.
- **Try scorer props** — Anytime try scorer probability vs. DraftKings market.
- **Kicker analysis** — Conversion %, penalty %, goal line vs. wide-angle.

## Month 5: Historical Analysis

- **Model accuracy by league** — Accuracy split across Six Nations, Super Rugby, Premiership, Top 14, URC, Champions Cup.
- **Cup competition tracker** — European Champions Cup bracket and model predictions.
- **Season-end playoff probability** — Playoff qualification odds for each club.

## Month 6: Automation

- **Weekend email** — Friday picks email with top bets for the weekend slate.
- **Nightly pipeline** — GitHub Action runs `scripts/pipeline.py` at 03:00 UTC daily.
- **Discord webhook** — Post fixture predictions with value bets to Discord.
