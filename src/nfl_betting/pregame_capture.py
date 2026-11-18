"""Plan, seal and restore one pregame evidence window."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4

from pytz import timezone

from . import archive
from .canonical import build
from .ingest_nflverse import SOURCES, collect
from .projection import _connect, read_catalog
from .provenance import code_identity, sha256
from .temporal_roster import utc
from .web_export import _games

VERSION = 1
MAX_WINDOW_MINUTES = 30
SAO_PAULO = timezone("America/Sao_Paulo")
REQUIRED = set(SOURCES) - {"injuries"}
OFFICIAL_FILES = ("manifest.json", "source.bin", "authorization.bin")


def _now():
    return datetime.now(UTC)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def _output(path, *parents):
    result = Path(path).resolve()
    repo = Path(__file__).resolve().parents[2]
    protected = [repo / name for name in ("data", "legacy", "web/public")]
    protected.extend(Path(parent).resolve() for parent in parents)
    if any(result.is_relative_to(parent) for parent in protected):
        raise ValueError("Output must be outside catalogs, archives and protected data")
    if result.exists():
        raise FileExistsError(result)
    return result


def _verified_files(folder, names):
    for name in names:
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing or unsafe evidence file: {name}")


def _official(folder):
    _verified_files(folder, OFFICIAL_FILES)
    manifest = _read(folder / "manifest.json")
    parts = urlsplit(manifest["source_url"])
    if (
        manifest["schema_version"] != VERSION
        or parts.scheme != "https" or parts.netloc not in {"media.nfl.com", "www.nfl.com", "nfl.com"}
        or not parts.path or parts.query or parts.fragment
        or not manifest["source_version"] or not manifest["reviewed_by"]
        or manifest["capture_authorized"] is not True
    ):
        raise ValueError("A reviewed, authorized NFL schedule source is required")
    for name, key in (("source.bin", "sha256"), ("authorization.bin", "authorization_sha256")):
        path = folder / name
        if not path.stat().st_size or sha256(path) != manifest[key]:
            raise ValueError(f"Official evidence hash mismatch: {name}")
    start = utc(manifest["started_at_utc"])
    end = utc(manifest["finished_at_utc"])
    available = utc(manifest["available_at_utc"])
    if not start <= end <= available:
        raise ValueError("Invalid official capture chronology")
    published = manifest.get("published_at_utc")
    if published and utc(published) > end:
        raise ValueError("Official publication is posterior to capture")
    games = {game["game_id"]: game for game in manifest["games"]}
    if len(games) != len(manifest["games"]):
        raise ValueError("Duplicate official game IDs")
    return manifest, games


def _calendar(folder, season, week, cutoff):
    catalog = read_catalog(folder, season)
    if catalog.available_at > cutoff:
        raise ValueError("Catalog was unavailable at requested cutoff")
    with _connect(catalog.folder) as con:
        rows = _games(con, season, week, cutoff, catalog.manifest["source_snapshot_id"])
        roster_teams = {row[0] for row in con.execute("""
            SELECT DISTINCT team FROM player_crosswalk
            WHERE season=? AND season_type='REG' AND week=? AND source_snapshot_id=?
              AND available_at<=? AND player_id IS NOT NULL
            """, [season, week, catalog.manifest["source_snapshot_id"], cutoff]).fetchall()}
    return catalog, {row["game_id"]: row for row in rows}, roster_teams


def _same_game(row, target):
    return (
        row is not None and row["kickoff_utc"] is not None
        and utc(row["kickoff_utc"]) == utc(target["kickoff_utc"])
        and (row["away_team"], row["home_team"]) == (target["away_team"], target["home_team"])
        and row["has_result"] is False
    )


def plan_window(catalog_folder, official_folder, season, week, games, output, lead_minutes=135, *, clock=_now):
    official_folder = Path(official_folder).resolve()
    output = _output(output, catalog_folder, official_folder)
    if not 1 <= week <= 18 or not 1 <= lead_minutes <= 24 * 60:
        raise ValueError("Expected regular-season week 1..18 and a positive lead")
    ids = list(games)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Supply distinct game IDs for one window")
    now = utc(clock())
    official, reference = _official(official_folder)
    if (official["season"], official["week"]) != (season, week) or utc(official["available_at_utc"]) > now:
        raise ValueError("Official evidence does not match the season, week or planning clock")
    catalog, calendar, _ = _calendar(catalog_folder, season, week, now)
    targets = []
    for game_id in sorted(ids):
        game = reference.get(game_id)
        if game is None or not _same_game(calendar.get(game_id), game):
            raise ValueError(f"KICKOFF_CONFLICT_OR_UNVERIFIED: {game_id}")
        kickoff = utc(game["kickoff_utc"])
        cutoff = kickoff - timedelta(minutes=lead_minutes)
        if now > cutoff:
            raise ValueError(f"PLAN_CUTOFF_ELAPSED: {game_id}")
        targets.append({
            "game_id": game_id, "away_team": game["away_team"], "home_team": game["home_team"],
            "kickoff_utc": kickoff.isoformat(), "kickoff_sao_paulo": kickoff.astimezone(SAO_PAULO).isoformat(),
            "cutoff_utc": cutoff.isoformat(),
        })
    if max(utc(row["kickoff_utc"]) for row in targets) - min(
        utc(row["kickoff_utc"]) for row in targets
    ) > timedelta(minutes=MAX_WINDOW_MINUTES):
        raise ValueError("Games must belong to one window of at most 30 minutes")
    plan = {
        "schema_version": VERSION, "season": season, "week": week, "lead_minutes": lead_minutes,
        "planned_at_utc": now.isoformat(), "reference_catalog": catalog.lineage,
        "official_manifest_sha256": sha256(official_folder / "manifest.json"), "games": targets,
        "decision": "NO_BET",
    }
    output.mkdir(parents=True)
    _copy_official(official_folder, output / "official")
    _write(output / "plan.json", plan)
    return plan


def _copy_official(source, destination):
    destination.mkdir()
    for name in OFFICIAL_FILES:
        shutil.copyfile(source / name, destination / name)


def _load_plan(folder):
    _verified_files(folder, ("plan.json",))
    plan = _read(folder / "plan.json")
    official_path = folder / "official"
    if official_path.is_symlink():
        raise ValueError("Official evidence must be stored inside the plan")
    official, source_games = _official(official_path)
    if (
        plan["schema_version"] != VERSION
        or sha256(official_path / "manifest.json") != plan["official_manifest_sha256"]
        or (plan["season"], plan["week"]) != (official["season"], official["week"])
        or not 1 <= plan["week"] <= 18 or not 1 <= plan["lead_minutes"] <= 24 * 60
        or plan["decision"] != "NO_BET"
    ):
        raise ValueError("Plan and official manifest mismatch")
    now = utc(plan["planned_at_utc"])
    if not utc(official["available_at_utc"]) <= now or utc(plan["reference_catalog"]["available_at_utc"]) > now:
        raise ValueError("Plan references future evidence")
    timestamps, ids = [], set()
    for target in plan["games"]:
        game_id = target["game_id"]
        kickoff, cutoff = utc(target["kickoff_utc"]), utc(target["cutoff_utc"])
        src = source_games[game_id]
        if (
            game_id in ids or kickoff != utc(src["kickoff_utc"]) or not now <= cutoff < kickoff
            or target["kickoff_sao_paulo"] != kickoff.astimezone(SAO_PAULO).isoformat()
            or cutoff != kickoff - timedelta(minutes=plan["lead_minutes"])
            or (target["away_team"], target["home_team"]) != (src["away_team"], src["home_team"])
        ):
            raise ValueError("Invalid game binding in plan")
        timestamps.append(kickoff)
        ids.add(game_id)
    if not ids or max(timestamps) - min(timestamps) > timedelta(minutes=MAX_WINDOW_MINUTES):
        raise ValueError("Expected one capture window")
    return plan, official


def _nflverse_url(value):
    parts = urlsplit(value)
    return (
        parts.scheme == "https" and parts.netloc == "github.com"
        and parts.path.startswith("/nflverse/nflverse-data/releases/download/")
        and not parts.query and not parts.fragment
    )


def _source_inputs(raw, start, end):
    inputs = []
    for name in SOURCES:
        item = raw["sources"].get(name, {})
        received = item.get("http_responses", [])
        successful = [response for response in received if response["status_code"] == 200]
        if item.get("status") != "OK":
            inputs.append({
                "name": name, "required": name in REQUIRED, "status": "UNAVAILABLE",
                "started_at_utc": item.get("started_at_utc"),
                "finished_at_utc": item.get("finished_at_utc"), "available_at_utc": None,
            })
            continue
        started, finished = utc(item["started_at_utc"]), utc(item["finished_at_utc"])
        published = utc(item["published_at_utc"]) if item.get("published_at_utc") else None
        if (
            not start <= started <= finished <= end or not successful
            or not _nflverse_url(item.get("resolved_download_url") or "")
            or any(not response.get("sha256") or not response.get("path")
                   or not _nflverse_url(response["requested_url"])
                   or not started <= utc(response["received_at_utc"]) <= finished
                   for response in successful)
        ):
            raise ValueError(f"Invalid captured source provenance: {name}")
        inputs.append({
            "name": name, "required": name in REQUIRED, "status": "OK", "source_url": item["resolved_download_url"],
            "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat(),
            "available_at_utc": finished.isoformat(), "published_at_utc": published.isoformat() if published else None,
            "source_updated_at": item.get("source_updated_at"), "sha256": item["sha256"],
            "bodies": [{key: response[key] for key in ("path", "sha256", "received_at_utc")} for response in successful],
        })
    return inputs


def _checked_raw(folder, manifest_hash, started, sealed):
    path = folder / "manifest.json"
    if sha256(path) != manifest_hash:
        raise ValueError("Raw manifest hash mismatch")
    raw = _read(path)
    source_start, source_end = utc(raw["started_at_utc"]), utc(raw["finished_at_utc"])
    if not started <= source_start <= source_end <= sealed:
        raise ValueError("Invalid collection chronology")
    for item in raw["sources"].values():
        if item["status"] == "OK":
            archive.check_declared(folder, item)
        for response in item.get("http_responses", []):
            if response["status_code"] == 200:
                archive.check_declared(folder, response)
    return raw, source_end, _source_inputs(raw, source_start, source_end)


def _derive(folder, plan, official, run, catalog_digest):
    started, sealed = utc(run["started_at_utc"]), utc(run["sealed_at_utc"])
    if not utc(plan["planned_at_utc"]) <= started <= sealed:
        raise ValueError("Invalid run chronology")
    sources, calendar, roster = [], {}, set()
    official_proof = {
        "source_url": official["source_url"], "source_version": official["source_version"],
        "started_at_utc": official["started_at_utc"], "finished_at_utc": official["finished_at_utc"],
        "available_at_utc": official["available_at_utc"], "published_at_utc": official.get("published_at_utc"),
        "sha256": official["sha256"], "authorization_sha256": official["authorization_sha256"],
        "manifest_sha256": plan["official_manifest_sha256"],
    }
    raw_hash = run.get("raw_manifest_sha256")
    source_end = None
    if raw_hash:
        raw_path = folder / ("archive/raw" if catalog_digest else "excluded_raw")
        raw, source_end, sources = _checked_raw(raw_path, raw_hash, started, sealed)
        if raw["season"] != plan["season"]:
            raise ValueError("Raw snapshot season differs from capture plan")
    if catalog_digest:
        if source_end is None:
            raise ValueError("Canonical archive requires a verified raw manifest")
        inner = folder / "archive"
        build_manifest = _read(inner / "canonical/build_manifest.json")
        build_start = utc(build_manifest["built_at_utc"])
        build_end = utc(build_manifest["finished_at_utc"])
        if not source_end <= build_start <= build_end <= sealed:
            raise ValueError("Invalid collection, build and archive chronology")
        if raw["season"] != plan["season"] or raw["run_id"] != build_manifest["source_snapshot_id"]:
            raise ValueError("Snapshot identity mismatch")
        if sha256(inner / "raw/manifest.json") != build_manifest["source_manifest_sha256"]:
            raise ValueError("Canonical build was derived from another raw snapshot")
        catalog, calendar, roster = _calendar(inner / "canonical", plan["season"], plan["week"], sealed)
        if catalog.available_at != source_end:
            raise ValueError("Canonical availability differs from raw capture")
        lineage = catalog.lineage
        build_ready_at = build_end.isoformat()
    else:
        lineage, build_ready_at = None, None

    receipts = {}
    for game in plan["games"]:
        cutoff = utc(game["cutoff_utc"])
        reason = run.get("failure")
        if started > cutoff:
            reason = "LATE_START"
        elif lineage is not None:
            if not _same_game(calendar.get(game["game_id"]), game):
                reason = "KICKOFF_CONFLICT"
            elif not {game["away_team"], game["home_team"]} <= roster:
                reason = "MISSING_WEEKLY_ROSTER"
            elif any(item["required"] and item["status"] != "OK" for item in sources):
                reason = "REQUIRED_SOURCE_UNAVAILABLE"
            elif any(
                item.get("published_at_utc") and (
                    utc(item["published_at_utc"]) > cutoff
                    or utc(item["published_at_utc"]) > utc(item["finished_at_utc"])
                )
                for item in sources
            ):
                reason = "LATE_OR_INCONSISTENT_PUBLICATION"
            elif any(
                item.get("available_at_utc") and utc(item["available_at_utc"]) > cutoff
                for item in sources
            ):
                reason = "LATE_CAPTURE"
            elif utc(build_ready_at) > cutoff:
                reason = "LATE_BUILD"
            elif sealed > cutoff:
                reason = "LATE_SEAL"
        elif not reason:
            reason = "ARCHIVE_UNAVAILABLE"

        key = f"{game['game_id']}@{game['cutoff_utc']}"
        receipts[key] = {
            **game, "status": "ELIGIBLE" if reason is None else "EXCLUDED", "reason": reason,
            "kickoff_evidence": official_proof, "inputs": sources, "canonical": lineage,
            "build_available_at_utc": build_ready_at, "run_id": run["run_id"], "code": run["code"],
            "capture_started_at_utc": started.isoformat(),
            "capture_finished_at_utc": source_end.isoformat() if source_end else None,
            "sealed_at_utc": sealed.isoformat(),
            "decision": "NO_BET",
        }
    return receipts


def _seal(folder, plan, official, run, digest):
    index = {
        "schema_version": VERSION, "season": plan["season"], "week": plan["week"], "run": run,
        "plan_sha256": sha256(folder / "plan.json"), "archive_catalog_sha256": digest,
        "games": _derive(folder, plan, official, run, digest), "decision": "NO_BET",
    }
    _write(folder / "index.json", index)
    return index, sha256(folder / "index.json")


def capture_window(plan_folder, output, *, authorized=False, for_actions=False, clock=_now):
    if not authorized:
        raise ValueError("Explicit authorization for this capture is required")
    plan_folder = Path(plan_folder).resolve()
    output = _output(output, plan_folder)
    plan, official = _load_plan(plan_folder)
    if for_actions and official.get("public_redistribution_authorized") is not True:
        raise ValueError("Public archive redistribution is not authorized")
    started = utc(clock())
    if started < utc(plan["planned_at_utc"]):
        raise ValueError("Capture clock precedes the plan")
    deadline = min(utc(game["cutoff_utc"]) for game in plan["games"])
    output.mkdir(parents=True)
    _copy_official(plan_folder / "official", output / "official")
    shutil.copyfile(plan_folder / "plan.json", output / "plan.json")
    run = {"run_id": uuid4().hex, "started_at_utc": started.isoformat(), "code": code_identity()}
    if for_actions:
        run["github_run_id"] = os.environ.get("GITHUB_RUN_ID")
        run["github_run_attempt"] = os.environ.get("GITHUB_RUN_ATTEMPT")
    digest = None
    if started > deadline:
        run["failure"] = "WINDOW_CUTOFF_ELAPSED"
    else:
        with TemporaryDirectory(prefix="nfl-pregame-pilot-") as work:
            root = Path(work)
            manifest_path, _ = collect(plan["season"], root / "raw", SOURCES)
            manifest = _read(manifest_path)
            run["raw_manifest_sha256"] = sha256(manifest_path)
            if any(manifest["sources"].get(source, {}).get("status") != "OK" for source in REQUIRED):
                run["failure"] = "REQUIRED_SOURCE_UNAVAILABLE"
            elif utc(manifest["finished_at_utc"]) > deadline:
                run["failure"] = "LATE_CAPTURE"
            else:
                destination, result = build(manifest_path.parent, root / "canonical")
                if result["status"] not in {"OK", "PARTIAL"}:
                    run["failure"] = "CANONICAL_BUILD_FAILED"
                else:
                    exported = archive.export(manifest_path.parent, destination, output / "archive")
                    digest = exported["catalog_sha256"]
            if not digest:
                shutil.copytree(manifest_path.parent, output / "excluded_raw")
    run["sealed_at_utc"] = utc(clock()).isoformat()
    return _seal(output, plan, official, run, digest)


def verify_bundle(folder, expected_index):
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError("ARTIFACT_UNAVAILABLE_OR_EXPIRED: provide a retained offline copy")
    _verified_files(folder, ("index.json",))
    if sha256(folder / "index.json") != expected_index:
        raise ValueError("Independent index digest mismatch")
    index = _read(folder / "index.json")
    plan, official = _load_plan(folder)
    digest = index["archive_catalog_sha256"]
    if (
        index["schema_version"] != VERSION or index["decision"] != "NO_BET"
        or index["plan_sha256"] != sha256(folder / "plan.json")
        or (index["season"], index["week"]) != (plan["season"], plan["week"])
        or any(path.is_symlink() for path in folder.rglob("*"))
    ):
        raise ValueError("Pilot bundle provenance mismatch")
    allowed = {"index.json", "plan.json", "official"} | ({"archive"} if digest else set())
    if index["run"].get("raw_manifest_sha256") and not digest:
        allowed.add("excluded_raw")
    if {path.name for path in folder.iterdir()} != allowed or {
        path.name for path in (folder / "official").iterdir()
    } != set(OFFICIAL_FILES):
        raise ValueError("Unexpected or missing bundle content")
    if digest:
        archive.verify(folder / "archive", digest)
    if index["games"] != _derive(folder, plan, official, index["run"], digest):
        raise ValueError("Receipts differ from verified evidence")
    return index


def restore_bundle(folder, expected_index, destination):
    source = Path(folder).resolve()
    index = verify_bundle(source, expected_index)
    destination = _output(destination, source)
    shutil.copytree(source, destination)
    verify_bundle(destination, expected_index)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="command", required=True)
    plan = actions.add_parser("plan")
    plan.add_argument("--catalog", required=True)
    plan.add_argument("--official", required=True)
    plan.add_argument("--season", type=int, required=True)
    plan.add_argument("--week", type=int, required=True)
    plan.add_argument("--game", action="append", required=True)
    plan.add_argument("--lead-minutes", type=int, default=135)
    plan.add_argument("--output", required=True)
    capture = actions.add_parser("capture")
    capture.add_argument("--plan", required=True)
    capture.add_argument("--output", required=True)
    capture.add_argument("--authorized", action="store_true")
    capture.add_argument("--for-actions", action="store_true")
    for name in ("verify", "restore"):
        action = actions.add_parser(name)
        action.add_argument("--folder", required=True)
        action.add_argument("--expected-index", required=True)
        if name == "restore":
            action.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = plan_window(args.catalog, args.official, args.season, args.week, args.game,
                                 args.output, args.lead_minutes)
        elif args.command == "capture":
            result, digest = capture_window(args.plan, args.output, authorized=args.authorized, for_actions=args.for_actions)
            result = {**result, "index_sha256": digest}
        else:
            result = (verify_bundle(args.folder, args.expected_index) if args.command == "verify"
                      else restore_bundle(args.folder, args.expected_index, args.output))
        print(json.dumps(result, ensure_ascii=False))
        if args.command == "capture" and any(row["status"] != "ELIGIBLE" for row in result["games"].values()):
            return 2
    except (KeyError, OSError, ValueError) as exc:
        parser.exit(2, f"Pregame pilot failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
