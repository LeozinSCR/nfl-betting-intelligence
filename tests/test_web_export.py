import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone

import duckdb

from nfl_betting.odds_sources import PROVIDERS, normalize_fixture
from nfl_betting.web_export import (
    analytical_thresholds,
    distribution,
    export_static,
    parse_cutoff,
)


UTC = timezone.utc


class WebMetricTests(unittest.TestCase):
    def test_distribution_and_windows_are_observed_not_probability(self):
        result = distribution([1, 2, 3, 4], line=2.5)
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["hit_count"], 2)
        self.assertEqual(result["median"], 2.5)
        self.assertEqual(result["frequency_semantics"], "OBSERVED_NOT_PROSPECTIVE_PROBABILITY")
        self.assertAlmostEqual(result["stddev_sample"], 1.2909944487)

    def test_analytical_thresholds_are_finite_scenarios(self):
        self.assertEqual(analytical_thresholds([2, 4, 6, 8], "receptions"), [3.5, 4.5, 5.5])
        self.assertEqual(analytical_thresholds([0, 0, 1], "anytime_td"), [None])
        self.assertEqual(analytical_thresholds([], "rush_yards"), [])

    def test_cutoff_requires_timezone(self):
        with self.assertRaises(ValueError):
            parse_cutoff("2026-11-16T12:00:00")


class OddsInterfaceTests(unittest.TestCase):
    def quote(self):
        return {
            "provider": "fixture-provider",
            "bookmaker": "Fixture Book",
            "source_url": "https://example.invalid/quote/1",
            "selection_id": "s1",
            "game_id": "g1",
            "player_id": "00-0000001",
            "market": "receptions",
            "side": "over",
            "line": 4.5,
            "decimal_odds": 1.9,
            "available": True,
            "observed_at": "2026-11-16T20:00:00+00:00",
            "valid_until": "2026-11-16T20:05:00+00:00",
        }

    def test_provider_registry_enables_no_live_paid_dependency(self):
        self.assertEqual(set(PROVIDERS), {"propline", "parlayapi", "the_odds_api", "fanline_wire", "stake"})
        self.assertTrue(all(not provider.live_enabled for provider in PROVIDERS.values()))

    def test_fixture_normalizer_preserves_bookmaker_and_no_bet(self):
        result = normalize_fixture({"quotes": [self.quote()]}, expected_provider="fixture-provider")
        self.assertEqual(result["quotes"][0]["bookmaker"], "Fixture Book")
        self.assertEqual(result["decision"], "NO_BET")
        self.assertFalse(result["financial_approved"])

    def test_fixture_normalizer_reports_partial_and_invalid_odds(self):
        valid = self.quote()
        invalid = self.quote() | {"selection_id": "s2", "decimal_odds": float("inf")}
        result = normalize_fixture({"quotes": [valid, invalid]})
        self.assertEqual(len(result["quotes"]), 1)
        self.assertEqual(len(result["rejected"]), 1)
        self.assertTrue(result["partial"])


class WebExportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.canonical = self.root / "canonical"
        self.canonical.mkdir()
        self.database = self.canonical / "nfl.duckdb"
        con = duckdb.connect(str(self.database))
        con.execute("CREATE TABLE games(game_id VARCHAR,season INTEGER,season_type VARCHAR,week INTEGER,kickoff_utc TIMESTAMPTZ,home_team VARCHAR,away_team VARCHAR,home_score INTEGER,away_score INTEGER,has_result BOOLEAN,completion_basis VARCHAR,source_snapshot_id VARCHAR,available_at TIMESTAMPTZ)")
        con.execute("CREATE TABLE teams(season INTEGER,team VARCHAR,source_snapshot_id VARCHAR,available_at TIMESTAMPTZ)")
        con.execute("CREATE TABLE team_week(season INTEGER,season_type VARCHAR,week INTEGER,game_id VARCHAR,team VARCHAR,offensive_plays BIGINT,pass_attempts BIGINT,rush_attempts BIGINT,dropbacks BIGINT,epa_per_play DOUBLE,epa_observations BIGINT,success_rate DOUBLE,available_at TIMESTAMPTZ)")
        con.execute("CREATE TABLE defensive_matchups(season INTEGER,season_type VARCHAR,game_id VARCHAR,defense VARCHAR,position VARCHAR,targets BIGINT,receptions DOUBLE,receiving_yards DOUBLE,available_at TIMESTAMPTZ)")
        con.execute("CREATE TABLE player_week(season INTEGER,season_type VARCHAR,week INTEGER,game_id VARCHAR,team VARCHAR,player_id VARCHAR,display_name VARCHAR,roster_position VARCHAR,roster_status VARCHAR,participation VARCHAR,opportunity_basis VARCHAR,receptions DOUBLE,receiving_yards DOUBLE,rushing_yards DOUBLE,offensive_td BIGINT,targets BIGINT,carries BIGINT,offense_snaps DOUBLE,offensive_snap_share DOUBLE,source_snapshot_id VARCHAR,available_at TIMESTAMPTZ)")
        con.execute("CREATE TABLE offensive_opportunities(season INTEGER,season_type VARCHAR,game_id VARCHAR,player_id VARCHAR,classification VARCHAR,yardline_100 DOUBLE,opportunity_type VARCHAR,available_at TIMESTAMPTZ)")
        available = "2026-09-30T00:00:00+00:00"
        games = [
            ("g1", 1, "2026-09-10T00:00:00+00:00"),
            ("g2", 2, "2026-09-17T00:00:00+00:00"),
            ("g3", 3, "2026-09-24T00:00:00+00:00"),
        ]
        for game_id, week, kickoff in games:
            con.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [game_id, 2026, "REG", week, kickoff, "OPP", "LAC", 10, 20, True, "END GAME", "fixture-snapshot", available])
            con.execute("INSERT INTO team_week VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [2026, "REG", week, game_id, "LAC", 60, 32, 24, 36, 0.1 * week, 60, 0.4 + week / 100, available])
            con.execute("INSERT INTO team_week VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [2026, "REG", week, game_id, "BAL", 58, 30, 25, 34, 0.05 * week, 58, 0.39 + week / 100, available])
            con.execute("INSERT INTO defensive_matchups VALUES (?,?,?,?,?,?,?,?,?)", [2026, "REG", game_id, "BAL", "WR", 8 + week, 5 + week, 60 + week, available])
            con.execute("INSERT INTO player_week VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [2026, "REG", week, game_id, "LAC", "00-0000001", "Fixture Receiver", "WR", "ACT", "OPPORTUNITIES_RECORDED", "COMPLETE_PBP_OBSERVATION", 2 + week, 20 + 10 * week, 0, int(week == 3), 4 + week, 0, 45 + week, 0.7 + week / 100, "fixture-snapshot", available])
            con.execute("INSERT INTO offensive_opportunities VALUES (?,?,?,?,?,?,?,?)", [2026, "REG", game_id, "00-0000001", "STANDARD", 10, "TARGET", available])
        con.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ["target", 2026, "REG", 4, "2026-10-02T00:00:00+00:00", "BAL", "LAC", None, None, False, None, "fixture-snapshot", available])
        con.execute("INSERT INTO player_week VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [2026, "REG", 4, "target", "LAC", "00-0000001", "Fixture Receiver", "WR", "ACT", "NO_CONFIRMED_PARTICIPATION", None, None, None, None, None, None, None, None, None, "fixture-snapshot", available])
        con.execute("INSERT INTO teams VALUES (?,?,?,?),(?,?,?,?)", [2026, "BAL", "fixture-snapshot", available, 2026, "LAC", "fixture-snapshot", available])
        con.close()
        digest = hashlib.sha256(self.database.read_bytes()).hexdigest()
        manifest = {
            "status": "PARTIAL",
            "source_snapshot_id": "fixture-snapshot",
            "source_manifest_sha256": "a" * 64,
            "database": {"path": "nfl.duckdb", "sha256": digest},
            "coverage_by_week": [],
            "pending_audit_rows": 1,
        }
        (self.canonical / "build_manifest.json").write_text(json.dumps(manifest))

    def tearDown(self):
        self.tmp.cleanup()

    def test_static_export_has_lineage_windows_and_no_bet(self):
        destination, slate = export_static(
            self.canonical,
            self.root / "web-data",
            season=2026,
            week=4,
            cutoff=datetime(2026, 10, 1, tzinfo=UTC),
            published_at=datetime(2026, 10, 1, 1, tzinfo=UTC),
            publish_current=True,
        )
        self.assertEqual(slate["source_snapshot_id"], "fixture-snapshot")
        self.assertEqual(slate["decision"], "NO_BET")
        self.assertEqual(slate["counts"]["scheduled_games_with_analysis"], 1)
        self.assertGreater(slate["counts"]["prop_scenarios"], 0)
        self.assertTrue((destination / "metadata.json").exists())
        self.assertTrue((self.root / "web-data" / "slate.json").exists())
        for prop in slate["props"]:
            self.assertEqual(prop["decision"], "NO_BET")
            self.assertIsNone(prop["quote"])
            self.assertFalse(prop["model"]["validated"])
            self.assertNotIn("target", [item["game_id"] for item in prop["history"]["observations"]])
            self.assertEqual(prop["quality"]["score_semantics"], "DATA_COMPLETENESS_NOT_EDGE_OR_PROBABILITY")

    def test_export_is_immutable_per_source_snapshot(self):
        kwargs = dict(
            season=2026,
            week=4,
            cutoff=datetime(2026, 10, 1, tzinfo=UTC),
            published_at=datetime(2026, 10, 1, 1, tzinfo=UTC),
        )
        export_static(self.canonical, self.root / "out", **kwargs)
        with self.assertRaises(FileExistsError):
            export_static(self.canonical, self.root / "out", **kwargs)

    def test_cutoff_before_snapshot_yields_no_games(self):
        with self.assertRaises(ValueError):
            export_static(
                self.canonical,
                self.root / "early",
                season=2026,
                week=4,
                cutoff=datetime(2026, 9, 1, tzinfo=UTC),
                published_at=datetime(2026, 9, 1, 1, tzinfo=UTC),
            )


if __name__ == "__main__":
    unittest.main()
