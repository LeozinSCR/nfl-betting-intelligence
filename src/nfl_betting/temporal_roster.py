"""Immutable, explicitly selected evidence for weekly rosters and NFL kickoff changes."""

from collections import Counter, defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from html import unescape
from io import BytesIO
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import uuid4

import polars as pl

from .research import aware

ROSTER_URL = "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{season}.parquet"
KICKOFF_URL = (
    "https://media.nfl.com/news-and-releases/"
    "week-11-schedule-change--jaguars-giants-to-4-25-p-m--et--steeler"
)
KICKOFF_CHANGES = {
    "2026_11_PIT_PHI": "2026-11-22T18:00:00+00:00",
    "2026_11_JAX_NYG": "2026-11-22T21:25:00+00:00",
}
KICKOFF_TEAMS = {"2026_11_PIT_PHI": ("PIT", "PHI"), "2026_11_JAX_NYG": ("JAX", "NYG")}
GSIS = re.compile(r"00-\d{7}")
TEAM = re.compile(r"[A-Z]{2,3}")
TEAM_ALIASES = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}


def utc(value):
    return aware(value).astimezone(UTC)


def _team(value):
    if not isinstance(value, str) or not TEAM.fullmatch(value):
        raise ValueError("Invalid team code")
    return TEAM_ALIASES.get(value, value)


def _roster_rows(body, season):
    columns = ["season", "game_type", "week", "team", "gsis_id", "full_name", "position", "status"]
    frame = pl.read_parquet(BytesIO(body), columns=columns)
    if frame.is_empty() or set(frame["season"].to_list()) != {season}:
        raise ValueError("Empty or wrong-season roster asset")
    rows = []
    for row in frame.filter(pl.col("game_type") == "REG").iter_rows(named=True):
        week = row["week"]
        if type(week) is not int or not 1 <= week <= 18:
            raise ValueError("Invalid regular-season roster week")
        player_id = row["gsis_id"]
        rows.append({
            "team": _team(row["team"]), "week": week,
            "player_id": player_id if GSIS.fullmatch(player_id or "") else None,
            "display_name": row["full_name"], "position": row["position"],
            "roster_status": row["status"],
        })
    if not rows:
        raise ValueError("No regular-season roster rows")
    return rows


def _kickoff_rows(body):
    text = unescape(unescape(body.decode("utf-8", errors="replace")))
    text = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    for phrase in (
        "Nov. 9, 2026",
        "Jacksonville Jaguars at New York Giants game will move to 4:25 p.m. ET",
        "Pittsburgh Steelers at Philadelphia Eagles game will move to 1 p.m. ET",
        "Sunday, Nov. 22",
    ):
        if phrase not in text:
            raise ValueError("NFL release does not substantiate the expected kickoff corrections")
    return KICKOFF_CHANGES.copy()


def _transaction_rows(review, collected_at, source_sha256):
    if not isinstance(review, dict) or review.get("source_sha256") != source_sha256:
        raise ValueError("Transactions must be reviewed against the exact captured source bytes")
    data = review["records"]
    if not isinstance(data, list) or not data:
        raise ValueError("Expected individually reviewed transaction records")
    rows = []
    for row in data:
        player_id = row["player_id"]
        if not isinstance(player_id, str) or not GSIS.fullmatch(player_id):
            raise ValueError("Transactions require a resolved GSIS ID")
        former = _team(row["from_team"]) if row["from_team"] is not None else None
        target = _team(row["to_team"]) if row["to_team"] is not None else None
        if former == target:
            raise ValueError("Transaction must change a team association")
        effective = utc(row["effective_at_utc"])
        published = utc(row["published_at_utc"])
        if published > collected_at:
            raise ValueError("Transaction publication after capture")
        rows.append((player_id, former, target, effective))
    return rows


def _read_capture(folder, cutoff):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1 or manifest["snapshot_id"] != folder.name:
        raise ValueError("Invalid evidence snapshot identity")
    collected = utc(manifest["collected_at_utc"])
    available = utc(manifest["available_at_utc"])
    stamp = collected.strftime("%Y%m%dT%H%M%S%fZ")
    if not re.fullmatch(rf"{re.escape(manifest['kind'])}-{stamp}-[0-9a-f]{{32}}", folder.name):
        raise ValueError("Snapshot identity does not match the captured timestamp")
    if collected > available:
        raise ValueError("Evidence cannot be available before its collection")
    if available > cutoff:
        return None
    body = (folder / "source.bin").read_bytes()
    if sha256(body).hexdigest() != manifest["sha256"]:
        raise ValueError("Evidence source hash mismatch")
    kind, url = manifest["kind"], manifest["source_url"]
    if kind == "roster" and url == ROSTER_URL.format(season=manifest["season"]):
        rows = _roster_rows(body, manifest["season"])
    elif kind == "kickoff" and url == KICKOFF_URL:
        rows = _kickoff_rows(body)
    elif kind == "transactions" and _transaction_source(url):
        reviewed = (folder / "reviewed.json").read_bytes()
        if sha256(reviewed).hexdigest() != manifest["reviewed_sha256"]:
            raise ValueError("Reviewed transactions hash mismatch")
        rows = _transaction_rows(json.loads(reviewed), collected, manifest["sha256"])
    else:
        raise ValueError("Unsupported evidence source")
    return manifest, rows


def _transaction_source(url):
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https" and parsed.netloc == "www.nfl.com"
        and (parsed.path == "/transactions" or parsed.path.startswith("/transactions/"))
        and not parsed.query and not parsed.fragment
    )


def capture(kind, output, *, season=None, url=None, reviewed=None):
    """Capture one public asset, preserving the exact source bytes."""
    if kind == "roster" and type(season) is int and 1999 <= season <= 9999:
        source = ROSTER_URL.format(season=season)
        provider = "NFLverse"
    elif kind == "kickoff":
        source = KICKOFF_URL
        provider = "NFL Football Communications"
    elif kind == "transactions" and url and _transaction_source(url) and reviewed:
        source = url
        provider = "NFL League Transactions"
    else:
        raise ValueError("Roster needs --season. Transactions need --url and reviewed GSIS records.")
    output = Path(output).resolve()
    repo = Path(__file__).resolve().parents[2]
    protected = ("legacy", "data/processed", "data/reference", "data/canonical", "data/raw_auto", "web/public")
    if any(output.is_relative_to(repo / path) for path in protected) or any(
        (folder / name).exists()
        for folder in (output, *output.parents)
        for name in ("manifest.json", "build_manifest.json")
    ):
        raise ValueError("Capture output must be outside historical artifacts and web assets")
    with urlopen(source, timeout=30) as response:
        body = response.read()
        modified = response.headers.get("Last-Modified")
    collected = datetime.now(UTC)
    source_hash = sha256(body).hexdigest()
    reviewed_bytes = None
    if kind == "roster":
        _roster_rows(body, season)
    elif kind == "kickoff":
        _kickoff_rows(body)
    else:
        reviewed_bytes = Path(reviewed).read_bytes()
        _transaction_rows(json.loads(reviewed_bytes), collected, source_hash)

    stamp = collected.strftime("%Y%m%dT%H%M%S%fZ")
    destination = output / f"{kind}-{stamp}-{uuid4().hex}"
    manifest = {
        "schema_version": 1, "snapshot_id": destination.name, "kind": kind,
        "provider": provider, "source_url": source, "season": season,
        "source_last_modified": modified, "collected_at_utc": collected.isoformat(),
        "sha256": source_hash,
    }
    if kind == "kickoff":
        manifest["source_publication_date"] = "2026-11-09"
    destination.mkdir(parents=True)
    (destination / "source.bin").write_bytes(body)
    if reviewed_bytes is not None:
        (destination / "reviewed.json").write_bytes(reviewed_bytes)
        manifest["reviewed_sha256"] = sha256(reviewed_bytes).hexdigest()
    manifest["available_at_utc"] = datetime.now(UTC).isoformat()
    # The final manifest is the receipt. An interrupted run has no usable receipt.
    with (destination / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return destination, manifest


def load_evidence(paths, season, cutoff):
    captures = {}
    for path in paths:
        loaded = _read_capture(path, cutoff)
        if loaded is not None:
            manifest, rows = loaded
            if manifest["kind"] in {"roster", "transactions"} and manifest["season"] != season:
                raise ValueError("Evidence belongs to a different season")
            previous = captures.get(manifest["snapshot_id"])
            if previous is not None and previous[0] != manifest:
                raise ValueError("Conflicting copies of an evidence snapshot")
            captures[manifest["snapshot_id"]] = manifest, rows
    return list(captures.values())


def select_roster(canonical_rows, captures, week, cutoff, *, fallback):
    batches = defaultdict(list)
    for row in canonical_rows:
        source = row["source"]
        batches[row["team"], row["week"], source["available_at_utc"], source["snapshot_id"]].append(row)
    for source, rows in captures:
        if source["kind"] != "roster":
            continue
        for row in rows:
            if row["week"] <= week and (fallback or row["week"] == week):
                batches[row["team"], row["week"], source["available_at_utc"], source["snapshot_id"]].append(
                    {**row, "source": source}
                )

    choices = {}
    conflicts = set()
    for (team, origin, available, snapshot), rows in batches.items():
        if not (origin == week or fallback and origin < week) or utc(available) > cutoff:
            continue
        rank = (origin, utc(available))
        previous = choices.get(team)
        if previous is None or rank > previous[0]:
            choices[team] = (rank, rows)
            conflicts.discard(team)
        elif rank == previous[0] and snapshot != previous[1][0]["source"]["snapshot_id"]:
            conflicts.add(team)

    selected = []
    for team, ((origin, available), rows) in choices.items():
        if team in conflicts:
            continue
        for row in rows:
            selected.append({
                **row, "roster_evidence": {
                    **row["source"], "source_week": origin, "cutoff_utc": cutoff.isoformat(),
                    "status": "EXACT_WEEK_ROSTER" if origin == week else "PROVISIONAL_ROSTER",
                    "age_weeks": week - origin,
                    "days_since_collection": (cutoff - utc(row["source"]["collected_at_utc"])).days,
                    "team_membership_status": "UNVERIFIED",
                },
            })

    events = {}
    for source, rows in captures:
        if source["kind"] != "transactions":
            continue
        for player, former, target, effective in rows:
            if effective > cutoff:
                continue
            for team, ended in ((former, True), (target, False)):
                if team is None:
                    continue
                old = events.get((player, team))
                if not old or effective > old[0] or (effective == old[0] and ended):
                    events[player, team] = effective, ended
    for row in selected:
        player = row["player_id"]
        row["excluded_reason"] = (
            "CUT" if row["roster_status"] == "CUT"
            else "ENDED_TEAM_MEMBERSHIP" if events.get((player, row["team"]), (None, False))[1]
            else None
        )
    # Resolve confirmed removals first, then fail closed on remaining conflicts
    # league-wide, including franchises outside the selected slate.
    id_counts = Counter(
        row["player_id"] for row in selected if row["player_id"] and not row["excluded_reason"]
    )
    for row in selected:
        row["id_rows"] = id_counts[row["player_id"]]
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("roster", "kickoff", "transactions"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--season", type=int)
    parser.add_argument("--url")
    parser.add_argument("--reviewed", type=Path)
    args = parser.parse_args(argv)
    if args.kind == "transactions" and args.season is None:
        parser.error("--season is required for transactions")
    destination, manifest = capture(**vars(args))
    print(json.dumps({"destination": str(destination), **manifest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
