"""Synthetic offline controls for V1.7. No loader may make an HTTP request."""

from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import duckdb

import test_projection as fixtures
from nfl_betting.backtesting import STRICT, backtest
from nfl_betting.ingest_nflverse import SOURCES
from nfl_betting.pregame_capture import capture_window, plan_window, restore_bundle, verify_bundle
from nfl_betting.provenance import sha256
from nfl_betting.temporal_roster import utc

START = "2026-10-01T18:20:00Z"
END = "2026-10-01T18:40:00Z"
SEAL = "2026-10-01T18:55:00Z"


def _save(file, payload):
    file.write_text(json.dumps(payload), encoding="utf-8")


def _change_catalog(path, sql):
    db = path / "nfl.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute(sql)
    file = path / "build_manifest.json"
    data = json.loads(file.read_text())
    data["database"]["sha256"] = sha256(db)
    _save(file, data)


def _official(path, kickoff):
    path.mkdir()
    schedule = path / "source.bin"
    approval = path / "authorization.bin"
    schedule.write_bytes(b"Synthetic schedule text; not an official NFL document.")
    approval.write_bytes(b"Synthetic authorization; no real authorization is represented.")
    _save(path / "manifest.json", {
        "schema_version": 1, "season": 2026, "week": 6, "source_url": "https://media.nfl.com/synthetic-fixture",
        "source_version": "SYNTHETIC", "reviewed_by": "offline-fixture",
        "capture_authorized": True, "public_redistribution_authorized": True,
        "sha256": sha256(schedule), "authorization_sha256": sha256(approval),
        "started_at_utc": "2026-10-01T17:05:00Z", "finished_at_utc": "2026-10-01T17:10:00Z",
        "available_at_utc": "2026-10-01T17:11:00Z", "published_at_utc": None,
        "games": [{"game_id": "target", "away_team": "LAC", "home_team": "BAL", "kickoff_utc": kickoff}],
    })
    return path


def _collected(season, output, sources, *, finish=END, published=None):
    assert tuple(sources) == SOURCES
    raw = Path(output) / "synthetic-snapshot"
    raw.mkdir(parents=True)
    items = {}
    for source in sources:
        url = f"https://github.com/nflverse/nflverse-data/releases/download/{source}/synthetic.parquet"
        blob = raw / f"{source}.body"
        processed = raw / f"{source}.parquet"
        blob.write_bytes(b"Offline HTTP stand-in, not NFLverse data")
        processed.write_bytes(b"Offline source stand-in; the builder is mocked")
        items[source] = {
            "status": "OK", "path": processed.name, "sha256": sha256(processed),
            "resolved_download_url": url, "started_at_utc": START, "finished_at_utc": finish,
            "published_at_utc": published if source == "schedules" else None,
            "http_responses": [{
                "status_code": 200, "requested_url": url, "received_at_utc": finish,
                "path": blob.name, "sha256": sha256(blob),
            }],
        }
    manifest = raw / "manifest.json"
    _save(manifest, {"season": season, "run_id": raw.name, "started_at_utc": START,
                     "finished_at_utc": finish, "sources": items})
    return manifest, 0


def _built(snapshot, output, *, shifted_kickoff=None, build_delay=5):
    raw_path = Path(snapshot) / "manifest.json"
    raw_end = utc(json.loads(raw_path.read_text())["finished_at_utc"])
    root = Path(output)
    root.mkdir()
    where = root / Path(snapshot).name
    fixtures._catalog(where)
    sql = f"""
        UPDATE games SET available_at='{raw_end.isoformat()}';
        INSERT INTO player_crosswalk SELECT * REPLACE ('BAL' AS team, '00-0000002' AS player_id)
            FROM player_crosswalk;
    """
    if shifted_kickoff:
        sql += f"UPDATE games SET kickoff_utc='{shifted_kickoff}' WHERE game_id='target';"
    _change_catalog(where, sql)
    audit = where / "audit.csv"
    audit.write_text("synthetic\n", encoding="utf-8")
    manifest = where / "build_manifest.json"
    data = json.loads(manifest.read_text())
    data.update(
        built_at_utc=(raw_end + timedelta(minutes=1)).isoformat(),
        finished_at_utc=(raw_end + timedelta(minutes=build_delay)).isoformat(),
        source_manifest_sha256=sha256(raw_path), tables={},
        audit_csv={"path": audit.name, "sha256": sha256(audit)},
    )
    _save(manifest, data)
    return where, data


class PregamePilotTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.reference = self.root / "reference"
        fixtures._catalog(self.reference)
        self.official = _official(self.root / "official", "2026-10-01T16:00:00-04:00")

    def prepare(self, label="plan"):
        target = self.root / label
        plan_window(self.reference, self.official, 2026, 6, ["target"], target,
                    lead_minutes=60, clock=lambda: utc("2026-10-01T18:15:00Z"))
        return target

    def sealed(self, plan, name, *, start=START, finish=END, seal=SEAL, published=None,
               shift=None, build_delay=5, for_actions=False):
        folder = self.root / name
        clock_times = iter([utc(start), utc(seal)])
        with patch("nfl_betting.pregame_capture.collect",
                   side_effect=lambda *args: _collected(*args, finish=finish, published=published)) as loader:
            with patch("nfl_betting.pregame_capture.build",
                       side_effect=lambda *args: _built(*args, shifted_kickoff=shift, build_delay=build_delay)) as builder:
                index, digest = capture_window(
                    plan, folder, authorized=True, for_actions=for_actions, clock=lambda: next(clock_times)
                )
        return folder, index, digest, loader.call_count, builder.call_count

    def test_eligible_before_cutoff_and_offline_restore_without_overwrite(self):
        plan = self.prepare()
        folder, index, digest, collects, builds = self.sealed(plan, "eligible")
        self.assertEqual((collects, builds), (1, 1))
        receipt, = index["games"].values()
        self.assertEqual((receipt["status"], receipt["reason"]), ("ELIGIBLE", None))
        self.assertEqual(receipt["capture_finished_at_utc"], "2026-10-01T18:40:00+00:00")
        self.assertEqual(receipt["kickoff_sao_paulo"], "2026-10-01T17:00:00-03:00")
        self.assertEqual(receipt["decision"], "NO_BET")
        self.assertEqual(verify_bundle(folder, digest), index)
        restored = self.root / "restored"
        self.assertEqual(restore_bundle(folder, digest, restored), index)
        with self.assertRaises(FileExistsError):
            restore_bundle(folder, digest, restored)
        with patch("nfl_betting.pregame_capture.collect") as loader:
            with self.assertRaises(FileExistsError):
                capture_window(plan, folder, authorized=True)
            loader.assert_not_called()
        self.assertEqual(sha256(folder / "index.json"), digest)

    def test_actions_late_start_and_capture_after_cutoff(self):
        plan = self.prepare()
        folder, index, digest, collects, builds = self.sealed(
            plan, "late-job", start="2026-10-01T19:00:01Z", seal="2026-10-01T19:00:02Z", for_actions=True
        )
        self.assertEqual((collects, builds), (0, 0))
        self.assertEqual(next(iter(index["games"].values()))["reason"], "LATE_START")
        self.assertEqual(verify_bundle(folder, digest), index)
        folder, index, digest, collects, builds = self.sealed(
            plan, "late-download", finish="2026-10-01T19:01:00Z", seal="2026-10-01T19:02:00Z"
        )
        self.assertEqual((collects, builds), (1, 0))
        receipt, = index["games"].values()
        self.assertEqual(receipt["reason"], "LATE_CAPTURE")
        self.assertEqual(receipt["capture_finished_at_utc"], "2026-10-01T19:01:00+00:00")
        self.assertTrue(receipt["inputs"])
        self.assertEqual(verify_bundle(folder, digest), index)

    def test_late_published_source_late_build_and_late_seal(self):
        plan = self.prepare()
        cases = [
            ("late-release", {"published": "2026-10-01T19:01:00Z"}, "LATE_OR_INCONSISTENT_PUBLICATION"),
            ("late-build", {"seal": "2026-10-01T19:15:00Z", "build_delay": 25}, "LATE_BUILD"),
            ("late-seal", {"seal": "2026-10-01T19:05:00Z"}, "LATE_SEAL"),
        ]
        for name, options, reason in cases:
            with self.subTest(name):
                folder, index, digest, *_ = self.sealed(plan, name, **options)
                self.assertEqual(next(iter(index["games"].values()))["reason"], reason)
                self.assertEqual(verify_bundle(folder, digest), index)

    def test_advanced_delayed_and_unresolved_kickoff(self):
        plan = self.prepare()
        for name, changed in (
            ("advanced", "2026-10-01T19:30:00Z"), ("delayed", "2026-10-01T21:00:00Z"),
        ):
            _, index, _, _, _ = self.sealed(plan, name, shift=changed)
            self.assertEqual(next(iter(index["games"].values()))["reason"], "KICKOFF_CONFLICT")
        wrong = _official(self.root / "conflicting-official", "2026-10-01T19:00:00Z")
        with self.assertRaisesRegex(ValueError, "KICKOFF_CONFLICT_OR_UNVERIFIED"):
            plan_window(self.reference, wrong, 2026, 6, ["target"], self.root / "conflict",
                        lead_minutes=60, clock=lambda: utc("2026-10-01T18:15:00Z"))

    def test_dst_and_default_lead(self):
        after_dst = _official(self.root / "after-dst", "2026-11-05T15:00:00-05:00")
        _change_catalog(self.reference, "UPDATE games SET kickoff_utc='2026-11-05T20:00:00Z' WHERE game_id='target'")
        plan = plan_window(self.reference, after_dst, 2026, 6, ["target"], self.root / "november-plan",
                           clock=lambda: utc("2026-11-05T17:30:00Z"))
        game, = plan["games"]
        self.assertEqual(game["kickoff_sao_paulo"], "2026-11-05T17:00:00-03:00")
        self.assertEqual(game["cutoff_utc"], "2026-11-05T17:45:00+00:00")

    def test_tamper_missing_and_expired_artifact(self):
        folder, _, digest, *_ = self.sealed(self.prepare(), "eligible")
        restore = self.root / "safe-local-copy"
        restore_bundle(folder, digest, restore)
        with self.assertRaisesRegex(ValueError, "UNAVAILABLE_OR_EXPIRED"):
            restore_bundle(self.root / "expired", digest, self.root / "invalid")
        with self.assertRaisesRegex(ValueError, "index digest"):
            verify_bundle(folder, "0" * 64)
        body = folder / "archive/raw/schedules.body"
        body.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            verify_bundle(folder, digest)
        body.unlink()
        with self.assertRaisesRegex(ValueError, "Missing or unexpected"):
            verify_bundle(folder, digest)
        self.assertTrue(verify_bundle(restore, digest)["games"])

    def test_backtest_pilot_facts_are_invariant_to_future_results(self):
        folder, _, digest, *_ = self.sealed(self.prepare(), "eligible")
        labels_a, labels_b = self.root / "labels-a", self.root / "labels-b"
        fixtures._catalog(labels_a, label=7)
        fixtures._catalog(labels_b, label=0)
        def replay(labels):
            return backtest(STRICT, 2026, "2026-10-03T00:00:00Z", [], [labels],
                            weeks=[6], lead_minutes=60, pilot_archives=[(folder, digest)])
        before, after = replay(labels_a), replay(labels_b)
        self.assertEqual(before["projections"], after["projections"])
        self.assertTrue(before["projections"])
        self.assertNotEqual(before["paired_outcomes"], after["paired_outcomes"])
        self.assertEqual(before["counts"]["games_schedule_eligible"], 1)
        self.assertTrue(before["inventoried_games"][0]["pilot_receipt"])
        self.assertNotIn("target", {obs["game_id"] for row in before["projections"] for obs in row["observations"]})
        with self.assertRaisesRegex(ValueError, "policies differ"):
            backtest(STRICT, 2026, "2026-10-03T00:00:00Z", [], [labels_a],
                     lead_minutes=135, pilot_archives=[(folder, digest)])


if __name__ == "__main__":
    unittest.main()
