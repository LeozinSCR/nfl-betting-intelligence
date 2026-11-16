"""Build an auditable research database; no legacy updates or model approval."""

import argparse
from datetime import datetime, timezone
from importlib.resources import files
import json
from pathlib import Path
import sys
from uuid import uuid4

import duckdb
import polars as pl

from .ingest_nflverse import SOURCES, collect, utc_now, write_json
from .provenance import code_identity, sha256

TABLES = (
    "games",
    "teams",
    "players",
    "player_crosswalk",
    "player_week",
    "team_week",
    "offensive_opportunities",
    "snap_counts",
    "injuries",
    "defensive_matchups",
    "ingestion_manifest",
    "reconciliation_audit",
    "coverage_audit",
    "source_coverage",
)
KEYS = {
    "schedules": ["game_id"],
    "pbp": ["game_id", "play_id"],
    "player_stats": ["season", "season_type", "week", "game_id", "team", "player_id"],
    "snap_counts": ["season", "game_type", "week", "game_id", "team", "pfr_player_id"],
    "rosters_weekly": ["season", "game_type", "week", "team", "gsis_id"],
}
CANONICAL_KEYS = {
    "games": ["game_id"],
    "teams": ["season", "team"],
    "players": ["player_key"],
    "player_week": ["season", "season_type", "week", "team", "player_key"],
    "team_week": ["game_id", "team"],
    "snap_counts": ["game_id", "team", "player_key"],
    "offensive_opportunities": ["game_id", "play_id", "opportunity_type"],
    "defensive_matchups": ["game_id", "defense", "position"],
}


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def empty_injuries():
    return pl.DataFrame(
        schema={
            k: (pl.Int64 if k in ("season", "week") else pl.String)
            for k in (
                "season",
                "season_type",
                "week",
                "team",
                "gsis_id",
                "full_name",
                "position",
                "report_status",
                "practice_status",
                "report_primary_injury",
                "report_secondary_injury",
                "practice_primary_injury",
                "practice_secondary_injury",
            )
        }
    )


def source_frames(snapshot, manifest):
    frames = {}
    missing = []
    for source in SOURCES:
        item = manifest["sources"].get(source, {})
        if item.get("status") != "OK":
            missing.append(source)
            if source == "injuries":
                frames[source] = empty_injuries().with_row_index("_source_row")
                continue
            raise ValueError("Essential source missing/failed: " + source)
        path = (snapshot / item["path"]).resolve()
        if (
            not path.is_relative_to(snapshot.resolve())
            or sha256(path) != item["sha256"]
        ):
            raise ValueError("Source path/hash mismatch: " + source)
        frame = pl.read_parquet(path).with_row_index("_source_row")
        if (
            frame.is_empty()
            or frame["season"].null_count()
            or set(frame["season"].unique()) != {manifest["season"]}
        ):
            raise ValueError("Empty/wrong-season source: " + source)
        frames[source] = frame
    return frames, missing


def input_constraints(frames):
    """Do not deduplicate or select an arbitrary identity in ambiguous input."""
    findings = []
    for name, keys in KEYS.items():
        data = frames[name]
        if "team" in data.columns:
            data = data.with_columns(
                pl.col("team").replace({"LAR": "LA", "JAC": "JAX", "WSH": "WAS"})
            )
        rows = data.drop_nulls(keys).group_by(keys).len().filter(pl.col("len") > 1)
        if rows.height:
            findings.append(
                {
                    "source": name,
                    "constraint": "DUPLICATE_KEY",
                    "keys": keys,
                    "records": rows.to_dicts(),
                }
            )
        if (
            name in ("schedules", "pbp", "snap_counts")
            and data.select(keys).null_count().sum_horizontal().sum() > 0
        ):
            findings.append({"source": name, "constraint": "NULL_REQUIRED_KEY"})
    roster = frames["rosters_weekly"].with_columns(
        pl.col("team").replace({"LAR": "LA", "JAC": "JAX", "WSH": "WAS"})
    )
    for other in ("pfr_id", "sleeper_id"):
        key = ["season", "game_type", "week", "team", other]
        rows = (
            roster.drop_nulls(key + ["gsis_id"])
            .group_by(key)
            .agg(pl.col("gsis_id").n_unique().alias("identities"))
            .filter(pl.col("identities") > 1)
        )
        if rows.height:
            findings.append(
                {
                    "source": "rosters_weekly",
                    "constraint": "AMBIGUOUS_" + other.upper(),
                    "records": rows.to_dicts(),
                }
            )
    return findings


def rows(con, sql):
    result = con.execute(sql)
    names = [d[0] for d in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def add_checks(con):
    # Cross-source inconsistencies are retained as reconciliation evidence.
    checks = [
        (
            "GAME_TEAM_WEEK_MISMATCH",
            "SELECT 'player_week' AS source, stats_source_row source_row,season,week,game_id,team,player_id FROM player_week w WHERE game_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM game_teams g WHERE g.game_id=w.game_id AND g.team=w.team AND g.season=w.season AND g.week=w.week AND g.season_type=w.season_type)",
        ),
        (
            "OPPORTUNITY_WITH_ZERO_OFFENSIVE_SNAPS",
            "SELECT 'player_week' AS source,snap_source_row source_row,season,week,game_id,team,player_id FROM player_week WHERE targets+carries>0 AND offense_snaps=0 AND NOT EXISTS(SELECT 1 FROM offensive_opportunities o WHERE o.game_id=player_week.game_id AND o.player_id=player_week.player_id AND o.formation_context='PUNT_FORMATION')",
        ),
        (
            "INVALID_SNAP_COUNTS",
            "SELECT 'snap_counts' AS source,snap_source_row source_row,season,week,game_id,team,player_id FROM snap_counts WHERE offense_snaps<0 OR defense_snaps<0 OR st_snaps<0 OR offensive_snap_share NOT BETWEEN 0 AND 1",
        ),
        (
            "PBP_SCORE_MISMATCH",
            "SELECT 'coverage_audit' AS source,NULL::BIGINT source_row,season,week,game_id,team,NULL::VARCHAR player_id FROM coverage_audit WHERE has_result AND has_end_marker AND (observed_home_score<>home_score OR observed_away_score<>away_score)",
        ),
        (
            "UNMAPPED_OPPORTUNITY_ID",
            "SELECT 'pbp' AS source,pbp_source_row source_row,season,week,game_id,team,player_id FROM offensive_opportunities WHERE position IS NULL",
        ),
    ]
    for category, sql in checks:
        con.execute(
            f"INSERT INTO reconciliation_audit(category,severity,source,source_row,season,week,game_id,team,player_id,original_json,canonical_json,detail) SELECT {literal(category)},'PENDING',source,source_row,season,week,game_id,team,player_id,NULL,NULL,'Retained for review; no inferred correction' FROM ({sql})"
        )
    con.execute("""INSERT INTO reconciliation_audit(category,severity,source,source_row,season,week,game_id,team,player_id,original_json,canonical_json,detail)
        SELECT 'OPPORTUNITY_FROM_PUNT_FORMATION','INFO','pbp',pbp_source_row,season,week,game_id,team,player_id,
        to_json(struct_pack(play_id:=play_id,kind:=opportunity_type,formation_context:=formation_context)),
        '{"standard_carry":1}','Conventional rush on punt formation; snap provider classified participation as special teams'
        FROM offensive_opportunities WHERE classification='STANDARD' AND opportunity_type='RUSH' AND formation_context='PUNT_FORMATION'""")
    con.execute("""UPDATE reconciliation_audit a SET category='HISTORICAL_TD_ATTRIBUTION_RESOLVED',severity='INFO',
      detail='PBP TD scorer is lateral recipient, not initial receiver; weekly receiving TD confirms canonical value. Legacy generator unavailable; original value retained.'
      WHERE category='HISTORICAL_OPPORTUNITY_DIFFERENCE'
      AND EXISTS(SELECT 1 FROM raw_pbp p WHERE p.game_id=a.game_id AND p.receiver_player_id=a.player_id
       AND p.pass_touchdown=1 AND p.td_player_id=p.lateral_receiver_player_id AND p.td_player_id<>p.receiver_player_id)
      AND EXISTS(SELECT 1 FROM normalized_stats s WHERE s.game_id=a.game_id AND s.player_id=a.player_id
       AND s.receiving_tds=CAST(json_extract(a.canonical_json,'$.td') AS INTEGER))""")
    for table, keys in CANONICAL_KEYS.items():
        duplicates = con.execute(
            f"SELECT count(*) FROM (SELECT {','.join(keys)} FROM {table} GROUP BY ALL HAVING count(*)>1)"
        ).fetchone()[0]
        if duplicates:
            raise ValueError(
                f"Canonical key violation: {table}, {duplicates} duplicated keys"
            )
    orphan_plays = con.execute("""SELECT count(*) FROM raw_pbp p LEFT JOIN games g ON p.game_id=g.game_id
      WHERE g.game_id IS NULL OR p.season<>g.season OR p.week<>g.week OR p.season_type<>g.season_type
      OR (p.posteam IS NOT NULL AND team_code(p.posteam) NOT IN (g.home_team,g.away_team))
      OR (p.defteam IS NOT NULL AND team_code(p.defteam) NOT IN (g.home_team,g.away_team))""").fetchone()[
        0
    ]
    future_outcomes = con.execute("""SELECT count(*) FROM games g WHERE kickoff_utc>available_at
      AND (has_result OR EXISTS(SELECT 1 FROM raw_pbp p WHERE p.game_id=g.game_id))""").fetchone()[
        0
    ]
    if orphan_plays or future_outcomes:
        raise ValueError(
            f"Calendar/outcome temporal violation: orphan plays={orphan_plays}, future outcomes={future_outcomes}"
        )
    bad = con.execute(
        "SELECT count(*) FROM reconciliation_audit WHERE category IN ('GAME_TEAM_WEEK_MISMATCH','INVALID_SNAP_COUNTS')"
    ).fetchone()[0]
    if bad:
        raise ValueError(
            "Invalid calendar/identity/snap records; inspect reconciliation audit"
        )


def reconcile_opportunity_history(con):
    con.execute("""
    INSERT INTO reconciliation_audit
    WITH totals AS (
      SELECT week,game_id,team,player_id,opportunity_type,count(*) opportunities,
       count(yardline_100) with_yardline,count(*) FILTER(WHERE yardline_100<=20) inside20,
       count(*) FILTER(WHERE yardline_100<=10) inside10,count(*) FILTER(WHERE yardline_100<=5) inside5,
       sum(receptions) catches,sum(CASE WHEN opportunity_type='TARGET' THEN yards ELSE 0 END) receiving_yards,
       sum(CASE WHEN opportunity_type='RUSH' THEN yards ELSE 0 END) rushing_yards,sum(offensive_td) offensive_td
      FROM offensive_opportunities WHERE classification='STANDARD' GROUP BY ALL
    )
    SELECT CASE WHEN t.player_id IS NULL THEN 'HISTORICAL_OPPORTUNITY_UNMATCHED'
          WHEN h.opportunities=t.opportunities AND h.with_yardline=t.with_yardline
           AND h.inside20=t.inside20 AND h.inside10=t.inside10 AND h.inside5=t.inside5
           AND h.catches=t.catches AND h.receiving_yards=t.receiving_yards
           AND h.rushing_yards=t.rushing_yards AND h.offensive_td=t.offensive_td
          THEN 'HISTORICAL_OPPORTUNITY_MATCH' ELSE 'HISTORICAL_OPPORTUNITY_DIFFERENCE' END,
     CASE WHEN h.opportunities=t.opportunities AND h.with_yardline=t.with_yardline
           AND h.inside20=t.inside20 AND h.inside10=t.inside10 AND h.inside5=t.inside5
           AND h.catches=t.catches AND h.receiving_yards=t.receiving_yards
           AND h.rushing_yards=t.rushing_yards AND h.offensive_td=t.offensive_td THEN 'INFO' ELSE 'PENDING' END,
     'opportunities_corrected_2026.csv',h._source_row,2026,h.week,h.game_id,team_code(h.team),h.player_id,
     to_json(struct_pack(type:=h.type,opportunities:=h.opportunities,inside20:=h.inside20,inside10:=h.inside10,inside5:=h.inside5,catches:=h.catches,rec_yards:=h.receiving_yards,rush_yards:=h.rushing_yards,td:=h.offensive_td)),
     to_json(struct_pack(type:=t.opportunity_type,opportunities:=t.opportunities,inside20:=t.inside20,inside10:=t.inside10,inside5:=t.inside5,catches:=t.catches,rec_yards:=t.receiving_yards,rush_yards:=t.rushing_yards,td:=t.offensive_td)),
     'Compare opportunity count, yardline coverage, red zone, catches, yards and TD; no legacy mutation'
    FROM historical_opportunities h LEFT JOIN totals t
    ON h.week=t.week AND h.game_id=t.game_id AND team_code(h.team)=t.team AND h.player_id=t.player_id AND h.type=t.opportunity_type
    """)


def build(snapshot, output="data/canonical", history="data/processed"):
    snapshot = Path(snapshot).resolve()
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    code = code_identity()
    root = Path(output).resolve()
    repo = Path(__file__).resolve().parents[2]
    for protected in (
        repo / "legacy",
        repo / "data/processed",
        repo / "data/reference",
    ):
        if root == protected or root.is_relative_to(protected):
            raise ValueError("Historical destination protected")
    folder = (
        root / str(manifest["season"]) / (manifest["run_id"] + "-build-" + uuid4().hex)
    )
    folder.mkdir(parents=True, exist_ok=False)
    summary = {
        "schema_version": 1,
        "status": "RUNNING",
        "source_snapshot_id": manifest["run_id"],
        "source_manifest_sha256": sha256(manifest_path),
        "source_snapshot_path": str(snapshot),
        "code": code,
        "built_at_utc": utc_now(),
        "tables": {},
        "errors": [],
        "historical_data_updated": False,
        "financial_approved": False,
        "statistical_approved": False,
    }
    dest = folder / "build_manifest.json"
    write_json(dest, summary)
    con = None
    try:
        frames, missing = source_frames(snapshot, manifest)
        constraints = input_constraints(frames)
        summary["input_constraints"] = constraints
        if constraints:
            raise ValueError(
                "Input key/identity constraint failure; raw evidence retained"
            )
        con = duckdb.connect(str(folder / "nfl.duckdb"))
        con.execute("SET TimeZone='UTC'")
        for name, data in frames.items():
            con.register("raw_" + name, data.to_arrow())
        history_hashes = {}
        for name, filename in (
            ("historical_weekly", "weekly_reconciliation_2026.csv"),
            ("historical_opportunities", "opportunities_corrected_2026.csv"),
            ("historical_participation", "weekly_participation_2026.csv"),
        ):
            path = Path(history) / filename
            history_hashes[filename] = sha256(path)
            con.register(
                name, pl.read_csv(path).with_row_index("_source_row").to_arrow()
            )
        summary["history_sha256"] = history_hashes
        con.execute(files("nfl_betting").joinpath("canonical.sql").read_text())
        reconcile_opportunity_history(con)
        con.execute(
            "CREATE TABLE ingestion_manifest (source VARCHAR,status VARCHAR,ingested_at_utc TIMESTAMPTZ,source_updated_at VARCHAR,resolved_download_url VARCHAR,sha256 VARCHAR,rows BIGINT,schema_json VARCHAR,http_json VARCHAR,code_json VARCHAR)"
        )
        for name in SOURCES:
            item = manifest["sources"].get(name, {})
            con.execute(
                "INSERT INTO ingestion_manifest VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    name,
                    item.get("status", "MISSING"),
                    item.get("finished_at_utc"),
                    item.get("source_updated_at"),
                    item.get("resolved_download_url"),
                    item.get("sha256"),
                    item.get("rows"),
                    json.dumps(item.get("schema")),
                    json.dumps(item.get("http_responses", [])),
                    json.dumps(manifest.get("code")),
                ],
            )
        for source in missing:
            con.execute(
                "INSERT INTO reconciliation_audit(category,severity,source,detail) VALUES ('SOURCE_UNAVAILABLE','PENDING',?,'Optional injury source failed; empty typed table, not invented reports')",
                [source],
            )
        # A snapshot is known only when collection finished, never backdated to event week.
        available = manifest.get("finished_at_utc")
        available_dt = datetime.fromisoformat(available.replace("Z", "+00:00"))
        if available_dt.tzinfo is None or available_dt > datetime.now(timezone.utc):
            raise ValueError("Invalid/future source availability timestamp")
        for table in TABLES:
            con.execute(
                f"ALTER TABLE {table} ADD COLUMN source_snapshot_id VARCHAR DEFAULT {literal(manifest['run_id'])}"
            )
            con.execute(
                f"ALTER TABLE {table} ADD COLUMN available_at TIMESTAMPTZ DEFAULT {literal(available)}"
            )
        add_checks(con)
        summary["coverage_by_week"] = rows(
            con,
            "SELECT week,count(*)/2 AS scheduled_games,sum(CAST(has_result AS INTEGER))/2 AS games_with_result,sum(CAST(has_result AND has_end_marker AND stats_rows>0 AND snap_rows>0 AND roster_rows>0 AS INTEGER))/2 AS fully_covered_result_games FROM coverage_audit GROUP BY week ORDER BY week",
        )
        summary["participation"] = rows(
            con,
            "SELECT participation,count(*) records FROM player_week GROUP BY participation ORDER BY participation",
        )
        summary["reconciliation"] = rows(
            con,
            "SELECT category,severity,count(*) records FROM reconciliation_audit GROUP BY category,severity ORDER BY category,severity",
        )
        summary["source_null_id_counts"] = {
            name: {
                k: frame[k].null_count()
                for k in ("player_id", "gsis_id", "pfr_player_id")
                if k in frame.columns
            }
            for name, frame in frames.items()
        }
        for table in TABLES:
            path = folder / (table + ".parquet")
            con.execute(
                f"COPY {table} TO {literal(path)} (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            summary["tables"][table] = {
                "rows": con.execute(f"SELECT count(*) FROM {table}").fetchone()[0],
                "path": path.name,
                "sha256": sha256(path),
                "schema": rows(con, f"DESCRIBE {table}"),
            }
        # Complete evidence for every historical row and pending diagnostic; no selective sample.
        audit_csv = folder / "reconciliation_audit.csv"
        con.execute(
            f"COPY reconciliation_audit TO {literal(audit_csv)} (HEADER, DELIMITER ',')"
        )
        summary["audit_csv"] = {"path": audit_csv.name, "sha256": sha256(audit_csv)}
        pending = con.execute(
            "SELECT count(*) FROM reconciliation_audit WHERE severity='PENDING'"
        ).fetchone()[0]
        summary["status"] = "PARTIAL" if pending or missing else "OK"
        summary["pending_audit_rows"] = pending
        con.close()
        con = None
        summary["database"] = {
            "path": "nfl.duckdb",
            "sha256": sha256(folder / "nfl.duckdb"),
        }
    except Exception as exc:
        summary["status"] = "ERROR"
        summary["errors"].append(
            {"type": type(exc).__name__, "message": str(exc)[:4000]}
        )
    finally:
        if con is not None:
            con.close()
        summary["finished_at_utc"] = utc_now()
        write_json(dest, summary)
    return folder, summary


def open_database(folder):
    folder = Path(folder).resolve()
    m = json.loads((folder / "build_manifest.json").read_text())
    if (
        m["status"] == "ERROR"
        or sha256(folder / m["database"]["path"]) != m["database"]["sha256"]
    ):
        raise ValueError("Unusable or modified database")
    return duckdb.connect(str(folder / m["database"]["path"]), read_only=True)


def as_of(folder, table, cutoff):
    if table not in TABLES:
        raise ValueError("Unknown table")
    if not isinstance(cutoff, datetime) or cutoff.tzinfo is None:
        raise ValueError("Aware cutoff required")
    with open_database(folder) as con:
        return con.execute(
            f"SELECT * FROM {table} WHERE available_at <= ?", [cutoff]
        ).fetch_arrow_table()


def resolve_player(
    folder,
    *,
    season,
    week,
    team,
    pfr_id=None,
    sleeper_id=None,
    cutoff,
    season_type="REG",
):
    if (pfr_id is None) == (sleeper_id is None):
        raise ValueError("Exactly one source identifier required")
    if not isinstance(cutoff, datetime) or cutoff.tzinfo is None:
        raise ValueError("Aware cutoff required")
    team = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}.get(team, team)
    field, value = (
        ("pfr_id", pfr_id) if pfr_id is not None else ("sleeper_id", sleeper_id)
    )
    with open_database(folder) as con:
        return rows(
            con,
            f"SELECT * FROM player_crosswalk WHERE season={int(season)} AND season_type={literal(season_type)} AND week={int(week)} AND team={literal(team)} AND {field}={literal(value)} AND available_at<={literal(cutoff.isoformat())}::TIMESTAMPTZ",
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", help="Existing immutable ingestion run folder")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--raw-out", default="data/raw_auto")
    parser.add_argument("--out", default="data/canonical")
    parser.add_argument("--history", default="data/processed")
    args = parser.parse_args(argv)
    try:
        ingestion_code = 0
        if args.snapshot:
            snapshot = Path(args.snapshot)
        else:
            manifest_path, ingestion_code = collect(args.season, args.raw_out)
            snapshot = manifest_path.parent
        folder, summary = build(snapshot, args.out, args.history)
        print(
            json.dumps(
                {
                    "folder": str(folder),
                    "status": summary["status"],
                    "tables": {k: v["rows"] for k, v in summary["tables"].items()},
                    "errors": summary["errors"],
                },
                indent=2,
            )
        )
        return 2 if summary["status"] == "ERROR" or ingestion_code else 0
    except Exception as exc:
        print(f"Pipeline failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
