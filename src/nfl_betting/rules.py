"""Fail-closed structural checks. These checks never authorize a wager.

Inputs are explicit mappings so evidence can be serialized alongside a report.
See docs/VALIDATION_CONTRACT.md. No implicit independence or model approval.
"""
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from math import isfinite
from numbers import Real
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BEST_CAP = Decimal("35.00")
TD_CAP = Decimal("15.00")
TOTAL_CAP = Decimal("50.00")
PLAYER_MARKETS = frozenset({
    "receptions", "targets", "carries", "rec_yards", "rush_yards",
    "pass_yards", "pass_attempts", "completions", "anytime_td",
})


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    message: str
    leg_index: int | None = None


@dataclass(frozen=True)
class ValidationResult:
    issues: tuple[Issue, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def valid(self):
        return not self.issues

    @property
    def statistical_approved(self):
        return False

    @property
    def financial_approved(self):
        return False

    @property
    def decision(self):
        return "NO_BET"

    def __bool__(self):
        raise TypeError("Inspect .valid explicitly; structural validation is not wager approval")


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(f"{label} must be a finite number")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{label} must be finite") from exc
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def validate_probability(value):
    value = _number(value, "probability")
    if not 0 <= value <= 1:
        raise ValueError("Probability outside [0, 1]")
    return value


def validate_decimal_odds(value):
    value = _number(value, "decimal_odds")
    if value <= 1:
        raise ValueError("Decimal odds must exceed 1")
    return value


def implied_probability(decimal_odds):
    return 1 / validate_decimal_odds(decimal_odds)


def validate_joint_probability(probability, marginals):
    """Validate arbitrary-leg Fréchet bounds; never clamp historical values."""
    p = validate_probability(probability)
    if not marginals:
        raise ValueError("Marginal probabilities required")
    ps = [validate_probability(x) for x in marginals]
    if not max(0.0, sum(ps) - (len(ps) - 1)) <= p <= min(ps):
        raise ValueError("Joint probability violates Frechet bounds")
    return p


def _timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _url(value):
    if not _text(value):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def _evidence(data, now, field, *, max_age, time_key="checked_at", index=None):
    issues = []
    if not isinstance(data, Mapping):
        return [Issue("MISSING_EVIDENCE", field, "Evidence mapping required", index)]
    if not _url(data.get("source_url")):
        issues.append(Issue("MISSING_ORIGIN", field + ".source_url", "HTTPS source URL required", index))
    try:
        observed = _timestamp(data.get(time_key))
        expires = _timestamp(data.get("valid_until"))
        if not observed <= now < expires or now - observed > max_age:
            raise ValueError("Future, expired or stale evidence")
    except (TypeError, ValueError, OverflowError):
        issues.append(Issue("INVALID_TIME", field, "Aware timestamps, observed <= as_of < valid_until and freshness required", index))
    return issues


def validate_quote(quote, *, as_of=None, max_age=timedelta(minutes=5), leg=None):
    now = _timestamp(as_of or datetime.now(timezone.utc))
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise ValueError("Positive quote max_age required")
    issues = _evidence(quote, now, "quote", max_age=max_age, time_key="observed_at")
    if not isinstance(quote, Mapping):
        return ValidationResult(tuple(issues))
    for key in ("provider", "bookmaker", "selection_id", "game_id", "player_id", "market", "side"):
        if not _text(quote.get(key)):
            issues.append(Issue("MISSING_FIELD", "quote." + key, "Nonempty identifier required"))
    try:
        validate_decimal_odds(quote.get("decimal_odds"))
    except ValueError as exc:
        issues.append(Issue("INVALID_ODDS", "quote.decimal_odds", str(exc)))
    if quote.get("available") is not True:
        issues.append(Issue("MARKET_UNAVAILABLE", "quote.available", "Explicit availability required"))
    if not _text(quote.get("market")) or quote["market"] not in PLAYER_MARKETS:
        issues.append(Issue("PLAYER_PROPS_ONLY", "quote.market", "Unsupported player market"))
    try:
        if quote.get("market") == "anytime_td":
            if quote.get("side") != "yes" or quote.get("line") is not None:
                raise ValueError("Anytime TD requires side=yes and line=null")
        elif quote.get("side") not in ("over", "under") or _number(quote.get("line"), "line") < 0:
            raise ValueError("Nonnegative line and over/under side required")
    except ValueError as exc:
        issues.append(Issue("INVALID_SELECTION", "quote.line", str(exc)))
    if leg is not None:
        for key in ("game_id", "player_id", "market", "side", "line"):
            if quote.get(key) != leg.get(key):
                issues.append(Issue("QUOTE_MISMATCH", "quote." + key, "Quote does not match selection"))
    return ValidationResult(tuple(issues))


@dataclass(frozen=True)
class ResearchEV:
    value_per_unit: float
    label: str = "EXPLORATORY_NOT_CALIBRATION_APPROVAL"
    decision: str = "NO_BET"
    statistical_approved: bool = False
    financial_approved: bool = False


def expected_value(probability, quote, *, push_probability, as_of=None):
    """Research arithmetic only; no boolean flag can approve a model or wager."""
    p = validate_probability(probability)
    push = validate_probability(push_probability)
    if p + push > 1:
        raise ValueError("Win and push probabilities exceed 1")
    result = validate_quote(quote, as_of=as_of)
    if not result.valid:
        raise ValueError("Invalid quote: " + ",".join(x.code for x in result.issues))
    value = p * validate_decimal_odds(quote["decimal_odds"]) - (1 - push)
    return ResearchEV(value)


def _money(value):
    if isinstance(value, bool):
        raise ValueError("Invalid monetary amount")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Finite nonnegative BRL amount in cents required")
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid monetary amount") from exc
    return amount


def validate_budget(best=Decimal("0"), td=Decimal("0")):
    issues = []
    amounts = {}
    for name, value, cap in (("best", best, BEST_CAP), ("td", td, TD_CAP)):
        try:
            amounts[name] = _money(value)
            if amounts[name] > cap:
                issues.append(Issue("BUDGET_EXCEEDED", name, f"Cap BRL {cap}"))
        except ValueError as exc:
            issues.append(Issue("INVALID_BUDGET", name, str(exc)))
    if len(amounts) == 2 and sum(amounts.values()) > TOTAL_CAP:
        issues.append(Issue("TOTAL_BUDGET_EXCEEDED", "total", "Cap BRL 50.00"))
    return ValidationResult(tuple(issues))


def _validate_parlay(legs, *, kind, schedule=None, slate_date=None, as_of=None,
                     timezone_name="America/Sao_Paulo", require_quotes=False,
                     stake=Decimal("0"), joint_probability=None):
    issues, warnings = [], []
    try:
        now = _timestamp(as_of or datetime.now(timezone.utc))
        zone = ZoneInfo(timezone_name)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return ValidationResult((Issue("INVALID_CONTEXT", "as_of/timezone", "Valid timezone and aware as_of required"),))
    if not isinstance(slate_date, date) or isinstance(slate_date, datetime):
        issues.append(Issue("MISSING_SLATE_DATE", "slate_date", "Explicit calendar date required"))
    games = {}
    if not isinstance(schedule, Sequence) or isinstance(schedule, (str, bytes)) or not schedule:
        issues.append(Issue("MISSING_SCHEDULE", "schedule", "Nonempty sourced schedule required"))
    else:
        for game in schedule:
            if not isinstance(game, Mapping) or not _text(game.get("game_id")):
                issues.append(Issue("INVALID_SCHEDULE", "schedule", "Game identifier required"))
                continue
            gid = game["game_id"]
            issues.extend(_evidence(game, now, "schedule", max_age=timedelta(days=7)))
            try:
                kickoff = _timestamp(game.get("kickoff"))
                if kickoff.astimezone(zone).date() != slate_date:
                    raise ValueError("Game outside slate date")
                if gid in games or not _text(game.get("home_team")) or not _text(game.get("away_team")) or game["home_team"] == game["away_team"]:
                    raise ValueError("Duplicate game or invalid teams")
                games[gid] = (kickoff, game["home_team"], game["away_team"])
            except (TypeError, ValueError, OverflowError) as exc:
                issues.append(Issue("INVALID_SCHEDULE", "schedule", str(exc)))
    if not isinstance(legs, Sequence) or isinstance(legs, (str, bytes)):
        return ValidationResult(tuple(issues + [Issue("INVALID_LEGS", "legs", "Sequence required")]))
    if kind == "best":
        issues.extend(validate_budget(best=stake).issues)
        minimum = 8
    else:
        issues.extend(validate_budget(td=stake).issues)
        minimum = 2 if len(games) == 1 else 4
    if len(legs) < minimum:
        issues.append(Issue("TOO_FEW_LEGS", "legs", f"At least {minimum} selections required"))
    counts, seen, player_markets = Counter(), set(), set()
    probabilities = []
    for i, leg in enumerate(legs):
        if not isinstance(leg, Mapping):
            issues.append(Issue("INVALID_LEG", "legs", "Mapping required", i))
            continue
        for key in ("game_id", "player_id", "team", "market", "side"):
            if not _text(leg.get(key)):
                issues.append(Issue("MISSING_FIELD", key, "Nonempty string required", i))
        gid, pid, market, side = (leg.get(k) for k in ("game_id", "player_id", "market", "side"))
        # Malformed JSON identifiers cannot become dict/set keys.
        if not all(_text(x) for x in (gid, pid, market, side)):
            continue
        counts[gid] += 1
        if gid not in games:
            issues.append(Issue("GAME_NOT_IN_SLATE", "game_id", "Unknown game", i))
        else:
            kickoff, home, away = games[gid]
            if kickoff <= now:
                issues.append(Issue("GAME_STARTED", "game_id", "Pregame selections only", i))
            if leg.get("team") not in (home, away):
                issues.append(Issue("TEAM_GAME_MISMATCH", "team", "Player team must belong to game", i))
        if market not in PLAYER_MARKETS or leg.get("is_player_prop") is not True:
            issues.append(Issue("PLAYER_PROPS_ONLY", "market", "Explicit supported player prop required", i))
        if kind == "td" and market != "anytime_td":
            issues.append(Issue("TD_MARKET_ONLY", "market", "Anytime TD required", i))
        try:
            line = leg.get("line")
            if market == "anytime_td":
                if line is not None or side != "yes":
                    raise ValueError("Anytime TD requires side=yes, line=null")
            else:
                line = _number(line, "line")
                if line < 0 or side not in ("over", "under"):
                    raise ValueError("Nonnegative line and over/under required")
            key = (gid, pid, market, side, line)
            if key in seen:
                issues.append(Issue("DUPLICATE_SELECTION", "legs", "Repeated selection", i))
            seen.add(key)
        except ValueError as exc:
            issues.append(Issue("INVALID_SELECTION", "line/side", str(exc), i))
        pm = (gid, pid, market)
        if pm in player_markets:
            issues.append(Issue("REDUNDANT_PLAYER_MARKET", "legs", "Same player/market repeated or conflicting", i))
        player_markets.add(pm)
        for field, max_age in (("player_availability", timedelta(hours=24)), ("market_availability", timedelta(minutes=5))):
            value = leg.get(field)
            issues.extend(_evidence(value, now, field, max_age=max_age, index=i))
            value = value if isinstance(value, Mapping) else {}
            if field == "player_availability" and value.get("status") != "ACTIVE":
                issues.append(Issue("PLAYER_UNAVAILABLE", field, "Confirmed ACTIVE status required", i))
            if field == "market_availability" and value.get("available") is not True:
                issues.append(Issue("MARKET_UNAVAILABLE", field, "Confirmed market availability required", i))
        injury = leg.get("injury_status")
        if not isinstance(injury, str) or injury.strip().upper() not in {"HEALTHY", "ACTIVE", "QUESTIONABLE"}:
            issues.append(Issue("INELIGIBLE_PLAYER", "injury_status", "Unknown, inactive, OUT, IR or other unavailable status blocked", i))
        elif injury.strip().upper() == "QUESTIONABLE":
            warnings.append(f"leg[{i}]: QUESTIONABLE; requires current ACTIVE confirmation")
        if leg.get("team_stable") is not True:
            issues.append(Issue("TEAM_INSTABILITY", "team_stable", "Explicit stability assessment required for selected team", i))
        if "probability" in leg:
            try:
                probabilities.append(validate_probability(leg["probability"]))
            except ValueError as exc:
                issues.append(Issue("INVALID_PROBABILITY", "probability", str(exc), i))
        if require_quotes or "quote" in leg:
            q = validate_quote(leg.get("quote"), as_of=now, leg=leg)
            issues.extend(Issue(x.code, x.field, x.message, i) for x in q.issues)
    if kind == "best":
        if len(counts) < 4:
            issues.append(Issue("MIN_FOUR_GAMES", "legs", "At least four distinct games required"))
        if any(n < 2 for n in counts.values()):
            issues.append(Issue("MIN_TWO_PER_GAME", "legs", "Each included game needs at least two props"))
    elif len(games) > 1:
        if len(counts) < 2:
            issues.append(Issue("TD_DISTRIBUTION_VIOLATION", "legs", "TDs must span multiple games"))
        if any(n > 2 for n in counts.values()):
            warnings.append("TD_DISTRIBUTION_REVIEW: more than two TDs in one game; preference is one or two")
    if joint_probability is not None:
        try:
            if len(probabilities) != len(legs):
                raise ValueError("All marginal probabilities required")
            validate_joint_probability(joint_probability, probabilities)
        except ValueError as exc:
            issues.append(Issue("INVALID_JOINT_PROBABILITY", "joint_probability", str(exc)))
    warnings.append("STRUCTURAL_ONLY: calibration, correlations, settlement rules and financial approval remain unverified")
    return ValidationResult(tuple(issues), tuple(warnings))


def validate_best_parlay(legs, **context):
    return _validate_parlay(legs, kind="best", **context)


def validate_td_parlay(legs, **context):
    return _validate_parlay(legs, kind="td", **context)
