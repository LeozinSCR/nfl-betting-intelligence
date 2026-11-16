"""Synthetic offline fixtures: no selections or prices here are recommendations."""
from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import math
import unittest

from nfl_betting.rules import (
    expected_value, implied_probability, validate_best_parlay, validate_td_parlay,
    validate_budget, validate_decimal_odds, validate_joint_probability,
    validate_probability, validate_quote,
)

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
DAY = date(2026, 11, 16)


def evidence(minutes=60):
    return {"source_url": "https://fixtures.invalid/evidence", "checked_at": NOW.isoformat(),
            "valid_until": (NOW + timedelta(minutes=minutes)).isoformat()}


def schedule(count=4):
    return [dict(evidence(), game_id=f"game-{i}", kickoff=(NOW + timedelta(hours=8)).isoformat(),
                 home_team=f"HOME-{i}", away_team=f"AWAY-{i}") for i in range(count)]


def leg(game, player, market="receptions"):
    return {"game_id": f"game-{game}", "player_id": f"player-{game}-{player}",
            "team": f"HOME-{game}", "market": market,
            "side": "yes" if market == "anytime_td" else "over",
            "line": None if market == "anytime_td" else 2.5,
            "is_player_prop": True, "injury_status": "HEALTHY", "team_stable": True,
            "player_availability": dict(evidence(), status="ACTIVE"),
            "market_availability": dict(evidence(minutes=3), available=True)}


def best():
    return [leg(g, p) for g in range(4) for p in range(2)]


def quote(selection=None):
    selection = selection or leg(0, 0)
    return {**{k: selection[k] for k in ("game_id", "player_id", "market", "side", "line")},
            "provider": "synthetic-fixture", "bookmaker": "synthetic-fixture",
            "source_url": "https://fixtures.invalid/quote", "selection_id": "fixture-id",
            "observed_at": NOW.isoformat(), "valid_until": (NOW + timedelta(minutes=3)).isoformat(),
            "decimal_odds": 2.0, "available": True}


class RuleTests(unittest.TestCase):
    def check_best(self, legs=None, **extra):
        context = dict(schedule=schedule(), slate_date=DAY, as_of=NOW)
        context.update(extra)
        return validate_best_parlay(best() if legs is None else legs, **context)

    def codes(self, result):
        return {issue.code for issue in result.issues}

    def test_minimum_and_approval_separation(self):
        result = self.check_best(stake=Decimal("35"))
        self.assertTrue(result.valid)
        self.assertFalse(result.statistical_approved)
        self.assertFalse(result.financial_approved)
        self.assertEqual(result.decision, "NO_BET")
        with self.assertRaises(TypeError):
            bool(result)
        self.assertFalse(self.check_best(best()[:-1]).valid)
        self.assertIsInstance(asdict(result), dict)

    def test_every_game_needs_two_and_at_least_four_games(self):
        legs = best()
        legs[-1] = leg(0, 9)
        self.assertIn("MIN_TWO_PER_GAME", self.codes(self.check_best(legs)))
        legs[-2] = leg(0, 8)
        self.assertIn("MIN_FOUR_GAMES", self.codes(self.check_best(legs)))

    def test_extra_games_allowed_with_two_each(self):
        self.assertTrue(self.check_best(best() + [leg(4, 0), leg(4, 1)], schedule=schedule(5)).valid)

    def test_malformed_inputs_are_structured(self):
        for bad in (None, 1, "legs", [None] * 8, [{}] * 8):
            with self.subTest(bad=bad):
                self.assertFalse(self.check_best(bad if bad is not None else 42).valid)
        for key in ("game_id", "player_id", "market", "side"):
            a = best()
            a[0][key] = []
            self.assertIn("MISSING_FIELD", self.codes(self.check_best(a)))

    def test_duplicates_conflicts_and_same_player_different_markets(self):
        a = best(); a[1] = deepcopy(a[0])
        self.assertIn("DUPLICATE_SELECTION", self.codes(self.check_best(a)))
        a[1]["side"] = "under"
        self.assertIn("REDUNDANT_PLAYER_MARKET", self.codes(self.check_best(a)))
        a[1]["market"] = "rec_yards"
        self.assertTrue(self.check_best(a).valid)

    def test_out_ir_unknown_and_unavailable_players_block(self):
        for field, value in (("injury_status", "out"), ("injury_status", "IR"),
                             ("injury_status", "UNKNOWN"), ("injury_status", None)):
            a = best(); a[0][field] = value
            self.assertIn("INELIGIBLE_PLAYER", self.codes(self.check_best(a)))
        for value in ("OUT", "IR", "UNKNOWN", None):
            a = best(); a[0]["player_availability"]["status"] = value
            self.assertIn("PLAYER_UNAVAILABLE", self.codes(self.check_best(a)))

    def test_questionable_requires_active_evidence(self):
        a = best(); a[0]["injury_status"] = "QUESTIONABLE"
        self.assertTrue(self.check_best(a).valid)
        self.assertTrue(self.check_best(a).warnings)
        a[0]["player_availability"]["status"] = "UNKNOWN"
        self.assertFalse(self.check_best(a).valid)

    def test_market_missing_unavailable_and_wrong_type_block(self):
        for value in (False, None, "True", 1):
            a = best(); a[0]["market_availability"]["available"] = value
            self.assertIn("MARKET_UNAVAILABLE", self.codes(self.check_best(a)))
        a = best(); a[0]["market"] = "team_total"
        self.assertIn("PLAYER_PROPS_ONLY", self.codes(self.check_best(a)))
        a = best(); a[0]["is_player_prop"] = "true"
        self.assertFalse(self.check_best(a).valid)

    def test_no_odds_required_for_shortlist_but_required_mode_fails(self):
        self.assertTrue(self.check_best().valid)
        self.assertFalse(self.check_best(require_quotes=True).valid)
        a = best()
        for item in a:
            item["quote"] = quote(item)
        self.assertTrue(self.check_best(a, require_quotes=True).valid)
        a[0]["quote"]["player_id"] = "other-player"
        self.assertIn("QUOTE_MISMATCH", self.codes(self.check_best(a)))

    def test_invalid_supplied_quote_blocks_even_shortlist_mode(self):
        a = best(); a[0]["quote"] = quote(a[0]); a[0]["quote"]["source_url"] = ""
        self.assertIn("MISSING_ORIGIN", self.codes(self.check_best(a)))

    def test_team_instability_applies_only_to_selected_team(self):
        a = best(); a[0]["team_stable"] = False
        self.assertIn("TEAM_INSTABILITY", self.codes(self.check_best(a)))
        a[0]["team"] = "AWAY-0"; a[0]["team_stable"] = True
        self.assertTrue(self.check_best(a).valid)
        a[0]["team"] = "NOT_IN_GAME"
        self.assertIn("TEAM_GAME_MISMATCH", self.codes(self.check_best(a)))

    def test_evidence_origin_time_and_freshness(self):
        for field in ("player_availability", "market_availability"):
            for key, value in (("source_url", ""), ("source_url", "http://example.invalid"),
                               ("checked_at", None), ("checked_at", "2026-11-16T12:00:00"),
                               ("checked_at", (NOW + timedelta(seconds=1)).isoformat()),
                               ("valid_until", NOW.isoformat()),
                               ("checked_at", (NOW - timedelta(days=8)).isoformat())):
                with self.subTest(field=field, key=key):
                    a = best(); a[0][field][key] = value
                    self.assertFalse(self.check_best(a).valid)

    def test_schedule_date_timezone_game_and_kickoff(self):
        self.assertIn("MISSING_SCHEDULE", self.codes(self.check_best(schedule=None)))
        self.assertFalse(self.check_best(slate_date=None).valid)
        self.assertFalse(self.check_best(timezone_name="Invalid/Zone").valid)
        self.assertFalse(self.check_best(as_of=NOW.replace(tzinfo=None)).valid)
        s = schedule(); s[0]["kickoff"] = NOW.isoformat()
        self.assertIn("GAME_STARTED", self.codes(self.check_best(schedule=s)))
        a = best(); a[0]["game_id"] = "unknown"
        self.assertIn("GAME_NOT_IN_SLATE", self.codes(self.check_best(a)))
        s = schedule(); s[0]["kickoff"] = (NOW + timedelta(days=1)).isoformat()
        self.assertFalse(self.check_best(schedule=s).valid)
        s = schedule(); s.append(deepcopy(s[0]))
        self.assertFalse(self.check_best(schedule=s).valid)

    def test_sao_paulo_day_boundary(self):
        s = schedule(); s[0]["kickoff"] = "2026-11-17T01:00:00Z"
        self.assertTrue(self.check_best(schedule=s).valid)
        s[0]["kickoff"] = "2026-11-17T04:00:00Z"
        self.assertFalse(self.check_best(schedule=s).valid)

    def test_line_and_probability_validation(self):
        for value in (math.nan, math.inf, -1, None, True, "2.5"):
            a = best(); a[0]["line"] = value
            self.assertIn("INVALID_SELECTION", self.codes(self.check_best(a)))
        for value in (math.nan, math.inf, -0.01, 1.01, True):
            a = best(); a[0]["probability"] = value
            self.assertIn("INVALID_PROBABILITY", self.codes(self.check_best(a)))
        a = best()
        for item in a:
            item["probability"] = .5
        self.assertIn("INVALID_JOINT_PROBABILITY", self.codes(self.check_best(a, joint_probability=.6)))
        self.assertTrue(self.check_best(a, joint_probability=.01).valid)
        self.assertIn("INVALID_JOINT_PROBABILITY", self.codes(self.check_best(joint_probability=.1)))

    def test_td_multiple_and_single_game(self):
        four = [leg(g, p, "anytime_td") for g in range(2) for p in range(2)]
        args = dict(schedule=schedule(2), slate_date=DAY, as_of=NOW, stake=15)
        self.assertTrue(validate_td_parlay(four, **args).valid)
        self.assertFalse(validate_td_parlay(four[:-1], **args).valid)
        two = [leg(0, p, "anytime_td") for p in range(2)]
        self.assertTrue(validate_td_parlay(two, schedule=schedule(1), slate_date=DAY, as_of=NOW).valid)
        self.assertFalse(validate_td_parlay(two[:1], schedule=schedule(1), slate_date=DAY, as_of=NOW).valid)
        self.assertFalse(validate_td_parlay(two * 2, **args).valid)
        four[0]["market_availability"]["available"] = False
        self.assertFalse(validate_td_parlay(four, **args).valid)

    def test_td_preferred_distribution_is_warning_not_rigid_cap(self):
        legs = [leg(0, p, "anytime_td") for p in range(3)] + [leg(1, 0, "anytime_td")]
        result = validate_td_parlay(legs, schedule=schedule(2), slate_date=DAY, as_of=NOW)
        self.assertTrue(result.valid)
        self.assertTrue(any("DISTRIBUTION_REVIEW" in w for w in result.warnings))
        legs[0]["market"] = "receptions"
        self.assertIn("TD_MARKET_ONLY", self.codes(validate_td_parlay(legs, schedule=schedule(2), slate_date=DAY, as_of=NOW)))

    def test_budget_caps_and_no_bet_zero(self):
        for a, b in ((0, 0), (35, 15), (10, 0), (Decimal("34.99"), 15)):
            self.assertTrue(validate_budget(a, b).valid)
        for a, b in ((35.01, 15), (35, 15.01), (-1, 0), (True, 0), ("NaN", 0), (1.001, 0), ("Infinity", 0)):
            self.assertFalse(validate_budget(a, b).valid)
        self.assertFalse(self.check_best(stake=36).valid)


class NumericAndQuoteTests(unittest.TestCase):
    def test_probability_and_odds_nonfinite_and_types(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, None, "0.5", [], Decimal("NaN")):
            for fn in (validate_probability, validate_decimal_odds):
                with self.subTest(value=value, fn=fn), self.assertRaises(ValueError):
                    fn(value)
        for value in (0, 1, -2):
            with self.assertRaises(ValueError):
                implied_probability(value)
        self.assertEqual(implied_probability(2), .5)
        self.assertEqual(validate_probability(0), 0)
        self.assertEqual(validate_probability(1), 1)

    def test_joint_bounds_reject_original_audit_violation_without_mutation(self):
        a, b, joint = .9792964888420533, 2.5331716052168143e-10, 9.680823682207268e-06
        with self.assertRaises(ValueError):
            validate_joint_probability(joint, [a, b])
        self.assertEqual(joint, 9.680823682207268e-06)
        self.assertEqual(validate_joint_probability(.25, [.5, .5]), .25)
        with self.assertRaises(ValueError):
            validate_joint_probability(.1, [.9, .9])
        with self.assertRaises(ValueError):
            validate_joint_probability(.1, [])

    def test_quote_origin_time_availability_and_binding(self):
        self.assertTrue(validate_quote(quote(), as_of=NOW, leg=leg(0, 0)).valid)
        for key, value in (("source_url", ""), ("provider", ""), ("bookmaker", ""),
                           ("selection_id", ""), ("observed_at", None), ("market", []),
                           ("observed_at", (NOW + timedelta(seconds=1)).isoformat()),
                           ("valid_until", NOW.isoformat()), ("decimal_odds", math.inf),
                           ("decimal_odds", "2.0"), ("available", False),
                           ("observed_at", (NOW - timedelta(minutes=6)).isoformat())):
            q = quote(); q[key] = value
            self.assertFalse(validate_quote(q, as_of=NOW).valid, key)
        self.assertFalse(validate_quote(None, as_of=NOW).valid)
        self.assertFalse(validate_quote(quote(), as_of=NOW, leg=leg(1, 0)).valid)

    def test_ev_requires_valid_quote_and_explicit_push_assumption(self):
        result = expected_value(.6, quote(), push_probability=0, as_of=NOW)
        self.assertAlmostEqual(result.value_per_unit, .2)
        self.assertFalse(result.financial_approved)
        self.assertFalse(result.statistical_approved)
        self.assertEqual(result.decision, "NO_BET")
        self.assertAlmostEqual(expected_value(.5, quote(), push_probability=.1, as_of=NOW).value_per_unit, .1)
        for q in (1.8, None, dict(quote(), decimal_odds=-2)):
            with self.assertRaises(ValueError):
                expected_value(.7, q, push_probability=0, as_of=NOW)
        with self.assertRaises(ValueError):
            expected_value(.9, quote(), push_probability=.2, as_of=NOW)
        with self.assertRaises(TypeError):
            expected_value(.7, quote(), calibrated=True, price_verified=True)


if __name__ == "__main__":
    unittest.main()
