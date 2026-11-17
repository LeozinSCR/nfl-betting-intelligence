"""Minimal preview contracts: temporal exclusion, thresholds and financial gates."""

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from nfl_betting.mnf_preview import GAME, classify, describe, eligible_games

ROOT = Path(__file__).resolve().parents[1]


class PreviewTests(unittest.TestCase):
    def test_alt_line_inclusive_and_null_not_zero(self):
        over = describe([69, 70, 71, None], 70, ">")
        alt = describe([69, 70, 71, None], 70, ">=")
        self.assertEqual((over["n"], over["hits"], over["missing"]), (3, 1, 1))
        self.assertEqual(alt["hits"], 2)
        self.assertIsNone(describe([None])["mean"])

    def test_calendar_excludes_target_future_and_late_available(self):
        t = datetime(2026, 11, 17, tzinfo=timezone.utc)

        def game(id, start, available, result=True):
            return dict(
                game_id=id, kickoff_utc=start, available_at=available, has_result=result
            )

        past = t - timedelta(days=1)
        rows = [
            game("prior", past, past),
            game(GAME, past, past),
            game("future", t + timedelta(hours=1), past),
            game("late", past, t + timedelta(seconds=1)),
            game("unfinished", past, past, False),
        ]
        self.assertEqual([g["game_id"] for g in eligible_games(rows, t)], ["prior"])

    def test_unknown_and_inactive_never_favorable(self):
        for status in (
            "PENDENTE",
            "UNKNOWN",
            "ROSTER_ONLY",
            "INACTIVE_OFFICIAL",
            "IR_OFFICIAL",
        ):
            self.assertNotEqual(classify(status, 10, 10), "FAVORÁVEL")
        self.assertEqual(classify("STARTER_OFFICIAL", 10, 10, risk=True), "NEUTRO")
        self.assertEqual(
            classify("ACTIVE_EXPLICIT_OFFICIAL", 2, 2), "DADOS INSUFICIENTES"
        )

    def test_published_report_cutoff_and_no_execution_authorization(self):
        data = json.loads((ROOT / "reports/MNF_2026_11_16_EVIDENCE.json").read_text())
        t = datetime.fromisoformat(data["cutoff"])
        self.assertLess(t, datetime.fromisoformat(data["game"]["kickoff_utc"]))
        self.assertNotIn(GAME, data["past_game_ids"])
        self.assertFalse(data["financial_approved"])
        self.assertFalse(data["statistical_approved"])
        self.assertEqual(data["decision"], "NO_BET")
        self.assertEqual(data["budget"]["total"], 0)
        for player in data["players"].values():
            self.assertTrue(
                all(
                    w["game_id"] != GAME and w["week"] < 10
                    for w in player["historical_rows"]
                )
            )
        for source in data["pregame_observations"]["sources"].values():
            self.assertLessEqual(
                datetime.fromisoformat(source["observed_no_later_than"]), t
            )
        brissett = data["players"]["00-0033119"]
        self.assertFalse(any(w["team"] == "BAL" for w in brissett["historical_rows"]))
        for row in data["props"]:
            if row["player_id"] == "00-0033119":
                self.assertEqual(row["distributions"]["last3"]["n"], 0)
            if row["player_id"] in ("00-0039915", "00-0034796"):
                self.assertEqual(row["classification"], "EVITAR")
            if row["source"]:
                self.assertIsNone(row["valid_until"])
                self.assertEqual(row["bookmaker"], "DraftKings")
            else:
                self.assertEqual(row["line_kind"], "HYPOTHETICAL_SCENARIO")
                self.assertIsNone(row["american_odds"])
        self.assertFalse(data["stake"]["player_props_demonstrated"])

    def test_csv_and_markdown_match_evidence_without_clipped_rows(self):
        data = json.loads((ROOT / "reports/MNF_2026_11_16_EVIDENCE.json").read_text())
        for file, key in [("PLAYER_PROPS", "props"), ("ANYTIME_TD", "anytime_td")]:
            with (ROOT / f"reports/MNF_2026_11_16_{file}.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(data[key]))
            self.assertTrue(all(r["decision"] == "NO_BET" for r in rows))
        lines = (ROOT / "reports/MNF_2026_11_16_PREVIEW.md").read_text().splitlines()
        for previous, current in zip(lines, lines[1:]):
            if current.startswith("|---"):
                self.assertEqual(previous.count("|"), current.count("|"))
        self.assertIn("HIPOTÉTICA", "\n".join(lines))
        self.assertIn("Sem probabilidade calibrada", "\n".join(lines))
