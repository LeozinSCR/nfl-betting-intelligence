"""Offline boundary/integrity tests; canonical fixture is entirely synthetic."""

import hashlib
import importlib.util
import json
import socket
import tempfile
import unittest
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from test_canonical import fixture

from nfl_betting.archive import export, verify
from nfl_betting.canonical import build
from nfl_betting.pregame import unavailable, validate_evidence
from nfl_betting.provenance import sha256
from nfl_betting.research import query

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "publish_refresh", ROOT / "tools/publish_refresh.py"
)
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.raw, cls.history, _, _ = fixture(cls.temp.name)
        cls.folder, cls.manifest = build(
            cls.raw, Path(cls.temp.name) / "canonical", cls.history
        )
        cls.cutoff = datetime(2030, 1, 1, tzinfo=UTC)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def call(self, task="players", **kwargs):
        options = {"season": 2026, "week": 1, "cutoff": self.cutoff}
        options.update(kwargs)
        return query(self.folder, task, **options)

    def test_readonly_and_snapshot_receipt(self):
        before = sha256(self.folder / "nfl.duckdb")
        r = self.call()
        self.assertGreater(r["total_rows"], 0)
        self.assertEqual(r["decision"], "NO_BET")
        self.assertFalse(r["financial_approved"])
        self.assertFalse(r["statistical_approved"])
        self.assertEqual(r["source_snapshot_id"], self.manifest["source_snapshot_id"])
        self.assertEqual(sha256(self.folder / "nfl.duckdb"), before)

    def test_no_network_required(self):
        with patch.object(
            socket, "create_connection", side_effect=AssertionError("network forbidden")
        ):
            self.assertEqual(self.call("games")["status"], "OK")

    def test_before_collection_returns_no_rows(self):
        self.assertEqual(
            self.call(cutoff="2020-01-01T00:00:00+00:00")["status"], "NO_DATA_AS_OF"
        )

    def test_wrong_week_and_season_do_not_backfill(self):
        self.assertEqual(self.call(season=2025)["total_rows"], 0)
        self.assertEqual(self.call(week=20)["total_rows"], 0)

    def test_sql_injection_is_parameter_not_sql(self):
        self.assertEqual(self.call(team="X' OR 1=1 --")["total_rows"], 0)
        with self.assertRaises(ValueError):
            self.call("players; DROP TABLE games")

    def test_limits_and_naive_cutoff(self):
        for options in (
            {"limit": 0},
            {"limit": 501},
            {"week": True},
            {"cutoff": datetime(2026, 1, 1)},
        ):
            with self.assertRaises(ValueError):
                self.call(**options)

    def test_truncation_replay(self):
        a, b = self.call(limit=1), self.call(limit=1)
        self.assertTrue(a["truncated"])
        self.assertEqual(a["records"], b["records"])

    def test_unsupported_filter_is_not_silently_ignored(self):
        with self.assertRaises(ValueError):
            self.call("games", player_id="00-TEST")

    def test_all_tasks(self):
        for task in (
            "games",
            "players",
            "teams",
            "snaps",
            "injuries",
            "usage",
            "matchups",
            "identities",
        ):
            self.assertIn(self.call(task)["status"], ("OK", "NO_DATA_AS_OF"))
        self.assertTrue(
            all(x["severity"] == "PENDING" for x in self.call("identities")["records"])
        )

    def test_skill_frontmatter_helper_and_contract(self):
        skill = ROOT / ".agents/skills/nfl-betting-intelligence"
        text = (skill / "SKILL.md").read_text()
        self.assertTrue(
            text.startswith("---\nname: nfl-betting-intelligence\ndescription:")
        )
        for token in (
            "NO_BET",
            "validate_best_parlay",
            "validate_td_parlay",
            "R$35",
            "R$15",
            "R$50",
        ):
            self.assertIn(token, text)
        helper = importlib.util.spec_from_file_location(
            "internal_skill_query", skill / "scripts/query.py"
        )
        module = importlib.util.module_from_spec(helper)
        helper.loader.exec_module(module)
        from nfl_betting.research import main

        self.assertIs(module.main, main)

    def test_archive_export_relocate_and_tamper(self):
        destination = Path(self.temp.name) / "archive"
        r = export(self.raw, self.folder, destination)
        self.assertGreater(r["files"], 14)
        self.assertEqual(verify(destination, r["catalog_sha256"])["status"], "VERIFIED")
        # Same controlled query still works after relocation.
        result = query(
            destination / "canonical", "games", season=2026, week=1, cutoff=self.cutoff
        )
        self.assertGreater(result["total_rows"], 0)
        with self.assertRaises(FileExistsError):
            export(self.raw, self.folder, destination)
        (destination / "canonical/nfl.duckdb").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            verify(destination, r["catalog_sha256"])

    def test_archive_refuses_recursion(self):
        with self.assertRaises(ValueError):
            export(self.raw, self.folder, self.raw / "recursive")


class PregameTests(unittest.TestCase):
    def setUp(self):
        self.cutoff = datetime(2026, 11, 16, 23, tzinfo=UTC)
        self.kickoff = self.cutoff + timedelta(hours=2)
        payload = {"status": "UNKNOWN"}
        self.item = {
            "kind": "player_status",
            "provider": "SYNTHETIC_TEST_ONLY",
            "source_url": "https://example.org/report",
            "game_id": "TEST",
            "player_id": "00-SYNTHETIC",
            "snapshot_id": "test",
            "payload": payload,
            "observed_at": (self.cutoff - timedelta(minutes=1)).isoformat(),
            "valid_until": (self.cutoff + timedelta(minutes=1)).isoformat(),
            "payload_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }

    def validate(self, item=None):
        return validate_evidence(
            item or self.item, cutoff=self.cutoff, kickoff=self.kickoff
        )

    def test_valid_envelope_is_not_verified_fact(self):
        r = self.validate()
        self.assertTrue(r["envelope_valid"])
        self.assertFalse(r["facts_verified"])
        self.assertEqual(r["decision"], "NO_BET")

    def test_future_stale_postkickoff_and_naive(self):
        for key, val in [
            ("observed_at", self.kickoff.isoformat()),
            ("valid_until", self.cutoff.isoformat()),
            ("valid_until", (self.kickoff + timedelta(seconds=1)).isoformat()),
            ("observed_at", "2026-11-16T22:59:00"),
        ]:
            item = deepcopy(self.item)
            item[key] = val
            with self.assertRaises(ValueError):
                self.validate(item)

    def test_missing_origin_and_credential_url(self):
        for key, val in [
            ("provider", ""),
            ("source_url", "https://user:secret@example.org/"),
            ("source_url", "https://example.org/?token=secret"),
            ("snapshot_id", ""),
        ]:
            item = deepcopy(self.item)
            item[key] = val
            with self.assertRaises(ValueError):
                self.validate(item)

    def test_names_do_not_resolve_identity(self):
        item = deepcopy(self.item)
        item["player_id"] = "John Test"
        with self.assertRaises(ValueError):
            self.validate(item)

    def test_tampered_payload(self):
        item = deepcopy(self.item)
        item["payload"]["status"] = "ACTIVE"
        with self.assertRaises(ValueError):
            self.validate(item)

    def test_unknown_and_unconfigured(self):
        self.assertEqual(unavailable("Stake", "quote")["status"], "UNCONFIGURED")
        self.assertEqual(unavailable("NFL", "official_inactives")["records"], [])
        with self.assertRaises(ValueError):
            unavailable("X", "place_bet")

    def test_existing_quote_validation_cannot_be_bypassed(self):
        item = deepcopy(self.item)
        item["kind"] = "quote"
        item["payload"] = {
            "game_id": "TEST",
            "player_id": "00-SYNTHETIC",
            "observed_at": item["observed_at"],
            "valid_until": item["valid_until"],
            "odds": float("inf"),
        }
        with self.assertRaises(ValueError):
            self.validate(item)


class PublicationTests(unittest.TestCase):
    def good(self):
        return dict.fromkeys(
            (
                "INSTALL_OUTCOME",
                "TESTS_OUTCOME",
                "INGEST_OUTCOME",
                "CANONICAL_OUTCOME",
                "ARTIFACT_OUTCOME",
            ),
            "success",
        ) | {"ARTIFACT_URL": "https://github.com/a/b/actions/runs/1/artifacts/2"}

    def test_no_pr_permission_needed(self):
        r = publish.receipt(self.good())
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["PR_OUTCOME"], "NOT_REQUESTED")
        self.assertEqual(r["permission_requirement"], "contents: read")

    def test_failure_partial_receipt_still_rendered(self):
        for stage in (
            "INSTALL_OUTCOME",
            "TESTS_OUTCOME",
            "INGEST_OUTCOME",
            "CANONICAL_OUTCOME",
            "ARTIFACT_OUTCOME",
        ):
            env = self.good()
            env[stage] = "failure"
            r = publish.receipt(env)
            self.assertEqual(r["status"], "ERROR")
            self.assertIn("NO_BET", publish.render(r))

    def test_untrusted_link_and_missing_artifact(self):
        for link in (
            "",
            "https://evil.example/a",
            "https://github.com/a?token=secret",
            "https://github.com/a/)[x](bad",
        ):
            env = self.good()
            env["ARTIFACT_URL"] = link
            r = publish.receipt(env)
            self.assertEqual(r["status"], "ERROR")
            self.assertNotIn("secret", publish.render(r))

    def test_summary_does_not_echo_source_errors(self):
        env = self.good()
        env["INGEST_OUTCOME"] = "<script>secret</script>"
        self.assertNotIn("secret", publish.render(publish.receipt(env)))
