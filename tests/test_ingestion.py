"""Deterministic failure/success tests; loaders return synthetic tables only."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import polars as pl
from nfl_betting.ingest_nflverse import collect, main
from tools.refresh_diagnostics import summarize
from tools.verify_history import verify


def pbp():
    return pl.DataFrame({"season": [2026], "week": [1], "game_id": ["fixture"], "play_id": [1]})


def fail(_):
    raise ConnectionError("synthetic offline outage")


class IngestionTests(unittest.TestCase):
    def test_success_manifest_hash_and_unique_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            p1, code = collect(2026, folder, ["pbp"], loaders={"pbp": lambda _: pbp()})
            original = p1.read_bytes()
            p2, code2 = collect(2026, folder, ["pbp"], loaders={"pbp": lambda _: pbp()})
            self.assertEqual((code, code2), (0, 0))
            self.assertNotEqual(p1.parent, p2.parent)
            self.assertEqual(p1.read_bytes(), original)
            m = json.loads(original)
            self.assertEqual(m["status"], "OK")
            self.assertEqual(m["sources"]["pbp"]["weeks"], [1])
            path = p1.parent / m["sources"]["pbp"]["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), m["sources"]["pbp"]["sha256"])
            self.assertFalse(m["financial_approved"])
            self.assertFalse(m["reconciled"])
            self.assertIsNone(m["sources"]["pbp"]["source_updated_at"])

    def test_partial_failure_preserves_success_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            p, code = collect(2026, folder, ["pbp", "injuries"], loaders={"pbp": lambda _: pbp(), "injuries": fail})
            self.assertEqual(code, 2)
            m = json.loads(p.read_text())
            self.assertEqual(m["status"], "ERROR")
            self.assertEqual(m["sources"]["pbp"]["status"], "OK")
            self.assertEqual(m["sources"]["injuries"]["error"]["type"], "ConnectionError")
            self.assertTrue((p.parent / "pbp.parquet").exists())
            result = summarize(folder, Path(folder) / "diagnostic.json", outcomes={"install": "success", "tests": "success", "ingest": "failure"})
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(len(result["ingestions"]), 1)

    def test_dependency_import_failure_still_writes_manifest(self):
        with tempfile.TemporaryDirectory() as folder, patch("nfl_betting.ingest_nflverse.make_loaders", side_effect=ImportError("synthetic import failure")):
            p, code = collect(2026, folder)
            m = json.loads(p.read_text())
            self.assertEqual(code, 2)
            self.assertEqual(m["errors"][0]["type"], "ImportError")
            self.assertIsNotNone(m["finished_at_utc"])

    def test_empty_schema_wrong_season_and_write_failure(self):
        frames = [pl.DataFrame(), pl.DataFrame({"season": [2026]}), pbp().with_columns(pl.lit(2025).alias("season"))]
        for table in frames:
            with self.subTest(table=table), tempfile.TemporaryDirectory() as folder:
                p, code = collect(2026, folder, ["pbp"], loaders={"pbp": lambda _, t=table: t})
                self.assertEqual(code, 2)
                self.assertTrue(json.loads(p.read_text())["errors"])
        with tempfile.TemporaryDirectory() as folder, patch.object(pl.DataFrame, "write_parquet", side_effect=OSError("synthetic disk failure")):
            p, code = collect(2026, folder, ["pbp"], loaders={"pbp": lambda _: pbp()})
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(p.read_text())["errors"][0]["type"], "OSError")

    def test_invalid_sources_get_error_manifest(self):
        for sources in ([], ["not-a-source"], ["pbp", "pbp"]):
            with tempfile.TemporaryDirectory() as folder:
                p, code = collect(2026, folder, sources, loaders={})
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(p.read_text())["status"], "ERROR")

    def test_cli_returns_failure_and_missing_output_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder, patch("nfl_betting.ingest_nflverse.make_loaders", return_value={"pbp": fail}):
            with patch("builtins.print"):
                self.assertEqual(main(["--out", folder, "--sources", "pbp"]), 2)
        with patch("nfl_betting.ingest_nflverse.collect", side_effect=PermissionError("synthetic destination denial")), patch("builtins.print"):
            self.assertEqual(main([]), 2)

    def test_historical_destinations_protected(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("legacy", "data/processed", "data/reference/subdir"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                collect(2026, root / name, ["pbp"], loaders={})


class DiagnosticsAndHistoryTests(unittest.TestCase):
    def test_history_zip_and_audit_unchanged(self):
        self.assertEqual(verify(), [])

    def test_no_manifest_setup_or_test_failure_is_auditable(self):
        with tempfile.TemporaryDirectory() as folder:
            for outcomes in ({"install": "failure", "tests": "skipped", "ingest": "skipped"},
                             {"install": "success", "tests": "failure", "ingest": "skipped"}):
                result = summarize(folder, Path(folder) / "diagnostic.json", outcomes=outcomes)
                self.assertEqual(result["status"], "ERROR")
                self.assertIn("NO_MANIFEST", result["diagnostic"])
                self.assertEqual(result["step_outcomes"], outcomes)
                self.assertFalse(result["historical_data_updated"])

    def test_corrupt_or_multiple_manifests_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder) / "2026/run"; run.mkdir(parents=True)
            (run / "manifest.json").write_text("invalid json")
            result = summarize(folder, Path(folder) / "out.json", outcomes={k: "success" for k in ("install", "tests", "ingest")})
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("error", result["ingestions"][0])
            (run / "manifest.json").write_text('{"status":"OK"}')
            second = Path(folder) / "2026/other"; second.mkdir()
            (second / "manifest.json").write_text('{"status":"OK"}')
            result = summarize(folder, Path(folder) / "out.json", outcomes={k: "success" for k in ("install", "tests", "ingest")})
            self.assertEqual(result["status"], "ERROR")

    def test_success_diagnostic_is_not_model_or_history_update(self):
        with tempfile.TemporaryDirectory() as folder:
            collect(2026, folder, ["pbp"], loaders={"pbp": lambda _: pbp()})
            result = summarize(folder, Path(folder) / "out.json", outcomes={k: "success" for k in ("install", "tests", "ingest")}, run_url="https://fixtures.invalid/run")
            self.assertEqual(result["status"], "OK")
            self.assertFalse(result["financial_approved"])
            self.assertFalse(result["historical_data_updated"])
            self.assertEqual(result["workflow_run_url"], "https://fixtures.invalid/run")


if __name__ == "__main__":
    unittest.main()
