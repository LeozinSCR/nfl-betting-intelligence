"""Entirely synthetic NFL-like fixture; no real player facts or HTTP requests."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import polars as pl
from nfl_betting.canonical import (
    build,
    open_database,
    rows,
    as_of,
    resolve_player,
    TABLES,
)
from nfl_betting.provenance import sha256


def fixture(root):
    root = Path(root)
    snapshot = root / "raw"
    snapshot.mkdir()
    history = root / "history"
    history.mkdir()
    schemas = {
        "schedules": {
            "game_id": str,
            "season": int,
            "game_type": str,
            "week": int,
            "gameday": str,
            "gametime": str,
            "home_team": str,
            "away_team": str,
            "home_score": float,
            "away_score": float,
        },
        "rosters_weekly": {
            "season": int,
            "game_type": str,
            "week": int,
            "team": str,
            "gsis_id": str,
            "pfr_id": str,
            "sleeper_id": str,
            "full_name": str,
            "position": str,
            "status": str,
        },
        "snap_counts": {
            "game_id": str,
            "season": int,
            "game_type": str,
            "week": int,
            "team": str,
            "pfr_player_id": str,
            "player": str,
            "position": str,
            "offense_snaps": float,
            "defense_snaps": float,
            "st_snaps": float,
            "offense_pct": float,
            "defense_pct": float,
            "st_pct": float,
        },
        "player_stats": {
            "season": int,
            "season_type": str,
            "week": int,
            "game_id": str,
            "team": str,
            "player_id": str,
            "player_display_name": str,
            "position": str,
            "targets": int,
            "carries": int,
            "receptions": int,
            "receiving_yards": float,
            "rushing_yards": float,
            "receiving_tds": int,
            "rushing_tds": int,
        },
        "injuries": {
            "season": int,
            "season_type": str,
            "week": int,
            "team": str,
            "gsis_id": str,
            "full_name": str,
            "position": str,
            "report_status": str,
            "practice_status": str,
            "report_primary_injury": str,
            "report_secondary_injury": str,
            "practice_primary_injury": str,
            "practice_secondary_injury": str,
        },
        "pbp": {
            **{
                k: str
                for k in (
                    "game_id",
                    "season_type",
                    "posteam",
                    "defteam",
                    "receiver_player_id",
                    "receiver_player_name",
                    "rusher_player_id",
                    "rusher_player_name",
                    "passer_player_id",
                    "play_type",
                    "td_player_id",
                    "desc",
                    "lateral_receiver_player_id",
                    "lateral_receiver_player_name",
                    "lateral_rusher_player_id",
                    "lateral_rusher_player_name",
                )
            },
            **{
                k: float
                for k in (
                    "play_id",
                    "pass_attempt",
                    "rush_attempt",
                    "two_point_attempt",
                    "play_deleted",
                    "yardline_100",
                    "complete_pass",
                    "receiving_yards",
                    "rushing_yards",
                    "pass_touchdown",
                    "rush_touchdown",
                    "total_home_score",
                    "total_away_score",
                    "sack",
                    "qb_dropback",
                    "epa",
                    "success",
                    "lateral_receiving_yards",
                    "lateral_rushing_yards",
                )
            },
            "season": int,
            "week": int,
        },
    }
    data = {k: [] for k in schemas}
    data["schedules"] = [
        dict(
            game_id="fixture-1",
            season=2026,
            game_type="REG",
            week=1,
            gameday="2026-09-10",
            gametime="20:00",
            home_team="H",
            away_team="A",
            home_score=7.0,
            away_score=0.0,
        )
    ]
    for i in range(1, 8):
        team = "H" if i < 7 else "A"
        pid = f"00-fixture-{i}"
        data["rosters_weekly"].append(
            dict(
                season=2026,
                game_type="REG",
                week=1,
                team=team,
                gsis_id=pid,
                pfr_id=f"pfr-{i}",
                sleeper_id=str(i),
                full_name=f"Synthetic {i}",
                position="WR",
                status="ACT",
            )
        )
        data["snap_counts"].append(
            dict(
                game_id="fixture-1",
                season=2026,
                game_type="REG",
                week=1,
                team=team,
                pfr_player_id=f"pfr-{i}",
                player=f"Synthetic {i}",
                position="WR",
                offense_snaps=10.0 if i < 4 or i == 5 else 0.0,
                defense_snaps=10.0 if i == 7 else 0.0,
                st_snaps=3.0 if i == 4 else 0.0,
                offense_pct=1.0 if i < 4 or i == 5 else 0.0,
                defense_pct=0.0,
                st_pct=0.5 if i == 4 else 0.0,
            )
        )
    # Player 6 has no confirmed participation, despite being rostered.
    data["snap_counts"] = [
        r for r in data["snap_counts"] if r["pfr_player_id"] != "pfr-6"
    ]
    base = dict(
        game_id="fixture-1",
        season=2026,
        season_type="REG",
        week=1,
        posteam="H",
        defteam="A",
        pass_attempt=0.0,
        rush_attempt=0.0,
        two_point_attempt=0.0,
        play_deleted=0.0,
        yardline_100=15.0,
        complete_pass=0.0,
        pass_touchdown=0.0,
        rush_touchdown=0.0,
        total_home_score=7.0,
        total_away_score=0.0,
        sack=0.0,
        qb_dropback=0.0,
        epa=0.1,
        success=1.0,
    )

    def play(pid, **extra):
        row = dict(base)
        row.update(play_id=float(pid))
        row.update(extra)
        data["pbp"].append(row)

    play(
        1,
        play_type="pass",
        receiver_player_id="00-fixture-1",
        receiver_player_name="Synthetic 1",
        pass_attempt=1.0,
        complete_pass=1.0,
        receiving_yards=5.0,
        desc="Synthetic complete pass",
    )
    play(
        2,
        play_type="run",
        rusher_player_id="00-fixture-3",
        rusher_player_name="Synthetic 3",
        rush_attempt=1.0,
        rushing_yards=3.0,
        desc="Synthetic run",
    )
    play(
        3,
        play_type="pass",
        receiver_player_id="00-fixture-1",
        pass_attempt=1.0,
        two_point_attempt=1.0,
        complete_pass=1.0,
        receiving_yards=2.0,
        desc="Synthetic two point",
    )
    play(
        4,
        play_type="run",
        rusher_player_id="00-fixture-3",
        rush_attempt=1.0,
        two_point_attempt=1.0,
        rushing_yards=2.0,
        desc="Synthetic two point run",
    )
    play(
        5,
        play_type="no_play",
        receiver_player_id="00-fixture-1",
        pass_attempt=1.0,
        desc="Synthetic nullified play",
    )
    play(
        6,
        play_type="qb_kneel",
        rusher_player_id="00-fixture-3",
        rush_attempt=1.0,
        rushing_yards=-1.0,
        desc="Synthetic kneel",
    )
    play(
        7,
        play_type="pass",
        receiver_player_id="00-fixture-1",
        pass_attempt=1.0,
        complete_pass=1.0,
        receiving_yards=2.0,
        lateral_receiver_player_id="00-fixture-2",
        lateral_receiver_player_name="Synthetic 2",
        lateral_receiving_yards=40.0,
        pass_touchdown=1.0,
        td_player_id="00-fixture-2",
        desc="Synthetic lateral TD",
    )
    play(8, desc="END GAME")
    for i in (1, 2, 3, 7):
        data["player_stats"].append(
            dict(
                season=2026,
                season_type="REG",
                week=1,
                game_id="fixture-1",
                team="H" if i < 7 else "A",
                player_id=f"00-fixture-{i}",
                player_display_name=f"Synthetic {i}",
                position="WR",
                targets=2 if i == 1 else 0,
                carries=2 if i == 3 else 0,
                receptions=2 if i == 1 else 0,
                receiving_yards=7.0 if i == 1 else 40.0 if i == 2 else 0.0,
                rushing_yards=2.0 if i == 3 else 0.0,
                receiving_tds=1 if i == 2 else 0,
                rushing_tds=0,
            )
        )
    data["injuries"] = [
        dict(
            season=2026,
            season_type="REG",
            week=1,
            team="H",
            gsis_id="00-fixture-6",
            full_name="Synthetic 6",
            position="WR",
            report_status="OUT",
            practice_status="DNP",
            report_primary_injury="Synthetic injury",
        )
    ]
    types = {str: pl.String, int: pl.Int64, float: pl.Float64}
    for name, schema in schemas.items():
        pl.DataFrame(
            [{k: r.get(k) for k in schema} for r in data[name]],
            schema={k: types[v] for k, v in schema.items()},
        ).write_parquet(snapshot / (name + ".parquet"))
    weekly = pl.DataFrame(
        {
            "week": [1],
            "game_id": ["fixture-1"],
            "team": ["H"],
            "player_id": ["00-fixture-1"],
            "corrected_targets": [2],
            "corrected_carries": [0],
        }
    )
    weekly.write_csv(history / "weekly_reconciliation_2026.csv")
    weekly.with_columns(pl.lit("OFFENSE_TOUCH_CONFIRMED").alias("evidence")).write_csv(
        history / "weekly_participation_2026.csv"
    )
    opp = pl.DataFrame(
        {
            "week": [1],
            "game_id": ["fixture-1"],
            "team": ["H"],
            "player_id": ["00-fixture-1"],
            "player_name": [""],
            "position": ["UNKNOWN"],
            "type": ["TARGET"],
            "opportunities": [2],
            "with_yardline": [2],
            "inside20": [2],
            "inside10": [0],
            "inside5": [0],
            "catches": [2],
            "receiving_yards": [7.0],
            "rushing_yards": [0.0],
            "offensive_td": [0],
        }
    )
    opp.write_csv(history / "opportunities_corrected_2026.csv")
    manifest = {
        "schema_version": 2,
        "run_id": "SYNTHETIC_TEST",
        "season": 2026,
        "status": "OK",
        "finished_at_utc": "2026-11-16T10:00:00+00:00",
        "sources": {},
    }

    def refresh():
        for name in schemas:
            path = snapshot / (name + ".parquet")
            manifest["sources"][name] = {
                "status": "OK",
                "path": path.name,
                "sha256": sha256(path),
                "finished_at_utc": manifest["finished_at_utc"],
            }
        (snapshot / "manifest.json").write_text(json.dumps(manifest))

    refresh()
    return snapshot, history, manifest, refresh


class CanonicalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.snapshot, self.history, self.manifest, self.refresh = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def run_build(self):
        folder, summary = build(self.snapshot, self.root / "out", self.history)
        self.assertNotEqual(summary["status"], "ERROR", summary["errors"])
        return folder, summary

    def change(self, source, fn):
        p = self.snapshot / (source + ".parquet")
        fn(pl.read_parquet(p)).write_parquet(p)
        self.refresh()

    def test_tables_keys_and_roundtrip_parquet(self):
        folder, summary = self.run_build()
        self.assertEqual(set(summary["tables"]), set(TABLES))
        with open_database(folder) as c:
            for name, item in summary["tables"].items():
                self.assertEqual(
                    pl.read_parquet(folder / item["path"]).height,
                    c.execute(f"SELECT count(*) FROM {name}").fetchone()[0],
                )
        self.assertFalse(summary["financial_approved"])
        self.assertEqual(summary["status"], "OK")

    def test_targets_carries_two_point_no_play_kneel_lateral(self):
        folder, _ = self.run_build()
        with open_database(folder) as c:
            self.assertEqual(
                c.execute(
                    "SELECT sum(targets),sum(carries) FROM player_week"
                ).fetchone(),
                (2, 2),
            )
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM offensive_opportunities WHERE classification='TWO_POINT_CONVERSION'"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM offensive_opportunities WHERE classification='NULLIFIED_OR_DELETED'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                c.execute(
                    "SELECT targets,receiving_yards,offensive_td FROM player_week WHERE player_id='00-fixture-2'"
                ).fetchone(),
                (0, 40.0, 1),
            )
            self.assertEqual(
                c.execute(
                    "SELECT offensive_td FROM player_week WHERE player_id='00-fixture-1'"
                ).fetchone()[0],
                0,
            )

    def test_participation_special_teams_zero_and_unknown(self):
        folder, _ = self.run_build()
        with open_database(folder) as c:
            states = dict(
                c.execute("SELECT player_id,participation FROM player_week").fetchall()
            )
            self.assertEqual(states["00-fixture-4"], "SPECIAL_TEAMS_ONLY")
            self.assertEqual(
                states["00-fixture-5"], "OFFENSIVE_SNAPS_ZERO_OPPORTUNITIES"
            )
            self.assertEqual(states["00-fixture-6"], "NO_CONFIRMED_PARTICIPATION")
            self.assertEqual(states["00-fixture-1"], "OPPORTUNITIES_RECORDED")

    def test_temporal_crosswalk_and_no_leakage(self):
        folder, _ = self.run_build()
        before = datetime(2026, 10, 1, tzinfo=timezone.utc)
        after = datetime.now(timezone.utc)
        self.assertEqual(as_of(folder, "player_week", before).num_rows, 0)
        self.assertEqual(
            resolve_player(
                folder, season=2026, week=1, team="H", pfr_id="pfr-1", cutoff=before
            ),
            [],
        )
        self.assertEqual(
            len(
                resolve_player(
                    folder, season=2026, week=1, team="H", pfr_id="pfr-1", cutoff=after
                )
            ),
            1,
        )
        self.assertEqual(
            resolve_player(
                folder, season=2026, week=2, team="H", pfr_id="pfr-1", cutoff=after
            ),
            [],
        )
        self.assertEqual(
            resolve_player(
                folder,
                season=2026,
                week=1,
                team="H",
                season_type="POST",
                pfr_id="pfr-1",
                cutoff=after,
            ),
            [],
        )
        self.assertEqual(
            resolve_player(
                folder, season=2026, week=1, team="A", pfr_id="pfr-1", cutoff=after
            ),
            [],
        )
        with self.assertRaises(ValueError):
            as_of(folder, "player_week", before.replace(tzinfo=None))

    def test_duplicate_input_and_ambiguous_identity_fail(self):
        self.change("pbp", lambda d: pl.concat([d, d.head(1)]))
        _, s = build(self.snapshot, self.root / "bad", self.history)
        self.assertEqual(s["status"], "ERROR")
        self.assertTrue(s["input_constraints"])
        self.change("pbp", lambda d: d.unique(subset=["game_id", "play_id"]))
        self.change(
            "rosters_weekly",
            lambda d: pl.concat(
                [d, d.head(1).with_columns(pl.lit("different-gsis").alias("gsis_id"))]
            ),
        )
        _, s = build(self.snapshot, self.root / "bad2", self.history)
        self.assertEqual(s["status"], "ERROR")
        self.assertTrue(
            any(r["constraint"] == "AMBIGUOUS_PFR_ID" for r in s["input_constraints"])
        )

    def test_hash_tampering_blocked(self):
        p = self.snapshot / "pbp.parquet"
        p.write_bytes(b"corrupted")
        _, s = build(self.snapshot, self.root / "bad", self.history)
        self.assertEqual(s["status"], "ERROR")
        self.assertIn("hash", s["errors"][0]["message"])

    def test_optional_failure_partial_but_essential_failure_error(self):
        for source in ("injuries", "pbp"):
            self.manifest["sources"][source]["status"] = "ERROR"
            (self.snapshot / "manifest.json").write_text(json.dumps(self.manifest))
            _, s = build(self.snapshot, self.root / source, self.history)
            self.assertEqual(
                s["status"], "PARTIAL" if source == "injuries" else "ERROR"
            )
            if source == "injuries":
                self.assertEqual(s["tables"]["injuries"]["rows"], 0)

    def test_completed_game_missing_snaps_is_explicit_gap(self):
        self.change("snap_counts", lambda d: d.filter(pl.col("team") == "H"))
        folder, s = self.run_build()
        self.assertEqual(s["status"], "PARTIAL")
        with open_database(folder) as c:
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM reconciliation_audit WHERE category='COMPLETED_GAME_COVERAGE_GAP'"
                ).fetchone()[0],
                1,
            )

    def test_calendar_mismatch_and_future_outcomes_fail(self):
        self.change(
            "pbp", lambda d: d.with_columns(pl.lit("not-scheduled").alias("game_id"))
        )
        _, s = build(self.snapshot, self.root / "bad", self.history)
        self.assertEqual(s["status"], "ERROR")
        self.change(
            "pbp", lambda d: d.with_columns(pl.lit("fixture-1").alias("game_id"))
        )
        self.change(
            "schedules", lambda d: d.with_columns(pl.lit("2027-01-01").alias("gameday"))
        )
        _, s = build(self.snapshot, self.root / "future", self.history)
        self.assertEqual(s["status"], "ERROR")
        self.assertIn("future outcomes", s["errors"][0]["message"])

    def test_missing_mapping_preserved_not_matched_by_name(self):
        self.change(
            "rosters_weekly",
            lambda d: d.with_columns(
                pl.when(pl.col("gsis_id") == "00-fixture-4")
                .then(pl.lit(None))
                .otherwise(pl.col("pfr_id"))
                .alias("pfr_id")
            ),
        )
        folder, s = self.run_build()
        self.assertEqual(s["status"], "PARTIAL")
        with open_database(folder) as c:
            self.assertEqual(
                c.execute(
                    "SELECT player_id FROM snap_counts WHERE pfr_id='pfr-4'"
                ).fetchone()[0],
                None,
            )
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM player_week WHERE player_key='PFR:pfr-4'"
                ).fetchone()[0],
                1,
            )

    def test_history_and_source_files_never_mutated(self):
        paths = list(self.snapshot.glob("*")) + list(self.history.glob("*"))
        before = {str(p): sha256(p) for p in paths}
        self.run_build()
        self.run_build()
        self.assertEqual(before, {str(p): sha256(p) for p in paths})

    def test_pbp_end_marker_required_for_known_zero(self):
        self.change(
            "pbp",
            lambda d: d.with_columns(
                pl.when(pl.col("desc") == "END GAME")
                .then(pl.lit("not ended"))
                .otherwise(pl.col("desc"))
                .alias("desc")
            ),
        )
        folder, s = self.run_build()
        self.assertEqual(s["status"], "PARTIAL")
        with open_database(folder) as c:
            self.assertIsNone(
                c.execute(
                    "SELECT targets FROM player_week WHERE player_id='00-fixture-5'"
                ).fetchone()[0]
            )
            self.assertEqual(
                c.execute(
                    "SELECT participation FROM player_week WHERE player_id='00-fixture-5'"
                ).fetchone()[0],
                "OFFENSIVE_SNAPS_OPPORTUNITIES_UNKNOWN",
            )

    def test_team_alias_resolves_without_name_matching(self):
        for source in (
            "schedules",
            "player_stats",
            "rosters_weekly",
            "snap_counts",
            "pbp",
            "injuries",
        ):
            self.change(
                source,
                lambda d: d.with_columns(
                    [
                        pl.col(k).replace({"H": "LA"})
                        for k in ("home_team", "team", "posteam", "defteam")
                        if k in d.columns
                    ]
                ),
            )
        for path in self.history.glob("*.csv"):
            pl.read_csv(path).with_columns(
                pl.col("team").replace({"H": "LAR"})
            ).write_csv(path)
        folder, _ = self.run_build()
        with open_database(folder) as c:
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM reconciliation_audit WHERE category='HISTORICAL_TEAM_ALIAS_RESOLVED'"
                ).fetchone()[0],
                1,
            )

    def test_invalid_snap_share_and_negative_counts_fail(self):
        self.change(
            "snap_counts", lambda d: d.with_columns(pl.lit(-1.0).alias("offense_snaps"))
        )
        _, s = build(self.snapshot, self.root / "bad", self.history)
        self.assertEqual(s["status"], "ERROR")

    def test_unresolved_ids_never_become_zero_opportunities(self):
        self.change('rosters_weekly',lambda d:d.with_columns(pl.when(pl.col('gsis_id')=='00-fixture-5').then(pl.lit(None)).otherwise(pl.col('pfr_id')).alias('pfr_id')))
        self.change('player_stats',lambda d:d.with_columns(pl.when(pl.col('player_id')=='00-fixture-3').then(pl.lit(None)).otherwise(pl.col('player_id')).alias('player_id')))
        folder,_=self.run_build()
        with open_database(folder) as c:
            self.assertEqual(c.execute("SELECT targets,carries,participation FROM player_week WHERE player_key='PFR:pfr-5'").fetchone(),(None,None,'OFFENSIVE_SNAPS_OPPORTUNITIES_UNKNOWN'))
            self.assertEqual(c.execute("SELECT targets,carries FROM player_week WHERE player_key LIKE 'STATS:%'").fetchone(),(None,None))
            self.assertEqual(c.execute("SELECT count(*) FROM reconciliation_audit WHERE category='STATS_GSIS_MISSING'").fetchone()[0],1)

    def test_identity_325_like_row_resolved_only_by_same_week(self):
        folder, _ = self.run_build()
        with open_database(folder) as c:
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM reconciliation_audit WHERE category='HISTORICAL_IDENTITY_RESOLVED'"
                ).fetchone()[0],
                1,
            )
        self.change("rosters_weekly", lambda d: d.with_columns(pl.lit(2).alias("week")))
        folder, _ = self.run_build()
        with open_database(folder) as c:
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM reconciliation_audit WHERE category='HISTORICAL_IDENTITY_PENDING'"
                ).fetchone()[0],
                1,
            )


if __name__ == "__main__":
    unittest.main()
