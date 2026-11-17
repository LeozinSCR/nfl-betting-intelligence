"""Fail-closed interfaces for future, free-only odds integrations.

No live provider is enabled here.  The normalizer exists so provider fixtures
can be tested without credentials, network access, or redistribution of feeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProviderState:
    provider: str
    live_enabled: bool
    authentication: str
    zero_cost_status: str
    coverage_status: str
    redistribution_status: str


PROVIDERS = {
    "propline": ProviderState(
        "PropLine", False, "UNVERIFIED", "UNVERIFIED", "UNVERIFIED",
        "UNVERIFIED",
    ),
    "parlayapi": ProviderState(
        "ParlayAPI", False, "UNVERIFIED", "UNVERIFIED", "UNVERIFIED",
        "UNVERIFIED",
    ),
    "the_odds_api": ProviderState(
        "The Odds API", False, "API_KEY_REQUIRED", "FREE_QUOTA_REQUIRES_SIGNUP",
        "NFL_PLAYER_PROPS_DOCUMENTED_NOT_TESTED_IN_TASK6", "TERMS_REVIEW_REQUIRED",
    ),
    "fanline_wire": ProviderState(
        "FanLine Wire", False, "UNVERIFIED", "UNVERIFIED", "UNVERIFIED",
        "UNVERIFIED",
    ),
    "stake": ProviderState(
        "Stake", False, "PUBLIC_LIMITED_ENDPOINT_OBSERVED",
        "NO_ADDITIONAL_COST_OBSERVED_WITH_RATE_LIMIT",
        "TEAM_MARKETS_OBSERVED_PLAYER_PROPS_NOT_DEMONSTRATED",
        "TERMS_REVIEW_REQUIRED",
    ),
}


REQUIRED_FIELDS = {
    "provider",
    "bookmaker",
    "source_url",
    "selection_id",
    "game_id",
    "player_id",
    "market",
    "side",
    "line",
    "decimal_odds",
    "available",
    "observed_at",
    "valid_until",
}


def _aware(value, field):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be an aware datetime")
    return value


def normalize_fixture(payload, *, expected_provider=None):
    """Normalize already-mapped fixture quotes, rejecting partial records.

    This function deliberately does not infer IDs, expiry, bookmaker, player,
    line, or availability from provider-specific nested payloads.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("quotes"), list):
        raise ValueError("fixture payload must contain a quotes list")
    normalized, rejected = [], []
    for index, raw in enumerate(payload["quotes"]):
        if not isinstance(raw, dict):
            rejected.append({"index": index, "reason": "NOT_AN_OBJECT"})
            continue
        missing = sorted(REQUIRED_FIELDS - raw.keys())
        if missing:
            rejected.append({"index": index, "reason": "MISSING_FIELDS", "fields": missing})
            continue
        try:
            if expected_provider and raw["provider"] != expected_provider:
                raise ValueError("provider mismatch")
            url = urlsplit(raw["source_url"])
            if url.scheme != "https" or not url.netloc or url.username or url.password:
                raise ValueError("invalid source_url")
            odds = raw["decimal_odds"]
            if isinstance(odds, bool) or not isinstance(odds, (int, float)):
                raise ValueError("decimal_odds must be numeric")
            if not math.isfinite(odds) or odds <= 1:
                raise ValueError("decimal_odds must be finite and >1")
            observed = _aware(raw["observed_at"], "observed_at")
            valid_until = _aware(raw["valid_until"], "valid_until")
            if valid_until <= observed:
                raise ValueError("valid_until must follow observed_at")
            if raw["available"] is not True:
                raise ValueError("selection is unavailable")
            if not all(
                isinstance(raw[field], str) and raw[field].strip()
                for field in (
                    "provider", "bookmaker", "selection_id", "game_id",
                    "player_id", "market", "side",
                )
            ):
                raise ValueError("quote identity fields must be non-empty strings")
            item = dict(raw)
            item["decimal_odds"] = float(odds)
            item["observed_at"] = observed.isoformat()
            item["valid_until"] = valid_until.isoformat()
            normalized.append(item)
        except (TypeError, ValueError) as exc:
            rejected.append({"index": index, "reason": str(exc)})
    return {
        "quotes": normalized,
        "rejected": rejected,
        "partial": bool(rejected),
        "decision": "NO_BET",
        "financial_approved": False,
    }
