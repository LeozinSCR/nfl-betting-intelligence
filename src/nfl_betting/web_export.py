"""Export a verified canonical snapshot to compact, static web JSON.

The export is descriptive.  It never estimates a prospective probability, EV,
player availability, or a bookmaker price.  Thresholds are empirical research
scenarios and are labelled as such in every record.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
from tempfile import NamedTemporaryFile

from .canonical import open_database
from .provenance import code_identity, sha256


SCHEMA_VERSION = "1.3.0"
POSITIONS = {"QB", "RB", "WR", "TE"}
MARKETS = {
    "receptions": ("receptions", "weekly_receptions", POSITIONS - {"QB"}),
    "rec_yards": ("receiving_yards", "weekly_receiving_yards", POSITIONS - {"QB"}),
    "rush_yards": ("rushing_yards", "weekly_rushing_yards", POSITIONS),
    "anytime_td": ("offensive_td", "weekly_offensive_td", POSITIONS),
}
MIN_HISTORY = 3
UNMATERIALIZED_QB_MARKETS = ("pass_yards", "pass_attempts", "completions")
ARTIFACTS = {
    "games.json": ("games", "games"),
    "teams.json": ("teams", None),
    "players.json": ("players", "players"),
    "game_analysis.json": ("game_analysis", "matchups"),
    "player_props_analysis.json": ("player_props_analysis", "props"),
    "player_coverage.json": ("player_coverage", "player_coverage"),
}


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


def _utc(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone offset")
    return value.astimezone(timezone.utc)


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


def _mean(rows, field):
    values = [row[field] for row in rows if row.get(field) is not None]
    return statistics.fmean(values) if values else None


def _team_window(rows):
    window = {
        "games": len(rows),
        "epa_per_play": _weighted(rows, "epa_per_play", "epa_observations"),
        "success_rate": _weighted(rows, "success_rate", "epa_observations"),
        "offensive_plays_per_game": _mean(rows, "offensive_plays"),
        "pass_attempts_per_game": _mean(rows, "pass_attempts"),
        "rush_attempts_per_game": _mean(rows, "rush_attempts"),
        "dropbacks_per_game": _mean(rows, "dropbacks"),
        "epa_dropback": None,
        "epa_rush": None,
        "pace_seconds_per_play": None,
    }
    not_materialized = {"epa_dropback", "epa_rush", "pace_seconds_per_play"}
    window["unavailable_metrics"] = {
        field: "NOT_MATERIALIZED" if field in not_materialized else "NO_COMPLETE_OBSERVATIONS"
        for field, value in window.items() if value is None
    }
    return window


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


def _games(con, season, week, cutoff, snapshot):
    return _rows(
        con,
        """
        SELECT game_id,season,season_type,week,kickoff_utc,home_team,away_team,
               home_score,away_score,has_result,available_at
        FROM games
        WHERE season=? AND season_type='REG' AND week=? AND available_at<=?
          AND source_snapshot_id=?
        ORDER BY kickoff_utc NULLS LAST,game_id
        """,
        [season, week, cutoff, snapshot],
    )


def _history_games(con, season, cutoff, snapshot):
    # A calendar score alone does not prove complete play-by-play.
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE web_history_games AS
        SELECT g.game_id, g.season, g.season_type, g.week, g.home_team, g.away_team,
               g.kickoff_utc, greatest(g.available_at, completion.available_at) AS available_at,
               g.source_snapshot_id
        FROM games g
        JOIN (
            SELECT game_id,season,season_type,week,source_snapshot_id,min(available_at) AS available_at
            FROM coverage_audit WHERE has_end_marker AND available_at<=?
            GROUP BY game_id,season,season_type,week,source_snapshot_id
        ) completion USING (game_id,season,season_type,week,source_snapshot_id)
        WHERE g.season=? AND g.season_type='REG' AND g.source_snapshot_id=?
          AND g.available_at<=? AND g.kickoff_utc<?
          AND g.has_result AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
        """,
        [cutoff, season, snapshot, cutoff, cutoff],
    )


def _team_history(con, team, cutoff):
    return _rows(
        con,
        """
        SELECT tw.offensive_plays,tw.pass_attempts,tw.rush_attempts,tw.dropbacks,
               tw.epa_per_play,tw.epa_observations,tw.success_rate
        FROM team_week tw JOIN web_history_games g
          USING(game_id,season,season_type,week,source_snapshot_id)
        WHERE tw.team=? AND tw.team IN (g.home_team,g.away_team) AND tw.available_at<=?
        ORDER BY g.kickoff_utc,tw.game_id
        """,
        [team, cutoff],
    )


def _defense_history(con, defense, cutoff):
    rows = _rows(
        con,
        """
        SELECT dm.position,count(*) AS games_with_position_events,
               avg(dm.targets) AS targets_allowed_per_game,
               avg(dm.receptions) AS receptions_allowed_per_game,
               avg(dm.receiving_yards) AS receiving_yards_allowed_per_game
        FROM defensive_matchups dm JOIN web_history_games g
          USING(game_id,season,season_type,week,source_snapshot_id)
        WHERE dm.defense=? AND dm.defense IN (g.home_team,g.away_team)
          AND dm.position IN ('RB','WR','TE') AND dm.available_at<=?
        GROUP BY dm.position ORDER BY dm.position
        """,
        [defense, cutoff],
    )
    return {
        row["position"]: {
            **row,
            "scope_note": "Position aggregate; not an individual defender matchup or opponent-adjusted model.",
        }
        for row in rows
    }


def _weekly_roster(con, season, week, cutoff, snapshot):
    # Use the selected week's canonical roster association, not target statistics.
    return _rows(
        con,
        """
        SELECT team,player_id,display_name,position,roster_status,
               count(*) OVER (PARTITION BY player_id) AS id_rows
        FROM player_crosswalk
        WHERE season=? AND season_type='REG' AND week=? AND available_at<=?
          AND source_snapshot_id=?
        ORDER BY team,position,player_id
        """,
        [season, week, cutoff, snapshot],
    )


def _player_history(con, player_id, cutoff):
    return _rows(
        con,
        """
        SELECT pw.week,pw.game_id,pw.team,pw.receptions,pw.receiving_yards,
               pw.rushing_yards,pw.offensive_td,pw.targets,pw.carries,
               pw.weekly_receptions,pw.weekly_receiving_yards,pw.weekly_rushing_yards,
               pw.weekly_receiving_tds + pw.weekly_rushing_tds AS weekly_offensive_td,
               pw.offensive_snap_share,g.kickoff_utc,
               greatest(pw.available_at,g.available_at) AS available_at
        FROM player_week pw JOIN web_history_games g
          USING(game_id,season,season_type,week,source_snapshot_id)
        WHERE pw.player_id=? AND pw.team IN (g.home_team,g.away_team)
          AND pw.available_at<=? AND pw.opportunity_basis='COMPLETE_PBP_OBSERVATION'
          AND pw.participation IN (
              'OPPORTUNITIES_RECORDED','OFFENSIVE_SNAPS_ZERO_OPPORTUNITIES',
              'LATERAL_TOUCH_RECORDED'
          )
        -- Ambiguity within a historical game cannot count as a second observation.
        QUALIFY count(*) OVER (PARTITION BY pw.game_id)=1
        ORDER BY g.kickoff_utc,pw.game_id
        """,
        [player_id, cutoff],
    )


def _red_zone(con, player_id, history, cutoff):
    return _rows(
        con,
        """
        SELECT
          CASE WHEN count(yardline_100)=count(*) AND count(*)>0
               THEN count(*) FILTER (WHERE yardline_100<=20) END AS red_zone_opportunities,
          CASE WHEN count(yardline_100)=count(*) AND count(*)>0
               THEN count(*) FILTER (WHERE yardline_100<=5) END AS goal_line_opportunities,
          CASE WHEN count(yardline_100)=count(*) AND count(*)>0
               THEN count(*) FILTER (WHERE yardline_100<=20 AND opportunity_type='TARGET') END AS red_zone_targets,
          CASE WHEN count(yardline_100)=count(*) AND count(*)>0
               THEN count(*) FILTER (WHERE yardline_100<=20 AND opportunity_type='RUSH') END AS red_zone_carries
        FROM offensive_opportunities o JOIN web_history_games g
          USING(game_id,season,season_type,week,source_snapshot_id)
        JOIN (SELECT unnest(?) AS game_id, unnest(?) AS team) h
          ON o.game_id=h.game_id AND o.team=h.team
        WHERE o.player_id=? AND o.classification='STANDARD'
          AND o.opportunity_type IN ('TARGET','RUSH') AND o.available_at<=?
        """,
        [[row["game_id"] for row in history], [row["team"] for row in history], player_id, cutoff],
    )[0]


def _volume(history, red_zone):
    volume = {
        "games": len(history),
        "targets_per_game": _mean(history, "targets"),
        "receptions_per_game": _mean(history, "receptions"),
        "carries_per_game": _mean(history, "carries"),
        "offensive_snap_share_mean": _mean(history, "offensive_snap_share"),
        "offensive_snap_share_last3_mean": _mean(history[-3:], "offensive_snap_share"),
        **red_zone,
        "routes_run": None,
        "tprr": None,
        "yprr": None,
    }
    not_materialized = {"routes_run", "tprr", "yprr"}
    volume["unavailable_metrics"] = {
        field: "NOT_MATERIALIZED" if field in not_materialized else "NO_COMPLETE_OBSERVATIONS"
        for field, value in volume.items() if value is None
    }
    return volume


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


def _observations(history, field, weekly_field):
    values = []
    for row in history:
        source = field if row[field] is not None else weekly_field
        value = row[source]
        if value is not None and math.isfinite(value):
            values.append({
                "value": value,
                "week": row["week"],
                "game_id": row["game_id"],
                "team": row["team"],
                "kickoff_utc": _iso(row["kickoff_utc"]),
                "available_at_utc": _iso(row["available_at"]),
                "source_field": source,
            })
    return values


def _prop_records(con, game, cutoff, defense_context, roster, histories):
    records, player_records, coverage = [], [], []
    for player in roster:
        player_id = player["player_id"]
        if player_id not in histories:
            histories[player_id] = _player_history(con, player_id, cutoff)
        history = histories[player_id]
        quality = _quality(history)
        opponent = (
            game["home_team"] if player["team"] == game["away_team"]
            else game["away_team"]
        )
        profile = {
            "player_id": player_id,
            "display_name": player["display_name"],
            "team": player["team"],
            "position": player["position"],
            "game_id": game["game_id"],
            "roster_status": player["roster_status"],
            "availability_status": "UNVERIFIED",
            "availability_note": "Weekly roster is not official inactive confirmation.",
            "quality": quality,
        }
        market_coverage = (
            {market: {"n": None, "status": "NOT_MATERIALIZED"} for market in UNMATERIALIZED_QB_MARKETS}
            if player["position"] == "QB" else {}
        )
        volume = None
        for market, (source_field, weekly_field, positions) in MARKETS.items():
            if player["position"] not in positions:
                market_coverage[market] = {"n": None, "status": "NOT_APPLICABLE_POSITION"}
                continue
            values = _observations(history, source_field, weekly_field)
            n = len(values)
            if n < MIN_HISTORY:
                reason = (
                    "NO_CONFIRMED_OFFENSIVE_HISTORY" if not history else
                    "NO_METRIC_OBSERVATIONS" if n == 0 else "INSUFFICIENT_OBSERVATIONS"
                )
                market_coverage[market] = {"n": n, "status": reason}
                continue
            market_coverage[market] = {"n": n, "status": "AVAILABLE"}
            if volume is None:
                volume = _volume(history, _red_zone(con, player_id, history, cutoff))
            observed_ids = {item["game_id"] for item in values}
            market_quality = _quality([row for row in history if row["game_id"] in observed_ids])
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
                if any(item["team"] != player["team"] for item in values):
                    against.append("A amostra inclui outra equipe e não confirma estabilidade de função.")
                if last3 and season_dist and abs(last3["historical_frequency"] - season_dist["historical_frequency"]) >= 0.34:
                    against.append("Recorrência recente difere materialmente da temporada.")
                record = {
                    "id": f"{game['game_id']}:{player['player_id']}:{market}:{line if line is not None else 'yes'}",
                    "game_id": game["game_id"],
                    "player_id": player["player_id"],
                    "player_name": player["display_name"],
                    "team": player["team"],
                    "opponent": opponent,
                    "position": player["position"],
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
                    "volume": volume,
                    "context": {
                        "defense_vs_position": defense_context[opponent].get(player["position"]),
                        "quarterback_status": "UNVERIFIED",
                        "role_stability": "DESCRIPTIVE_ONLY",
                        "game_script": "NOT_MODELED",
                    },
                    "evidence": {
                        "favors": favor,
                        "weakens": against,
                        "summary": "Hipótese exploratória baseada somente na distribuição histórica observada.",
                    },
                    "quality": market_quality,
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
                        _metric_source("player_week", [source_field, *(
                            ("weekly_receiving_tds", "weekly_rushing_tds") if anytime else (weekly_field,)
                        ), "targets", "carries", "offensive_snap_share"]),
                        _metric_source("offensive_opportunities", ["yardline_100", "classification"]),
                    ],
                }
                records.append(record)
        coverage.append({
            "player_id": player_id, "display_name": player["display_name"],
            "team": player["team"], "position": player["position"],
            "game_id": game["game_id"], "offensive_history_games": len(history),
            "markets": market_coverage,
        })
        if volume is not None:
            player_records.append(profile)
    records.sort(
        key=lambda r: (
            -r["quality"]["evidence_completeness_score"],
            r["player_name"] or "",
            r["market"],
            -1 if r["line"] is None else r["line"],
        )
    )
    return records, player_records, coverage


def _game_status(game, cutoff):
    kickoff = game["kickoff_utc"]
    if kickoff is None:
        return "UNKNOWN"
    if kickoff > cutoff:
        return "SCHEDULED_AT_CUTOFF" if game["has_result"] is False else "UNKNOWN"
    if kickoff < cutoff and game["has_result"] and game["home_score"] is not None and game["away_score"] is not None:
        return "RESULT_RECORDED"
    return "STARTED_STATUS_UNKNOWN"


def _game_analysis(con, game, cutoff):
    team_metrics, defense_context = {}, {}
    for team in (game["away_team"], game["home_team"]):
        history = _team_history(con, team, cutoff)
        team_metrics[team] = {
            "season": _team_window(history),
            "last5": _team_window(history[-5:]),
            "last3": _team_window(history[-3:]),
            "source": _metric_source(
                "team_week",
                ["epa_per_play", "success_rate", "offensive_plays", "pass_attempts", "rush_attempts", "dropbacks"],
            ),
        }
        defense_context[team] = _defense_history(con, team, cutoff)
    if not any(windows["season"]["games"] for windows in team_metrics.values()) and not any(defense_context.values()):
        return None, defense_context
    return {
        "game_id": game["game_id"],
        "cutoff_utc": _iso(cutoff),
        "teams": team_metrics,
        "defense_vs_position": defense_context,
        "quarterbacks": {team: "UNVERIFIED" for team in team_metrics},
        "verified_injuries": [],
        "injury_note": "O roster semanal não confirma titulares ou inativos oficiais.",
        "summary": "Comparação descritiva de jogos concluídos e disponíveis até o cutoff. EPA por dropback, EPA por corrida e pace oficial não estão materializados.",
        "decision": "NO_BET",
    }, defense_context


def _game_coverage(con, game, status, cutoff, roster, histories):
    coverage = {
        "matchup_status": "KICKOFF_UNAVAILABLE" if game["kickoff_utc"] is None else "PREGAME_NOT_VERIFIABLE",
        "props_status": "KICKOFF_UNAVAILABLE" if game["kickoff_utc"] is None else "PREGAME_NOT_VERIFIABLE",
        "roster_teams": None,
        "unresolved_roster_rows": None,
        "roster_candidates": None,
        "players_with_props": 0,
        "prop_scenarios": 0,
    }
    if status != "SCHEDULED_AT_CUTOFF":
        return coverage, None, [], [], []

    matchup, defense = _game_analysis(con, game, cutoff)
    coverage["matchup_status"] = "AVAILABLE" if matchup else "NO_COMPLETE_TEAM_HISTORY"
    game_roster = [p for p in roster if p["team"] in (game["away_team"], game["home_team"])]
    offensive = [p for p in game_roster if p["position"] in POSITIONS]
    resolved = [p for p in offensive if p["player_id"] and p["id_rows"] == 1]
    props, players, diagnostics = _prop_records(con, game, cutoff, defense, resolved, histories)
    roster_teams = sorted({player["team"] for player in game_roster})
    if props:
        complete = len(roster_teams) == 2 and len(resolved) == len(offensive) and all(
            item["status"] in {"AVAILABLE", "NOT_APPLICABLE_POSITION"}
            for player in diagnostics for item in player["markets"].values()
        )
        reason = "AVAILABLE" if complete else "PARTIAL"
    elif not game_roster:
        reason = "NO_WEEKLY_ROSTER"
    elif not resolved:
        reason = "NO_RESOLVED_OFFENSIVE_ROSTER"
    else:
        reason = "INSUFFICIENT_PLAYER_COVERAGE"
    coverage.update(
        props_status=reason, roster_teams=roster_teams, roster_candidates=len(resolved),
        unresolved_roster_rows=len(offensive) - len(resolved),
        players_with_props=len(players), prop_scenarios=len(props),
    )
    return coverage, matchup, props, players, diagnostics


def build_export(con, manifest, *, season, week, cutoff, published_at):
    snapshot = manifest["source_snapshot_id"]
    games = _games(con, season, week, cutoff, snapshot)
    if not games:
        raise ValueError("No games are available for season/week at the cutoff")
    _history_games(con, season, cutoff, snapshot)
    roster = _weekly_roster(con, season, week, cutoff, snapshot)
    game_items, analyses, all_props, all_players, player_coverage = [], [], [], [], []
    histories = {}
    for game in games:
        status = _game_status(game, cutoff)
        coverage, matchup, props, players, diagnostics = _game_coverage(
            con, game, status, cutoff, roster, histories
        )
        game_items.append({
            "game_id": game["game_id"],
            "season": game["season"],
            "week": game["week"],
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "kickoff_utc": _iso(game["kickoff_utc"]),
            "available_at_utc": _iso(game["available_at"]),
            "status": status,
            "away_score": game["away_score"] if status == "RESULT_RECORDED" else None,
            "home_score": game["home_score"] if status == "RESULT_RECORDED" else None,
            "status_source": "canonical.games",
            "coverage": coverage,
        })
        if matchup:
            analyses.append(matchup)
        all_props.extend(props)
        all_players.extend(players)
        player_coverage.extend(diagnostics)
    teams = _rows(
        con,
        """
        SELECT season,team,source_snapshot_id FROM teams
        WHERE season=? AND available_at<=? AND source_snapshot_id=? ORDER BY team
        """,
        [season, cutoff, snapshot],
    )
    eligible = [game for game in game_items if game["status"] == "SCHEDULED_AT_CUTOFF"]
    counts = {
        "games": len(game_items),
        "scheduled_games_at_cutoff": len(eligible),
        "scheduled_games_with_analysis": len(analyses),
        "games_with_props": sum(game["coverage"]["prop_scenarios"] > 0 for game in eligible),
        "players": len({p["player_id"] for p in all_players}),
        "players_assessed": len({p["player_id"] for p in player_coverage}),
        "prop_scenarios": len(all_props),
        "verified_quotes": 0,
    }
    complete = bool(eligible) and manifest["status"] == "OK" and all(
        game["coverage"]["matchup_status"] == "AVAILABLE"
        and game["coverage"]["props_status"] == "AVAILABLE" for game in eligible
    )
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "status": "READY_DESCRIPTIVE_ONLY" if complete else "PARTIAL",
        "decision": "NO_BET",
        "financial_approved": False,
        "statistical_model_approved": False,
        "season": season,
        "season_type": "REG",
        "week": week,
        "cutoff_utc": _iso(cutoff),
        "published_at_utc": _iso(published_at),
        "temporal_mode": "FROZEN_SNAPSHOT_AS_OF_CUTOFF",
        "source_snapshot_id": snapshot,
        "source_snapshot_status": manifest["status"],
        "source_available_at_utc": _iso(max(game["available_at"] for game in games)),
        "database_sha256": manifest["database"]["sha256"],
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "code": code_identity(),
        "coverage": {
            "game_status_counts": dict(Counter(game["status"] for game in game_items)),
            "prop_coverage_counts": dict(Counter(game["coverage"]["props_status"] for game in game_items)),
            "minimum_player_observations_per_market": MIN_HISTORY,
        },
        "pending_identity_audit_rows": manifest.get("pending_audit_rows"),
        "counts": counts,
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
        "players": all_players,
        "game_analysis": analyses,
        "player_props_analysis": all_props,
        "player_coverage": player_coverage,
    }


def _load_json(path):
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def _export_name(snapshot_id, season, week, cutoff):
    if not isinstance(snapshot_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", snapshot_id):
        raise ValueError("Invalid canonical source_snapshot_id")
    stamp = cutoff.strftime("%Y%m%dT%H%M%S%fZ")
    return f"{snapshot_id}-v{SCHEMA_VERSION}-{season}-REG-W{week:02d}-{stamp}"


def validate_export(destination):
    """Verify the archived bundle and its descriptive-only temporal contract."""
    destination = Path(destination)
    metadata = _load_json(destination / "metadata.json")
    slate = _load_json(destination / "slate.json")
    cutoff = parse_cutoff(metadata["cutoff_utc"])
    name = _export_name(metadata["source_snapshot_id"], metadata["season"], metadata["week"], cutoff)
    if destination.name != name or slate["snapshot_path"] != f"snapshots/{name}/":
        raise ValueError("Export identity does not match its snapshot path")
    if (
        metadata["schema_version"] != SCHEMA_VERSION
        or metadata["season_type"] != "REG"
        or type(metadata["week"]) is not int or not 1 <= metadata["week"] <= 18
        or metadata["source_snapshot_status"] not in {"OK", "PARTIAL"}
        or any(slate.get(key) != value for key, value in metadata.items())
        or slate["generated_at_utc"] != metadata["published_at_utc"]
        or parse_cutoff(metadata["published_at_utc"]) < cutoff
        or parse_cutoff(metadata["source_available_at_utc"]) > cutoff
        or set(metadata["artifact_sha256"]) != set(ARTIFACTS)
    ):
        raise ValueError("Inconsistent export metadata")

    for filename, (_, slate_key) in ARTIFACTS.items():
        path = destination / filename
        if sha256(path) != metadata["artifact_sha256"][filename]:
            raise ValueError(f"Artifact hash mismatch: {filename}")
        payload = _load_json(path)
        if payload["schema_version"] != SCHEMA_VERSION or not isinstance(payload["items"], list):
            raise ValueError(f"Invalid artifact schema: {filename}")
        if slate_key and slate[slate_key] != payload["items"]:
            raise ValueError(f"Slate differs from artifact: {filename}")

    if (
        slate["decision"] != "NO_BET" or slate["financial_approved"] is not False
        or slate["statistical_model_approved"] is not False or slate["counts"]["verified_quotes"] != 0
    ):
        raise ValueError("Export must remain descriptive and NO_BET")
    games = {game["game_id"]: game for game in slate["games"]}
    scheduled = {game_id for game_id, game in games.items() if game["status"] == "SCHEDULED_AT_CUTOFF"}
    def valid_game(game):
        if (
            parse_cutoff(game["available_at_utc"]) > cutoff
            or game["season"] != slate["season"] or game["week"] != slate["week"]
        ):
            return False
        status = game["status"]
        kickoff = parse_cutoff(game["kickoff_utc"]) if game["kickoff_utc"] else None
        scores = (game["home_score"], game["away_score"])
        if status == "RESULT_RECORDED":
            return kickoff is not None and kickoff < cutoff and all(score is not None for score in scores)
        if any(score is not None for score in scores):
            return False
        if status == "SCHEDULED_AT_CUTOFF":
            return kickoff is not None and kickoff > cutoff
        if status == "STARTED_STATUS_UNKNOWN":
            return kickoff is not None and kickoff <= cutoff
        return status == "UNKNOWN"

    if len(games) != len(slate["games"]) or not all(valid_game(game) for game in games.values()):
        raise ValueError("Invalid game identity, season/week or temporal bounds")
    matchup_ids = {matchup["game_id"] for matchup in slate["matchups"]}

    def binds_to_game(item):
        game_id = item["game_id"]
        return game_id in scheduled and item["team"] in (games[game_id]["away_team"], games[game_id]["home_team"])

    if (
        len(matchup_ids) != len(slate["matchups"]) or not matchup_ids <= scheduled
        or any(matchup["cutoff_utc"] != slate["cutoff_utc"] or matchup["decision"] != "NO_BET"
               for matchup in slate["matchups"])
        or any(not binds_to_game(item) for key in ("players", "player_coverage", "props") for item in slate[key])
    ):
        raise ValueError("Invalid pregame binding")
    if len({prop["id"] for prop in slate["props"]}) != len(slate["props"]):
        raise ValueError("Duplicate prop ids")
    for prop in slate["props"]:
        observations = prop["history"]["observations"]
        if (
            prop["decision"] != "NO_BET" or prop["quote"] is not None or prop["ev"] is not None
            or prop["model"]["validated"] is not False or prop["model"]["probability"] is not None
            or len(observations) < MIN_HISTORY or prop["history"]["season"]["n"] != len(observations)
            or len({row["game_id"] for row in observations}) != len(observations)
            or any(
                row["game_id"] == prop["game_id"]
                or parse_cutoff(row["kickoff_utc"]) >= cutoff
                or parse_cutoff(row["available_at_utc"]) > cutoff
                for row in observations
            )
        ):
            raise ValueError(f"Invalid prop evidence or financial state: {prop['id']}")
    counts = slate["counts"]
    if (
        counts["games"] != len(games) or counts["scheduled_games_at_cutoff"] != len(scheduled)
        or counts["scheduled_games_with_analysis"] != len(matchup_ids)
        or counts["games_with_props"] != len({prop["game_id"] for prop in slate["props"]})
        or counts["players"] != len({player["player_id"] for player in slate["players"]})
        or counts["players_assessed"] != len({player["player_id"] for player in slate["player_coverage"]})
        or counts["prop_scenarios"] != len(slate["props"])
    ):
        raise ValueError("Export counts do not match the bundle")
    return slate


def _safe_output_root(output_root):
    output_root = Path(output_root).resolve()
    repo = Path(__file__).resolve().parents[2]
    protected = [repo / "legacy", *(repo / "data" / name for name in (
        "processed", "reference", "raw", "raw_auto", "canonical", "snapshots"
    ))]
    if any(output_root.is_relative_to(folder) for folder in protected):
        raise ValueError("Output cannot be inside historical or canonical data")
    if any(
        folder.parent.name == "snapshots" and (folder / "metadata.json").is_file()
        for folder in (output_root, *output_root.parents)
    ):
        raise ValueError("Output cannot be inside an archived web snapshot")
    return output_root


def publish_export(destination, output_root):
    output_root = _safe_output_root(output_root)
    destination = Path(destination).resolve()
    if destination.parent != output_root / "snapshots":
        raise ValueError("Export must be an immediate child of the output snapshots directory")
    slate = validate_export(destination)
    # Generation never touches the live pointer. Serialize the short replacement.
    lock = output_root / ".slate-publish.lock"
    with lock.open("x"):
        pass
    temporary = None
    try:
        with NamedTemporaryFile(dir=output_root, prefix=".slate-", delete=False) as handle:
            temporary = Path(handle.name)
        _write_json(temporary, slate)
        temporary.replace(output_root / "slate.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink()
    return slate


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
    output_root = _safe_output_root(output_root)
    if output_root.is_relative_to(canonical_folder):
        raise ValueError("Output cannot be inside the input canonical build")
    if type(season) is not int or type(week) is not int or not 1 <= week <= 18:
        raise ValueError("An integer season and regular-season week (1..18) are required")
    cutoff = _utc(cutoff)
    published_at = _utc(published_at or datetime.now(timezone.utc))
    manifest_path = canonical_folder / "build_manifest.json"
    manifest = _load_json(manifest_path)
    if (
        manifest["status"] not in {"OK", "PARTIAL"}
        or manifest["database"]["path"] != "nfl.duckdb"
        or (canonical_folder / "nfl.duckdb").is_symlink()
    ):
        raise ValueError("Unusable canonical build")
    if published_at < cutoff:
        raise ValueError("published_at cannot precede cutoff")
    name = _export_name(manifest["source_snapshot_id"], season, week, cutoff)
    snapshots = output_root / "snapshots"
    if snapshots.is_symlink() or snapshots.resolve() != snapshots:
        raise ValueError("Snapshot output directory must be local to the output root")
    destination = snapshots / name
    if destination.exists():
        raise FileExistsError(f"Snapshot export already exists: {destination}")
    with open_database(canonical_folder) as con:
        con.execute("SET enable_external_access=false")
        payload = build_export(
            con, manifest, season=season, week=week, cutoff=cutoff, published_at=published_at
        )
    metadata = payload["metadata"]
    metadata["build_manifest_sha256"] = sha256(manifest_path)

    destination.mkdir(parents=True)
    try:
        for filename, (payload_key, _) in ARTIFACTS.items():
            _write_json(destination / filename, {"schema_version": SCHEMA_VERSION, "items": payload[payload_key]})
        metadata["artifact_sha256"] = {name: sha256(destination / name) for name in ARTIFACTS}
        _write_json(destination / "metadata.json", metadata, compact=False)
        slate = {
            **metadata,
            "generated_at_utc": metadata["published_at_utc"],
            "snapshot_path": f"snapshots/{name}/",
            **{slate_key: payload[key] for key, slate_key in ARTIFACTS.values() if slate_key},
        }
        _write_json(destination / "slate.json", slate)
        validate_export(destination)
    except Exception:
        for filename in (*ARTIFACTS, "metadata.json", "slate.json"):
            (destination / filename).unlink(missing_ok=True)
        destination.rmdir()
        raise
    if publish_current:
        publish_export(destination, output_root)
    return destination, slate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--validate-export", type=Path, metavar="FOLDER")
    operation.add_argument("--publish-export", type=Path, metavar="FOLDER")
    parser.add_argument("--database", help="Canonical build folder")
    parser.add_argument("--output", default="web/public/data")
    parser.add_argument("--season", type=int)
    parser.add_argument("--week", type=int)
    parser.add_argument("--cutoff", help="Aware ISO-8601 cutoff")
    parser.add_argument("--published-at", help="Aware ISO-8601 publication time")
    parser.add_argument("--publish-current", action="store_true", help="Generate, validate and replace the local current slate")
    args = parser.parse_args(argv)
    try:
        if args.validate_export or args.publish_export:
            destination = args.validate_export or args.publish_export
            slate = (publish_export(destination, args.output) if args.publish_export else validate_export(destination))
        else:
            if any(value is None for value in (args.database, args.season, args.week, args.cutoff)):
                parser.error("--database, --season, --week and --cutoff are required to generate")
            destination, slate = export_static(
                args.database, args.output, season=args.season, week=args.week,
                cutoff=parse_cutoff(args.cutoff),
                published_at=parse_cutoff(args.published_at) if args.published_at else None,
                publish_current=args.publish_current,
            )
        print(json.dumps({
            "destination": str(destination), "status": slate["status"],
            "counts": slate["counts"], "decision": slate["decision"],
        }, indent=2))
        return 0
    except Exception as exc:
        print(f"Web export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
