"""Validate the local NFLverse calendar evidence used by the pregame pilot."""

from datetime import UTC, datetime
import json
import re
from urllib.parse import urlsplit

import polars as pl
from pytz import InvalidTimeError, timezone

from .provenance import sha256
from .temporal_roster import _team, utc

MODE = "NFLVERSE_LICENSED"
SOURCE = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.parquet"
LICENSE = {
    "id": "CC-BY-4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "declaration_url": "https://github.com/nflverse/nflverse-data/blob/ab1331c85fd222ce953fe61363b099c0629de0a1/LICENSE.md",
    "attribution": ["NFLverse", "Lee Sharpe"],
}
FILES = ("manifest.json", "origin.json", "source.parquet", "retention.txt")
GAME_FIELDS = ("game_id", "away_team", "home_team", "kickoff_utc")
TRANSFORMATIONS = ["REG season/week filter", "canonical team codes", "America/New_York to UTC", "four calendar fields"]
EASTERN = timezone("America/New_York")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _file(folder, name):
    path = folder / name
    if path.is_symlink() or not path.is_file() or not path.stat().st_size:
        raise ValueError(f"Missing or unsafe licensed calendar file: {name}")
    return path


def _games(path, season, week):
    try:
        table = pl.read_parquet(path, columns=["season", "week", "game_type", "game_id", "away_team",
                                               "home_team", "gameday", "gametime"])
        table = table.filter((pl.col("season") == season) & (pl.col("week") == week) & (pl.col("game_type") == "REG"))
        games = {}
        for row in table.iter_rows(named=True):
            game_id = row["game_id"]
            away, home = _team(row["away_team"]), _team(row["home_team"])
            if not isinstance(game_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", game_id) or game_id in games or away == home:
                raise ValueError("Invalid or duplicate licensed game identity")
            kickoff = datetime.fromisoformat(f'{row["gameday"]}T{row["gametime"]}')
            kickoff = EASTERN.localize(kickoff, is_dst=None).astimezone(UTC)
            games[game_id] = dict(zip(GAME_FIELDS, (game_id, away, home, kickoff.isoformat()), strict=True))
    except (pl.exceptions.PolarsError, InvalidTimeError, TypeError) as exc:
        raise ValueError("Invalid licensed schedule parquet or ambiguous Eastern kickoff") from exc
    if not games:
        raise ValueError("Licensed schedule has no games for the requested week")
    return games


def _observations(rows):
    observations = {}
    for row in rows:
        url = urlsplit(row["source_url"])
        observed = utc(row["observed_at_utc"])
        published = row.get("published_at_utc")
        game_id = row["game_id"]
        if (
            game_id in observations or not _text(row["reviewed_by"])
            or url.scheme != "https" or url.netloc not in {"nfl.com", "www.nfl.com", "media.nfl.com"}
            or url.path in {"", "/"} or url.query or url.fragment
            or (published is not None and utc(published) > observed)
        ):
            raise ValueError("KICKOFF_CONFLICT_OR_UNVERIFIED: invalid official observation")
        observations[game_id] = {
            "source_url": row["source_url"], "reviewed_by": row["reviewed_by"],
            "kickoff_utc": utc(row["kickoff_utc"]).isoformat(), "observed_at_utc": observed.isoformat(),
            "published_at_utc": utc(published).isoformat() if published is not None else None,
        }
    return observations


def load(folder):
    files = {name: _file(folder, name) for name in FILES}
    manifest = json.loads(files["manifest.json"].read_text(encoding="utf-8-sig"))
    origin = json.loads(files["origin.json"].read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1 or manifest["license"] != LICENSE:
        raise ValueError("LICENSE_SCOPE_UNVERIFIED: schedules license or attribution mismatch")
    retention = manifest["local_retention"]
    if (
        retention["scope"] != "LOCAL_PILOT_RAW_ARCHIVE" or not _text(retention["reviewed_by"])
        or not _text(retention["basis_reference"]) or not files["retention.txt"].read_text(encoding="utf-8").strip()
        or sha256(files["retention.txt"]) != retention["sha256"]
    ):
        raise ValueError("LICENSE_SCOPE_UNVERIFIED: documented local raw retention is required")
    reviewed = utc(retention["reviewed_at_utc"])
    entry = origin["sources"]["schedules"]
    bodies = [row for row in entry["http_responses"] if row["status_code"] == 200]
    digest = sha256(files["source.parquet"])
    origin_digest = sha256(files["origin.json"])
    if (
        entry["status"] != "OK" or entry["resolved_download_url"] != SOURCE
        or len(bodies) != 1 or bodies[0]["requested_url"] != SOURCE or bodies[0]["sha256"] != digest
        or digest != manifest["sha256"] or origin_digest != manifest["origin_sha256"]
        or manifest["source_version"] != f"sha256:{digest}" or origin["season"] != manifest["season"]
        or not _text(origin["run_id"])
    ):
        raise ValueError("Licensed schedule source, SHA-256 or version mismatch")
    start, received, end = map(utc, (entry["started_at_utc"], bodies[0]["received_at_utc"], entry["finished_at_utc"]))
    available = utc(origin["finished_at_utc"])
    published = entry.get("published_at_utc")
    if (
        not utc(origin["started_at_utc"]) <= start <= received <= end <= available
        or (published is not None and utc(published) > received)
    ):
        raise ValueError("Invalid licensed schedule capture chronology")
    proof = {
        "kind": MODE, "season": manifest["season"], "week": manifest["week"],
        "source_url": SOURCE, "source_version": manifest["source_version"], "sha256": digest,
        "origin_sha256": origin_digest, "source_snapshot_id": origin["run_id"],
        "started_at_utc": start.isoformat(), "received_at_utc": received.isoformat(),
        "finished_at_utc": end.isoformat(), "source_available_at_utc": available.isoformat(),
        "available_at_utc": max(available, reviewed).isoformat(),
        "published_at_utc": utc(published).isoformat() if published is not None else None,
        "license": LICENSE, "transformations": TRANSFORMATIONS,
        "local_retention": {
            "sha256": retention["sha256"], "scope": retention["scope"], "basis_reference": retention["basis_reference"],
            "reviewed_by": retention["reviewed_by"], "reviewed_at_utc": reviewed.isoformat(),
        },
        "observations": _observations(manifest["official_observations"]),
    }
    return proof, _games(files["source.parquet"], manifest["season"], manifest["week"])


def confirm(proof, target, planned):
    observed = proof["observations"].get(target["game_id"])
    if (
        observed is None or utc(observed["kickoff_utc"]) != utc(target["kickoff_utc"])
        or not utc(proof["received_at_utc"]) <= utc(observed["observed_at_utc"]) <= planned
    ):
        raise ValueError(f'KICKOFF_CONFLICT_OR_UNVERIFIED: {target["game_id"]}')
