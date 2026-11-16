"""Read-only NFLverse collection into unique snapshots; never updates historical data."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import sys
from uuid import uuid4
from contextlib import nullcontext
from .provenance import capture_downloads, code_identity

SOURCES = (
    "schedules",
    "player_stats",
    "pbp",
    "snap_counts",
    "injuries",
    "rosters_weekly",
)
# Minimal contracts are availability checks, not a complete reconciliation policy.
REQUIRED = {
    "schedules": {
        "season",
        "week",
        "game_id",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
    },
    "player_stats": {"season", "week", "player_id", "targets", "carries"},
    "pbp": {"season", "week", "game_id", "play_id"},
    "snap_counts": {
        "season",
        "week",
        "game_id",
        "pfr_player_id",
        "offense_snaps",
        "st_snaps",
    },
    "injuries": {"season", "week", "gsis_id", "report_status"},
    "rosters_weekly": {"season", "week", "gsis_id", "pfr_id", "sleeper_id"},
}
DOCS_URL = "https://nflreadpy.nflverse.com/api/load_functions/"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    """Atomic checkpoint within this run's exclusive directory."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def make_loaders():
    import nflreadpy as nfl

    return {
        "schedules": lambda year: nfl.load_schedules([year]),
        "player_stats": lambda year: nfl.load_player_stats(
            [year], summary_level="week"
        ),
        "pbp": lambda year: nfl.load_pbp([year]),
        "snap_counts": lambda year: nfl.load_snap_counts([year]),
        "injuries": lambda year: nfl.load_injuries([year]),
        "rosters_weekly": lambda year: nfl.load_rosters_weekly([year]),
    }


def coverage(table):
    import polars as pl

    expressions = [pl.len().alias("rows")]
    for output, candidates in (
        ("games", ("game_id",)),
        ("teams", ("team", "posteam", "home_team")),
        ("players", ("player_id", "gsis_id", "pfr_player_id")),
    ):
        key = next((c for c in candidates if c in table.columns), None)
        if key:
            expressions.append(pl.col(key).drop_nulls().n_unique().alias(output))
    return table.group_by("week").agg(expressions).sort("week").to_dicts()


def collect(season, out, sources=SOURCES, *, loaders=None):
    """Always checkpoint a manifest once a run directory can be created.

    `loaders` is an offline test seam. ERROR records preserve the exception type;
    partial successes remain inspectable. No model/source provenance is invented.
    """
    root = Path(out).resolve()
    repo = Path(__file__).resolve().parents[2]
    # Prevent using collection output to replace legacy/processed/reference artifacts.
    for protected in (
        repo / "legacy",
        repo / "data/processed",
        repo / "data/reference",
    ):
        if root == protected or root.is_relative_to(protected):
            raise ValueError("Historical destination is protected")
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex
    )
    folder = root / str(season) / run_id
    folder.mkdir(parents=True, exist_ok=False)
    manifest_path = folder / "manifest.json"
    versions = {}
    for name in ("nflreadpy", "polars", "pyarrow", "duckdb"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    manifest = {
        "schema_version": 2,
        "run_id": run_id,
        "season": season,
        "code": code_identity(),
        "started_at_utc": utc_now(),
        "finished_at_utc": None,
        "status": "RUNNING",
        "requested_sources": list(sources),
        "versions": versions,
        "python": sys.version,
        "sources": {},
        "errors": [],
        "reconciled": False,
        "statistical_approved": False,
        "financial_approved": False,
        "limitations": [
            "Collection is not reconciliation or complete-week certification",
            "Publication time may be absent; HTTP Last-Modified is recorded only when returned",
        ],
    }
    write_json(manifest_path, manifest)
    try:
        if (
            not sources
            or len(set(sources)) != len(sources)
            or any(name not in SOURCES for name in sources)
        ):
            raise ValueError("Unique supported sources required")
        live = loaders is None
        if live:
            loaders = make_loaders()
        capture = capture_downloads(folder) if live else nullcontext(None)
        with capture as trace:
            for name in sources:
                if trace is not None:
                    trace["source"] = name
                item = {
                    "status": "RUNNING",
                    "started_at_utc": utc_now(),
                    "documentation_url": DOCS_URL,
                    "loader": "nflreadpy.load_" + name,
                    "source_updated_at": None,
                    "resolved_download_url": None,
                }
                manifest["sources"][name] = item
                write_json(manifest_path, manifest)
                try:
                    table = loaders[name](season)
                    if table is None or table.is_empty():
                        raise ValueError("Empty dataset")
                    missing = REQUIRED[name] - set(table.columns)
                    if missing:
                        raise ValueError(
                            "Missing columns: " + ", ".join(sorted(missing))
                        )
                    if table["season"].null_count() or set(
                        table["season"].unique().to_list()
                    ) != {season}:
                        raise ValueError("Wrong or missing season")
                    dest = folder / (name + ".parquet")
                    table.write_parquet(dest)
                    item.update(
                        status="OK",
                        rows=table.height,
                        columns=table.columns,
                        sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                        path=dest.name,
                        weeks=sorted(table["week"].drop_nulls().unique().to_list()),
                        schema={k: str(v) for k, v in table.schema.items()},
                        coverage_by_week=coverage(table),
                    )
                except Exception as exc:
                    error = {
                        "source": name,
                        "type": type(exc).__name__,
                        "message": str(exc)[:2000],
                    }
                    item.update(status="ERROR", error=error)
                    manifest["errors"].append(error)
                finally:
                    item["finished_at_utc"] = utc_now()
                    item["http_responses"] = (
                        [r for r in trace["responses"] if r["source"] == name]
                        if trace is not None
                        else []
                    )
                    item["source_mode"] = (
                        "HTTP_CAPTURED" if trace is not None else "INJECTED_TEST_LOADER"
                    )
                    ok = [r for r in item["http_responses"] if r["status_code"] == 200]
                    if ok:
                        item["resolved_download_url"] = ok[-1]["requested_url"]
                        item["source_updated_at"] = ok[-1]["headers"].get(
                            "Last-Modified"
                        )
                    write_json(manifest_path, manifest)
    except Exception as exc:
        manifest["errors"].append(
            {
                "source": "bootstrap",
                "type": type(exc).__name__,
                "message": str(exc)[:2000],
            }
        )
    finally:
        manifest["status"] = "ERROR" if manifest["errors"] else "OK"
        manifest["finished_at_utc"] = utc_now()
        write_json(manifest_path, manifest)
    return manifest_path, 2 if manifest["errors"] else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--out", default="data/raw_auto")
    parser.add_argument("--sources", nargs="+", choices=SOURCES, default=list(SOURCES))
    args = parser.parse_args(argv)
    try:
        path, code = collect(args.season, args.out, args.sources)
    except Exception as exc:
        print(
            f"Cannot create ingestion run: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        return 2
    print(f"Manifest: {path}")
    print(path.read_text(encoding="utf-8"))
    return code


if __name__ == "__main__":
    sys.exit(main())
