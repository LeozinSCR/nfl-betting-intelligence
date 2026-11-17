"""Offline unit and temporal contract tests using synthetic fixtures only."""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import duckdb

from nfl_betting.projection import MODELS, forecast_market, run, walk_forward
from nfl_betting.provenance import sha256
from nfl_betting.temporal_roster import utc

PLAYER = "00-0000001"
CUTOFF = "2026-10-01T19:00:00Z"


def _history(values):
    return [{
        "game_id": f"history-{index}", "kickoff_utc": f"2026-09-{index:02d}T17:00:00+00:00",
        "available_at_utc": "2026-10-01T18:00:00+00:00", "receptions": value,
        "targets": 10, "offense_snaps": 40 + index, "rushing_yards": -index,
    } for index, value in enumerate(values, 1)]


class ProjectionUnitTests(unittest.TestCase):
    def test_disjoint_weights_and_usage_formula(self):
        result = forecast_market("receptions", _history(range(1, 9)))
        self.assertEqual(result["windows"], {"season": 8, "last5": 5, "last3": 3})
        self.assertEqual(result["models"]["season_mean"]["point"], 4.5)
        expected = sum(i * w for i, w in zip(range(1, 9), [1, 1, 1, 1.5, 1.5, 2, 2, 2])) / 12
        self.assertAlmostEqual(result["models"]["recency_mean"]["point"], expected)
        usage = result["models"]["usage_efficiency"]
        self.assertEqual(usage["usage_games"], 8)
        self.assertAlmostEqual(
            usage["point"],
            usage["expected_offense_snaps"] * usage["opportunities_per_snap"] * usage["value_per_opportunity"],
        )

    def test_missing_snap_does_not_become_zero_and_signed_yards_remain(self):
        history = _history([0, None, 3, 4, 5, 6])
        for row in history:
            row["offense_snaps"] = None
        result = forecast_market("receptions", history)
        self.assertEqual(result["windows"]["season"], 5)
        self.assertEqual(result["observations"][0]["value"], 0)
        self.assertIsNone(result["observations"][0]["offense_snaps"])
        self.assertEqual(result["models"]["usage_efficiency"]["status"], "INSUFFICIENT_DATA")
        self.assertEqual(result["models"]["season_mean"]["point"], 3.6)
        self.assertLess(forecast_market("rush_yards", history)["models"]["season_mean"]["point"], 0)
        self.assertEqual(
            forecast_market("pass_yards", history)["models"]["recency_mean"]["reason"],
            "INDIVIDUAL_METRIC_NOT_MATERIALIZED",
        )
        self.assertEqual(forecast_market("receptions", history[:3])["status"], "INSUFFICIENT_DATA")

    def test_intervals_calibrate_on_earlier_available_dates_only(self):
        rows = []
        labels = {}
        base = datetime(2026, 9, 1, 18, tzinfo=UTC)
        for day in range(13):
            kickoff = base + timedelta(days=day)
            dates = kickoff.date().isoformat()
            cutoff = kickoff - timedelta(hours=1)
            forecast = {
                "game_id": f"game-{day}", "game_date_et": dates, "kickoff_utc": kickoff.isoformat(),
                "cutoff_utc": cutoff.isoformat(), "team": "LAC", "player_id": PLAYER,
                "market": "receptions", "models": forecast_market("receptions", _history([1]*5))["models"],
            }
            rows.append(forecast)
            if day == 12:
                # A second game on the same date may be scored, but it cannot
                # be used to calibrate another prediction on this date.
                rows.append({**forecast, "game_id": "same-date", "models": forecast_market(
                    "receptions", _history([1]*5)
                )["models"]})
            observed = kickoff + timedelta(hours=4)
            if day == 1:
                observed += timedelta(days=20)
            labels[(forecast["game_id"], PLAYER, "LAC", "receptions")] = {
                "value": 100 if day == 1 else 2, "available_at_utc": observed.isoformat(),
                "kickoff_utc": kickoff.isoformat(),
            }
        summary, rated = walk_forward(list(reversed(rows)), labels)
        result = [row["models"]["recency_mean"]["interval"] for row in rows]
        self.assertEqual(result[10]["calibration_dates"], 9)
        self.assertEqual(result[10]["status"], "INSUFFICIENT_DATA")
        self.assertEqual(result[11]["calibration_dates"], 10)
        self.assertEqual(result[11]["upper"], 2)
        self.assertEqual(result[11]["lower"], 0)
        self.assertEqual(result[12], result[13])
        self.assertEqual(summary["receptions"]["models"]["recency_mean"]["n"], 13)
        self.assertEqual(summary["receptions"]["models"]["recency_mean"]["interval_n"], 2)
        self.assertEqual(summary["receptions"]["models"]["recency_mean"]["interval_coverage"], 1.0)
        self.assertEqual(len(rated), 13)


def _catalog(path, *, label=None):
    """Small catalog with separately versioned, synthetic pregame and outcome data."""
    path.mkdir()
    db = path / "nfl.duckdb"
    snapshot = path.name
    available = "2026-10-01T18:00:00Z" if label is None else "2026-10-02T00:00:00Z"
    games = [(f"h{i}", i, f"2026-09-{5 * i:02d}T17:00:00Z", 1 + i)
             for i in range(1, 6)]
    games += [
        ("same-date-history", 5, "2026-10-01T11:00:00Z", 600),
        ("late-history", 5, "2026-09-27T17:00:00Z", 700),
        ("target", 6, "2026-10-01T20:00:00Z", label if label is not None else 800),
    ]
    with duckdb.connect(str(db)) as con:
        con.execute("""
            CREATE TABLE games (game_id VARCHAR, season INTEGER, season_type VARCHAR, week INTEGER,
                kickoff_utc TIMESTAMPTZ, away_team VARCHAR, home_team VARCHAR, away_score INTEGER,
                home_score INTEGER, has_result BOOLEAN, source_snapshot_id VARCHAR, available_at TIMESTAMPTZ);
            CREATE TABLE coverage_audit (game_id VARCHAR, season INTEGER, season_type VARCHAR,
                week INTEGER, has_end_marker BOOLEAN, source_snapshot_id VARCHAR, available_at TIMESTAMPTZ);
            CREATE TABLE player_crosswalk (season INTEGER, season_type VARCHAR, week INTEGER,
                team VARCHAR, player_id VARCHAR, display_name VARCHAR, position VARCHAR, roster_status VARCHAR,
                source_snapshot_id VARCHAR, available_at TIMESTAMPTZ);
            CREATE TABLE player_week (season INTEGER, season_type VARCHAR, week INTEGER, game_id VARCHAR,
                team VARCHAR, player_id VARCHAR, participation VARCHAR, opportunity_basis VARCHAR, targets INTEGER,
                carries INTEGER, offense_snaps INTEGER, receptions INTEGER, receiving_yards INTEGER,
                rushing_yards INTEGER, offensive_td INTEGER, weekly_receptions INTEGER, weekly_receiving_yards INTEGER,
                weekly_rushing_yards INTEGER, weekly_receiving_tds INTEGER, weekly_rushing_tds INTEGER,
                source_snapshot_id VARCHAR, available_at TIMESTAMPTZ);
        """)
        con.execute("INSERT INTO player_crosswalk VALUES (2026,'REG',6,'LAC',?,'Synthetic Receiver','WR','ACT',?,?)",
                    [PLAYER, snapshot, available])
        if label is not None:
            con.execute("INSERT INTO player_crosswalk VALUES (2026,'REG',6,'LAC','00-0000002','Future roster','WR','ACT',?,?)",
                        [snapshot, available])
        for game_id, week, kickoff, value in games:
            final = game_id != "target" or label is not None
            con.execute("INSERT INTO games VALUES (?,2026,'REG',?,?,'LAC','BAL',?,?,?,?,?)",
                        [game_id, week, kickoff, 20 if final else None, 10 if final else None, final,
                         snapshot, available])
            con.execute("INSERT INTO coverage_audit VALUES (?,2026,'REG',?,?,?,?)",
                        [game_id, week, final, snapshot, available])
            published = "2026-10-01T19:00:01Z" if game_id == "late-history" and label is None else available
            con.execute("""
                INSERT INTO player_week VALUES (2026,'REG',?,?,'LAC',?,'OPPORTUNITIES_RECORDED',
                    'COMPLETE_PBP_OBSERVATION',10,6,45,?,40,20,1,NULL,NULL,NULL,NULL,NULL,?,?)
                """, [week, game_id, PLAYER, value, snapshot, published])
    (path / "build_manifest.json").write_text(json.dumps({
        "status": "PARTIAL", "source_snapshot_id": snapshot,
        "database": {"path": db.name, "sha256": sha256(db)},
    }), encoding="utf-8")


class ProjectionTemporalTests(unittest.TestCase):
    def test_latest_known_source_exact_identity_and_outcome_only_evaluation(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pregame, labels_a, labels_b = (root / name for name in ("pregame", "labels-a", "labels-b"))
            _catalog(pregame)
            _catalog(labels_a, label=8)
            _catalog(labels_b, label=2)
            feature_hash = sha256(pregame / "nfl.duckdb")
            inputs = [(6, CUTOFF)]
            first = run(2026, inputs, [pregame, labels_a], [labels_a])
            second = run(2026, inputs, [labels_b, pregame], [labels_b])
            self.assertEqual(first["projections"], second["projections"])
            self.assertEqual(first["counts"]["scored_player_game_markets"], 5)
            self.assertEqual(first["counts"]["evaluated_predictions"], 5 * len(MODELS))
            self.assertEqual(first["folds"][0]["feature_catalog"]["snapshot_id"], "pregame")
            self.assertEqual(first["decision"], "NO_BET")
            self.assertFalse(first["statistical_model_approved"])
            result = next(row for row in first["projections"] if row["market"] == "receptions")
            self.assertEqual([item["game_id"] for item in result["observations"]], ["h1", "h2", "h3", "h4", "h5"])
            self.assertEqual({row["player_id"] for row in first["projections"]}, {PLAYER})
            self.assertLess(utc(result["cutoff_utc"]), utc(result["kickoff_utc"]))
            self.assertEqual(result["availability_status"], "UNVERIFIED")
            self.assertEqual(first["metrics_by_market"]["receptions"]["models"]["season_mean"]["bias_forecast_minus_actual"], -4)
            self.assertEqual(second["metrics_by_market"]["receptions"]["models"]["season_mean"]["bias_forecast_minus_actual"], 2)
            self.assertEqual(feature_hash, sha256(pregame / "nfl.duckdb"))

    def test_no_reconstruction_from_late_snapshot_and_no_duplicate_target(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary)
            late, pre = path / "late", path / "pre"
            _catalog(late, label=3)
            _catalog(pre)
            blocked = run(2026, [(6, CUTOFF)], [late], [late])
            self.assertEqual(blocked["folds"][0]["status"], "NO_PREGAME_SNAPSHOT")
            self.assertEqual(blocked["counts"]["evaluated_predictions"], 0)
            with self.assertRaisesRegex(ValueError, "multiple folds"):
                run(2026, [(6, CUTOFF), (6, "2026-10-01T19:59:00Z")], [pre])


if __name__ == "__main__":
    unittest.main()
