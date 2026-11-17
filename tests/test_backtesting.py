"""Synthetic, offline tests of the V1.6 temporal and approval contracts."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import duckdb

import test_projection as fixtures
from nfl_betting.backtesting import (
    PHASES, RETROSPECTIVE, STRICT, _market_result, _paired_rows, _partition,
    _strict_plan, backtest, markdown,
)
from nfl_betting.projection import Catalog, MODELS
from nfl_betting.provenance import sha256
from nfl_betting.temporal_roster import utc


def _update(path, sql):
    db = path / "nfl.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute(sql)
    manifest_path = path / "build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database"]["sha256"] = sha256(db)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _make_serial(path, *, available, finished_through, perturbed):
    """Six target dates with independent copies of roster, features and results."""
    fixtures._catalog(path)
    db = path / "nfl.duckdb"
    with duckdb.connect(str(db)) as con:
        target = con.execute("SELECT * FROM games WHERE game_id='target'").fetchone()
        roster = con.execute("SELECT * FROM player_crosswalk").fetchone()
        stats = con.execute("SELECT * FROM player_week WHERE game_id='target'").fetchone()
        con.execute("DELETE FROM games WHERE game_id='target'")
        con.execute("DELETE FROM coverage_audit WHERE game_id='target'")
        con.execute("DELETE FROM player_crosswalk")
        con.execute("DELETE FROM player_week WHERE game_id='target'")
        for table in ("games", "coverage_audit", "player_week"):
            con.execute(f"UPDATE {table} SET available_at=?", [available])
        for day in range(1, 7):
            game_id = f"series-{day}"
            week = day + 5
            kickoff = f"2026-10-{day:02d}T20:00:00Z"
            result = day <= finished_through
            score = 10 if result else None
            game_row = [game_id, *target[1:3], week, kickoff, *target[5:7], score, score, result,
                        path.name, available]
            con.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", game_row)
            con.execute("INSERT INTO coverage_audit VALUES (?,2026,'REG',?,?,?,?)",
                        [game_id, week, result, path.name, available])
            con.execute("INSERT INTO player_crosswalk VALUES (?,?,?,?,?,?,?,?,?,?)",
                        [*roster[:2], week, *roster[3:-1], available])
            if result:
                # Change a statistic from the first test date across runs.
                value = perturbed if day == 5 else 4
                player = [*stats[:2], week, game_id, *stats[4:11], value, *stats[12:-1], available]
                con.execute("INSERT INTO player_week VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", player)
    _update(path, "SELECT 1")


class BacktestTemporalTests(unittest.TestCase):
    def test_late_capture_strict_rejection_and_exploratory_proxy(self):
        with TemporaryDirectory() as root:
            archive = Path(root) / "late-labels"
            fixtures._catalog(archive, label=6)
            _update(archive, "UPDATE player_crosswalk SET week=5 WHERE player_id='00-0000001'")
            files = [archive]
            before = sha256(archive / "nfl.duckdb")
            strict = backtest(STRICT, 2026, "2026-10-03T00:00:00Z", files, files, weeks=[6])
            self.assertEqual(strict["exclusion_counts"]["LATE_CAPTURE"], 1)
            self.assertEqual(strict["projections"], [])
            retrospective = backtest(RETROSPECTIVE, 2026, "2026-10-03T00:00:00Z", files, files, weeks=[6])
            self.assertTrue(retrospective["projections"])
            self.assertFalse(retrospective["availability_claim"])
            self.assertTrue(all(row["player_id"] == fixtures.PLAYER for row in retrospective["projections"]))
            for row in retrospective["projections"]:
                self.assertEqual(row["roster_evidence"]["status"], "HISTORICAL_ROSTER_PROXY")
                self.assertTrue(all(obs["game_id"] not in {"target", "same-date-history"} for obs in row["observations"]))
                self.assertTrue(all(obs["available_at_utc"] > row["cutoff_utc"] for obs in row["observations"]))
            self.assertEqual(retrospective["status"], "INSUFFICIENT_EVALUATION_DATA")
            self.assertIn("RETROSPECTIVE_EXPLORATORY", markdown(retrospective))
            self.assertEqual(before, sha256(archive / "nfl.duckdb"))

    def test_holdout_freezes_earlier_test_outcomes_even_when_next_archive_has_them(self):
        with TemporaryDirectory() as root:
            root = Path(root)
            pre, mid_a, mid_b, labels_a, labels_b = [
                root / name for name in ("pre", "mid-a", "mid-b", "labels-a", "labels-b")
            ]
            _make_serial(pre, available="2026-10-01T18:00:00Z", finished_through=0, perturbed=0)
            _make_serial(mid_a, available="2026-10-06T15:00:00Z", finished_through=5, perturbed=777)
            _make_serial(mid_b, available="2026-10-06T15:00:00Z", finished_through=5, perturbed=0)
            _make_serial(labels_a, available="2026-10-07T15:00:00Z", finished_through=6, perturbed=777)
            _make_serial(labels_b, available="2026-10-07T15:00:00Z", finished_through=6, perturbed=0)

            def replay(mid, labels):
                return backtest(STRICT, 2026, "2026-10-08T00:00:00Z", [pre, mid], [labels], weeks=range(6, 12))

            first, second = replay(mid_a, labels_a), replay(mid_b, labels_b)
            self.assertEqual(first["fold_dates"]["test"], ["2026-10-05", "2026-10-06"])
            self.assertEqual(first["test_frozen_at_utc"], "2026-10-05T19:00:00+00:00")
            a, b = [next(row for row in report["projections"] if row["game_id"] == "series-6"
                         and row["market"] == "receptions") for report in (first, second)]
            self.assertEqual(a["models"], b["models"])
            self.assertEqual(a["history_snapshot_id"], "pre")
            self.assertEqual(a["feature_snapshot_id"], "mid-a")
            self.assertEqual(a["observations"], b["observations"])
            self.assertNotIn("series-5", {obs["game_id"] for obs in a["observations"]})
            self.assertEqual(first["markets"]["receptions"]["matched_support"]["test"]["pairs"], 2)
            self.assertIsNone(first["markets"]["receptions"]["metrics"])

    def test_identity_diagnostics_and_missing_snapshot(self):
        with TemporaryDirectory() as root:
            pre, labels = [Path(root) / role for role in ("pre", "labels")]
            fixtures._catalog(pre)
            fixtures._catalog(labels, label=6)
            _update(pre, """
                INSERT INTO player_crosswalk SELECT * REPLACE ('BAL' AS team) FROM player_crosswalk;
                INSERT INTO player_crosswalk SELECT * REPLACE (NULL AS player_id)
                    FROM player_crosswalk WHERE team='BAL';
            """)
            args = (STRICT, 2026, "2026-10-03T00:00:00Z")
            report = backtest(*args, [pre], [labels], weeks=[6])
            self.assertEqual(report["exclusion_counts"]["AMBIGUOUS_GSIS"], 2)
            self.assertEqual(report["exclusion_counts"]["MISSING_GSIS"], 1)
            self.assertEqual(report["projections"], [])
            missing = backtest(*args, [], [labels], weeks=[6])
            self.assertEqual(missing["exclusion_counts"]["SNAPSHOT_UNAVAILABLE"], 1)

    def test_official_schedule_cutoff_and_late_reschedule(self):
        original = utc("2026-11-22T21:25:00Z")
        corrected = utc("2026-11-22T18:00:00Z")
        available = utc("2026-11-22T15:00:00Z")
        audit_time = utc("2026-11-23T01:00:00Z")
        catalog = Catalog(Path("synthetic"), {"database": {"sha256": "synthetic"}}, available, "synthetic")
        game = {"game_id": "2026_11_PIT_PHI", "kickoff_utc": original, "available_at": available,
                "has_result": False, "away_team": "PIT", "home_team": "PHI"}
        revisions = {game["game_id"]: (corrected, {"available_at_utc": "2026-11-22T16:30:00Z"})}
        plan, _ = _strict_plan([(catalog, game)], revisions, timedelta(hours=1), audit_time)
        self.assertEqual(plan[0], utc("2026-11-22T17:00:00Z"))
        revisions[game["game_id"]][1]["available_at_utc"] = "2026-11-22T17:01:00Z"
        self.assertEqual(_strict_plan([(catalog, game)], revisions, timedelta(hours=1), audit_time),
                         (None, "KICKOFF_UNVERIFIED"))


def _pair(date, game, index, actual=1.0):
    kickoff = datetime.fromisoformat(date + "T20:00:00+00:00")
    row = {
        "game_date_et": date, "game_id": game, "cutoff_utc": (kickoff - timedelta(hours=1)).isoformat(),
        "kickoff_utc": kickoff.isoformat(), "player_id": f"00-{index:07d}", "team": "LAC",
        "market": "receptions", "status": "POINT_ESTIMATE",
        "models": {name: {"point": value, "interval": {"status": "INSUFFICIENT_DATA"}}
                   for name, value in zip(MODELS, (3.0, 2.0, 1.5))},
    }
    label = {"value": actual, "kickoff_utc": kickoff.isoformat(),
             "available_at_utc": (kickoff + timedelta(hours=4)).isoformat()}
    return row, label


class BacktestComparisonTests(unittest.TestCase):
    def test_common_cohort_removes_missing_models_but_retains_zero(self):
        day = "2026-10-01"
        zero = _pair(day, "game-a", 1, actual=0)
        bad = _pair(day, "game-a", 2)
        bad[0]["models"]["usage_efficiency"]["point"] = None
        excluded = []
        cases = [zero, bad]
        paired, _ = _paired_rows(
            [row for row, _ in cases],
            {(row["game_id"], row["player_id"], row["team"], row["market"]): label for row, label in cases},
            {day: "test"}, excluded,
        )
        self.assertEqual(paired["receptions"]["test"], [zero])
        self.assertEqual(excluded[0]["reason"], "MISSING_FEATURE")

    def test_final_gates_calibration_and_ci_use_identical_rows(self):
        base = datetime(2026, 9, 1, tzinfo=UTC)

        def pairs(start, dates, people):
            return [_pair((base + timedelta(days=day)).date().isoformat(), f"g{day}", i)
                    for day in range(start, start + dates) for i in range(people)]

        phases = {"train": pairs(0, 1, 1), "validation": pairs(1, 10, 1), "test": pairs(11, 20, 20)}
        predictions = [row for row, _ in phases["test"]]
        orphan, _ = _pair(predictions[-1]["game_date_et"], "no-label", 777)
        report = _market_result("receptions", phases, [*predictions, orphan], STRICT, utc(predictions[0]["cutoff_utc"]))
        self.assertEqual(report["calibration_dates"], 10)
        self.assertEqual(orphan["models"]["recency_mean"]["interval"]["status"], "EMPIRICAL_INTERVAL")
        self.assertEqual(report["status"], "EVALUATED_NOT_APPROVED")
        self.assertEqual({part["n"] for part in report["metrics"].values()}, {400})
        self.assertEqual(report["metrics"]["recency_mean"]["interval_n"], 400)
        self.assertLess(report["baseline_comparison"]["usage_efficiency"]["upper"], 0)
        self.assertFalse(report["statistical_model_approved"])

        concentrated = deepcopy(phases)
        concentrated["test"].extend(deepcopy(concentrated["test"][:20]) * 3)
        blocked = _market_result("receptions", concentrated, [], STRICT, None)
        self.assertEqual(blocked["status"], "INSUFFICIENT_EVALUATION_DATA")
        self.assertIsNone(blocked["metrics"])
        self.assertIn("EXCESSIVE_GAME_CONCENTRATION", blocked["approval_blocks"])

        without_last_validation = deepcopy(phases)
        without_last_validation["validation"][-1][1]["available_at_utc"] = "2026-12-01T00:00:00+00:00"
        clean_predictions = [row for row, _ in pairs(11, 20, 20)]
        late = _market_result("receptions", without_last_validation, clean_predictions,
                              STRICT, utc(clean_predictions[0]["cutoff_utc"]))
        self.assertEqual(late["calibration_dates"], 9)
        self.assertEqual(late["interval_status"], "INSUFFICIENT_DATA")
        self.assertEqual(clean_predictions[0]["models"]["recency_mean"]["interval"]["status"], "INSUFFICIENT_DATA")

    def test_partition_sorts_unique_dates(self):
        dates = ["2026-09-05", "2026-09-02", "2026-09-04", "2026-09-03", "2026-09-02"]
        splits, mapping = _partition(dates)
        self.assertEqual(list(splits), list(PHASES))
        self.assertEqual([len(splits[phase]) for phase in PHASES], [2, 1, 1])
        self.assertEqual(mapping["2026-09-05"], "test")


if __name__ == "__main__":
    unittest.main()
