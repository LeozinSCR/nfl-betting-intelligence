"""Synthetic response fixtures; tests make zero HTTP requests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import stake_odds
from nfl_betting.rules import validate_quote
from datetime import datetime, timezone


def snapshot(price=2.0, available=True, status="open"):
    return {"url": "https://fixtures.invalid/matches", "retrieved_utc": "2026-11-16T12:00:00Z",
            "payload": {"lastUpdatedAt": "2026-11-16T11:59:00Z", "data": [
                {"id": "fixture-event", "name": "Synthetic event", "startsAt": "2026-11-16T20:00:00Z",
                 "offers": [{"name": "Synthetic market", "status": status, "selections": [
                     {"name": "Synthetic selection", "decimalOdds": price, "available": available}]}]}]}}


class StakeExportTests(unittest.TestCase):
    def test_invalid_odds_are_quarantined(self):
        for price in (None, "2.0", True, 1, 0, -1, float("nan"), float("inf")):
            rows, rejected = stake_odds.normalize_offers(snapshot(price))
            self.assertEqual(rows, [])
            self.assertEqual(rejected[0]["reason"], "INVALID_ODDS")

    def test_export_keeps_source_time_and_event_but_no_invented_expiry(self):
        rows, rejected = stake_odds.normalize_offers(snapshot())
        self.assertEqual(rejected, [])
        row = rows[0]
        self.assertEqual(row["source_updated_at"], "2026-11-16T11:59:00Z")
        self.assertEqual(json.loads(row["event_json"])["id"], "fixture-event")
        self.assertEqual(row["valid_until"], "")
        self.assertEqual(row["binding_status"], "UNMAPPED_RESEARCH_ONLY")
        self.assertFalse(validate_quote(row, as_of=datetime(2026, 11, 16, 12, tzinfo=timezone.utc)).valid)

    def test_availability_is_not_inferred_from_truthy_values(self):
        for available, status in ((None, "open"), ("true", "open"), (True, "suspended"), (True, None)):
            rows, _ = stake_odds.normalize_offers(snapshot(available=available, status=status))
            self.assertFalse(rows[0]["available"])

    def test_mocked_cli_exports_complete_snapshot_and_coverage_warning(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"SPORTSBOOK_API_KEY": ""}):
            with patch("sys.argv", ["stake_odds.py", "--out", folder, "--sport-id", "known-sport", "--tournament-id", "known-league"]), patch.object(stake_odds.Client, "get", return_value=snapshot()), patch("builtins.print"):
                self.assertEqual(stake_odds.main(), 0)
            runs = list(Path(folder).iterdir())
            self.assertEqual(len(runs), 1)
            diagnostic = json.loads((runs[0] / "stake_normalization.json").read_text())
            self.assertEqual(diagnostic["player_props_coverage"], "NOT_DEMONSTRATED")
            self.assertFalse(diagnostic["financial_approved"])
            self.assertTrue((runs[0] / "stake_offers.csv").is_file())
            self.assertTrue((runs[0] / "stake_raw.json").is_file())

    def test_process_cap_prevents_network_call(self):
        with patch.object(stake_odds, "urlopen") as network:
            with self.assertRaises(RuntimeError):
                stake_odds.Client(0, "").get("/en/sports")
            network.assert_not_called()

    def test_partial_raw_snapshot_and_unique_output_on_failure(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"SPORTSBOOK_API_KEY": ""}):
            responses = {"url": "https://fixtures.invalid/sports", "retrieved_utc": "2026-11-16T12:00:00Z",
                         "payload": {"data": [{"id": "american-football", "name": "American Football"}]}}
            def mocked_get(client, path):
                if path == "/en/sports":
                    return responses
                raise ConnectionError("synthetic tournament failure")
            for _ in range(2):
                with patch("sys.argv", ["stake_odds.py", "--out", folder]), patch.object(stake_odds.Client, "get", mocked_get), patch("builtins.print"):
                    self.assertEqual(stake_odds.main(), 1)
            paths = list(Path(folder).glob("*/stake_raw.json"))
            self.assertEqual(len(paths), 2)
            for path in paths:
                self.assertEqual(json.loads(path.read_text())["snapshots"], [responses])


if __name__ == "__main__":
    unittest.main()
