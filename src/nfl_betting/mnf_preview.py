"""One-game descriptive MNF research report. No fitting, probability or execution."""

import argparse
import csv
from datetime import datetime, timezone
import json
import statistics
from pathlib import Path

import polars as pl

from .archive import check_declared
from .canonical import open_database
from .provenance import code_identity, sha256
from .research import aware, query
from .rules import validate_budget, validate_decimal_odds

GAME = "2026_10_LAC_BAL"
TEAMS = ("LAC", "BAL")
CANDIDATES = {
    "00-0036355": ("LAC", "QB"),
    "00-0033119": ("BAL", "QB"),
    "00-0034796": ("BAL", "QB"),
    "00-0032764": ("BAL", "RB"),
    "00-0034975": ("BAL", "RB"),
    "00-0039064": ("BAL", "WR"),
    "00-0036550": ("BAL", "WR"),
    "00-0040870": ("BAL", "WR"),
    "00-0039792": ("BAL", "WR"),
    "00-0034753": ("BAL", "TE"),
    "00-0040887": ("BAL", "TE"),
    "00-0040666": ("LAC", "RB"),
    "00-0039391": ("LAC", "RB"),
    "00-0038454": ("LAC", "RB"),
    "00-0038544": ("LAC", "WR"),
    "00-0040727": ("LAC", "WR"),
    "00-0040184": ("LAC", "WR"),
    "00-0038573": ("LAC", "WR"),
    "00-0039915": ("LAC", "WR"),
    "00-0040189": ("LAC", "TE"),
    "00-0038046": ("LAC", "TE"),
    "00-0033885": ("LAC", "TE"),
}
MARKET_FIELDS = {
    "receptions": "receptions",
    "rec_yards": "receiving_yards",
    "rush_yards": "rushing_yards",
    "pass_yards": "passing_yards",
    "pass_attempts": "attempts",
    "completions": "completions",
}
DEFAULT_LINES = {
    "receptions": 2.5,
    "rec_yards": 24.5,
    "rush_yards": 24.5,
    "pass_yards": 199.5,
    "pass_attempts": 29.5,
    "completions": 18.5,
}


def records(con, sql, params=None):
    cur = con.execute(sql, params or [])
    return [dict(zip([x[0] for x in cur.description], row)) for row in cur.fetchall()]


def describe(values, line=None, comparator=">"):
    """Observed conditional distribution, never a forecast probability."""
    clean = [v for v in values if v is not None]
    result = {
        "n": len(clean),
        "missing": len(values) - len(clean),
        "values": clean,
        "mean": statistics.mean(clean) if clean else None,
        "median": statistics.median(clean) if clean else None,
        "min": min(clean) if clean else None,
        "max": max(clean) if clean else None,
    }
    if line is not None:
        if comparator not in (">", ">="):
            raise ValueError("Explicit supported threshold comparator required")
        result["hits"] = sum(
            v > line if comparator == ">" else v >= line for v in clean
        )
        result["observed_frequency"] = result["hits"] / len(clean) if clean else None
    return result


def classify(status, n, hits, risk=False):
    if status in ("INACTIVE_OFFICIAL", "IR_OFFICIAL"):
        return "EVITAR"
    if (
        status
        not in {
            "STARTER_OFFICIAL",
            "ACTIVE_EXPLICIT_OFFICIAL",
            "ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES",
        }
        or n < 3
    ):
        return "DADOS INSUFICIENTES"
    # Frozen transparent descriptive rubric, not a fitted scoring model.
    if risk:
        return "NEUTRO"
    if n >= 5 and hits / n >= 0.7:
        return "FAVORÁVEL"
    return "NEUTRO"


def eligible_games(games, cutoff, target=GAME):
    return [
        g
        for g in games
        if g["game_id"] != target
        and g["has_result"]
        and aware(g["kickoff_utc"]) < cutoff
        and aware(g["available_at"]) <= cutoff
    ]


def build_report(folder, observations, stake_folder, out, generated_at=None):
    out = Path(out)
    names = [
        "MNF_2026_11_16_PREVIEW.md",
        "MNF_2026_11_16_PLAYER_PROPS.csv",
        "MNF_2026_11_16_ANYTIME_TD.csv",
        "MNF_2026_11_16_EVIDENCE.json",
    ]
    if any((out / name).exists() for name in names):
        raise FileExistsError(
            "Preserve previous preview; choose a new output directory"
        )
    config = json.loads(Path(observations).read_text())
    cutoff = aware(config["cutoff"])
    generated_at = generated_at or datetime.now(timezone.utc)
    for source in config["sources"].values():
        if aware(source["observed_no_later_than"]) > cutoff:
            raise ValueError("Source collected after cutoff")
        if source.get("published_at") and aware(source["published_at"]) > cutoff:
            raise ValueError("Source published after cutoff")
    folder = Path(folder)
    manifest = json.loads((folder / "build_manifest.json").read_text())
    if aware(manifest["finished_at_utc"]) > cutoff:
        raise ValueError("Build not available by cutoff")
    raw = Path(manifest["source_snapshot_path"])
    raw_manifest = json.loads((raw / "manifest.json").read_text())
    if sha256(raw / "manifest.json") != manifest["source_manifest_sha256"]:
        raise ValueError("Source manifest mismatch")
    for entry in raw_manifest["sources"].values():
        if entry.get("status") == "OK":
            check_declared(raw, entry)
    receipt = query(folder, "games", season=2026, week=10, team="LAC", cutoff=cutoff)
    if len(receipt["records"]) != 1 or receipt["records"][0]["game_id"] != GAME:
        raise ValueError("Target calendar mismatch")
    target = receipt["records"][0]
    kickoff = aware(target["kickoff_utc"])
    if cutoff >= kickoff:
        raise ValueError(
            "Decision cutoff must be pregame; no pregame classification allowed"
        )
    mode = (
        "PRE_GAME_RESEARCH"
        if generated_at < kickoff
        else "FROZEN_PREKICKOFF_DATA_PUBLISHED_AFTER_KICKOFF"
    )
    with open_database(folder) as con:
        games = records(
            con,
            "select * from games where season=2026 and season_type='REG' and available_at<=?",
            [cutoff],
        )
        past = eligible_games(games, cutoff)
        ids = {g["game_id"] for g in past}
        if GAME in ids:
            raise ValueError("Target leakage")
        con.register("preview_games", pl.DataFrame(past).to_arrow())
        for source in ("pbp", "player_stats"):
            con.register(
                "raw_" + source,
                pl.read_parquet(
                    raw / raw_manifest["sources"][source]["path"]
                ).to_arrow(),
            )
        con.execute(
            "CREATE TEMP TABLE clean_pbp AS SELECT p.* FROM raw_pbp p JOIN preview_games g USING(game_id) WHERE p.season=2026 AND p.season_type='REG' AND coalesce(p.two_point_attempt,0)=0 AND coalesce(p.play_deleted,0)=0 AND p.play_type IN ('pass','run') AND coalesce(p.qb_kneel,0)=0 AND coalesce(p.qb_spike,0)=0"
        )
        team_games = {
            t: sorted(
                [g for g in past if t in (g["home_team"], g["away_team"])],
                key=lambda g: g["kickoff_utc"],
            )
            for t in TEAMS
        }
        team_metrics = []
        for team in TEAMS:
            for window, size in [("season", None), ("last5", 5), ("last3", 3)]:
                gs = team_games[team][-size:] if size else team_games[team]
                con.register(
                    "window_games",
                    pl.DataFrame({"game_id": [g["game_id"] for g in gs]}).to_arrow(),
                )
                row = records(
                    con,
                    """SELECT count(*) n_plays,avg(epa) epa_play,
                    count(epa) n_epa,avg(epa) FILTER(WHERE qb_dropback=1) epa_dropback,
                    avg(epa) FILTER(WHERE play_type='run' AND coalesce(qb_scramble,0)=0) epa_rush,
                    avg(CASE WHEN epa>0 THEN 1.0 WHEN epa IS NOT NULL THEN 0.0 END) success_rate,
                    avg(CASE WHEN (play_type='pass' AND yards_gained>=20) OR (play_type='run' AND yards_gained>=10) THEN 1.0 ELSE 0.0 END) explosive_rate,
                    avg(CASE WHEN qb_dropback=1 THEN 1.0 ELSE 0.0 END) FILTER(WHERE qtr<=3 AND abs(score_differential)<=7 AND down IN (1,2)) neutral_dropback_rate,
                    count(*) FILTER(WHERE qtr<=3 AND abs(score_differential)<=7 AND down IN (1,2)) neutral_n,
                    sum(pass_attempt) pass_attempts_including_sacks_flag,sum(complete_pass) completions,
                    count(*) FILTER(WHERE play_type='pass' AND coalesce(sack,0)=0) pass_attempts,
                    count(*) FILTER(WHERE play_type='run') rush_plays,
                    sum(sack) sacks, sum(qb_hit) qb_hits,
                    count(*) FILTER(WHERE qb_dropback=1) dropbacks,
                    count(*) FILTER(WHERE yardline_100<=20) redzone_plays,
                    avg(cpoe) FILTER(WHERE play_type='pass' AND coalesce(sack,0)=0) cpoe
                    FROM clean_pbp JOIN window_games USING(game_id) WHERE posteam=?""",
                    [team],
                )[0]
                pace = records(
                    con,
                    """WITH ordered AS (
                    SELECT p.*,lead(posteam) OVER w next_team,lead(qtr) OVER w next_qtr,
                    lead(game_seconds_remaining) OVER w next_clock,
                    lead(play_type) OVER w next_type,lead(drive) OVER w next_drive
                    FROM raw_pbp p JOIN window_games USING(game_id)
                    WINDOW w AS (PARTITION BY game_id ORDER BY play_id))
                    SELECT median(game_seconds_remaining-next_clock) pace_seconds,
                    count(*) pace_pairs FROM ordered WHERE posteam=? AND next_team=posteam
                    AND next_qtr=qtr AND next_drive=drive AND play_type IN ('pass','run')
                    AND next_type IN ('pass','run') AND coalesce(two_point_attempt,0)=0
                    AND coalesce(play_deleted,0)=0 AND game_seconds_remaining-next_clock BETWEEN 1 AND 60""",
                    [team],
                )[0]
                row["targets"] = records(
                    con,
                    "SELECT count(*) targets FROM offensive_opportunities o JOIN window_games USING(game_id) WHERE o.team=? AND o.classification='STANDARD' AND o.opportunity_type='TARGET' AND o.available_at<=?",
                    [team, cutoff],
                )[0]["targets"]
                row.update(pace)
                row.update(
                    team=team,
                    window=window,
                    games=len(gs),
                    weeks=[g["week"] for g in gs],
                )
                team_metrics.append(row)
        # Defense by position includes rushing and receiving, unlike receiving-only canonical DVP.
        defense = records(
            con,
            '''SELECT o.defense,coalesce(o.position,'UNKNOWN') AS "position",
            count(DISTINCT o.game_id) observed_games,
            count(*) FILTER(WHERE o.opportunity_type='TARGET') targets,
            sum(o.receptions) FILTER(WHERE o.opportunity_type='TARGET') receptions,
            sum(o.yards) FILTER(WHERE o.opportunity_type IN ('TARGET','LATERAL_RECEIVE')) receiving_yards,
            count(*) FILTER(WHERE o.opportunity_type='RUSH') carries,
            sum(o.yards) FILTER(WHERE o.opportunity_type IN ('RUSH','LATERAL_RUSH')) rushing_yards,
            sum(o.offensive_td) touchdowns
            FROM offensive_opportunities o JOIN preview_games g USING(game_id)
            WHERE o.defense IN ('LAC','BAL') AND o.classification IN ('STANDARD','LATERAL_TOUCH')
            AND o.available_at<=? GROUP BY ALL ORDER BY o.defense,"position"''',
            [cutoff],
        )
        passing_defense = records(
            con,
            """SELECT defteam defense,count(DISTINCT game_id) games,
            avg(epa) epa_per_dropback_allowed,sum(passing_yards) passing_yards_allowed,
            sum(sack) sacks,count(*) dropbacks,sum(qb_hit) qb_hits
            FROM clean_pbp WHERE defteam IN ('LAC','BAL') AND qb_dropback=1 GROUP BY defteam""",
        )
        pw = records(
            con,
            "SELECT w.* FROM player_week w JOIN preview_games g USING(game_id) WHERE w.available_at<=?",
            [cutoff],
        )
        stats = records(
            con,
            "SELECT s.* FROM raw_player_stats s JOIN preview_games g USING(game_id) WHERE s.season=2026 AND s.season_type='REG'",
        )
        stats_index = {
            (s["player_id"], s["game_id"]): s for s in stats if s["player_id"]
        }
        current = records(
            con,
            "SELECT * FROM player_crosswalk WHERE season=2026 AND season_type='REG' AND week=10 AND team IN ('LAC','BAL') AND available_at<=?",
            [cutoff],
        )
        current_index = {p["player_id"]: p for p in current if p["player_id"]}
        opp = records(
            con,
            "SELECT o.* FROM offensive_opportunities o JOIN preview_games g USING(game_id) WHERE o.team IN ('LAC','BAL') AND o.available_at<=? AND o.classification='STANDARD'",
            [cutoff],
        )
        qb_splits = records(
            con,
            """SELECT posteam team,week,passer_player_id,
            max(passer_player_name) passer_name,count(*) dropbacks,avg(epa) epa_dropback,
            sum(sack) sacks,sum(passing_yards) passing_yards,sum(complete_pass) completions
            FROM clean_pbp WHERE posteam IN ('BAL','LAC') AND qb_dropback=1
            GROUP BY posteam,week,passer_player_id ORDER BY posteam,week,passer_player_id""",
        )
        # Compare receiving deployment on individual targeted plays, not a causal QB effect.
        receiver_qb = records(
            con,
            """SELECT posteam team,passer_player_id,receiver_player_id,
            count(*) targets,sum(complete_pass) receptions,sum(receiving_yards) yards
            FROM clean_pbp WHERE posteam IN ('BAL','LAC') AND receiver_player_id IS NOT NULL
            GROUP BY ALL ORDER BY team,receiver_player_id,passer_player_id""",
        )
        ol = records(
            con,
            """SELECT w.team,w.week,w.display_name,w.player_key,w.roster_position,
            w.offense_snaps,w.offensive_snap_share,w.participation FROM player_week w
            JOIN preview_games g USING(game_id) WHERE w.team IN ('LAC','BAL')
            AND w.week>=8 AND w.offense_snaps>0 AND (w.roster_position IN ('C','G','T','OL','OT','OG','LT','LG','RG','RT')
            OR w.player_key LIKE 'PFR:%') AND w.available_at<=? ORDER BY w.team,w.week,w.offense_snaps DESC""",
            [cutoff],
        )
        schedule_row = (
            pl.read_parquet(raw / raw_manifest["sources"]["schedules"]["path"])
            .filter(pl.col("game_id") == GAME)
            .to_dicts()[0]
        )
    players = {}
    props = []
    td = []
    for pid, (team, position) in CANDIDATES.items():
        roster = current_index.get(pid)
        if not roster or roster["team"] != team:
            raise ValueError("Current temporal GSIS/team linkage unavailable: " + pid)
        name = roster["display_name"]
        override = config["overrides_by_gsis"].get(pid)
        if override:
            availability = override["status"]
            availability_source = override["source"]
        elif roster["roster_status"] == "ACT":
            availability = "ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES"
            availability_source = "lac_inactives" if team == "LAC" else "bal_inactives"
        else:
            availability = "PENDENTE"
            availability_source = "lac_inactives" if team == "LAC" else "bal_inactives"
        # No name join: the official inactive names remain a source list; explicitly
        # bound offensive IDs above cover all unavailable members of this candidate set.
        rows = [
            dict(w)
            for w in pw
            if w["player_id"] == pid
            and (
                (w["offense_snaps"] or 0) > 0
                or (w["targets"] or 0) > 0
                or (w["carries"] or 0) > 0
            )
        ]
        rows.sort(key=lambda w: (w["week"], w["game_id"]))
        for w in rows:
            st = stats_index.get((pid, w["game_id"]))
            for field in (
                "passing_yards",
                "attempts",
                "completions",
                "passing_tds",
                "passing_interceptions",
                "sacks_suffered",
            ):
                w[field] = st.get(field) if st else None
            if w["opportunity_basis"] == "COMPLETE_PBP_OBSERVATION":
                if w["targets"] == 0:
                    w["receptions"] = 0
                    w["receiving_yards"] = 0
                if w["carries"] == 0:
                    w["rushing_yards"] = 0
        opportunities = [o for o in opp if o["player_id"] == pid]
        rz = {}
        for window, size in [("season", None), ("last5", 5), ("last3", 3)]:
            window_ids = {
                g["game_id"]
                for g in (team_games[team][-size:] if size else team_games[team])
            }
            oo = [o for o in opportunities if o["game_id"] in window_ids]
            rz[window] = {
                "targets_inside20": sum(
                    o["opportunity_type"] == "TARGET"
                    and o["yardline_100"] is not None
                    and o["yardline_100"] <= 20
                    for o in oo
                ),
                "carries_inside20": sum(
                    o["opportunity_type"] == "RUSH"
                    and o["yardline_100"] is not None
                    and o["yardline_100"] <= 20
                    for o in oo
                ),
                "carries_inside5": sum(
                    o["opportunity_type"] == "RUSH"
                    and o["yardline_100"] is not None
                    and o["yardline_100"] <= 5
                    for o in oo
                ),
                "td_events": sum(o["offensive_td"] or 0 for o in oo),
            }
        players[pid] = {
            "name": name,
            "team": team,
            "position": position,
            "availability": availability,
            "availability_source": availability_source,
            "participation_note": "Roster ACT + complete official inactive list; eligibility is not snap confirmation",
            "historical_rows": rows,
            "redzone": rz,
            "current_roster_status": roster["roster_status"],
        }
        markets = (
            ["pass_yards", "pass_attempts", "completions", "rush_yards"]
            if position == "QB"
            else (
                ["rush_yards", "receptions", "rec_yards"]
                if position == "RB"
                else ["receptions", "rec_yards"]
            )
        )
        for market in markets:
            real = [
                x
                for x in config["market_observations"]
                if x["player_id"] == pid and x["market"] == market
            ]
            scenarios = real or [
                {
                    "line": DEFAULT_LINES[market],
                    "comparator": ">",
                    "display_line": "Over " + str(DEFAULT_LINES[market]),
                    "source": None,
                }
            ]
            for scenario in scenarios:
                distributions = {}
                for window, size in [("season", None), ("last5", 5), ("last3", 3)]:
                    if size is None:
                        wr = rows  # includes prior ARI for Brissett, explicitly labeled
                    else:
                        game_ids = {g["game_id"] for g in team_games[team][-size:]}
                        wr = [w for w in rows if w["game_id"] in game_ids]
                    distributions[window] = describe(
                        [w.get(MARKET_FIELDS[market]) for w in wr],
                        scenario["line"],
                        scenario["comparator"],
                    )
                season = distributions["season"]
                recent = distributions["last3"]
                risk = (
                    team == "BAL"
                    or pid in ("00-0033885", "00-0040189", "00-0038046")
                    or recent["n"] < 3
                    or (recent["n"] >= 3 and recent.get("hits", 0) / recent["n"] < 0.5)
                )
                classification = classify(
                    availability, season["n"], season.get("hits", 0), risk
                )
                props.append(
                    {
                        "player_id": pid,
                        "player": name,
                        "team": team,
                        "position": position,
                        "market": market,
                        "line": scenario["line"],
                        "comparator": scenario["comparator"],
                        "line_label": scenario["display_line"],
                        "line_kind": "PUBLISHED_DRAFTKINGS_BOARD"
                        if real
                        else "HYPOTHETICAL_SCENARIO",
                        "american_odds": scenario.get("american_odds"),
                        "bookmaker": "DraftKings" if real else None,
                        "source": scenario.get("source"),
                        "availability": availability,
                        "classification": classification,
                        "distributions": distributions,
                        "history_teams": sorted({w["team"] for w in rows}),
                        "recent_targets": describe(
                            [
                                w["targets"]
                                for w in rows
                                if w["game_id"]
                                in {g["game_id"] for g in team_games[team][-3:]}
                            ]
                        ),
                        "recent_carries": describe(
                            [
                                w["carries"]
                                for w in rows
                                if w["game_id"]
                                in {g["game_id"] for g in team_games[team][-3:]}
                            ]
                        ),
                        "recent_snap_share": describe(
                            [
                                w["offensive_snap_share"]
                                for w in rows
                                if w["game_id"]
                                in {g["game_id"] for g in team_games[team][-3:]}
                            ]
                        ),
                        "opponent": "BAL" if team == "LAC" else "LAC",
                        "qb_context": "Brissett estreia BAL; nenhuma amostra neste ataque"
                        if team == "BAL"
                        else "Herbert continuo; susto mao esquerda, McConkey OUT e Njoku retorna",
                        "supporting_hypothesis": "Volume e frequencia observados somente; nao e projecao",
                        "source_url": config["sources"][scenario["source"]]["url"]
                        if real
                        else None,
                        "observed_at_upper_bound": config["cutoff"] if real else None,
                        "valid_until": None,
                        "risk": "QB novo sem amostra BAL; nao transportar ARI/Lamar como regime Brissett"
                        if team == "BAL"
                        else "McConkey fora; retorno Njoku redistribui alvos; OL e eficiencia ofensiva limitam extrapolacao",
                        "decision": "NO_BET",
                        "financial_approved": False,
                    }
                )
        if position != "QB" or pid == "00-0036355":
            td_dist = {}
            for window, size in [("season", None), ("last5", 5), ("last3", 3)]:
                valid = {
                    g["game_id"]
                    for g in (team_games[team][-size:] if size else team_games[team])
                }
                rr = [w for w in rows if w["game_id"] in valid]
                td_dist[window] = describe([w["offensive_td"] for w in rr], 1, ">=")
            real = next(
                (
                    x
                    for x in config["market_observations"]
                    if x["player_id"] == pid and x["market"] == "anytime_td"
                ),
                None,
            )
            score = (
                rz["season"]["carries_inside5"] * 2
                + rz["season"]["targets_inside20"]
                + rz["season"]["td_events"]
            )
            td.append(
                {
                    "player_id": pid,
                    "player": name,
                    "team": team,
                    "position": position,
                    "availability": availability,
                    "redzone": rz,
                    "distribution": td_dist,
                    "american_odds": real.get("american_odds") if real else None,
                    "source": "dk_props" if real else None,
                    "opportunity_order_score": score,
                    "classification": "EVITAR"
                    if availability in ("INACTIVE_OFFICIAL", "IR_OFFICIAL")
                    else (
                        "DADOS INSUFICIENTES"
                        if td_dist["season"]["n"] < 3
                        else "NEUTRO"
                    ),
                    "decision": "NO_BET",
                    "financial_approved": False,
                }
            )
    for prop in props:
        matchup = next(
            (
                r
                for r in (passing_defense if prop["position"] == "QB" else defense)
                if r["defense"] == prop["opponent"]
                and (prop["position"] == "QB" or r["position"] == prop["position"])
            ),
            None,
        )
        prop["defensive_matchup"] = matchup
        prop["supporting_hypothesis"] = player_note(prop["player_id"], positive=True)
        prop["risk"] += "; " + player_note(prop["player_id"], positive=False)
        prop["availability_source_url"] = config["sources"][
            players[prop["player_id"]]["availability_source"]
        ]["url"]
        if prop["american_odds"] is not None:
            a = prop["american_odds"]
            prop["decimal_odds_published"] = validate_decimal_odds(
                1 + (100 / abs(a) if a < 0 else a / 100)
            )
        else:
            prop["decimal_odds_published"] = None
        for window, distribution in prop["distributions"].items():
            for key in (
                "n",
                "mean",
                "median",
                "min",
                "max",
                "hits",
                "observed_frequency",
            ):
                prop[window + "_" + key] = distribution.get(key)
    for item in td:
        item["source_url"] = (
            config["sources"]["dk_props"]["url"] if item["source"] else None
        )
        item["observed_at_upper_bound"] = config["cutoff"] if item["source"] else None
        item["valid_until"] = None
        item["risk"] = (
            "Regime Brissett sem amostra BAL"
            if item["team"] == "BAL"
            else "Ataque ineficiente e papel sujeito a redistribuicao/rotacao"
        )
        item["availability_source_url"] = config["sources"][
            players[item["player_id"]]["availability_source"]
        ]["url"]
        if item["american_odds"] is not None:
            a = item["american_odds"]
            item["decimal_odds_published"] = validate_decimal_odds(
                1 + (100 / abs(a) if a < 0 else a / 100)
            )
        else:
            item["decimal_odds_published"] = None
    props.sort(
        key=lambda r: (
            {"FAVORÁVEL": 0, "NEUTRO": 1, "DADOS INSUFICIENTES": 2, "EVITAR": 3}[
                r["classification"]
            ],
            r["team"],
            r["player"],
            r["market"],
            r["line"],
        )
    )
    td.sort(
        key=lambda r: (
            r["classification"] == "EVITAR",
            -r["opportunity_order_score"],
            r["player"],
        )
    )
    for i, row in enumerate(props, 1):
        row["rank"] = i
    for i, row in enumerate(td, 1):
        row["rank"] = i
    stake_raw = Path(stake_folder) / "stake_raw.json"
    stake = json.loads(stake_raw.read_text())
    stake_events = stake["snapshots"][-1]["payload"]["data"]
    stake_matches = [
        e
        for e in stake_events
        if "chargers" in json.dumps(e).lower() and "ravens" in json.dumps(e).lower()
    ]
    stake_names = sorted(
        {
            offer.get("name", "")
            for event in stake_matches
            for offer in event.get("offers", [])
        }
    )
    source_matches = {
        name: entry["sha256"]
        == json.load(
            open(
                Path(__file__).resolve().parents[2]
                / "reports/task3_2026-11-16/ingestion_manifest.json"
            )
        )["sources"][name]["sha256"]
        for name, entry in raw_manifest["sources"].items()
    }
    evidence = {
        "schema_version": 1,
        "mode": mode,
        "game": target,
        "cutoff": cutoff.isoformat(),
        "generated_at": generated_at.isoformat(),
        "code": code_identity(),
        "generator_sha256": sha256(__file__),
        "observations_sha256": sha256(observations),
        "snapshot_id": manifest["source_snapshot_id"],
        "canonical_status": manifest["status"],
        "build_manifest_sha256": sha256(folder / "build_manifest.json"),
        "database_sha256": manifest["database"]["sha256"],
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "source_hash_matches_task3": source_matches,
        "raw_folder": str(raw),
        "canonical_folder": str(folder),
        "source_versions": raw_manifest["versions"],
        "excluded_target_game": GAME,
        "past_game_ids": sorted(ids),
        "team_game_ids": {
            t: [g["game_id"] for g in gs] for t, gs in team_games.items()
        },
        "skill_query_receipt": receipt,
        "pregame_observations": config,
        "team_metrics": team_metrics,
        "defense_by_position": defense,
        "passing_defense": passing_defense,
        "qb_splits": qb_splits,
        "receiver_qb_splits": receiver_qb,
        "offensive_line_recent": ol,
        "players": players,
        "props": props,
        "anytime_td": td,
        "source_conflicts": [
            {
                "field": "schedule.home_qb",
                "raw_id": schedule_row["home_qb_id"],
                "raw_name": schedule_row["home_qb_name"],
                "official_current": "Jacoby Brissett 00-0033119; source bal_inactives; raw preserved",
            },
            {
                "field": "roster.Njoku.status",
                "raw": current_index["00-0033885"]["roster_status"],
                "official_current": "Activated and active; source lac_inactives; overlay only",
            },
        ],
        "stake": {
            "raw_path": str(stake_raw),
            "raw_sha256": sha256(stake_raw),
            "requests": stake.get("request_count"),
            "observed_at": stake["snapshots"][-1]["retrieved_utc"],
            "source_url": stake["snapshots"][-1]["url"],
            "event_count": len(stake_events),
            "matching_events": len(stake_matches),
            "observed_market_names": stake_names,
            "player_props_demonstrated": False,
            "note": "Only the returned first page/offer schema was inspected; no private endpoints used",
        },
        "decision": "NO_BET",
        "financial_approved": False,
        "statistical_approved": False,
        "budget": {
            "best": 0,
            "td": 0,
            "total": 0,
            "validation_valid": validate_budget(0, 0).valid,
        },
        "best_parlay": "NOT_ASSEMBLED_SINGLE_GAME_CANNOT_MEET_FOUR_GAME_RULE",
        "td_parlay": "NOT_ASSEMBLED_NO_CALIBRATED_JOINT_MODEL_OR_EXECUTABLE_QUOTES",
        "definitions": {
            "success": "EPA>0 on nonnull EPA; no kneels/spikes/deleted/two-point",
            "explosive": "pass gain>=20 or rush gain>=10; scrambles use rush threshold",
            "neutral_pass": "dropback share on downs1/2 quarters1-3 abs preplay score<=7",
            "pace": "median elapsed game clock between adjacent same-drive same-team scrimmage plays in same quarter, 1..60s; not official situation-adjusted pace",
            "participation_denominator": "Only confirmed offensive participation/opportunities; not all roster/active games; last5/3 are team games, not last appearances",
            "qb_pressure": "Unavailable; qb_hit and sacks are separate observed proxies, never pressure rate",
            "redzone": "STANDARD targets/carries at yardline<=20; goal-line carries<=5",
            "classification": "FAVORAVEL iff eligible n>=5 and observed hits/n>=.7 with no explicit regime/role/last3<50% guard; descriptive threshold rubric, not statistical significance, forecast or financial authorization",
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    for name, data in [(names[1], props), (names[2], td)]:
        flattened = []
        for r in data:
            flat = {
                k: (
                    json.dumps(v, ensure_ascii=False, default=str, allow_nan=False)
                    if isinstance(v, (dict, list))
                    else v
                )
                for k, v in r.items()
            }
            flattened.append(flat)
        with (out / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(flattened[0]))
            writer.writeheader()
            writer.writerows(flattened)
    (out / names[3]).write_text(
        json.dumps(evidence, indent=2, default=str, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
    (out / names[0]).write_text(render(evidence), encoding="utf-8")
    return evidence


def fmt(value, places=2):
    return "—" if value is None else f"{value:.{places}f}"


def dist_text(d):
    return (
        f"n={d['n']}; média {fmt(d['mean'])}; mediana {fmt(d['median'])}; faixa {fmt(d['min'])}–{fmt(d['max'])}; {d.get('hits', 0)}/{d['n']} ({fmt((d.get('observed_frequency') or 0) * 100, 1)}%)"
        if d["n"]
        else "Sem amostra"
    )


def player_note(pid, positive):
    notes = {
        "00-0032764": (
            "Henry concentra carries de goal line; revisar TD antes de jardas altas",
            "70+/80+ rush: nenhuma ultrapassagem L3; Brissett e game script mudam oportunidades",
        ),
        "00-0039064": (
            "Flowers lidera targets e jardas BAL; volume pode sustentar recepcoes curtas",
            "QB estreante no sistema; volume/jardas nao implicam touchdown",
        ),
        "00-0034753": (
            "Andrews tem targets na red zone e uso como TE principal",
            "Targets RZ nao se converteram regularmente em TD; disputa alvos com Flowers e outros TEs",
        ),
        "00-0038544": (
            "Johnston tem snap share recente alto e jardas L3 acima do cenario24.5",
            "Poucas recepcoes e distribuicao de jardas volatil; ultimo TD longo nao e repetivel por suposicao",
        ),
        "00-0040727": (
            "Harris jogou60 snaps e recebeu7 targets em W9; McConkey fora abre hipotese de volume",
            "So duas participacoes na janelaL3; Njoku pode absorver parte dos alvos",
        ),
        "00-0040666": (
            "Hampton lidera carries LAC na temporada e tem uso de goal line",
            "Cenario24.5 passou apenas1/3 L3; divide trabalho com Vidal/Mitchell; game script desfavoravel pode reduzir corridas",
        ),
        "00-0036355": (
            "Herbert tem continuidade de titular e algum volume em eventual placar adverso",
            "200+ em4/8; protecao/pass efficiency baixa e distribuicao sem McConkey; mao esquerda exige ressalva",
        ),
        "00-0033119": (
            "Historico ARI oferece contexto descritivo de passes, nao projecao BAL",
            "Zero jogos BAL; mediana ARI245 nao pode ser transferida como parametro calibrado",
        ),
        "00-0033885": (
            "Njoku explicitamente ativo apos IR; pode modificar distribuicao de TE",
            "Amostra curta e retorno sem limite de snaps/rotas confirmado; evitar extrapolar",
        ),
        "00-0040189": (
            "Gadsden tem alvos na red zone e snaps ofensivos recentes",
            "Retorno Njoku pode reduzir papel; targets RZ nao garantem TD",
        ),
        "00-0038046": (
            "Kolar tem snaps e targets recentes comprovados",
            "Snaps podem ser bloqueio; Njoku/Gadsden concorrem; nao tratar snap share como routes",
        ),
        "00-0034975": (
            "Hill participa do passe e teve nove carries em W9",
            "Henry concentra goal line; nova hierarquia com Brissett ainda nao observada",
        ),
        "00-0039391": (
            "Vidal tem participacao recente e oportunidades de passe",
            "Backfield triplo; TDs observados sem carries dentro da5 nao comprovam papel de goal line",
        ),
        "00-0038454": (
            "Mitchell teve aumento recente de carries/targets",
            "Rodizio com Hampton/Vidal e ausencia de papel comprovado de goal line",
        ),
        "00-0040184": (
            "Lambert-Smith teve snaps e quatro targets em W9",
            "Papel oscilante; nao presumir absorcao integral dos alvos McConkey",
        ),
        "00-0039915": (
            "Historico preservado para auditoria",
            "INATIVO OFICIAL: excluir hoje; W9 ativo sem jogar mostra limite de roster",
        ),
        "00-0034796": (
            "Historico Lamar preservado para comparar regimes",
            "IR OFICIAL: nao elegivel hoje; Brissett substitui, sem transportar mobilidade/eficiencia",
        ),
    }
    pair = notes.get(
        pid,
        (
            "Oportunidades historicas preservadas por ID",
            "Amostra/papel secundario; zeros e snaps nao provam volume futuro",
        ),
    )
    return pair[0 if positive else 1]


def render(e):
    lines = [
        "# MNF — Chargers @ Ravens — 16/11/2026",
        "",
        "**Pesquisa descritiva; NO_BET. Sem probabilidade calibrada, EV afirmativo ou aprovação financeira.**",
        "",
        f"Modo: `{e['mode']}`. Cutoff **{e['cutoff']}** (21h36m04 de 16/11 em São Paulo); kickoff **01h15 UTC / 22h15 BRT**.",
        f"Snapshot `{e['snapshot_id']}`; banco `{e['canonical_status']}`. Manifesto SHA `{e['build_manifest_sha256']}`.",
        f"Código base `{e['code']['git_commit']}`, dirty={e['code']['worktree_dirty']}; o JSON fixa hashes de cada arquivo executado e do gerador. Geração {e['generated_at']}.",
        "",
        "## Leitura prioritária",
        "",
        "Brissett estreia por Baltimore: não há uma partida dele no ataque BAL na amostra. As séries com Lamar, Huntley e Fagnano não devem ser transportadas como se o regime fosse igual. Isso reduz a confiança em Flowers, Andrews e Henry, inclusive quando o volume histórico é alto. A instabilidade de BAL não exclui automaticamente os jogadores LAC.",
        "",
        "Herbert oferece continuidade de QB, mas a ausência de McConkey e a volta de Njoku mudam a distribuição dos targets. Examinar Harris/Johnston e os TEs sem assumir que todos absorverão os alvos vagos. O backfield LAC divide oportunidades entre Hampton, Vidal e Mitchell; volume agregado não pertence integralmente ao titular.",
        "",
        "## QBs, inativos e linha ofensiva",
        "",
        "Herbert: elegível pelo roster ACT + lista oficial de inativos, previsto como QB LAC no calendário. O clube informou exames negativos na mão esquerda após W9. Elegibilidade não garante ausência de limitação nem snaps. Brissett: estreia anunciada pelo clube. Lamar Jackson e Tyler Huntley: IR oficial, excluídos. McConkey: inativo oficial. Njoku: explicitamente ativo após ativação da IR, mas função/minutos ainda incertos.",
        "",
    ]
    for t, names in e["pregame_observations"]["official_inactives"].items():
        lines.append(f"- **{t}**: " + ", ".join(names) + ".")
    lines += [
        "",
        "OL BAL: clube informou que Cam Jurgens segue center; Ryan Neuzil chega para profundidade/backup, com possível treino em guard. Emery Jones está inativo. O levantamento de snaps W8/W9 está no JSON, preservando IDs PFR não resolvidos. OL LAC: participação de Pipkins permanece PENDENTE nesta V1; não estar na lista de inativos não comprova ativação da IR. Awosika e mudanças recentes exigem cuidado; não há rating de pass-block ou titulares completos confirmados.",
        "",
        "**Conflitos preservados:** o calendário NFLverse ainda lista Huntley como QB BAL e o roster lista Njoku RES. As publicações oficiais mais recentes substituem esses campos somente na camada de contexto deste relatório; nenhum registro canônico/histórico foi reescrito.",
        "",
        "Fontes primárias lidas antes do cutoff:",
        "",
    ]
    for key in (
        "lac_inactives",
        "bal_inactives",
        "bal_ir",
        "herbert_update",
        "lac_injury",
        "bal_ol",
    ):
        s = e["pregame_observations"]["sources"][key]
        lines.append(
            f"- [{key}]({s['url']}), publicação {s['published_at']}; consulta anterior ou igual ao cutoff."
        )
    lines += [
        "",
        "## Shortlist de pesquisa para leitura rápida",
        "",
        "Johnston receiving yards **Over24.5 hipotético** é a hipótese descritiva mais consistente nesta grade:5/7 na temporada e3/3 L3, com snap share alto. Harris receptions **Over2.5 hipotético** merece monitoramento pela ausência McConkey, mas há apenas2 jogos com participação na janelaL3. Nenhum desses limiares foi verificado como oferta atual.",
        "",
        "Henry mantém prioridade na investigação de **Anytime TD** (16 carries dentro da5 e9 TDs observados), mas suas linhas publicadas de70+/80+ rush têm0/3 L3. Hampton é candidato de TD pelo papel acumulado, porém seu cenário rush Over24.5 passou só1/3 L3: classificado NEUTRO pelo guard de deterioração recente. Flowers e Andrews completam a shortlist de TD por targets na red zone, com ressalva explícita da estreia de Brissett; quatro nomes não significam quatro aprovações.",
        "",
        "Game script é condicional: se LAC ficar atrás, pode haver mais passes sem melhorar eficiência; se BAL controlar o placar, carries Henry podem crescer, mas isso não é previsão do resultado. EPA/play L3: LAC≈-0.303 e BAL≈-0.290; EPA/dropback BAL L3≈-0.353. Henry70+ e Herbert200+ publicados são NEUTROS, não oportunidades de EV comprovado.",
        "",
    ]
    lines += [
        "",
        "## Ataques: temporada, últimas 5 e últimas 3 partidas",
        "",
        "EPA usa jogadas de scrimmage sem kneels/spikes/anuladas/dois pontos. Dropback inclui sacks/scrambles; rush EPA exclui scrambles. Success=EPA>0. Explosive=20+ em passe/10+ em corrida. Neutral pass=share de dropbacks, downs1/2, Q1–Q3, placar pré-jogada ±7. Pace abaixo é proxy do relógio, não métrica ajustada oficial. Denominadores e semanas no JSON.",
        "",
        "|Time|Janela / jogos|EPA/play|EPA/DB|EPA/rush|Success|Explosive|Neutral pass (n)|Pace s (pares)|Pass att / rush plays / targets|Sacks / DB|QB hits|RZ plays|",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in e["team_metrics"]:
        lines.append(
            f"|{r['team']}|{r['window']} / {r['games']}|{fmt(r['epa_play'])}|{fmt(r['epa_dropback'])}|{fmt(r['epa_rush'])}|{fmt(r['success_rate'] * 100, 1)}%|{fmt(r['explosive_rate'] * 100, 1)}%|{fmt(r['neutral_dropback_rate'] * 100, 1)}% ({r['neutral_n']})|{fmt(r['pace_seconds'])} ({r['pace_pairs']})|{r['pass_attempts']} / {r['rush_plays']} / {r['targets']}|{r['sacks']} / {r['dropbacks']}|{r['qb_hits']}|{r['redzone_plays']}|"
        )
    lines += [
        "",
        "Contagens de passe acima excluem sacks; rush plays incluem scrambles. QB hits não são pressão: pressure rate, routes run, TPRR e YPRR não disponíveis. Para QBs, passing yards/attempts/completions vêm do feed semanal; métricas por QB e semana constam no JSON.",
        "",
        "## Defesa contra posições",
        "",
        "|Defesa|Posição|Jogos totais defesa|Targets|Recepções|Rec yds/jogo|Carries|Rush yds/jogo|TDs rush+rec|",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in e["defense_by_position"]:
        if r["position"] not in ("RB", "WR", "TE"):
            continue
        n = len(e["team_game_ids"][r["defense"]])
        lines.append(
            f"|{r['defense']}|{r['position']}|{n}|{r['targets']}|{fmt(r['receptions'], 0)}|{fmt((r['receiving_yards'] or 0) / n)}|{r['carries']}|{fmt((r['rushing_yards'] or 0) / n)}|{r['touchdowns']}|"
        )
    lines += [
        "",
        "Agregados descritivos por posição, sem ajuste por força do adversário, alinhamento ou defensor individual. As jardas de lateral são preservadas sem criar target. Snaps ofensivos não são routes.",
        "",
        "## Ranking de hipóteses de player props",
        "",
        "Linhas PUBLISHED são observações da página pública DraftKings, não Quotes executáveis. As demais são **cenários hipotéticos**, não mercados oferecidos. Frequência = hit/n em partidas com participação ofensiva confirmada; não é probabilidade futura nem calibrada. Temporada pode incluir ARI para Brissett; L5/L3 usam jogos de sua equipe atual, sem inventar amostra BAL. A rubrica FAVORÁVEL é apenas um filtro descritivo transparente (n>=5, frequência>=70%, sem guard de regime/função ou deterioração L3<50%), não teste de significância.",
        "",
        "|#|Jogador / time|Mercado / linha|Origem|Temporada: distribuição e frequência|L5 hits/n|L3 hits/n|Classificação|",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in e["props"]:
        s = p["distributions"]["season"]
        l5 = p["distributions"]["last5"]
        l3 = p["distributions"]["last3"]
        lines.append(
            f"|{p['rank']}|{p['player']} / {p['team']}|{p['market']} {p['line_label']}|{'DK publicada' if p['source'] else 'HIPOTÉTICA'}|{dist_text(s)}|{l5.get('hits', 0)}/{l5['n']}|{l3.get('hits', 0)}/{l3['n']}|{p['classification']}|"
        )
    lines += ["", "### Evidência individual: volume, participação e riscos", ""]
    for pid, p in e["players"].items():
        recent = [
            w
            for w in p["historical_rows"]
            if w["game_id"] in set(e["team_game_ids"][p["team"]][-3:])
        ]
        usage = (
            "; ".join(
                f"W{w['week']}: {w['targets']} tgt/{w['carries']} car, {fmt(w['offensive_snap_share'] * 100 if w['offensive_snap_share'] is not None else None, 1)}% snaps"
                for w in recent
            )
            or "sem participação ofensiva recente na equipe atual"
        )
        lines.append(
            f"- **{p['name']} ({p['team']}, {p['position']}, GSIS {pid})** — {p['availability']}; {usage}. RZ temporada: {p['redzone']['season']}. Favorece: {player_note(pid, True)}. Risco: {player_note(pid, False)}. "
            + (
                "Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal."
                if p["team"] == "BAL"
                else "McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores."
            )
        )
    lines += [
        "",
        "### Mudanças de QB observadas",
        "",
        "|Time|Semana|QB|Dropbacks|EPA/DB|Pass yds|Sacks|",
        "|---|---|---|---|---|---|---|",
    ]
    for r in e["qb_splits"]:
        lines.append(
            f"|{r['team']}|{r['week']}|{r['passer_name']}|{r['dropbacks']}|{fmt(r['epa_dropback'])}|{fmt(r['passing_yards'], 0)}|{r['sacks']}|"
        )
    lines += [
        "",
        "Targets por QB nos passes direcionados (mesmas exclusões PBP):",
        "",
        "|Recebedor BAL|QB|Targets|Recepções|Jardas|",
        "|---|---|---|---|---|",
    ]
    qb_names = {
        r["passer_player_id"]: r["passer_name"]
        for r in e["qb_splits"]
        if r["passer_player_id"]
    }
    for row in e["receiver_qb_splits"]:
        if row["team"] == "BAL" and row["receiver_player_id"] in (
            "00-0039064",
            "00-0034753",
            "00-0032764",
        ):
            lines.append(
                f"|{e['players'][row['receiver_player_id']]['name']}|{qb_names.get(row['passer_player_id'], row['passer_player_id'])}|{row['targets']}|{fmt(row['receptions'], 0)}|{fmt(row['yards'], 0)}|"
            )
    lines += [
        "",
        "Distribuição de targets por receiver ID/passser ID está no JSON. W8 BAL tem apenas um snap ofensivo de Lamar na fonte; não agrupar W8 inteiro como regime Lamar. Comparações são amostras desiguais, sem ajuste pelo adversário. Brissett tem histórico ARI separado, não há split pós-estreia BAL antes deste jogo.",
        "",
        "## Anytime TD: ordem por oportunidades, sem quatro aprovações forçadas",
        "",
        "Ordenação exploratória por 2×carries dentro da5 + targets dentro da20 + TDs observados. Não é xTD ou probabilidade; TD baixo/alto não altera automaticamente elegibilidade. Preferir revisar a posição na goal line, volume e qualidade do ataque.",
        "",
        "|#|Jogador|Time|RZ targets / carries / GL<=5 (temporada)|TDs / jogos com TD / n|L3 RZ tgt/car/GL|Preço publicado DK|Classificação|",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in e["anytime_td"]:
        rz = p["redzone"]["season"]
        l3 = p["redzone"]["last3"]
        d = p["distribution"]["season"]
        lines.append(
            f"|{p['rank']}|{p['player']}|{p['team']}|{rz['targets_inside20']} / {rz['carries_inside20']} / {rz['carries_inside5']}|{rz['td_events']} / {d.get('hits', 0)} / {d['n']}|{l3['targets_inside20']} / {l3['carries_inside20']} / {l3['carries_inside5']}|{p['american_odds'] if p['american_odds'] is not None else 'não observado'}|{p['classification']}|"
        )
    lines += [
        "",
        "Henry é o primeiro nome para investigar pela utilização próxima à end zone. As demais opções devem ser comparadas pela tabela: uso RZ, divisão de backfield, retorno de Njoku e troca de QB em BAL impedem transformar a shortlist em aprovações. Flowers/Andrews competem por chances de passe; Henry/Flowers/Andrews compartilham dependência do ataque BAL. Hampton/Vidal/Mitchell dividem jogo corrido LAC. Nenhuma multiplicação de marginais ou probabilidade conjunta foi calculada.",
        "",
        "## Mercado observado e limites de execução",
        "",
        f"Stake: consulta pública única em {e['stake']['observed_at']}; {e['stake']['event_count']} eventos, {e['stake']['matching_events']} correspondente(s) a LAC–BAL. Mercados efetivamente retornados: {', '.join(e['stake']['observed_market_names'])}. **Player props/Anytime TD não demonstrados** nessa resposta; não usar endpoints privados.",
        "",
        f"[Página pública DraftKings]({e['pregame_observations']['sources']['dk_props']['url']}) observada antes do cutoff; refresh anunciado de5min, porém sem timestamp individual/valid_until. Preços abaixo são indicativos publicados, com bookmaker correto; não são Stake, não comprovam disponibilidade atual/SGP e não passam sozinhos no contrato Quote.",
        "",
        "|Jogador|Mercado / linha|Odd americana publicada|Bookmaker|",
        "|---|---|---|---|",
    ]
    for m in e["pregame_observations"]["market_observations"]:
        lines.append(
            f"|{e['players'][m['player_id']]['name']}|{m['market']} {m['display_line']}|{m['american_odds']}|DraftKings|"
        )
    lines += [
        "",
        "Não foi calculado EV: não há probabilidades calibradas. Frequências históricas e probabilidades implícitas de preço não substituem isso. Sem validade temporal individual não se libera cotação para execução. Linhas reais publicadas e cenários hipotéticos ficam separados nos CSVs.",
        "",
        "## Limitações, decisão e reprodução",
        "",
        "- Snapshot cobre W1–W9 e W10 parcial (jogo-alvo excluído). Números de LAC usam8 jogos, BAL9; janelas são últimas partidas, não simplesmente semanas consecutivas.",
        "- Condicionar à participação ofensiva causa seleção: não mede chance de estar ativo/jogar. Missing/sem snaps não vira zero; zeros apenas com identidade e PBP completo. McConkey foi ativo sem jogar em W9, e está fora hoje.",
        "- Lesões/inativos são observações manuais oficiais desta sessão, sem adapter produtivo. Disponibilidade para jogar não garante função ou ausência de mudança de última hora.",
        "- Modelos legados, probabilidades históricas e Masters não foram alterados; nenhuma pendência de identidade não relacionada bloqueou a análise. Nenhum modelo treinado/promovido.",
        "- Best Parlay não montada: um jogo não atende quatro jogos. TD Parlay permitiria>=2 TDs estruturalmente, mas shortlist não é uma combinada aprovada; nenhuma foi montada. Stake total R$0 de limite R$50.",
        "",
        "Reproduzir em diretório novo (não sobrescrever os quatro relatórios):",
        "",
        "```bash",
        "python -m nfl_betting.mnf_preview --database /BUILD --observations reports/mnf_2026_11_16_support/pregame_observations.json --stake-folder /STAKE_RUN --out /NOVA_PASTA",
        "python -m unittest discover -s tests -v",
        "python tools/verify_history.py",
        "```",
        "",
        "O JSON contém vetores observados, denominadores, chaves, métricas, versões, hashes, conflitos e fontes. Reexecutar depois do kickoff muda explicitamente o modo para publicação posterior com dados pré-kickoff congelados; não representa nova análise pré-jogo.",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--stake-folder", required=True)
    parser.add_argument("--out", default="reports")
    args = vars(parser.parse_args(argv))
    args["folder"] = args.pop("database")
    result = build_report(**args)
    print(
        json.dumps(
            {
                "mode": result["mode"],
                "props": len(result["props"]),
                "td": len(result["anytime_td"]),
                "decision": result["decision"],
            }
        )
    )


if __name__ == "__main__":
    main()
