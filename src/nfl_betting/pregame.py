"""Unconfigured future evidence boundary; validates envelopes, never confirms facts."""

import hashlib
import json
from urllib.parse import urlsplit

from .research import aware
from .rules import validate_quote

KINDS = frozenset(
    {
        "official_inactives",
        "player_status",
        "depth_chart",
        "qb_change",
        "market_availability",
        "quote",
    }
)


def validate_evidence(item, *, cutoff, kickoff):
    """Require captured, source-attributed, unexpired evidence strictly pregame.

    A valid envelope is not authentication of the supplier or an ACTIVE decision.
    Published time may be unknown; collection time must never be backdated.
    """
    cutoff, kickoff = aware(cutoff), aware(kickoff)
    if cutoff >= kickoff:
        raise ValueError("Pregame cutoff must precede kickoff")
    if item.get("kind") not in KINDS:
        raise ValueError("Unsupported evidence kind")
    for field in ("provider", "game_id", "snapshot_id", "payload_sha256"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"Missing {field}")
    url = urlsplit(item.get("source_url", ""))
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("Credential-free HTTPS source URL required")
    observed, expires = aware(item.get("observed_at")), aware(item.get("valid_until"))
    if not observed <= cutoff < expires <= kickoff:
        raise ValueError("Future, stale or post-kickoff evidence")
    if item.get("published_at") is not None and aware(item["published_at"]) > observed:
        raise ValueError("Publication after capture")
    encoded = json.dumps(
        item.get("payload"), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    if hashlib.sha256(encoded).hexdigest() != item["payload_sha256"]:
        raise ValueError("Payload hash mismatch")
    player_evidence = item["kind"] in {
        "player_status",
        "qb_change",
        "quote",
        "market_availability",
    }
    if player_evidence and (
        not isinstance(item.get("player_id"), str)
        or not item["player_id"].startswith("00-")
    ):
        raise ValueError("GSIS identity required; names are not identifiers")
    if item["kind"] == "quote":
        quote = item["payload"]
        if (
            quote.get("game_id") != item["game_id"]
            or quote.get("player_id") != item["player_id"]
        ):
            raise ValueError("Quote identity mismatch")
        if (
            quote.get("observed_at") != item["observed_at"]
            or quote.get("valid_until") != item["valid_until"]
        ):
            raise ValueError("Quote time mismatch")
        if not validate_quote(quote, as_of=cutoff).valid:
            raise ValueError("Existing quote contract rejected payload")
    return {"envelope_valid": True, "facts_verified": False, "decision": "NO_BET"}


def unavailable(provider, kind):
    if kind not in KINDS:
        raise ValueError("Unsupported evidence kind")
    return {
        "provider": provider,
        "kind": kind,
        "status": "UNCONFIGURED",
        "records": [],
        "decision": "NO_BET",
    }
