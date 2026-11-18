"""Audit and compare the V1.5 NFL baselines in explicitly separate time modes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from random import Random

from .projection import (
    EASTERN, MARKETS, MIN_CALIBRATION_DATES, MODELS, _connect, _facts, _fold,
    _game_roster, _histories, _interval, _labels, _project_game, _score, read_catalog,
)
from .provenance import code_identity
from .temporal_roster import KICKOFF_CHANGES, KICKOFF_TEAMS, load_evidence, select_roster, utc
from .web_export import _rows, _weekly_roster

STRICT = "STRICT_AS_OF"
RETROSPECTIVE = "RETROSPECTIVE_EXPLORATORY"
SCHEMA_VERSION = "1.6.0"
MIN_TEST_DATES = 20
MIN_TEST_PAIRS = 400
MIN_EVENT_CLASS = 50
MAX_GAME_SHARE = 0.10
BOOTSTRAP_REPLICATES = 1000
BASELINE = "season_mean"
PHASES = ("train", "validation", "test")


def _date(kickoff):
    return utc(kickoff).astimezone(EASTERN).date().isoformat()


def _snapshot(catalog, season, audit_at):
    with _connect(catalog.folder) as con:
        games = _rows(con, """
            SELECT game_id,week,home_team,away_team,kickoff_utc,available_at,has_result
            FROM games WHERE season=? AND season_type='REG' AND source_snapshot_id=?
              AND available_at<=?
            ORDER BY week,game_id
            """, [season, catalog.manifest["source_snapshot_id"], audit_at])
        valid = con.execute("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema='main' AND table_name='ingestion_manifest'
            """).fetchone()[0]
        sources = _rows(con, """
            SELECT source,status,source_updated_at,resolved_download_url,sha256,ingested_at_utc
            FROM ingestion_manifest ORDER BY source
            """) if valid else []
    for source in sources:
        source["ingested_at_utc"] = (
            utc(source["ingested_at_utc"]).isoformat() if source["ingested_at_utc"] else None
        )
    return games, {**catalog.lineage, "source_versions": sources}


def _matchup(game):
    return game["week"], game["away_team"], game["home_team"]


def _schedule(game, kickoff_sources, lead, *, strict):
    original = game["kickoff_utc"]
    game_id = game["game_id"]
    if game_id not in KICKOFF_CHANGES:
        return utc(original) if original is not None else None, None
    if KICKOFF_TEAMS[game_id] != (game["away_team"], game["home_team"]):
        return None, None
    revision = kickoff_sources.get(game_id)
    if revision is None:
        return None, None
    kickoff, source = revision
    deadline = min(kickoff, utc(original)) if original is not None else kickoff
    if strict and utc(source["available_at_utc"]) > deadline - lead:
        return None, None
    return kickoff, source


def _kickoffs(captures):
    result = {}
    for source, rows in captures:
        if source["kind"] == "kickoff":
            for game_id, kickoff in rows.items():
                previous = result.get(game_id)
                if previous is None or utc(source["available_at_utc"]) < utc(previous[1]["available_at_utc"]):
                    result[game_id] = utc(kickoff), source
    return result


def _strict_plan(versions, corrections, lead, audit_at):
    if not versions:
        return None, "SNAPSHOT_UNAVAILABLE"
    admissible = []
    for catalog, game in versions:
        kickoff, source = _schedule(game, corrections, lead, strict=True)
        if kickoff is not None:
            admissible.append((kickoff - lead, catalog, game, kickoff, source))
    if not admissible:
        return None, "KICKOFF_UNVERIFIED"
    elapsed = [item for item in admissible if item[0] <= audit_at]
    if not elapsed:
        return None, "CUTOFF_NOT_REACHED"
    timely = [
        item for item in elapsed
        if max(item[1].available_at, utc(item[2]["available_at"])) <= item[0]
        and item[2]["has_result"] is False
    ]
    if not timely:
        return None, "LATE_CAPTURE"

    # Freeze the first feasible deadline. If a newer calendar already visible
    # at that deadline disagrees, omit the game rather than choosing a vintage
    # by the eventual label or moving the deadline backwards.
    cutoff = min(item[0] for item in timely)
    visible = [
        (catalog, game) for catalog, game in versions
        if max(catalog.available_at, utc(game["available_at"])) <= cutoff
    ]
    latest = max(catalog.available_at for catalog, _ in visible)
    newest = [(catalog, game) for catalog, game in visible if catalog.available_at == latest]
    if len({catalog.manifest["database"]["sha256"] for catalog, _ in newest}) != 1:
        return None, "KICKOFF_VERSION_CONFLICT"
    catalog, game = newest[0]
    kickoff, source = _schedule(game, corrections, lead, strict=True)
    if kickoff is None or kickoff - lead != cutoff or game["has_result"] is not False:
        return None, "KICKOFF_VERSION_CONFLICT"
    return (cutoff, catalog, game, kickoff, source), None


def _partition(dates):
    ordered = sorted(set(dates))
    # Always preserve the last date for test, including degenerate archives.
    train_end = len(ordered) * 50 // 100
    validation_end = len(ordered) * 75 // 100
    groups = dict(zip(PHASES, (ordered[:train_end], ordered[train_end:validation_end], ordered[validation_end:])))
    return groups, {date: phase for phase, group in groups.items() for date in group}


def _prior_history(catalog, season, cutoff, captures, first_test_date=None):
    with _connect(catalog.folder) as con:
        _, players = _facts(con, catalog, season, cutoff, captures)
    return _histories([
        row for row in players
        if first_test_date is None or _date(row["kickoff_utc"]) < first_test_date
    ])


def _retro_roster(catalog, season, week, latest_week):
    if latest_week < 1:
        return []
    with _connect(catalog.folder) as con:
        rows = _weekly_roster(con, season, latest_week, catalog.available_at, catalog.manifest, True)
    roster = select_roster(rows, [], week, catalog.available_at, fallback=True)
    for row in roster:
        evidence = row["roster_evidence"]
        # The time recorded by select_roster is the real archive lookup time,
        # not the hypothetical decision time of the historical replay.
        del evidence["cutoff_utc"]
        evidence["status"] = "HISTORICAL_ROSTER_PROXY"
        evidence["archive_lookup_at_utc"] = catalog.available_at.isoformat()
    return roster


def _coverage(rows):
    games = Counter(row["game_id"] for row, _ in rows)
    n = sum(games.values())
    return {
        "pairs": n, "predictions": n * len(MODELS), "games": len(games),
        "dates": len({row["game_date_et"] for row, _ in rows}),
        "largest_game_share": max(games.values()) / n if n else None,
    }


def _paired_ci(rows, model):
    groups = defaultdict(list)
    for row, label in rows:
        observed = label["value"]
        baseline_error = abs(row["models"][BASELINE]["point"] - observed)
        delta = abs(row["models"][model]["point"] - observed) - baseline_error
        groups[row["game_date_et"]].append(delta)
    blocks = [(sum(values), len(values)) for _, values in sorted(groups.items())]
    rng = Random(2026)
    samples = []
    for _ in range(BOOTSTRAP_REPLICATES):
        resampled = rng.choices(blocks, k=len(blocks))
        samples.append(sum(total for total, _ in resampled) / sum(n for _, n in resampled))
    samples.sort()
    return {
        "metric": "MAE_DELTA_VS_SEASON_MEAN",
        "lower": samples[int(0.025 * BOOTSTRAP_REPLICATES)],
        "upper": samples[int(0.975 * BOOTSTRAP_REPLICATES) - 1],
        "bootstrap_date_blocks": len(blocks),
    }


def _market_result(key, by_phase, test_predictions, mode, test_freeze):
    test_rows = by_phase["test"]
    supports = {phase: _coverage(by_phase[phase]) for phase in PHASES}
    support = supports["test"]
    gates = []
    if MARKETS[key].field is None:
        gates.append("INDIVIDUAL_METRIC_NOT_MATERIALIZED")
    if support["dates"] < MIN_TEST_DATES:
        gates.append("MIN_TEST_DATES")
    if support["pairs"] < MIN_TEST_PAIRS:
        gates.append("MIN_TEST_PAIRS")
    if support["largest_game_share"] is not None and support["largest_game_share"] > MAX_GAME_SHARE:
        gates.append("EXCESSIVE_GAME_CONCENTRATION")
    if not by_phase["train"] or not by_phase["validation"]:
        gates.append("MISSING_TRAIN_OR_VALIDATION_SUPPORT")

    residuals = {model: [] for model in MODELS}
    if mode == STRICT and test_freeze:
        for row, label in by_phase["validation"]:
            if utc(label["available_at_utc"]) <= test_freeze:
                for model in MODELS:
                    residuals[model].append((
                        row["game_date_et"], label["available_at_utc"],
                        abs(row["models"][model]["point"] - label["value"]),
                    ))
    cal_dates = len({date for date, _, _ in residuals[BASELINE]})
    interval_status = "INSUFFICIENT_DATA"
    if cal_dates >= MIN_CALIBRATION_DATES and test_predictions:
        interval_status = "EMPIRICAL_INTERVAL"
        for row in test_predictions:
            for model in MODELS:
                estimate = row["models"][model]
                if estimate["point"] is not None:
                    estimate["interval"] = _interval(residuals[model], row, estimate, MARKETS[key])

    metrics, comparison = None, None
    status = "INSUFFICIENT_DATA" if MARKETS[key].field is None else "INSUFFICIENT_EVALUATION_DATA"
    if not gates:
        status = "EVALUATED_NOT_APPROVED"
        metrics = {
            model: _score([(row, label, row["models"][model]) for row, label in test_rows])
            for model in MODELS
        }
        comparison = {model: _paired_ci(test_rows, model) for model in MODELS if model != BASELINE}
        if not any(result["upper"] < 0 for result in comparison.values()):
            gates.append("BASELINE_IMPROVEMENT_NOT_ESTABLISHED")

    if mode == RETROSPECTIVE:
        gates.append("EXPLORATORY_ONLY")
    # The current engine has point forecasts. Future probabilistic approval
    # requires actual event classes and calibration, irrespective of MAE.
    gates.append("PROBABILISTIC_VALIDATION_UNAVAILABLE")
    return {
        "status": status, "matched_support": supports, "metrics": metrics, "baseline_comparison": comparison,
        "interval_status": interval_status, "calibration_dates": cal_dates,
        "probabilistic_gate": {
            "status": "INSUFFICIENT_DATA", "min_events_per_threshold": MIN_EVENT_CLASS,
            "min_non_events_per_threshold": MIN_EVENT_CLASS, "calibration_required": True,
        },
        "approval_blocks": gates, "statistical_model_approved": False,
    }


def _paired_rows(projections, labels, phases, exclusions):
    paired = defaultdict(lambda: {phase: [] for phase in PHASES})
    games_with_label = set()
    for row in projections:
        market = row["market"]
        fields = {key: row[key] for key in ("game_id", "player_id", "team", "market")}
        key = tuple(fields.values())
        label = labels.get(key)
        feature_missing = any(row["models"][name]["point"] is None for name in MODELS)
        if feature_missing:
            reason = "INSUFFICIENT_HISTORY" if (
                MARKETS[market].field is not None and row["status"] == "INSUFFICIENT_DATA"
            ) else "MISSING_FEATURE"
            exclusions.append({**fields, "reason": reason, "models_unavailable": [
                name for name in MODELS if row["models"][name]["point"] is None
            ]})
        if label is None or (
            utc(label["kickoff_utc"]) != utc(row["kickoff_utc"])
            or utc(label["available_at_utc"]) <= utc(row["kickoff_utc"])
        ):
            if MARKETS[market].field is not None:
                exclusions.append({**fields, "reason": "MISSING_OUTCOME"})
            continue
        games_with_label.add(row["game_id"])
        if not feature_missing:
            paired[market][phases[row["game_date_et"]]].append((row, label))
    return paired, games_with_label


def _pilot_features(specifications, season, as_of, lead):
    from .pregame_capture import verify_bundle

    sources, receipts, evidence = [], {}, []
    for path, digest in specifications:
        folder = Path(path).resolve()
        index = verify_bundle(folder, digest)
        if index["season"] != season:
            raise ValueError("Pilot season differs from backtest season")
        catalog = folder / "archive/canonical"
        for receipt in index["games"].values():
            if receipt["status"] != "ELIGIBLE" or utc(receipt["sealed_at_utc"]) > as_of:
                continue
            if utc(receipt["kickoff_utc"]) - utc(receipt["cutoff_utc"]) != lead:
                raise ValueError("Pilot receipt and backtest cutoff policies differ")
            key = catalog, receipt["game_id"]
            receipts[key] = receipt
        if any(key[0] == catalog for key in receipts):
            sources.append(catalog)
        evidence.append({"index_sha256": digest, "run_id": index["run"]["run_id"]})
    return list(dict.fromkeys(sources)), receipts, evidence


def _pilot_plan(versions, receipts, audit_at):
    admissible = [
        (utc(receipt["cutoff_utc"]), catalog, game, utc(receipt["kickoff_utc"]), receipt["kickoff_evidence"])
        for catalog, game in versions
        if (receipt := receipts.get((catalog.folder, game["game_id"]))) is not None
        and game["kickoff_utc"] is not None and utc(game["kickoff_utc"]) == utc(receipt["kickoff_utc"])
        and game["has_result"] is False
    ]
    if not admissible:
        return None, "PILOT_RECEIPT_UNAVAILABLE"
    if len({item[3] for item in admissible}) != 1:
        return None, "PILOT_KICKOFF_CONFLICT"
    if admissible[0][3] > audit_at:
        return None, "GAME_NOT_STARTED_AT_AUDIT"
    return max(admissible, key=lambda item: (item[1].available_at, item[1].manifest_hash)), None


def backtest(mode, season, as_of, feature_folders, label_folders, evidence_paths=(), weeks=range(1, 19),
             lead_minutes=60, *, pilot_archives=()):
    if mode not in {STRICT, RETROSPECTIVE} or not 1 <= lead_minutes <= 7 * 24 * 60:
        raise ValueError("Specify a supported mode and an appropriate positive lead")
    as_of = utc(as_of)
    weeks = set(weeks)
    if not weeks or not weeks <= set(range(1, 19)):
        raise ValueError("Select regular-season weeks 1..18")
    lead = timedelta(minutes=lead_minutes)
    pilot_receipts, pilot_evidence = {}, []
    if pilot_archives:
        if mode != STRICT or feature_folders:
            raise ValueError("Pilot archives require strict mode and cannot mix with legacy feature inputs")
        feature_folders, pilot_receipts, pilot_evidence = _pilot_features(pilot_archives, season, as_of, lead)
    features = [c for p in feature_folders if (c := read_catalog(p, season)).available_at <= as_of]
    labels = [c for p in label_folders if (c := read_catalog(p, season)).available_at <= as_of]
    captures = load_evidence(evidence_paths, season, as_of)
    corrections = _kickoffs(captures)

    versions, anchors, inventory = defaultdict(list), {}, {}
    entries = sorted(
        [("features", c) for c in features] + [("labels", c) for c in labels],
        key=lambda item: (item[1].available_at, item[1].manifest["source_snapshot_id"]),
    )
    for role, catalog in entries:
        games, receipt = _snapshot(catalog, season, as_of)
        identity = (catalog.manifest["source_snapshot_id"], catalog.manifest_hash)
        if identity not in inventory:
            inventory[identity] = {**receipt, "roles": []}
        if role not in inventory[identity]["roles"]:
            inventory[identity]["roles"].append(role)
        for game in games:
            if game["week"] not in weeks:
                continue
            game_id = game["game_id"]
            anchors[game_id] = game
            if role == "features":
                versions[game_id].append((catalog, game))

    plans, game_inventory, exclusions, dates = {}, {}, [], []
    for game_id, anchor in sorted(anchors.items()):
        kickoff, schedule = _schedule(anchor, corrections, lead, strict=False)
        nominal = kickoff if kickoff is not None else anchor["kickoff_utc"]
        entry = {
            "game_id": game_id, "week": anchor["week"], "candidate_snapshots": [
                {"snapshot_id": catalog.manifest["source_snapshot_id"],
                 "catalog_available_at_utc": catalog.available_at.isoformat(),
                 "schedule_available_at_utc": utc(game["available_at"]).isoformat(),
                 "catalog_kickoff_utc": utc(game["kickoff_utc"]).isoformat() if game["kickoff_utc"] else None}
                for catalog, game in versions[game_id]
            ],
        }
        game_inventory[game_id] = entry
        if mode == STRICT:
            if pilot_archives:
                plan, reason = _pilot_plan(versions[game_id], pilot_receipts, as_of)
            else:
                plan, reason = _strict_plan(versions[game_id], corrections, lead, as_of)
            if plan and plan[3] > as_of:
                plan, reason = None, "GAME_NOT_STARTED_AT_AUDIT"
            elif not plan and nominal is not None and utc(nominal) > as_of:
                reason = "GAME_NOT_STARTED_AT_AUDIT"
        elif nominal is not None and utc(nominal) > as_of:
            plan, reason = None, "GAME_NOT_STARTED_AT_AUDIT"
        elif not versions[game_id] or kickoff is None:
            plan, reason = None, "SNAPSHOT_UNAVAILABLE" if not versions[game_id] else "KICKOFF_UNVERIFIED"
        else:
            catalog, archived = versions[game_id][-1]
            kickoff, schedule = _schedule(archived, corrections, lead, strict=False)
            if kickoff is not None and kickoff <= as_of:
                plan, reason = (kickoff - lead, catalog, archived, kickoff, schedule), None
            else:
                plan, reason = None, "KICKOFF_UNVERIFIED"
        if plan is not None:
            _, _, game, target_kickoff, _ = plan
            game_date = _date(target_kickoff)
            plans[game_id] = plan
            dates.append(game_date)
        else:
            game_date = _date(nominal) if nominal is not None else None
            exclusions.append({"game_id": game_id, "reason": reason})
        entry.update(game_date_et=game_date, status=reason or "SCHEDULE_ELIGIBLE")

    splits, phases = _partition(dates)
    test_plans = [plan for game_id, plan in plans.items()
                  if phases[game_inventory[game_id]["game_date_et"]] == "test"]
    test_freeze = min((plan[0] for plan in test_plans), default=None)
    first_test_date = splits["test"][0] if splits["test"] else None
    frozen = None
    frozen_catalog = None
    last_training_roster_week = None
    if mode == STRICT and test_freeze:
        _, catalog, _, _, _ = min(test_plans, key=lambda plan: plan[0])
        frozen_catalog = catalog
        frozen = _prior_history(catalog, season, test_freeze, load_evidence(evidence_paths, season, test_freeze),
                                first_test_date)
    elif test_freeze:
        catalog = max(features, key=lambda item: (item.available_at, item.manifest["source_snapshot_id"]))
        frozen_catalog = catalog
        archived = load_evidence(evidence_paths, season, catalog.available_at)
        frozen_facts = _prior_history(catalog, season, catalog.available_at, archived, first_test_date)
        frozen = defaultdict(list, {
            key: [row for row in rows if utc(row["kickoff_utc"]) < test_freeze]
            for key, rows in frozen_facts.items()
        })
        last_training_roster_week = min(plan[2]["week"] for plan in test_plans) - 1

    retrospective_histories, retrospective_rosters = {}, {}
    projections = []
    strict_batches = defaultdict(set)
    for game_id, (cutoff, catalog, game, kickoff, schedule) in plans.items():
        entry = game_inventory[game_id]
        entry.update(phase=phases[entry["game_date_et"]], cutoff_utc=cutoff.isoformat(),
                     kickoff_utc=kickoff.isoformat(), selected_snapshot_id=catalog.manifest["source_snapshot_id"],
                     kickoff_evidence=schedule)
        if pilot_archives:
            entry["pilot_receipt"] = pilot_receipts[catalog.folder, game_id]
        if mode == STRICT:
            strict_batches[catalog.folder, game["week"], cutoff, entry["phase"]].add(game_id)
            continue
        latest_week = game["week"] - 1
        if entry["phase"] == "test" and last_training_roster_week is not None:
            latest_week = min(latest_week, last_training_roster_week)
        roster_key = (catalog.folder, game["week"], latest_week)
        if roster_key not in retrospective_rosters:
            retrospective_rosters[roster_key] = _retro_roster(catalog, season, game["week"], latest_week)
        roster, skipped = _game_roster(retrospective_rosters[roster_key], _matchup(game)[1:])
        if entry["phase"] == "test":
            histories = frozen
        else:
            if catalog.folder not in retrospective_histories:
                archived = load_evidence(evidence_paths, season, catalog.available_at)
                retrospective_histories[catalog.folder] = _prior_history(catalog, season, catalog.available_at, archived)
            histories = retrospective_histories[catalog.folder]
        projections.extend(_project_game(
            {**game, "kickoff_utc": kickoff}, roster, histories, cutoff,
            catalog.manifest["source_snapshot_id"], schedule,
        ))
        entry["candidate_count"] = len(roster)
        exclusions.extend({"game_id": game_id, **row} for row in skipped)

    feature_by_folder = {catalog.folder: catalog for catalog in features}
    for (folder, week, cutoff, phase), game_ids in strict_batches.items():
        catalog = feature_by_folder[folder]
        rows, details = _fold(
            catalog, season, week, cutoff, load_evidence(evidence_paths, season, cutoff),
            game_ids=game_ids, frozen_histories=frozen if phase == "test" else None,
            verified_targets={
                game_id: pilot_receipts[folder, game_id]["kickoff_evidence"] for game_id in game_ids
            } if pilot_archives else None,
        )
        projections.extend(rows)
        for result in details["games"]:
            game_id = result["game_id"]
            game_inventory[game_id]["candidate_count"] = result["candidate_count"]
            exclusions.extend({"game_id": game_id, **player} for player in result["excluded_players"])
    for game_id in plans:
        if not game_inventory[game_id].get("candidate_count"):
            exclusions.append({"game_id": game_id, "reason": "MISSING_FEATURE", "detail": "NO_ELIGIBLE_ROSTER"})

    outcomes = _labels(labels, season, set(plans), evidence_paths,
                       expected_kickoffs={game_id: plan[3] for game_id, plan in plans.items()})
    paired, games_with_label = _paired_rows(projections, outcomes, phases, exclusions)
    exclusions.extend({"game_id": game_id, "reason": "MISSING_OUTCOME"} for game_id in sorted(set(plans) - games_with_label))
    test_predictions = defaultdict(list)
    for row in projections:
        row["phase"] = phases[row["game_date_et"]]
        row["history_snapshot_id"] = (
            frozen_catalog.manifest["source_snapshot_id"] if row["phase"] == "test" else row["feature_snapshot_id"]
        )
        if row["phase"] == "test" and row["status"] != "INSUFFICIENT_DATA":
            test_predictions[row["market"]].append(row)
    results = {
        market: _market_result(market, paired[market], test_predictions[market], mode, test_freeze)
        for market in MARKETS
    }
    status = (
        "EVALUATED_NOT_APPROVED" if any(item["metrics"] is not None for item in results.values())
        else "INSUFFICIENT_EVALUATION_DATA"
    )
    return {
        "schema_version": SCHEMA_VERSION, "mode": mode, "status": status, "season": season, "season_type": "REG",
        "as_of_utc": as_of.isoformat(), "decision": "NO_BET", "statistical_model_approved": False,
        "financial_approved": False, "game_date_timezone": "America/New_York",
        "availability_claim": mode == STRICT, "policy": {
            "weeks": sorted(weeks), "lead_minutes": lead_minutes, "min_test_dates": MIN_TEST_DATES,
            "min_test_pairs": MIN_TEST_PAIRS, "max_game_share": MAX_GAME_SHARE,
            "min_calibration_dates": MIN_CALIBRATION_DATES, "paired_bootstrap_replicates": BOOTSTRAP_REPLICATES,
        },
        "code": code_identity(), "snapshots": list(inventory.values()),
        "pilot_archives": pilot_evidence,
        "supplemental_evidence": [source for source, _ in captures],
        "fold_dates": splits, "test_frozen_at_utc": test_freeze.isoformat() if test_freeze else None,
        "test_history_catalog": frozen_catalog.lineage if frozen_catalog else None,
        "inventoried_games": list(game_inventory.values()), "markets": results,
        "counts": {
            "games_in_inventory": len(game_inventory), "games_schedule_eligible": len(plans),
            "games_with_participating_label": len(games_with_label),
            "projection_rows": len(projections),
            "pairs_common_all_phases": sum(item["pairs"] for market in results.values() for item in market["matched_support"].values()),
        },
        "exclusion_counts": dict(Counter(row["reason"] for row in exclusions)), "exclusions": exclusions,
        "projections": projections,
        "paired_outcomes": [
            {"phase": phase, "game_id": row["game_id"], "player_id": row["player_id"],
             "team": row["team"], "market": key, "label": label}
            for key, groups in paired.items() for phase, rows in groups.items() for row, label in rows
        ],
    }


def markdown(report):
    title = f"# NFL Backtest {report['season']} — {report['mode']}"
    claim = ("Disponibilidade pré-kickoff comprovada para as features aceitas."
             if report["availability_claim"] else
             "Reconstrução por data do evento. Os insumos podem ter sido capturados após a partida.")
    counts = report["counts"]
    lines = [title, "", f"**{report['status']}** · **NO_BET**", "", claim, "",
             f"Corte da auditoria {report['as_of_utc']}. {counts['games_in_inventory']} jogos inventariados, "
             f"{counts['games_schedule_eligible']} com plano e {counts['pairs_common_all_phases']} pares comuns.",
             f"Datas de treino / validação / teste: {' / '.join(str(len(report['fold_dates'][phase])) for phase in PHASES)}.",
             f"Congelamento do teste: {report['test_frozen_at_utc'] or 'indisponível'}.",
             "", "## Catálogos e evidência", ""]
    for source in report["snapshots"]:
        lines.append(f"- `{source['snapshot_id']}` · {', '.join(source['roles'])} · "
                     f"{source['available_at_utc']} · SHA-256 `{source['database_sha256']}`")
    for source in report["supplemental_evidence"]:
        lines.append(f"- {source['kind']} `{source['snapshot_id']}` · {source['available_at_utc']} · "
                     f"SHA-256 `{source['sha256']}`")
    lines += ["", "## Teste final na coorte comum", "",
              "| Mercado | Pares treino / validação / teste | Jogos / datas de teste | Datas de calibração | Estado | Bloqueios |",
              "| --- | ---: | ---: | ---: | --- | --- |"]
    for key, result in report["markets"].items():
        support = result["matched_support"]
        test = support["test"]
        pairs = " / ".join(str(support[phase]["pairs"]) for phase in PHASES)
        lines.append(f"| {key} | {pairs} | {test['games']} / {test['dates']} | {result['calibration_dates']} | "
                     f"{result['status']} | {', '.join(result['approval_blocks'])} |")
    scored = [(key, model, metrics) for key, row in report["markets"].items()
              for model, metrics in (row["metrics"] or {}).items()]
    if scored:
        lines += ["", "| Mercado | Modelo | N | MAE | RMSE | Viés | Cobertura de intervalo (N) | IC 95% pareado da diferença de MAE |",
                  "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |"]
        for key, model, metrics in scored:
            ci = report["markets"][key]["baseline_comparison"].get(model)
            bounds = f"[{ci['lower']:.4f}, {ci['upper']:.4f}]" if ci else "—"
            coverage = metrics["interval_coverage"]
            intervals = f"{coverage:.1%} ({metrics['interval_n']})" if coverage is not None else "— (0)"
            lines.append(f"| {key} | {model} | {metrics['n']} | {metrics['mae']:.4f} | "
                         f"{metrics['rmse']:.4f} | {metrics['bias_forecast_minus_actual']:+.4f} | {intervals} | {bounds} |")
    lines += ["", "## Exclusões", ""]
    lines += [f"- {reason} · {n}" for reason, n in sorted(report["exclusion_counts"].items())]
    lines += ["", "O JSON detalha cutoffs, partições, exclusões individuais, valores usados e comparações pareadas.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=(STRICT, RETROSPECTIVE), required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    features = parser.add_mutually_exclusive_group(required=True)
    features.add_argument("--features", type=Path, action="append", default=[])
    features.add_argument("--pilot", action="append", nargs=2, default=[], metavar=("FOLDER", "INDEX_SHA256"))
    parser.add_argument("--labels", type=Path, action="append", required=True)
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    parser.add_argument("--week", type=int, action="append")
    parser.add_argument("--lead-minutes", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True, help="New report directory")
    args = parser.parse_args(argv)
    try:
        audit_at = utc(args.as_of)
        if audit_at > datetime.now(UTC):
            raise ValueError("Audit cutoff cannot be in the future")
        output = args.output.resolve()
        repo = Path(__file__).resolve().parents[2]
        protected = [repo / name for name in ("data", "legacy", "web/public")]
        protected.extend(path.resolve() for path in (*args.features, *args.labels, *args.evidence))
        protected.extend(Path(path).resolve() for path, _ in args.pilot)
        if any(output.is_relative_to(path) for path in protected):
            raise ValueError("Output must be outside catalogs, evidence and historical datasets")
        if output.exists():
            raise FileExistsError(output)
        report = backtest(args.mode, args.season, audit_at, args.features, args.labels, args.evidence,
                          args.week or range(1, 19), args.lead_minutes, pilot_archives=args.pilot)
        payload = json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        output.mkdir(parents=True)
        (output / "report.json").write_text(payload + "\n", encoding="utf-8")
        (output / "report.md").write_text(markdown(report), encoding="utf-8")
        print(json.dumps({"mode": args.mode, "status": report["status"], **report["counts"]}))
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"Backtest failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
