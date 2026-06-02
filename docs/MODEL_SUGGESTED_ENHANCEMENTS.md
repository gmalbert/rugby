# ScrumBet — Model Suggested Enhancements

## Priority 1: Elo Model

### Point Differential Weighting
- Current Elo uses `update_elo()` with a `point_diff` parameter. Validate that large blowouts (40+ point wins) are weighted proportionally but capped to avoid extreme Elo swings.
- Suggested cap: `k_adjusted = K * min(1.5, 1 + point_diff / 30)`.

### League-Specific K Values
- Super Rugby teams play fewer matches than Premiership. Use `ELO_K = 28` for Super Rugby vs. `ELO_K = 35` for high-fixture-count leagues.

### International Elo Crossover
- Top club sides include many international players. Where feasible, blend club Elo with national team Elo for Six Nations specifically.

## Priority 2: Dixon-Coles Model

### Rho Stability
- Dixon-Coles `rho` parameter corrects for the dependency between low-scoring draws. Verify rho is re-estimated each season as scoring patterns evolve.

### Exponential Time Decay
- Older matches should contribute less to parameter estimation. Add `exp(-lambda * days_ago)` weighting in the likelihood function.

### Try Scorer Integration
- The existing `try_scorer.py` model provides per-player try probabilities. Feed team-level try scorer quality as an attack feature into Dixon-Coles.

## Priority 3: New Markets

### Handicap Line Model
- Build a logistic regression on top of Dixon-Coles to predict `win_by_7+` (common rugby handicap line).

### Total Points Model
- Poisson simulation of `home_tries + away_tries`. Rugby totals markets (e.g., over/under 42.5 points) are often mispriced.

## Priority 4: Calibration

- Add a calibration curve page comparing model win probabilities to actual outcomes, split by league.
- Apply Platt scaling if systematic bias is identified.
