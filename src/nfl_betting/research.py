"""Offline, bounded, snapshot-attributed queries for the repository Agent Skill."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .canonical import open_database
from .provenance import code_identity, sha256

# No caller SQL, network, extensions, names-only joins or model promotion.
QUERIES = {
    "games": "games",
    "players": "player_week",
    "snaps": "snap_counts",
    "usage": "offensive_opportunities",
    "injuries": "injuries",
    "matchups": "defensive_matchups",
    "teams": "team_week",
    "identities": "reconciliation_audit",
}


def aware(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("Explicit timezone-aware cutoff required")
    return value


def query(
    folder,
    task,
    *,
    season,
    week,
    cutoff,
    team=None,
    player_id=None,
    season_type="REG",
    limit=100,
):
    cutoff = aware(cutoff)
    if type(season) is not int or type(week) is not int or not 1 <= week <= 22:
        raise ValueError("Explicit integer season and week required")
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("limit must be 1..500")
    if task not in QUERIES or season_type not in {"REG", "POST", "PRE"}:
        raise ValueError("Unknown task or season type")
    folder = Path(folder).resolve()
    manifest_path = folder / "build_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    database = Path(manifest["database"]["path"])
    if database.is_absolute() or database.parts != ("nfl.duckdb",):
        raise ValueError("Database must be the local materialized nfl.duckdb")
    if (folder / database).is_symlink():
        raise ValueError("Symlink database rejected")
    table = QUERIES[task]
    with open_database(folder) as con:
        con.execute("SET enable_external_access=false")
        columns = {r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()}
        where = ["season = ?", "week = ?", "available_at <= ?"]
        params = [season, week, cutoff]
        if team is not None and task == "games":
            where.append("(home_team = ? OR away_team = ?)")
            params.extend([team, team])
            team_filter = None
        else:
            team_filter = team
        for field, value in (
            ("season_type", season_type),
            ("defense" if task == "matchups" else "team", team_filter),
            ("player_id", player_id),
        ):
            if value is not None:
                if field not in columns:
                    if field == "season_type" and task == "identities":
                        continue  # audit schema has source/context, not season_type
                    raise ValueError(f"{task} does not support {field} filter")
                where.append(f"{field} = ?")
                params.append(value)
        if task == "identities":
            where.append("severity = 'PENDING'")
        predicate = " AND ".join(where)
        total = con.execute(
            f"SELECT count(*) FROM {table} WHERE {predicate}", params
        ).fetchone()[0]
        # Sorting all projected fields gives stable replay, including nulls.
        cursor = con.execute(
            f"SELECT * FROM {table} WHERE {predicate} ORDER BY ALL LIMIT ?",
            params + [limit],
        )
        names = [col[0] for col in cursor.description]
        records = [dict(zip(names, row)) for row in cursor.fetchall()]
    return {
        "status": "OK" if total else "NO_DATA_AS_OF",
        "decision": "NO_BET",
        "financial_approved": False,
        "statistical_approved": False,
        "task": task,
        "season": season,
        "season_type": season_type,
        "week": week,
        "cutoff": cutoff.isoformat(),
        "team": team,
        "player_id": player_id,
        "source_snapshot_id": manifest.get(
            "source_snapshot_id", manifest.get("snapshot_id")
        ),
        "build_manifest_sha256": sha256(manifest_path),
        "database_sha256": manifest["database"]["sha256"],
        "code": code_identity(),
        "total_rows": total,
        "truncated": total > limit,
        "records": records,
        "limitations": [
            "Historical research, not a pregame feature matrix",
            "No calibrated projection registry; no execution authorization",
            "Weekly injuries do not certify official inactives; snaps are not routes",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="Canonical build folder")
    parser.add_argument("--task", choices=QUERIES, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--season-type", default="REG")
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--team")
    parser.add_argument("--player-id")
    parser.add_argument("--limit", type=int, default=100)
    args = vars(parser.parse_args(argv))
    args["folder"] = args.pop("database")
    try:
        result = query(**args)
        result["queried_at_utc"] = datetime.now(UTC).isoformat()
        print(json.dumps(result, default=str, allow_nan=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "ERROR", "decision": "NO_BET", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
