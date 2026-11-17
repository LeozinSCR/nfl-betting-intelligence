"""Export a verified canonical snapshot to compact, static web JSON.

The export is descriptive.  It never estimates a prospective probability, EV,
player availability, or a bookmaker price.  Thresholds are empirical research
scenarios and are labelled as such in every record.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

from .canonical import open_database
from .provenance import code_identity, sha256


SCHEMA_VERSION = "1.1.0"
POSITIONS = {"QB", "RB", "WR", "TE"}
MARKETS = {
    "receptions": "receptions",
    "receiving_yards": "rec_yards",
    "rushing_yards": "rush_yards",
    "offensive_td": "anytime_td",
}
GENERATED_FILES = (
    "games.json",
    "teams.json",
    "players.json",
    "game_analysis.json",
    "player_props_analysis.json",
)


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value.isoformat() if hasattr(value, "isoformat") else value


def _json_default(value):
    if isinstance(value, datetime):
        return _iso(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def _write_json(path: Path, payload, *, compact=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":") if compact else None,
        indent=None if compact else 2,
        default=_json_default,
        allow_nan=False,
    )
    path.write_text(text + "\n", encoding="utf-8")


def parse_cutoff(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("cutoff must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def percentile(values, fraction):
    """Linear percentile with explicit finite numeric input."""
    ordered = sorted(float(v) for v in values)
    if not ordered or not 0 <= fraction <= 1:
        raise ValueError("percentile requires values and fraction in [0,1]")
    if not all(math.isfinite(v) for v in ordered):
        raise ValueError("distribution contains a non-finite value")
    point = (len(ordered) - 1) * fraction
    low, high = math.floor(point), math.ceil(point)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (point - low)


def distribution(values, *, line=None, anytime_td=False):
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    if not all(math.isfinite(v) for v in clean):
        raise ValueError("distribution contains a non-finite value")
    hits = sum(v > 0 for v in clean) if anytime_td else sum(v > line for v in clean)
    return {
        "n": len(clean),
        "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "stddev_sample": statistics.stdev(clean) if len(clean) > 1 else None,
        "p25": percentile(clean, 0.25),
        "p50": percentile(clean, 0.50),
        "p75": percentile(clean, 0.75),
        "p90": percentile(clean, 0.90),
        "min": min(clean),
        "max": max(clean),
        "hit_count": hits,
        "historical_frequency": hits / len(clean),
        "frequency_semantics": "OBSERVED_NOT_PROSPECTIVE_PROBABILITY",
    }


def analytical_thresholds(values, market):
    """Derive up to three transparent scenarios; these are not market lines."""
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return []
    if market == "anytime_td":
        return [None]
    step = 1 if market == "receptions" else 5
    result = []
    for q in (0.25, 0.50, 0.75):
        pivot = percentile(clean, q)
        threshold = max(0.5, round(pivot / step) * step - 0.5)
        if threshold not in result:
            result.append(float(threshold))
    return result


def _window(values, size, *, line, anytime_td):
    subset = values[-size:] if size else values
    return distribution(
        [item["value"] for item in subset], line=line, anytime_td=anytime_td
    )


def _weighted(rows, value_field, weight_field):
    pairs = [
        (float(row[value_field]), float(row[weight_field]))
        for row in rows
        if row.get(value_field) is not None
        and row.get(weight_field) is not None
        and float(row[weight_field]) > 0
    ]
    return sum(value * weight for value, weight in pairs) / sum(
        weight for _, weight in pairs
    ) if pairs else None


def _team_window(rows):
    return {
        "games": len(rows),
        "epa_per_play": _weighted(rows, "epa_per_play", "epa_observations"),
        "success_rate": _weighted(rows, "success_rate", "epa_observations"),
        "offensive_plays_per_game": statistics.fmean(
            float(r["offensive_plays"]) for r in rows
        ) if rows else None,
        "pass_attempts_per_game": statistics.fmean(
            float(r["pass_attempts"]) for r in rows
        ) if rows else None,
        "rush_attempts_per_game": statistics.fmean(
            float(r["rush_attempts"]) for r in rows
        ) if rows else None,
        "dropbacks_per_game": statistics.fmean(
            float(r["dropbacks"]) for r in rows
        ) if rows else None,
        "epa_dropback": None,
        "epa_rush": None,
        "pace_seconds_per_play": None,
        "unavailable_metrics": [
            "epa_dropback",
            "epa_rush",
            "pace_seconds_per_play",
        ],
    }


def _rows(con, query, params=()):
    cursor = con.execute(query, params)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _metric_source(table, columns):
    return {
        "provider": "NFLverse via canonical DuckDB",
        "table": table,
        "columns": columns,
    }


def _games(con, season, week, cutoff):
    return _rows(
        con,
        """
        SELECT game_id,season,season_type,week,kickoff_utc,home_team,away_team,
               home_score,away_score,has_result,completion_basis,source_snapshot_id,
               available_at
        FROM games
        WHERE season=? AND season_type='REG' AND week=? AND available_at<=?
        ORDER BY kickoff_utc,game_id
        """,
        [season, week, cutoff],
    )


def _team_history(con, season, team, kickoff, cutoff):
    return _rows(
        con,
        """
        SELECT tw.week,tw.game_id,tw.offensive_plays,tw.pass_attempts,
               tw.rush_attempts,tw.dropbacks,tw.epa_per_play,
               tw.epa_observations,tw.success_rate,g.kickoff_utc
        FROM team_week tw JOIN games g USING(game_id)
        WHERE tw.season=? AND tw.season_type='REG' AND tw.team=?
          AND tw.available_at<=? AND g.available_at<=? AND g.has_result
          AND g.kickoff_utc<?
        ORDER BY g.kickoff_utc,tw.game_id
        """,
        [season, team, cutoff, cutoff, kickoff],
    )


def _defense_history(con, season, defense, position, kickoff, cutoff):
    rows = _rows(
        con,
        """
        SELECT dm.game_id,dm.targets,dm.receptions,dm.receiving_yards,g.kickoff_utc
        FROM defensive_matchups dm JOIN games g USING(game_id)
        WHERE dm.season=? AND dm.season_type='REG' AND dm.defense=?
          AND dm.position=? AND dm.available_at<=? AND g.available_at<=?
          AND g.has_result AND g.kickoff_utc<?
        ORDER BY g.kickoff_utc,dm.game_id
        """,
        [season, defense, position, cutoff, cutoff, kickoff],
    )
    return {
        "position": position,
        "games_with_position_events": len(rows),
        "targets_allowed_per_game": statistics.fmean(
            float(r["targets"]) for r in rows
        ) if rows else None,
        "receptions_allowed_per_game": statistics.fmean(
            float(r["receptions"]) for r in rows
        ) if rows else None,
        "receiving_yards_allowed_per_game": statistics.fmean(
            float(r["receiving_yards"]) for r in rows
        ) if rows else None,
        "scope_note": "Position aggregate; not an individual defender matchup or opponent-adjusted model.",
    }


def _candidate_roster(con, game, cutoff):
    return _rows(
        con,
        """
        SELECT team,player_id,display_name,roster_position,roster_status,
               participation,source_snapshot_id
        FROM player_week
        WHERE season=? AND season_type='REG' AND week=?
          AND team IN (?,?) AND player_id IS NOT NULL
          AND roster_position IN ('QB','RB','WR','TE') AND available_at<=?
        ORDER BY team,roster_position,display_name,player_id
        """,
        [
            game["season"],
            game["week"],
            game["away_team"],
            game["home_team"],
            cutoff,
        ],
    )


def _player_history(con, season, team, player_id, kickoff, cutoff):
    return _rows(
        con,
        """
        SELECT pw.week,pw.game_id,pw.receptions,pw.receiving_yards,
               pw.rushing_yards,pw.offensive_td,pw.targets,pw.carries,
               pw.offense_snaps,pw.offensive_snap_share,pw.participation,
               pw.opportunity_basis,g.kickoff_utc
        FROM player_week pw JOIN games g USING(game_id)
        WHERE pw.season=? AND pw.season_type='REG' AND pw.team=?
          AND pw.player_id=? AND pw.available_at<=? AND g.available_at<=?
          AND g.has_result AND g.kickoff_utc<?
          AND pw.opportunity_basis='COMPLETE_PBP_OBSERVATION'
          AND pw.participation IN (
              'OPPORTUNITIES_RECORDED','OFFENSIVE_SNAPS_ZERO_OPPORTUNITIES'
          )
        ORDER BY g.kickoff_utc,pw.game_id
        """,
        [season, team, player_id, cutoff, cutoff, kickoff],
    )


def _red_zone(con, season, player_id, kickoff, cutoff):
    row = con.execute(
        """
        SELECT
          count(*) FILTER(WHERE yardline_100<=20) red_zone_opportunities,
          count(*) FILTER(WHERE yardline_100<=5) goal_line_opportunities,
          count(*) FILTER(WHERE yardline_100<=20 AND opportunity_type='TARGET') red_zone_targets,
          count(*) FILTER(WHERE yardline_100<=20 AND opportunity_type='CARRY') red_zone_carries
        FROM offensive_opportunities o JOIN games g USING(game_id)
        WHERE o.season=? AND o.season_type='REG' AND o.player_id=?
          AND o.classification='STANDARD' AND o.available_at<=?
          AND g.available_at<=? AND g.has_result AND g.kickoff_utc<?
        """,
        [season, player_id, cutoff, cutoff, kickoff],
    ).fetchone()
    return dict(
        zip(
            (
                "red_zone_opportunities",
                "goal_line_opportunities",
                "red_zone_targets",
                "red_zone_carries",
            ),
            row,
        )
    )


def _volume(history, red_zone):
    def mean(field):
        values = [float(r[field]) for r in history if r.get(field) is not None]
        return statistics.fmean(values) if values else None

    return {
        "games": len(history),
        "targets_per_game": mean("targets"),
        "receptions_per_game": mean("receptions"),
        "carries_per_game": mean("carries"),
        "offensive_snap_share_mean": mean("offensive_snap_share"),
        "offensive_snap_share_last3_mean": statistics.fmean(
            float(r["offensive_snap_share"])
            for r in history[-3:]
            if r.get("offensive_snap_share") is not None
        ) if any(r.get("offensive_snap_share") is not None for r in history[-3:]) else None,
        **red_zone,
        "routes_run": None,
        "tprr": None,
        "yprr": None,
    }


def _quality(history):
    n = len(history)
    snap_n = sum(r.get("offensive_snap_share") is not None for r in history)
    score = round(
        min(n, 8) / 8 * 60
        + min(n, 3) / 3 * 20
        + (snap_n / n * 20 if n else 0),
        1,
    )
    grade = "ROBUST_DESCRIPTIVE_SAMPLE" if n >= 6 and snap_n >= 5 else (
        "USABLE_DESCRIPTIVE_SAMPLE" if n >= 3 else "INSUFFICIENT_DATA"
    )
    return {
        "grade": grade,
        "evidence_completeness_score": score,
        "score_semantics": "DATA_COMPLETENESS_NOT_EDGE_OR_PROBABILITY",
    }


def _prop_records(con, game, cutoff, defense_context):
    records, player_records = [], []
    roster = _candidate_roster(con, game, cutoff)
    for player in roster:
        history = _player_history(
            con,
            game["season"],
            player["team"],
            player["player_id"],
            game["kickoff_utc"],
            cutoff,
        )
        if not history:
            continue
        red_zone = _red_zone(
            con, game["season"], player["player_id"], game["kickoff_utc"], cutoff
        )
        quality = _quality(history)
        opponent = (
            game["home_team"] if player["team"] == game["away_team"]
            else game["away_team"]
        )
        player_records.append(
            {
                "player_id": player["player_id"],
                "display_name": player["display_name"],
                "team": player["team"],
                "position": player["roster_position"],
                "game_id": game["game_id"],
                "roster_status": player["roster_status"],
                "availability_status": "UNVERIFIED",
                "availability_note": "Weekly roster is not official inactive confirmation.",
                "quality": quality,
            }
        )
        for source_field, market in MARKETS.items():
            if market == "receptions" and player["roster_position"] not in {"RB", "WR", "TE"}:
                continue
            if market == "rec_yards" and player["roster_position"] not in {"RB", "WR", "TE"}:
                continue
            if market == "rush_yards" and player["roster_position"] not in {"QB", "RB", "WR"}:
                continue
            values = [
                {"value": row[source_field], "week": row["week"], "game_id": row["game_id"]}
                for row in history
                if row[source_field] is not None
            ]
            if len(values) < 3:
                continue
            raw_values = [item["value"] for item in values]
            for line in analytical_thresholds(raw_values, market):
                anytime = market == "anytime_td"
                season_dist = distribution(raw_values, line=line, anytime_td=anytime)
                last5 = _window(values, 5, line=line, anytime_td=anytime)
                last3 = _window(values, 3, line=line, anytime_td=anytime)
                favor = [
                    f"Amostra descritiva de {len(values)} jogos concluídos antes do kickoff.",
                    f"Recorrência observada: {season_dist['hit_count']}/{season_dist['n']} na temporada disponível.",
                ]
                against = [
                    "Disponibilidade oficial do jogador não verificada neste snapshot.",
                    "Sem cotação válida e sem probabilidade prospectiva calibrada.",
                ]
                if len(values) < 6:
                    against.append("Amostra curta: menos de seis observações elegíveis.")
                if last3 and season_dist and abs(last3["historical_frequency"] - season_dist["historical_frequency"]) >= 0.34:
                    against.append("Recorrência recente difere materialmente da temporada.")
                record = {
                    "id": f"{game['game_id']}:{player['player_id']}:{market}:{line if line is not None else 'yes'}",
                    "game_id": game["game_id"],
                    "player_id": player["player_id"],
                    "player_name": player["display_name"],
                    "team": player["team"],
                    "opponent": opponent,
                    "position": player["roster_position"],
                    "market": market,
                    "side": "yes" if anytime else "over",
                    "line": line,
                    "line_kind": "ANYTIME_TD_RESEARCH" if anytime else "ANALYTICAL_THRESHOLD_NOT_BOOK_OFFER",
                    "history": {
                        "season": season_dist,
                        "last5": last5,
                        "last3": last3,
                        "observations": values,
                    },
                    "volume": _volume(history, red_zone),
                    "context": {
                        "defense_vs_position": defense_context[opponent].get(player["roster_position"]),
                        "quarterback_status": "UNVERIFIED",
                        "role_stability": "DESCRIPTIVE_ONLY",
                        "game_script": "NOT_MODELED",
                    },
                    "evidence": {
                        "favors": favor,
                        "weakens": against,
                        "summary": "Hipótese exploratória baseada somente na distribuição histórica observada.",
                    },
                    "quality": quality,
                    "eligibility": {
                        "status": "UNVERIFIED",
                        "roster_status": player["roster_status"],
                        "official_inactive_source": None,
                    },
                    "quote": None,
                    "model": {
                        "status": "UNAVAILABLE",
                        "validated": False,
                        "probability": None,
                        "calibration": None,
                    },
                    "ev": None,
                    "classification": "DATA_INSUFFICIENT_FOR_FINANCIAL_DECISION",
                    "decision": "NO_BET",
                    "sources": [
                        _metric_source("player_week", [source_field, "targets", "carries", "offensive_snap_share"]),
                        _metric_source("offensive_opportunities", ["yardline_100", "classification"]),
                    ],
                }
                records.append(record)
    records.sort(
        key=lambda r: (
            -r["quality"]["evidence_completeness_score"],
            r["player_name"] or "",
            r["market"],
            -1 if r["line"] is None else r["line"],
        )
    )
    return records, player_records


def build_export(con, manifest, *, season, week, cutoff, published_at):
    games = _games(con, season, week, cutoff)
    if not games:
        raise ValueError("No games are available for season/week at the cutoff")
    game_items = []
    analyses = []
    all_props, all_players = [], []
    for game in games:
        status = "FINAL" if game["has_result"] else "SCHEDULED_AT_CUTOFF"
        game_items.append(
            {
                "game_id": game["game_id"],
                "season": game["season"],
                "week": game["week"],
                "away_team": game["away_team"],
                "home_team": game["home_team"],
                "kickoff_utc": _iso(game["kickoff_utc"]),
                "status": status,
                "away_score": game["away_score"],
                "home_score": game["home_score"],
                "status_source": "canonical.games.has_result",
            }
        )
        if status != "SCHEDULED_AT_CUTOFF" or game["kickoff_utc"] <= cutoff:
            continue
        team_metrics = {}
        defense_context = defaultdict(dict)
        for team in (game["away_team"], game["home_team"]):
            history = _team_history(con, season, team, game["kickoff_utc"], cutoff)
            team_metrics[team] = {
                "season": _team_window(history),
                "last5": _team_window(history[-5:]),
                "last3": _team_window(history[-3:]),
                "source": _metric_source(
                    "team_week",
                    ["epa_per_play", "success_rate", "offensive_plays", "pass_attempts", "rush_attempts", "dropbacks"],
                ),
            }
            for position in ("RB", "WR", "TE"):
                defense_context[team][position] = _defense_history(
                    con, season, team, position, game["kickoff_utc"], cutoff
                )
        analyses.append(
            {
                "game_id": game["game_id"],
                "cutoff_utc": _iso(cutoff),
                "teams": team_metrics,
                "defense_vs_position": dict(defense_context),
                "quarterbacks": {game["away_team"]: "UNVERIFIED", game["home_team"]: "UNVERIFIED"},
                "verified_injuries": [],
                "injury_note": "Canonical weekly injuries lack individual publication timestamps and do not confirm official inactives.",
                "summary": "Comparação descritiva baseada em jogos concluídos e disponíveis antes do kickoff-alvo. EPA/dropback, EPA/rush, pace oficial, QBs titulares e inativos verificados não estão disponíveis neste export.",
                "decision": "NO_BET",
            }
        )
        props, players = _prop_records(con, game, cutoff, defense_context)
        all_props.extend(props)
        all_players.extend(players)
    teams = _rows(
        con,
        "SELECT season,team,source_snapshot_id FROM teams WHERE season=? AND available_at<=? ORDER BY team",
        [season, cutoff],
    )
    unique_players = {p["player_id"]: p for p in all_players}
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "status": "PARTIAL" if manifest["status"] != "OK" or not analyses else "READY_DESCRIPTIVE_ONLY",
        "decision": "NO_BET",
        "financial_approved": False,
        "statistical_model_approved": False,
        "season": season,
        "week": week,
        "cutoff_utc": _iso(cutoff),
        "published_at_utc": _iso(published_at),
        "temporal_mode": "FROZEN_SNAPSHOT_AS_OF_CUTOFF",
        "source_snapshot_id": manifest["source_snapshot_id"],
        "source_snapshot_status": manifest["status"],
        "database_sha256": manifest["database"]["sha256"],
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "build_manifest_sha256": None,
        "code": code_identity(),
        "coverage": manifest.get("coverage_by_week", []),
        "pending_identity_audit_rows": manifest.get("pending_audit_rows"),
        "counts": {
            "games": len(game_items),
            "scheduled_games_with_analysis": len(analyses),
            "players": len(unique_players),
            "prop_scenarios": len(all_props),
            "verified_quotes": 0,
        },
        "source_attribution": {
            "canonical": "NFLverse datasets through nflreadpy; see docs/DATA_SOURCES.md for dataset licences and attribution.",
            "odds": "No odds feed is published in this snapshot.",
        },
        "limitations": [
            "Historical frequency is not a calibrated prospective probability.",
            "Analytical thresholds are not bookmaker offers.",
            "No official inactive, verified QB starter, routes run, TPRR, YPRR, pressure rate, EPA/dropback, EPA/rush or pace is published.",
            "No EV ranking is available without a validated model and a verified, temporally valid quote.",
        ],
    }
    return {
        "metadata": metadata,
        "games": game_items,
        "teams": teams,
        "players": sorted(unique_players.values(), key=lambda p: (p["team"], p["position"], p["display_name"] or "")),
        "game_analysis": analyses,
        "player_props_analysis": all_props,
    }


def export_static(
    canonical_folder,
    output_root,
    *,
    season,
    week,
    cutoff,
    published_at=None,
    publish_current=False,
):
    canonical_folder = Path(canonical_folder).resolve()
    output_root = Path(output_root).resolve()
    cutoff = cutoff.astimezone(timezone.utc)
    published_at = (published_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    manifest_path = canonical_folder / "build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") == "ERROR":
        raise ValueError("Canonical build status ERROR")
    if published_at < cutoff:
        raise ValueError("published_at cannot precede cutoff")
    with open_database(canonical_folder) as con:
        payload = build_export(
            con,
            manifest,
            season=season,
            week=week,
            cutoff=cutoff,
            published_at=published_at,
        )
    payload["metadata"]["build_manifest_sha256"] = sha256(manifest_path)
    snapshot_id = manifest["source_snapshot_id"]
    destination = output_root / "snapshots" / snapshot_id
    if destination.exists():
        raise FileExistsError(f"Snapshot export already exists: {destination}")
    destination.mkdir(parents=True)
    mapping = {
        "games.json": {"items": payload["games"]},
        "teams.json": {"items": payload["teams"]},
        "players.json": {"items": payload["players"]},
        "game_analysis.json": {"items": payload["game_analysis"]},
        "player_props_analysis.json": {"items": payload["player_props_analysis"]},
    }
    for filename, content in mapping.items():
        _write_json(destination / filename, {"schema_version": SCHEMA_VERSION, **content})
    payload["metadata"]["artifact_sha256"] = {
        name: sha256(destination / name) for name in GENERATED_FILES
    }
    _write_json(destination / "metadata.json", payload["metadata"], compact=False)
    slate = {
        **payload["metadata"],
        "generated_at_utc": payload["metadata"]["published_at_utc"],
        "games": payload["games"],
        "props": payload["player_props_analysis"],
        "matchups": payload["game_analysis"],
        "players": payload["players"],
        "snapshot_path": f"snapshots/{snapshot_id}/",
    }
    _write_json(destination / "slate.json", slate)
    if publish_current:
        output_root.mkdir(parents=True, exist_ok=True)
        _write_json(output_root / "slate.json", slate)
    return destination, slate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="Canonical build folder")
    parser.add_argument("--output", default="web/public/data")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--cutoff", required=True, help="Aware ISO-8601 cutoff")
    parser.add_argument("--published-at", help="Aware ISO-8601 publication time")
    parser.add_argument("--publish-current", action="store_true")
    args = parser.parse_args(argv)
    try:
        destination, slate = export_static(
            args.database,
            args.output,
            season=args.season,
            week=args.week,
            cutoff=parse_cutoff(args.cutoff),
            published_at=parse_cutoff(args.published_at) if args.published_at else None,
            publish_current=args.publish_current,
        )
        print(
            json.dumps(
                {
                    "destination": str(destination),
                    "status": slate["status"],
                    "counts": slate["counts"],
                    "decision": slate["decision"],
                },
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        print(f"Web export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
