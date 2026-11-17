import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import duckdb
import polars as pl

from nfl_betting.odds_sources import PROVIDERS, normalize_fixture
from nfl_betting.temporal_roster import KICKOFF_URL, ROSTER_URL, capture, load_evidence, select_roster
from nfl_betting.web_export import (
    analytical_thresholds,
    distribution,
    export_static,
    parse_cutoff,
    publish_export,
    validate_export,
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
        for table in ("team_week", "defensive_matchups", "offensive_opportunities"):
            con.execute(f"ALTER TABLE {table} ADD COLUMN source_snapshot_id VARCHAR DEFAULT 'fixture-snapshot'")
        for table in ("defensive_matchups", "offensive_opportunities"):
            con.execute(f"ALTER TABLE {table} ADD COLUMN week INTEGER")
        con.execute("ALTER TABLE offensive_opportunities ADD COLUMN team VARCHAR DEFAULT 'LAC'")
        for column in ("weekly_receptions", "weekly_receiving_yards", "weekly_rushing_yards",
                       "weekly_receiving_tds", "weekly_rushing_tds"):
            con.execute(f"ALTER TABLE player_week ADD COLUMN {column} DOUBLE")
        con.execute("CREATE TABLE coverage_audit(game_id VARCHAR,season INTEGER,season_type VARCHAR,week INTEGER,source_snapshot_id VARCHAR,available_at TIMESTAMPTZ,has_end_marker BOOLEAN)")
        con.execute("CREATE TABLE player_crosswalk(season INTEGER,season_type VARCHAR,week INTEGER,team VARCHAR,player_id VARCHAR,display_name VARCHAR,position VARCHAR,roster_status VARCHAR,source_snapshot_id VARCHAR,available_at TIMESTAMPTZ)")
        available = "2026-09-30T00:00:00+00:00"
        games = [
            ("g1", 1, "2026-09-10T00:00:00+00:00"),
            ("g2", 2, "2026-09-17T00:00:00+00:00"),
            ("g3", 3, "2026-09-24T00:00:00+00:00"),
        ]
        for game_id, week, kickoff in games:
            con.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [game_id, 2026, "REG", week, kickoff, "OPP", "LAC", 10, 20, True, "END GAME", "fixture-snapshot", available])
            con.execute("INSERT INTO team_week VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,DEFAULT)", [2026, "REG", week, game_id, "LAC", 60, 32, 24, 36, 0.1 * week, 60, 0.4 + week / 100, available])
            con.execute("INSERT INTO team_week VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,DEFAULT)", [2026, "REG", week, game_id, "OPP", 58, 30, 25, 34, 0.05 * week, 58, 0.39 + week / 100, available])
            con.execute("INSERT INTO defensive_matchups VALUES (?,?,?,?,?,?,?,?,?,DEFAULT,?)", [2026, "REG", game_id, "OPP", "WR", 8 + week, 5 + week, 60 + week, available, week])
            con.execute("INSERT INTO player_week VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL)", [2026, "REG", week, game_id, "LAC", "00-0000001", "Fixture Receiver", "WR", "ACT", "OPPORTUNITIES_RECORDED", "COMPLETE_PBP_OBSERVATION", 2 + week, 20 + 10 * week, 0, int(week == 3), 4 + week, 0, 45 + week, 0.7 + week / 100, "fixture-snapshot", available])
            con.execute("INSERT INTO offensive_opportunities VALUES (?,?,?,?,?,?,?,?,DEFAULT,?,DEFAULT)", [2026, "REG", game_id, "00-0000001", "STANDARD", 10, "TARGET", available, week])
            con.execute("INSERT INTO coverage_audit VALUES (?,?,?,?,?,?,true)", [game_id, 2026, "REG", week, "fixture-snapshot", available])
        con.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ["target", 2026, "REG", 4, "2026-10-02T00:00:00+00:00", "BAL", "LAC", None, None, False, None, "fixture-snapshot", available])
        con.execute("INSERT INTO player_crosswalk VALUES (2026,'REG',4,'LAC','00-0000001','Fixture Receiver','WR','ACT','fixture-snapshot',?)", [available])
        con.execute("INSERT INTO teams VALUES (?,?,?,?),(?,?,?,?)", [2026, "BAL", "fixture-snapshot", available, 2026, "LAC", "fixture-snapshot", available])
        con.close()
        self.manifest = {
            "status": "PARTIAL",
            "source_snapshot_id": "fixture-snapshot",
            "source_manifest_sha256": "a" * 64,
            "database": {"path": "nfl.duckdb"},
            "coverage_by_week": [],
            "pending_audit_rows": 1,
        }
        self.refresh_manifest()

    def refresh_manifest(self):
        self.manifest["database"]["sha256"] = hashlib.sha256(self.database.read_bytes()).hexdigest()
        (self.canonical / "build_manifest.json").write_text(json.dumps(self.manifest))

    def export(self, *, output="out", week=4, cutoff="2026-10-01T00:00:00Z", **kwargs):
        timestamp = parse_cutoff(cutoff)
        return export_static(
            self.canonical, self.root / output, season=2026, week=week,
            cutoff=timestamp, published_at=timestamp + timedelta(seconds=1), **kwargs,
        )

    def evidence(self, kind, body, *, at="2026-10-01T00:00:00Z", reviewed=None):
        """Seal synthetic source bytes for offline contract tests only."""
        stamp = parse_cutoff(at).strftime("%Y%m%dT%H%M%S%fZ")
        folder = self.root / f"{kind}-{stamp}-{uuid4().hex}"
        folder.mkdir()
        url = {
            "roster": ROSTER_URL.format(season=2026), "kickoff": KICKOFF_URL,
            "transactions": "https://www.nfl.com/transactions/",
        }[kind]
        manifest = {
            "schema_version": 1, "snapshot_id": folder.name, "kind": kind, "provider": "SYNTHETIC",
            "source_url": url, "season": 2026, "collected_at_utc": at, "available_at_utc": at,
            "source_last_modified": "Wed, 30 Sep 2026 00:00:00 GMT",
            "sha256": hashlib.sha256(body).hexdigest(),
        }
        (folder / "source.bin").write_bytes(body)
        if reviewed is not None:
            payload = json.dumps({"source_sha256": manifest["sha256"], "records": reviewed}).encode()
            (folder / "reviewed.json").write_bytes(payload)
            manifest["reviewed_sha256"] = hashlib.sha256(payload).hexdigest()
        (folder / "manifest.json").write_text(json.dumps(manifest))
        return folder

    def roster_evidence(self, rows):
        buffer = BytesIO()
        pl.DataFrame([
            dict(season=2026, game_type="REG", week=week, team=team, gsis_id=player,
                 full_name="Synthetic Fixture", position="WR", status=status)
            for week, team, player, status in rows
        ]).write_parquet(buffer)
        return self.evidence("roster", buffer.getvalue())

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

    def test_multiple_pregame_matchups_with_roster_and_games_without_players(self):
        with duckdb.connect(str(self.database)) as con:
            con.execute("""
                INSERT INTO games
                SELECT * REPLACE ('target2' AS game_id, 'OPP' AS away_team, 'JAX' AS home_team)
                    FROM games WHERE game_id='target'
                UNION ALL
                SELECT * REPLACE ('schedule-only' AS game_id, 'MIA' AS away_team, 'NYJ' AS home_team)
                    FROM games WHERE game_id='target'
                UNION ALL
                SELECT * REPLACE ('missing-time' AS game_id, NULL AS kickoff_utc, 'CHI' AS away_team)
                    FROM games WHERE game_id='target'
                UNION ALL
                SELECT * REPLACE ('started' AS game_id, TIMESTAMPTZ '2026-10-01 00:00:00+00' AS kickoff_utc, 'GB' AS away_team)
                    FROM games WHERE game_id='target'
                """)
            con.execute("""
                INSERT INTO player_week SELECT * REPLACE (
                    '00-0000002' AS player_id, 'OPP' AS team,
                    NULL AS rushing_yards, week-1 AS weekly_rushing_yards,
                    NULL AS receiving_yards
                ) FROM player_week WHERE player_id='00-0000001'
                """)
            con.execute("""
                INSERT INTO player_crosswalk
                SELECT * REPLACE ('00-0000002' AS player_id, 'OPP' AS team, 'Fixture Back' AS display_name, 'RB' AS position)
                    FROM player_crosswalk WHERE player_id='00-0000001'
                UNION ALL
                SELECT * REPLACE ('00-0000003' AS player_id, 'JAX' AS team, 'No history' AS display_name)
                    FROM player_crosswalk WHERE player_id='00-0000001'
                UNION ALL
                SELECT * REPLACE (NULL AS player_id, 'OPP' AS team)
                    FROM player_crosswalk WHERE player_id='00-0000001'
                UNION ALL
                SELECT * REPLACE (3 AS week, 'MIA' AS team)
                    FROM player_crosswalk WHERE player_id='00-0000001'
                """)
        self.refresh_manifest()
        _, slate = self.export()
        counts = slate["counts"]
        self.assertEqual(
            [counts[k] for k in ("games", "scheduled_games_at_cutoff",
                                 "scheduled_games_with_analysis", "games_with_props",
                                 "players", "players_assessed")],
            [5, 3, 2, 2, 2, 3],
        )
        games = {item["game_id"]: item for item in slate["games"]}
        self.assertEqual(games["started"]["status"], "STARTED_STATUS_UNKNOWN")
        self.assertEqual(games["missing-time"]["status"], "UNKNOWN")
        self.assertEqual(games["schedule-only"]["coverage"]["props_status"], "NO_WEEKLY_ROSTER")
        self.assertEqual(games["target2"]["coverage"]["unresolved_roster_rows"], 1)
        self.assertIsNone(next(p for p in slate["props"] if p["game_id"] == "target2")["volume"]["red_zone_opportunities"])
        diagnostics = {p["player_id"]: p["markets"] for p in slate["player_coverage"]}
        self.assertEqual(diagnostics["00-0000002"]["rec_yards"]["status"], "NO_METRIC_OBSERVATIONS")
        self.assertEqual(diagnostics["00-0000003"]["receptions"]["status"], "NO_CONFIRMED_OFFENSIVE_HISTORY")
        rush = next(p for p in slate["props"] if p["game_id"] == "target2" and p["market"] == "rush_yards")
        self.assertEqual([r["value"] for r in rush["history"]["observations"]], [0, 1, 2])
        self.assertTrue(all(r["source_field"] == "weekly_rushing_yards" for r in rush["history"]["observations"]))

    def test_excludes_unfinished_future_unavailable_and_wrong_source_facts(self):
        with duckdb.connect(str(self.database)) as con:
            for game_id, kickoff, stamp, marker, source in (
                ("unfinished", "2026-09-26T00:00:00Z", "2026-09-30T00:00:00Z", False, "fixture-snapshot"),
                ("future", "2026-10-01T00:00:00Z", "2026-09-30T00:00:00Z", True, "fixture-snapshot"),
                ("late", "2026-09-27T00:00:00Z", "2026-10-01T00:00:01Z", True, "fixture-snapshot"),
                ("other-snapshot", "2026-09-28T00:00:00Z", "2026-09-30T00:00:00Z", True, "other"),
            ):
                con.execute("""
                    INSERT INTO games SELECT * REPLACE (? AS game_id, ?::TIMESTAMPTZ AS kickoff_utc)
                    FROM games WHERE game_id='g1'
                    """, [game_id, kickoff])
                con.execute("""
                    INSERT INTO coverage_audit SELECT * REPLACE (? AS game_id, ? AS has_end_marker)
                    FROM coverage_audit WHERE game_id='g1'
                    """, [game_id, marker])
                for table in ("player_week", "team_week", "defensive_matchups", "offensive_opportunities"):
                    con.execute(f"""
                        INSERT INTO {table}
                        SELECT * REPLACE (? AS game_id, ?::TIMESTAMPTZ AS available_at, ? AS source_snapshot_id)
                        FROM {table} WHERE game_id='g1'
                        """, [game_id, stamp, source])
            con.execute("UPDATE coverage_audit SET available_at='2026-10-01T00:00:00Z' WHERE game_id='g3'")
            con.execute("UPDATE offensive_opportunities SET opportunity_type='RUSH' WHERE game_id='g1'")
        self.refresh_manifest()
        _, slate = self.export()
        self.assertEqual(slate["matchups"][0]["teams"]["LAC"]["season"]["games"], 3)
        for prop in slate["props"]:
            self.assertEqual([r["game_id"] for r in prop["history"]["observations"]], ["g1", "g2", "g3"])
            self.assertEqual(prop["history"]["observations"][-1]["available_at_utc"], "2026-10-01T00:00:00+00:00")
            self.assertEqual(prop["volume"]["red_zone_carries"], 1)
            self.assertEqual(prop["volume"]["red_zone_opportunities"], 3)
        with self.assertRaisesRegex(ValueError, "timezone"):
            export_static(self.canonical, self.root / "naive", season=2026, week=4, cutoff=datetime(2026, 10, 1))

    def test_validation_and_publication_preserve_previous_files(self):
        first, slate = self.export()
        second, _ = self.export(cutoff="2026-10-01T01:00:00Z")
        different_week, _ = self.export(week=3)
        self.assertEqual(len({first, second, different_week}), 3)
        root = first.parent.parent
        current = root / "slate.json"
        self.assertFalse(current.exists())
        validate_export(first)
        publish_export(first, root)
        previous = current.read_bytes()
        self.assertEqual(json.loads(previous), slate)
        lock = root / ".slate-publish.lock"
        lock.touch()
        with self.assertRaises(FileExistsError):
            publish_export(second, root)
        self.assertEqual(current.read_bytes(), previous)
        lock.unlink()
        source_file = second / "player_coverage.json"
        source_file.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            publish_export(second, root)
        self.assertEqual(current.read_bytes(), previous)
        self.assertEqual((first / "slate.json").read_bytes(), previous)
        with self.assertRaisesRegex(ValueError, "archived web snapshot"):
            publish_export(first, first)

    def test_rejects_tampered_canonical_database(self):
        with self.database.open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaisesRegex(ValueError, "modified database"):
            self.export()
        self.assertFalse((self.root / "out").exists())

    def test_new_roster_uses_capture_time_and_preempts_prior_week(self):
        with duckdb.connect(str(self.database)) as con:
            con.execute("UPDATE player_crosswalk SET week=2")
        self.refresh_manifest()
        evidence = self.roster_evidence([(4, "LAC", "00-0000001", "ACT")])
        prev = "2026-09-30T23:59:59Z"
        _, strict = self.export(cutoff=prev, evidence_paths=[evidence])
        self.assertEqual(strict["props"], [])
        self.assertEqual(strict["evidence_snapshots"], [])
        _, provisional = self.export(cutoff=prev, evidence_paths=[evidence], roster_fallback=True)
        pending = provisional["props"][0]["roster_evidence"]
        self.assertEqual((pending["status"], pending["source_week"], pending["age_weeks"]),
                         ("PROVISIONAL_ROSTER", 2, 2))
        self.assertEqual(pending["team_membership_status"], "UNVERIFIED")
        _, exact = self.export(evidence_paths=[evidence], roster_fallback=True)
        self.assertGreater(len(exact["props"]), 0)
        for prop in exact["props"]:
            self.assertEqual(prop["roster_evidence"]["status"], "EXACT_WEEK_ROSTER")
            self.assertEqual(prop["eligibility"]["status"], "UNVERIFIED")
            self.assertNotIn(prop["game_id"], [o["game_id"] for o in prop["history"]["observations"]])
        (evidence / "source.bin").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.export(output="tamper", evidence_paths=[evidence])

    def test_capture_archives_each_response_without_overwriting(self):
        source = self.roster_evidence([(4, "LAC", "00-0000001", "ACT")])
        body = (source / "source.bin").read_bytes()
        output = self.root / "sealed"
        with patch("nfl_betting.temporal_roster.urlopen") as request:
            response = request.return_value.__enter__.return_value
            response.read.return_value = body
            response.headers = {"Last-Modified": "Wed, 30 Sep 2026 00:00:00 GMT"}
            first, manifest = capture("roster", output, season=2026)
            second, _ = capture("roster", output, season=2026)
        self.assertNotEqual(first, second)
        self.assertEqual((first / "source.bin").read_bytes(), body)
        self.assertEqual(json.loads((first / "manifest.json").read_text()), manifest)
        self.assertLessEqual(parse_cutoff(manifest["collected_at_utc"]), parse_cutoff(manifest["available_at_utc"]))

    def test_provisional_filters_cut_transfer_duplicate_and_honors_effective_time(self):
        roster = self.roster_evidence([
            (2, "LAC", "00-0000001", "ACT"), (2, "BAL", "00-0000001", "ACT"),
            (2, "LAC", "00-0000002", "CUT"), (2, "LAC", "00-0000003", "ACT"),
            (2, "BAL", "00-0000003", "ACT"), (2, "BAL", "00-0000004", "ACT"),
            (1, "BAL", "00-0000005", "ACT"), (5, "LAC", "00-0000006", "ACT"),
        ])
        transactions = self.evidence("transactions", b"Synthetic reviewed source", reviewed=[
            {"player_id": "00-0000001", "from_team": "LAC", "to_team": "BAL",
             "effective_at_utc": "2026-09-30T12:00:00Z", "published_at_utc": "2026-09-30T12:00:00Z"},
            {"player_id": "00-0000004", "from_team": "BAL", "to_team": None,
             "effective_at_utc": "2026-10-01T01:00:00Z", "published_at_utc": "2026-09-30T12:00:00Z"},
        ])
        cutoff = parse_cutoff("2026-10-01T00:00:00Z")
        captures = load_evidence([roster, transactions], 2026, cutoff)
        selected = select_roster([], captures, 4, cutoff, fallback=True)
        expected = {("BAL", "00-0000001"), ("BAL", "00-0000004")}
        self.assertEqual({(p["team"], p["player_id"]) for p in selected
                          if p["id_rows"] == 1 and not p["excluded_reason"]}, expected)
        reasons = {(p["team"], p["player_id"]): p["excluded_reason"] for p in selected}
        self.assertEqual(reasons["LAC", "00-0000001"], "ENDED_TEAM_MEMBERSHIP")
        self.assertEqual(reasons["LAC", "00-0000002"], "CUT")
        self.assertNotIn(("BAL", "00-0000005"), reasons)
        self.assertNotIn(("LAC", "00-0000006"), reasons)
        later = parse_cutoff("2026-10-01T01:00:00Z")
        later_rows = select_roster([], captures, 4, later, fallback=True)
        self.assertEqual(next(p["excluded_reason"] for p in later_rows if p["player_id"] == "00-0000004"),
                         "ENDED_TEAM_MEMBERSHIP")

    def test_official_kickoff_revision_gates_history_and_pregame_cutoff(self):
        evidence = self.evidence("kickoff", b"""
            Synthetic Fixture. Nov. 9, 2026. Sunday, Nov. 22.
            Jacksonville Jaguars at New York Giants game will move to 4:25 p.m. ET.
            Pittsburgh Steelers at Philadelphia Eagles game will move to 1 p.m. ET.
        """, at="2026-11-17T22:00:00Z")
        with duckdb.connect(str(self.database)) as con:
            con.execute("""
                UPDATE games SET game_id='2026_11_PIT_PHI', week=11, kickoff_utc='2026-11-22T21:25:00Z',
                away_team='PIT', home_team='PHI'
                WHERE game_id='target'
                """)
            con.execute("UPDATE player_crosswalk SET week=11, team='PIT'")
            con.execute("""
                INSERT INTO player_week SELECT * REPLACE(
                    '2026_11_PIT_PHI' AS game_id, 11 AS week, 999 AS receptions, 'PIT' AS team
                ) FROM player_week WHERE game_id='g1'
                """)
        self.refresh_manifest()
        options = {"week": 11, "evidence_paths": [evidence]}
        _, blocked = self.export(cutoff="2026-11-17T21:59:59Z", **options)
        self.assertEqual(blocked["games"][0]["status"], "KICKOFF_UNVERIFIED")
        self.assertEqual(blocked["props"], [])
        _, corrected = self.export(cutoff="2026-11-22T17:59:00Z", **options)
        game = corrected["games"][0]
        self.assertEqual(game["kickoff_utc"], "2026-11-22T18:00:00+00:00")
        self.assertEqual(game["canonical_kickoff_utc"], "2026-11-22T21:25:00+00:00")
        self.assertGreater(len(corrected["props"]), 0)
        for prop in corrected["props"]:
            self.assertNotIn(999, [row["value"] for row in prop["history"]["observations"]])
        _, started = self.export(cutoff="2026-11-22T18:00:00Z", **options)
        self.assertEqual(started["games"][0]["status"], "STARTED_STATUS_UNKNOWN")
        self.assertEqual(started["props"], [])


if __name__ == "__main__":
    unittest.main()
