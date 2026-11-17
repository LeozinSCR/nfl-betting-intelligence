# Codex workspace instructions — NFL Betting Intelligence

## North star and absolute rule
Build a **zero-additional-cost** NFL research web app (mobile-first, hybrid games + prop scanner), grounded in NFL data, to test for mispriced player props / Anytime TD using prospective calibrated probabilities, true bookmaker prices, uncertainty and matchup context. Paid APIs, credits, servers, domains or subscriptions are **not allowed**; reduce scope or use a lawful free alternative. Never place bets or merge PRs automatically.

## Always respect
- Historical CSVs, `legacy/` Masters and source artifacts are immutable. Keep SHA-256 and provenance.
- Use **pre-game as-of cutoffs**; future/current-game observations cannot enter pre-game predictors. Missing IDs, snaps, inactive status and missing values are not zeros.
- Distinguish hit-rate from projected probability. Unvalidated p, unavailable/expired/unknown odds, unverified availability or unpriced SGP → **NO_BET**; never invent model probabilities, quotes or source links.
- Price comparison uses sportsbook/provider + selection/line + capture timestamp + validity and settlement semantics; **minimum decimal odds 1.50** to highlight value candidates. No claim of +EV without independently tested model and valid quote. Rank robust, uncertainty-aware edge, not simply higher win rate.
- Correlation is **measured**, not assumed: within-game QB/WR/RB dependencies and proper joint pricing; for TD consider same-team joint relationships, not automatic positive correlation. Pairwise coefficients do not validate 3+ leg products.
- Three research cards: Multi-Game (>=4 games, >=2 props/game; >=8 legs), Same-Game (default 2–3 if supported), Anytime TD (>=4 on multi-game slate, >=2 on single-game slate); **total budget cap R$50**, no forced wager. Legacy caps R$35 Best + R$15 TD remain unless reallocations explicitly approved; suggested 20/15/15 is NOT adopted.
- Never commit keys or redistribute raw commercial odds without permission. Frontend is read-only and does not authorize financial action.

## Read context narrowly
- Current project roadmap and unresolved blockers: [Issue #6](https://github.com/LeozinSCR/nfl-betting-intelligence/issues/6).
- Research skill and data access: `.agents/skills/nfl-betting-intelligence/SKILL.md`.
- Contracts: `docs/VALIDATION_CONTRACT.md`, `docs/DATA_SOURCES.md`, `docs/OPERATIONS.md`.
- Data architecture: `docs/TASK3_DATA_RECONCILIATION.md`; skills: `docs/TASK4_AGENT_SKILLS_INTEGRATION.md`.
- Web UI: `web/README.md`. Do not load all phase reports unless the current task directly requires them.

## Work efficiently
1. Read only touched modules and their direct tests; give a short plan then implement one bounded objective.
2. Prefer deterministic local Python/DuckDB/npm and CI over token-heavy manual review of giant exports.
3. Run targeted tests, then wider suite if shared contracts changed. Report exact commands and whether they actually ran.
4. State files changed, tests and blockers in <=12 lines. Do not produce 2,000-line audit docs unless requested.
5. Keep PRs small and chained to the current latest reviewed branch; no merges/paid deployment.

## Useful commands
Python (3.12, after lockfile install per root README):
```sh
python -m unittest discover -s tests -q
python tools/verify_history.py
python -m pip check
```
Frontend:
```sh
cd web && npm install --no-audit --no-fund && npm run build
```
No network/internet requests in offline tests. The initial web `slate.json` has status UNAVAILABLE, **not actual picks**.
