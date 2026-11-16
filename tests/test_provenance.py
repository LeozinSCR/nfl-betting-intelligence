"""Capture lifecycle tests with a fake downloader and zero real HTTP calls."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nfl_betting.provenance import capture_downloads
from tools.refresh_diagnostics import summarize
import json


class ProvenanceTests(unittest.TestCase):
    def test_capture_actual_response_hash_url_headers_and_restore(self):
        config = SimpleNamespace(cache_mode="memory", verbose=True)
        response = SimpleNamespace(
            status_code=200,
            url="https://fixtures.invalid/asset?temporary-signature=do-not-store",
            content=b"SYNTHETIC BODY",
            headers={
                "ETag": "fixture-etag",
                "Last-Modified": "Mon, 16 Nov 2026 09:00:00 GMT",
            },
        )
        session = SimpleNamespace(hooks={"response": []})

        def download(url, **kw):
            for hook in session.hooks["response"]:
                hook(response)
            return "synthetic parsed table"

        downloader = SimpleNamespace(_download_file=download, session=session)
        with (
            TemporaryDirectory() as root,
            patch("nflreadpy.config.get_config", return_value=config),
            patch("nflreadpy.downloader.get_downloader", return_value=downloader),
        ):
            with capture_downloads(Path(root)) as trace:
                trace["source"] = "pbp"
                self.assertEqual(
                    downloader._download_file("https://fixtures.invalid/pbp.parquet"),
                    "synthetic parsed table",
                )
                record = trace["responses"][0]
                self.assertEqual(
                    record["response_url"], "https://fixtures.invalid/asset"
                )
                self.assertEqual(
                    record["requested_url"], "https://fixtures.invalid/pbp.parquet"
                )
                self.assertEqual(
                    record["sha256"], hashlib.sha256(b"SYNTHETIC BODY").hexdigest()
                )
                self.assertEqual(
                    (Path(root) / record["path"]).read_bytes(), b"SYNTHETIC BODY"
                )
                self.assertEqual(record["headers"]["ETag"], "fixture-etag")
                self.assertEqual(config.cache_mode, "off")
            self.assertIs(downloader._download_file, download)
            self.assertEqual(config.cache_mode, "memory")
            self.assertEqual(session.hooks["response"], [])

    def test_error_still_restores_capture_state(self):
        config = SimpleNamespace(cache_mode="memory", verbose=True)

        def fail(url):
            raise ConnectionError("synthetic HTTP failure")

        downloader = SimpleNamespace(
            _download_file=fail, session=SimpleNamespace(hooks={"response": []})
        )
        with (
            TemporaryDirectory() as root,
            patch("nflreadpy.config.get_config", return_value=config),
            patch("nflreadpy.downloader.get_downloader", return_value=downloader),
        ):
            with self.assertRaises(ConnectionError):
                with capture_downloads(Path(root)) as trace:
                    trace["source"] = "pbp"
                    downloader._download_file("https://fixtures.invalid/source")
            self.assertIs(downloader._download_file, fail)
            self.assertEqual(config.cache_mode, "memory")

    def test_partial_canonical_build_is_visible_in_workflow_diagnostic(self):
        with TemporaryDirectory() as root:
            root = Path(root)
            ingest = root / "raw/2026/run"
            ingest.mkdir(parents=True)
            (ingest / "manifest.json").write_text('{"status":"OK"}')
            canon = root / "canonical/2026/build"
            canon.mkdir(parents=True)
            (canon / "build_manifest.json").write_text(
                '{"status":"PARTIAL","pending_audit_rows":12}'
            )
            outcomes = {
                k: "success" for k in ("install", "tests", "ingest", "canonical")
            }
            result = summarize(
                root / "raw",
                root / "diagnostic.json",
                outcomes=outcomes,
                canonical_root=root / "canonical",
            )
            self.assertEqual(result["status"], "PARTIAL")
            self.assertFalse(result["historical_data_updated"])
            self.assertEqual(
                result["canonical_builds"][0]["manifest"]["pending_audit_rows"], 12
            )
            outcomes["canonical"] = "failure"
            result = summarize(
                root / "raw",
                root / "diagnostic.json",
                outcomes=outcomes,
                canonical_root=root / "canonical",
            )
            self.assertEqual(result["status"], "ERROR")

    def test_no_canonical_manifest_cannot_be_success(self):
        with TemporaryDirectory() as root:
            root = Path(root)
            ingest = root / "raw/2026/run"
            ingest.mkdir(parents=True)
            (ingest / "manifest.json").write_text('{"status":"OK"}')
            outcomes = {
                k: "success" for k in ("install", "tests", "ingest", "canonical")
            }
            result = summarize(
                root / "raw",
                root / "diagnostic.json",
                outcomes=outcomes,
                canonical_root=root / "missing",
            )
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("canonical_diagnostic", result)


if __name__ == "__main__":
    unittest.main()
