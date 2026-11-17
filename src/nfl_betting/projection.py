"""Time-gated NFL point projections and walk-forward evaluation."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from math import ceil, isfinite, sqrt
from pathlib import Path
from statistics import fmean

from pytz import timezone

from .canonical import open_database
from .provenance import code_identity, sha256
from .temporal_roster import KICKOFF_TEAMS, load_evidence, select_roster, utc
from .web_export import _game_status, _games, _history_games, _kickoff_revisions, _rows, _weekly_roster

SCHEMA_VERSION = "1.5.0"
EASTERN = timezone("America/New_York")
MIN_GAMES = 5
MIN_OPPORTUNITIES = 10
MIN_CALIBRATION_DATES = 10
INTERVAL_LEVEL = 0.8
MODELS = ("season_mean", "recency_mean", "usage_efficiency")
OFFENSE = frozenset({"QB", "RB", "WR", "TE"})
RECEIVERS = OFFENSE - {"QB"}


@dataclass(frozen=True)
class Market:
    positions: frozenset[str]
    field: str | None
    weekly: str | None = None
    exposure: str | None = None
    signed: bool = False


MARKETS = {
    "pass_yards": Market(frozenset({"QB"}), None),
    "pass_attempts": Market(frozenset({"QB"}), None),
    "rush_yards": Market(OFFENSE, "rushing_yards", "weekly_rushing_yards", "carries", signed=True),
    "carries": Market(OFFENSE, "carries", exposure="carries"),
    "receptions": Market(RECEIVERS, "receptions", "weekly_receptions", "targets"),
    "rec_yards": Market(RECEIVERS, "receiving_yards", "weekly_receiving_yards", "targets", signed=True),
    "touchdowns": Market(OFFENSE, "offensive_td", "weekly_offensive_td", "opportunities"),
}


def _number(value, *, signed=False):
    if type(value) not in (int, float) or not isfinite(value) or (not signed and value < 0):
        return None
    return value


def _value(row, market):
    for field in (market.field, market.weekly):
        if field and (value := _number(row.get(field), signed=market.signed)) is not None:
            return value, field
    return None, None


def _weights(count):
    # Each observed game gets one weight. The three bands are disjoint.
    return [2.0 if distance <= 3 else 1.5 if distance <= 5 else 1.0
            for distance in range(count, 0, -1)]


def _weighted_mean(values):
    weights = _weights(len(values))
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def _estimate(point=None, reason=None, **details):
    return {
        "status": "POINT_ESTIMATE" if point is not None else "INSUFFICIENT_DATA",
        "point": point,
        "reason": reason,
        "interval": {
            "status": "INSUFFICIENT_DATA",
            "reason": "INSUFFICIENT_PRIOR_CALIBRATION_DATES" if point is not None else "POINT_ESTIMATE_UNAVAILABLE",
        },
        **details,
    }


def forecast_market(market_key, history):
    market = MARKETS[market_key]
    observations = []
    for row in sorted(history, key=lambda item: (item["kickoff_utc"], item["game_id"])):
        value, field = _value(row, market)
        if value is not None:
            observations.append({
                "game_id": row["game_id"], "kickoff_utc": row["kickoff_utc"],
                "available_at_utc": row["available_at_utc"], "value": value, "source_field": field,
                "offense_snaps": _number(row.get("offense_snaps")),
                "opportunities": _number(row.get(market.exposure)),
            })
    n = len(observations)
    result = {
        "status": "INSUFFICIENT_DATA" if n < MIN_GAMES else "POINT_ESTIMATE",
        "windows": {"season": n, "last5": min(5, n), "last3": min(3, n)},
        "observations": observations,
    }
    if n < MIN_GAMES:
        reason = "INDIVIDUAL_METRIC_NOT_MATERIALIZED" if market.field is None else "INSUFFICIENT_OBSERVED_GAMES"
        return {**result, "models": {name: _estimate(reason=reason) for name in MODELS}}

    values = [row["value"] for row in observations]
    usage = []
    for row in observations:
        snaps, opportunities, value = row["offense_snaps"], row["opportunities"], row["value"]
        if not snaps or opportunities is None or opportunities > snaps:
            continue
        # Opportunity-based efficiency cannot explain lateral-only yardage and
        # touchdowns, nor receptions that exceed the available target count.
        if (opportunities == 0 and value != 0) or (
            market_key in {"receptions", "touchdowns"} and value > opportunities
        ):
            continue
        usage.append(row)
    usage_n = len(usage)
    exposure = sum(row["opportunities"] for row in usage)
    usage_model = _estimate(
        reason="INSUFFICIENT_SNAP_OR_OPPORTUNITY_EVIDENCE", usage_games=usage_n, opportunity_count=exposure
    )
    if usage_n >= MIN_GAMES and exposure >= MIN_OPPORTUNITIES:
        snap_estimate = _weighted_mean([row["offense_snaps"] for row in usage])
        opportunities_per_snap = exposure / sum(row["offense_snaps"] for row in usage)
        efficiency = 1.0 if market_key == "carries" else sum(row["value"] for row in usage) / exposure
        usage_model = _estimate(
            snap_estimate * opportunities_per_snap * efficiency,
            usage_games=usage_n, opportunity_count=exposure, expected_offense_snaps=snap_estimate,
            opportunities_per_snap=opportunities_per_snap, value_per_opportunity=efficiency,
            usage_game_ids=[row["game_id"] for row in usage],
        )
    return {**result, "models": {
        "season_mean": _estimate(fmean(values)),
        "recency_mean": _estimate(_weighted_mean(values)),
        "usage_efficiency": usage_model,
    }}


@dataclass(frozen=True)
class Catalog:
    folder: Path
    manifest: dict
    available_at: datetime
    manifest_hash: str

    @property
    def lineage(self):
        return {
            "snapshot_id": self.manifest["source_snapshot_id"], "status": self.manifest["status"],
            "database_sha256": self.manifest["database"]["sha256"],
            "manifest_sha256": self.manifest_hash, "available_at_utc": self.available_at.isoformat(),
        }


@contextmanager
def _connect(folder):
    with open_database(folder) as con:
        con.execute("SET enable_external_access=false")
        yield con


def read_catalog(folder, season):
    folder = Path(folder).resolve()
    path = folder / "build_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["status"] not in {"OK", "PARTIAL"} or manifest["database"]["path"] != "nfl.duckdb" or (
        folder / "nfl.duckdb"
    ).is_symlink():
        raise ValueError("Expected a verified, local canonical database")
    with _connect(folder) as con:
        available = con.execute(
            "SELECT max(available_at) FROM games WHERE season=? AND season_type='REG' AND source_snapshot_id=?",
            [season, manifest["source_snapshot_id"]],
        ).fetchone()[0]
    if available is None:
        raise ValueError(f"No regular-season data for {season} in {folder}")
    return Catalog(folder, manifest, utc(available), sha256(path))


def _completed_players(con, cutoff):
    return _rows(
        con,
        """
        SELECT pw.player_id,pw.team,pw.game_id,g.kickoff_utc,
               greatest(g.available_at,pw.available_at) AS available_at,
               pw.targets,pw.carries,pw.targets+pw.carries AS opportunities,
               pw.offense_snaps,pw.receptions,pw.receiving_yards,pw.rushing_yards,pw.offensive_td,
               pw.weekly_receptions,pw.weekly_receiving_yards,pw.weekly_rushing_yards,
               pw.weekly_receiving_tds+pw.weekly_rushing_tds AS weekly_offensive_td
        FROM player_week pw JOIN web_history_games g
          USING(game_id,season,season_type,week,source_snapshot_id)
        WHERE regexp_full_match(pw.player_id, '00-[0-9]{7}')
          AND pw.team IN (g.home_team,g.away_team) AND pw.available_at<=?
          AND pw.opportunity_basis='COMPLETE_PBP_OBSERVATION'
          AND pw.participation IN (
            'OPPORTUNITIES_RECORDED', 'OFFENSIVE_SNAPS_ZERO_OPPORTUNITIES', 'LATERAL_TOUCH_RECORDED'
          )
        QUALIFY count(*) OVER (PARTITION BY pw.game_id,pw.player_id)=1
        ORDER BY g.kickoff_utc,pw.game_id,pw.player_id
        """,
        [cutoff],
    )


def _facts(con, catalog, season, cutoff, captures):
    revisions = _kickoff_revisions(con, captures)
    _history_games(con, season, cutoff, catalog.manifest["source_snapshot_id"])
    players = _completed_players(con, cutoff)
    for row in players:
        row["kickoff_utc"] = utc(row["kickoff_utc"]).isoformat()
        row["available_at_utc"] = utc(row.pop("available_at")).isoformat()
    return revisions, players


def _audit(players):
    return {
        "known_offensive_player_games": len(players),
        "known_games": len({row["game_id"] for row in players}),
        "known_player_games_with_snaps": sum(_number(row["offense_snaps"]) is not None for row in players),
        "markets": {
            key: {
                "materialized": market.field is not None,
                "observed_player_games": sum(_value(row, market)[0] is not None for row in players),
                "fields": [field for field in (market.field, market.weekly) if field],
            }
            for key, market in MARKETS.items()
        },
        "opponent_adjustment": "NOT_APPLIED_NO_OUT_OF_SAMPLE_EVIDENCE",
    }


def _fold(catalog, season, week, cutoff, captures):
    snapshot = catalog.manifest["source_snapshot_id"]
    with _connect(catalog.folder) as con:
        revisions, players = _facts(con, catalog, season, cutoff, captures)
        games = _games(con, season, week, cutoff, snapshot)
        weekly = _weekly_roster(con, season, week, cutoff, catalog.manifest, False)
    roster = select_roster(weekly, captures, week, cutoff, fallback=False)
    by_team = defaultdict(list)
    for row in roster:
        if row["position"] in OFFENSE and row["player_id"] and row["id_rows"] == 1 and not row["excluded_reason"]:
            by_team[row["team"]].append(row)
    histories = defaultdict(list)
    for row in players:
        row["game_date_et"] = utc(row["kickoff_utc"]).astimezone(EASTERN).date()
        histories[row["team"], row["player_id"]].append(row)

    projections, diagnostics = [], []
    for game in games:
        game_id = game["game_id"]
        teams = (game["away_team"], game["home_team"])
        schedule = None
        if game_id in revisions:
            game["kickoff_utc"], schedule = revisions[game_id]
            if not schedule or teams != KICKOFF_TEAMS[game_id]:
                game["kickoff_conflict"] = True
        status = _game_status(game, cutoff)
        candidates = []
        if status == "SCHEDULED_AT_CUTOFF":
            candidates = by_team[teams[0]] + by_team[teams[1]]
        diagnostics.append({
            "game_id": game_id, "status": status, "candidate_count": len(candidates),
        })
        for player in candidates:
            team, player_id = player["team"], player["player_id"]
            kickoff = utc(game["kickoff_utc"])
            game_date = kickoff.astimezone(EASTERN).date()
            # The catalog gate already restricts completed games to prior to
            # cutoff. Also keep training outside the target date and game.
            history = [
                row for row in histories[team, player_id]
                if row["game_date_et"] < game_date and row["game_id"] != game_id
            ]
            for key, market in MARKETS.items():
                if player["position"] not in market.positions:
                    continue
                projections.append({
                    "game_id": game_id, "week": week, "player_id": player_id, "team": team,
                    "opponent": teams[1] if team == teams[0] else teams[0],
                    "position": player["position"], "player_name": player["display_name"],
                    "market": key, "game_date_et": game_date.isoformat(),
                    "kickoff_utc": kickoff.isoformat(), "cutoff_utc": cutoff.isoformat(),
                    "feature_snapshot_id": snapshot,
                    "roster_evidence": player["roster_evidence"], "kickoff_evidence": schedule,
                    "availability_status": "UNVERIFIED",
                    "condition": "CONDITIONAL_ON_OFFENSIVE_PARTICIPATION",
                    **forecast_market(key, history),
                    "decision": "NO_BET",
                })
    return projections, {
        "week": week, "cutoff_utc": cutoff.isoformat(), "feature_catalog": catalog.lineage,
        "supplemental_evidence": [manifest for manifest, _ in captures],
        "games": diagnostics, "data_audit": _audit(players),
    }


def _labels(catalogs, season, scored_games, evidence_paths):
    labels = {}
    if not scored_games:
        return labels
    for catalog in sorted(catalogs, key=lambda item: (item.available_at, item.manifest["source_snapshot_id"])):
        captures = load_evidence(evidence_paths, season, catalog.available_at)
        with _connect(catalog.folder) as con:
            _, players = _facts(con, catalog, season, catalog.available_at, captures)
        for row in players:
            if row["game_id"] not in scored_games:
                continue
            for key, market in MARKETS.items():
                value, field = _value(row, market)
                if value is None:
                    continue
                identity = row["game_id"], row["player_id"], row["team"], key
                previous = labels.get(identity)
                if previous is None or row["available_at_utc"] < previous["available_at_utc"]:
                    labels[identity] = {
                        "value": value, "source_field": field,
                        "available_at_utc": row["available_at_utc"], "kickoff_utc": row["kickoff_utc"],
                        "snapshot_id": catalog.manifest["source_snapshot_id"],
                    }
    return labels


def _interval(residuals, prediction, estimate, market):
    cutoff, date = prediction["cutoff_utc"], prediction["game_date_et"]
    labels_by_date = defaultdict(list)
    for previous_date, available, error in residuals:
        if previous_date < date and available <= cutoff:
            labels_by_date[previous_date].append(error)
    n = len(labels_by_date)
    if n < MIN_CALIBRATION_DATES:
        return {**estimate["interval"], "calibration_dates": n}
    # One maximum residual per earlier game date keeps games on the same date
    # together. This is an empirical interval under temporal drift.
    scores = sorted(max(errors) for errors in labels_by_date.values())
    rank = ceil((n + 1) * INTERVAL_LEVEL)
    radius = scores[rank - 1]
    low = estimate["point"] - radius
    return {
        "status": "EMPIRICAL_INTERVAL", "target_coverage": INTERVAL_LEVEL, "calibration_dates": n,
        "lower": low if market.signed else max(0, low), "upper": estimate["point"] + radius,
        "latest_calibration_available_at_utc": max(
            available for prior_date, available, _ in residuals if prior_date < date and available <= cutoff
        ),
    }


def _score(records):
    errors = [estimate["point"] - label["value"] for _, label, estimate in records]
    intervals = [(label["value"], estimate["interval"]) for _, label, estimate in records
                 if estimate["interval"]["status"] == "EMPIRICAL_INTERVAL"]
    return {
        "n": len(errors), "games": len({row["game_id"] for row, _, _ in records}),
        "game_dates": len({row["game_date_et"] for row, _, _ in records}),
        "mae": fmean(abs(error) for error in errors) if errors else None,
        "rmse": sqrt(fmean(error**2 for error in errors)) if errors else None,
        "bias_forecast_minus_actual": fmean(errors) if errors else None,
        "interval_n": len(intervals),
        "interval_coverage": fmean(bounds["lower"] <= actual <= bounds["upper"]
                                   for actual, bounds in intervals) if intervals else None,
    }


def walk_forward(projections, labels):
    """Evaluate fixed models, learning interval radii only from admissible earlier folds."""
    by_date = defaultdict(list)
    for row in projections:
        by_date[row["game_date_et"]].append(row)
    residuals = defaultdict(list)
    rated = defaultdict(list)
    matched = defaultdict(list)
    exclusions = defaultdict(Counter)
    evaluations = []
    for date in sorted(by_date):
        for row in by_date[date]:
            key = row["market"]
            identity = row["game_id"], row["player_id"], row["team"], key
            label = labels.get(identity)
            if label is not None and (
                label["available_at_utc"] <= row["kickoff_utc"]
                or label["kickoff_utc"] != row["kickoff_utc"]
            ):
                label = None
                exclusions[key]["LABEL_KICKOFF_OR_TIME_MISMATCH"] += 1
            ready = {name: estimate for name, estimate in row["models"].items() if estimate["point"] is not None}
            for name, estimate in ready.items():
                estimate["interval"] = _interval(residuals[key, name], row, estimate, MARKETS[key])
            if not ready:
                exclusions[key]["INSUFFICIENT_DATA"] += 1
                continue
            if label is None:
                exclusions[key]["NO_ADMISSIBLE_PARTICIPATING_LABEL"] += 1
                continue
            evaluations.append({
                "game_id": row["game_id"], "player_id": row["player_id"], "team": row["team"],
                "game_date_et": date, "cutoff_utc": row["cutoff_utc"], "market": key,
                "label": label, "evaluated_models": list(ready), "decision": "NO_BET",
            })
            for name, estimate in ready.items():
                record = row, label, estimate
                rated[key, name].append(record)
                if len(ready) == len(MODELS):
                    matched[key, name].append(record)
                residuals[key, name].append(
                    (date, label["available_at_utc"], abs(estimate["point"] - label["value"]))
                )
    summary = {
        key: {
            "status": "EVALUATED" if any(rated[key, name] for name in MODELS) else "INSUFFICIENT_DATA",
            "models": {name: _score(rated[key, name]) for name in MODELS},
            "common_cohort": {name: _score(matched[key, name]) for name in MODELS},
            "exclusions": dict(exclusions[key]),
        }
        for key in MARKETS
    }
    return summary, evaluations


def run(season, folds, feature_folders, label_folders=(), evidence_paths=()):
    catalogs = [read_catalog(folder, season) for folder in feature_folders]
    label_catalogs = [read_catalog(folder, season) for folder in label_folders]
    projections, fold_reports = [], []
    covered = set()
    chronological = sorted((utc(cutoff), week) for week, cutoff in folds)
    for cutoff, week in chronological:
        if not 1 <= week <= 18:
            raise ValueError("Expected a regular-season week (1..18)")
        eligible = [catalog for catalog in catalogs if catalog.available_at <= cutoff]
        if not eligible:
            fold_reports.append({"week": week, "cutoff_utc": cutoff.isoformat(), "status": "NO_PREGAME_SNAPSHOT"})
            continue
        latest = max(catalog.available_at for catalog in eligible)
        selected = {catalog.lineage["database_sha256"]: catalog for catalog in eligible if catalog.available_at == latest}
        if len(selected) != 1:
            raise ValueError("Ambiguous feature catalogs at the same collection time")
        captures = load_evidence(evidence_paths, season, cutoff)
        fold_rows, diagnostics = _fold(next(iter(selected.values())), season, week, cutoff, captures)
        game_ids = {game["game_id"] for game in diagnostics["games"] if game["status"] == "SCHEDULED_AT_CUTOFF"}
        if covered & game_ids:
            raise ValueError("Game selected by multiple folds; provide one pregame cutoff per target")
        covered.update(game_ids)
        projections.extend(fold_rows)
        fold_reports.append(diagnostics)
    labels = _labels(label_catalogs, season, covered, evidence_paths)
    metrics, evaluations = walk_forward(projections, labels)
    return {
        "schema_version": SCHEMA_VERSION, "season": season, "season_type": "REG",
        "generated_at_utc": datetime.now(UTC).isoformat(), "game_date_timezone": "America/New_York",
        "decision": "NO_BET", "financial_approved": False, "statistical_model_approved": False,
        "code": code_identity(), "policy": {
            "minimum_observed_games": MIN_GAMES, "minimum_usage_opportunities": MIN_OPPORTUNITIES,
            "minimum_calibration_dates": MIN_CALIBRATION_DATES, "interval_target_coverage": INTERVAL_LEVEL,
            "weights_old_to_new": [1.0, 1.5, 2.0], "reference_model": "recency_mean",
            "opponent_adjustment": "NOT_APPLIED_NO_OUT_OF_SAMPLE_EVIDENCE",
        },
        "folds": fold_reports, "label_catalogs": [catalog.lineage for catalog in label_catalogs],
        "counts": {
            "candidate_player_game_markets": len(projections),
            "scored_player_game_markets": len(evaluations),
            "evaluated_predictions": sum(len(item["evaluated_models"]) for item in evaluations),
        },
        "projections": projections, "evaluations": evaluations, "metrics_by_market": metrics,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--fold", action="append", required=True, metavar="WEEK@CUTOFF_ISO")
    parser.add_argument("--features", action="append", required=True, type=Path, metavar="CANONICAL_BUILD")
    parser.add_argument("--labels", action="append", default=[], type=Path, metavar="CANONICAL_BUILD")
    parser.add_argument("--evidence", action="append", default=[], type=Path, metavar="SNAPSHOT")
    parser.add_argument("--output", required=True, type=Path, metavar="NEW_REPORT_JSON")
    args = parser.parse_args(argv)
    try:
        output = args.output.resolve()
        protected = [folder.resolve() for folder in (*args.features, *args.labels, *args.evidence)]
        repo = Path(__file__).resolve().parents[2]
        protected.extend(repo / path for path in ("data", "legacy", "web/public"))
        if any(output.is_relative_to(folder) for folder in protected):
            raise ValueError("Report must be outside historical data, catalogs, evidence and web assets")
        folds = [(int(week), utc(cutoff)) for week, cutoff in (value.split("@", 1) for value in args.fold)]
        if any(cutoff > datetime.now(UTC) for _, cutoff in folds):
            raise ValueError("The decision cutoff cannot be in the future")
        report = run(args.season, folds, args.features, args.labels, args.evidence)
        with output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, allow_nan=False, indent=2)
            handle.write("\n")
        print(json.dumps(report["counts"]))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Projection failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
