-- Raw inputs are registered with _source_row; names are never identity keys.
CREATE TEMP MACRO team_code(x) AS CASE WHEN x='LAR' THEN 'LA' WHEN x='JAC' THEN 'JAX' WHEN x='WSH' THEN 'WAS' ELSE x END;
CREATE TABLE games AS
SELECT _source_row AS source_row, game_id, season, game_type AS season_type, week,
       CAST(gameday AS DATE) AS game_date,
       CAST(gameday || ' ' || gametime AS TIMESTAMP) AT TIME ZONE 'America/New_York' AS kickoff_utc,
       home_team AS home_team_raw, away_team AS away_team_raw,
       team_code(home_team) AS home_team, team_code(away_team) AS away_team,
       home_score, away_score,
       home_score IS NOT NULL AND away_score IS NOT NULL AS has_result,
       'schedule_scores_present' AS completion_basis
FROM raw_schedules;
CREATE TEMP TABLE game_teams AS
SELECT game_id,season,season_type,week,home_team AS team,away_team AS opponent FROM games
UNION ALL SELECT game_id,season,season_type,week,away_team,home_team FROM games;
CREATE TABLE teams AS SELECT DISTINCT season,team FROM game_teams;

CREATE TABLE player_crosswalk AS
SELECT _source_row AS roster_source_row, season, game_type AS season_type,week,
       team AS team_raw, team_code(team) AS team, gsis_id AS player_id,
       NULLIF(pfr_id,'') AS pfr_id, NULLIF(CAST(sleeper_id AS VARCHAR),'') AS sleeper_id,
       full_name AS display_name, position, status AS roster_status
FROM raw_rosters_weekly;
CREATE TEMP TABLE usable_crosswalk AS
SELECT * FROM player_crosswalk WHERE player_id IS NOT NULL
AND (season,season_type,week,team,player_id) IN
  (SELECT season,season_type,week,team,player_id FROM player_crosswalk GROUP BY ALL HAVING count(*)=1)
AND (pfr_id IS NULL OR (season,season_type,week,team,pfr_id) IN
  (SELECT season,season_type,week,team,pfr_id FROM player_crosswalk WHERE pfr_id IS NOT NULL GROUP BY ALL HAVING count(DISTINCT player_id)=1));
CREATE TABLE snap_counts AS
SELECT s._source_row AS snap_source_row,s.game_id,s.season,s.game_type AS season_type,s.week,
       s.team AS team_raw,team_code(s.team) AS team,x.player_id,s.pfr_player_id AS pfr_id,
       coalesce(x.player_id,'PFR:'||s.pfr_player_id) AS player_key,
       s.player AS display_name, s.position, s.offense_snaps,s.defense_snaps,s.st_snaps,
       s.offense_pct AS offensive_snap_share,s.defense_pct,s.st_pct,
       CASE WHEN x.player_id IS NULL THEN 'UNRESOLVED_PFR' ELSE 'SAME_WEEK_ID_MATCH' END AS identity_status,
       CASE WHEN x.player_id IS NOT NULL THEN 'SAME_WEEK_TEAM_ID_LINK'
            WHEN EXISTS(SELECT 1 FROM player_crosswalk z WHERE z.season=s.season AND z.week=s.week AND z.pfr_id=s.pfr_player_id) THEN 'PFR_OTHER_TEAM_THIS_WEEK'
            WHEN EXISTS(SELECT 1 FROM player_crosswalk z WHERE z.pfr_id=s.pfr_player_id) THEN 'PFR_OTHER_WEEK_ONLY'
            ELSE 'PFR_ABSENT_FROM_ROSTER_SNAPSHOT' END AS identity_diagnostic
FROM raw_snap_counts s LEFT JOIN usable_crosswalk x
 ON s.season=x.season AND s.game_type=x.season_type AND s.week=x.week
 AND team_code(s.team)=x.team AND s.pfr_player_id=x.pfr_id;
CREATE TABLE injuries AS
SELECT _source_row AS injury_source_row,season,season_type,week,team AS team_raw,team_code(team) AS team,
       gsis_id AS player_id,full_name AS display_name,position,report_status,practice_status,
       report_primary_injury,report_secondary_injury,practice_primary_injury,practice_secondary_injury,
       NULL::TIMESTAMPTZ AS source_published_at
FROM raw_injuries;

CREATE TEMP TABLE opportunity_events AS
SELECT _source_row AS pbp_source_row,season,season_type,week,game_id,play_id,
       team_code(posteam) AS team,team_code(defteam) AS defense,
       receiver_player_id AS player_id,receiver_player_name AS pbp_display_name,
       'TARGET' AS opportunity_type,pass_attempt AS attempt_flag,two_point_attempt,play_type,play_deleted,
       yardline_100,complete_pass AS receptions,
       CASE WHEN complete_pass=0 THEN 0 ELSE receiving_yards END AS yards,receiving_yards AS source_yards,
       CASE WHEN contains("desc",'(Punt formation)') THEN 'PUNT_FORMATION' ELSE 'OTHER' END AS formation_context,
       CASE WHEN td_player_id=receiver_player_id AND pass_touchdown=1 THEN 1 ELSE 0 END AS offensive_td
FROM raw_pbp WHERE receiver_player_id IS NOT NULL
UNION ALL
SELECT _source_row,season,season_type,week,game_id,play_id,team_code(posteam),team_code(defteam),
       rusher_player_id,rusher_player_name,'RUSH',rush_attempt,two_point_attempt,play_type,play_deleted,
       yardline_100,0,rushing_yards,rushing_yards,
       CASE WHEN contains("desc",'(Punt formation)') THEN 'PUNT_FORMATION' ELSE 'OTHER' END,
       CASE WHEN td_player_id=rusher_player_id AND rush_touchdown=1 THEN 1 ELSE 0 END
FROM raw_pbp WHERE rusher_player_id IS NOT NULL
UNION ALL
SELECT _source_row,season,season_type,week,game_id,play_id,team_code(posteam),team_code(defteam),
       lateral_receiver_player_id,lateral_receiver_player_name,'LATERAL_RECEIVE',0,two_point_attempt,play_type,play_deleted,
       yardline_100,0,lateral_receiving_yards,lateral_receiving_yards,'OTHER',
       CASE WHEN td_player_id=lateral_receiver_player_id AND pass_touchdown=1 THEN 1 ELSE 0 END
FROM raw_pbp WHERE lateral_receiver_player_id IS NOT NULL
UNION ALL
SELECT _source_row,season,season_type,week,game_id,play_id,team_code(posteam),team_code(defteam),
       lateral_rusher_player_id,lateral_rusher_player_name,'LATERAL_RUSH',0,two_point_attempt,play_type,play_deleted,
       yardline_100,0,lateral_rushing_yards,lateral_rushing_yards,'OTHER',
       CASE WHEN td_player_id=lateral_rusher_player_id AND rush_touchdown=1 THEN 1 ELSE 0 END
FROM raw_pbp WHERE lateral_rusher_player_id IS NOT NULL;
CREATE TABLE offensive_opportunities AS
SELECT e.*,x.position,x.display_name AS roster_display_name,
       CASE WHEN e.two_point_attempt=1 THEN 'TWO_POINT_CONVERSION'
            WHEN e.play_type='no_play' OR e.play_deleted=1 THEN 'NULLIFIED_OR_DELETED'
            WHEN e.opportunity_type IN ('LATERAL_RECEIVE','LATERAL_RUSH') THEN 'LATERAL_TOUCH'
            WHEN e.play_type IS NULL OR e.attempt_flag IS NULL THEN 'UNCLASSIFIED'
            WHEN e.attempt_flag<>1 THEN 'NOT_CONVENTIONAL_ATTEMPT'
            ELSE 'STANDARD' END AS classification
FROM opportunity_events e LEFT JOIN usable_crosswalk x
 ON e.season=x.season AND e.season_type=x.season_type AND e.week=x.week
 AND e.team=x.team AND e.player_id=x.player_id;
CREATE TEMP TABLE opportunity_totals AS
SELECT season,season_type,week,game_id,team,player_id,
 count(*) FILTER (WHERE classification='STANDARD' AND opportunity_type='TARGET') AS targets,
 count(*) FILTER (WHERE classification='STANDARD' AND opportunity_type='RUSH') AS carries,
 count(*) FILTER(WHERE classification='LATERAL_TOUCH') AS lateral_touches,
 sum(receptions) FILTER(WHERE classification='STANDARD') AS receptions,
 sum(yards) FILTER(WHERE classification IN ('STANDARD','LATERAL_TOUCH') AND opportunity_type IN ('TARGET','LATERAL_RECEIVE')) AS receiving_yards,
 sum(yards) FILTER(WHERE classification IN ('STANDARD','LATERAL_TOUCH') AND opportunity_type IN ('RUSH','LATERAL_RUSH')) AS rushing_yards,
 sum(offensive_td) FILTER(WHERE classification IN ('STANDARD','LATERAL_TOUCH')) AS offensive_td,
 list(pbp_source_row) AS pbp_source_rows
FROM offensive_opportunities GROUP BY ALL;
CREATE TEMP TABLE pbp_game_coverage AS
SELECT game_id,count(*) AS pbp_rows,
 bool_or(upper(trim("desc"))='END GAME') AS has_end_marker,
 max(total_home_score) AS observed_home_score,max(total_away_score) AS observed_away_score
FROM raw_pbp GROUP BY game_id;

CREATE TEMP TABLE normalized_stats AS
SELECT *,team_code(team) AS canonical_team,
 coalesce(player_id,'STATS:'||CAST(_source_row AS VARCHAR)) AS player_key
FROM raw_player_stats;
CREATE TEMP TABLE player_candidates AS
SELECT x.season,x.season_type,x.week,g.game_id,x.team,coalesce(x.player_id,'ROSTER:'||CAST(x.roster_source_row AS VARCHAR)) AS player_key
FROM player_crosswalk x LEFT JOIN game_teams g USING(season,season_type,week,team)
UNION SELECT season,season_type,week,game_id,canonical_team,player_key FROM normalized_stats
UNION SELECT season,season_type,week,game_id,team,player_key FROM snap_counts
UNION SELECT season,season_type,week,game_id,team,player_id FROM offensive_opportunities
UNION SELECT i.season,i.season_type,i.week,g.game_id,i.team,i.player_id FROM injuries i LEFT JOIN game_teams g USING(season,season_type,week,team);
CREATE TABLE player_week AS
SELECT c.*,CASE WHEN c.player_key NOT LIKE 'PFR:%' AND c.player_key NOT LIKE 'STATS:%' AND c.player_key NOT LIKE 'ROSTER:%' THEN c.player_key END AS player_id,
 x.pfr_id,x.sleeper_id,x.position AS roster_position,coalesce(x.display_name,n.display_name,s.player_display_name) AS display_name,x.roster_status,x.roster_source_row,
 s._source_row AS stats_source_row,n.snap_source_row,o.pbp_source_rows,
 s.targets AS weekly_targets,s.carries AS weekly_carries,
 s.receptions AS weekly_receptions,s.receiving_yards AS weekly_receiving_yards,s.rushing_yards AS weekly_rushing_yards,
 s.receiving_tds AS weekly_receiving_tds,s.rushing_tds AS weekly_rushing_tds,
 o.receptions,o.receiving_yards,o.rushing_yards,o.offensive_td,o.lateral_touches,
 CASE WHEN (c.player_key LIKE 'PFR:%' OR c.player_key LIKE 'STATS:%' OR c.player_key LIKE 'ROSTER:%') THEN NULL WHEN b.has_end_marker THEN coalesce(o.targets,0) ELSE o.targets END AS targets,
 CASE WHEN (c.player_key LIKE 'PFR:%' OR c.player_key LIKE 'STATS:%' OR c.player_key LIKE 'ROSTER:%') THEN NULL WHEN b.has_end_marker THEN coalesce(o.carries,0) ELSE o.carries END AS carries,
 n.offense_snaps,n.defense_snaps,n.st_snaps,n.offensive_snap_share,
 CASE WHEN coalesce(o.targets,0)+coalesce(o.carries,0)>0 THEN 'OPPORTUNITIES_RECORDED'
      WHEN o.lateral_touches>0 THEN 'LATERAL_TOUCH_RECORDED'
      WHEN n.offense_snaps>0 AND b.has_end_marker AND NOT (c.player_key LIKE 'PFR:%' OR c.player_key LIKE 'STATS:%' OR c.player_key LIKE 'ROSTER:%') THEN 'OFFENSIVE_SNAPS_ZERO_OPPORTUNITIES'
      WHEN n.offense_snaps>0 THEN 'OFFENSIVE_SNAPS_OPPORTUNITIES_UNKNOWN'
      WHEN n.offense_snaps=0 AND n.st_snaps>0 AND n.defense_snaps=0 THEN 'SPECIAL_TEAMS_ONLY'
      WHEN n.offense_snaps=0 AND n.defense_snaps>0 AND n.st_snaps>0 THEN 'DEFENSE_AND_SPECIAL_TEAMS'
      WHEN n.offense_snaps=0 AND n.defense_snaps>0 THEN 'DEFENSE_ONLY'
      ELSE 'NO_CONFIRMED_PARTICIPATION' END AS participation,
 CASE WHEN (c.player_key LIKE 'PFR:%' OR c.player_key LIKE 'STATS:%' OR c.player_key LIKE 'ROSTER:%') THEN 'IDENTITY_UNRESOLVED' WHEN b.has_end_marker THEN 'COMPLETE_PBP_OBSERVATION' ELSE 'PBP_INCOMPLETE_OR_ABSENT' END AS opportunity_basis
FROM player_candidates c
LEFT JOIN usable_crosswalk x ON c.season=x.season AND c.season_type=x.season_type AND c.week=x.week AND c.team=x.team AND c.player_key=x.player_id
LEFT JOIN normalized_stats s ON c.season=s.season AND c.season_type=s.season_type AND c.week=s.week AND c.game_id=s.game_id AND c.team=s.canonical_team AND c.player_key=s.player_key
LEFT JOIN snap_counts n ON c.season=n.season AND c.season_type=n.season_type AND c.week=n.week AND c.game_id=n.game_id AND c.team=n.team AND c.player_key=n.player_key
LEFT JOIN opportunity_totals o ON c.season=o.season AND c.season_type=o.season_type AND c.week=o.week AND c.game_id=o.game_id AND c.team=o.team AND c.player_key=o.player_id
LEFT JOIN pbp_game_coverage b ON c.game_id=b.game_id;
CREATE TABLE players AS
SELECT player_key,player_id,
 CASE WHEN player_id IS NOT NULL THEN 'GSIS' ELSE 'UNRESOLVED_SOURCE_ID' END AS identity_type,
 string_agg(DISTINCT display_name,' | ' ORDER BY display_name) AS display_names
FROM player_week GROUP BY player_key,player_id;
CREATE TABLE team_week AS
SELECT p.season,p.season_type,p.week,p.game_id,team_code(p.posteam) AS team,team_code(p.defteam) AS defense,
 count(*) AS offensive_plays,
 count(*) FILTER (WHERE pass_attempt=1 AND coalesce(sack,0)=0) AS pass_attempts,
 count(*) FILTER (WHERE rush_attempt=1) AS rush_attempts,
 count(*) FILTER (WHERE qb_dropback=1) AS dropbacks,
 avg(epa) AS epa_per_play,count(epa) AS epa_observations,avg(success) AS success_rate
FROM raw_pbp p
WHERE coalesce(two_point_attempt,0)<>1 AND coalesce(play_deleted,0)<>1
 AND play_type IN ('pass','run','qb_kneel','qb_spike') GROUP BY ALL;
CREATE TABLE defensive_matchups AS
SELECT season,season_type,week,game_id,defense,team AS opponent,coalesce(position,'UNKNOWN') AS position,
 count(*) FILTER(WHERE opportunity_type='TARGET') AS targets,sum(receptions) AS receptions,sum(yards) AS receiving_yards
FROM offensive_opportunities WHERE classification IN ('STANDARD','LATERAL_TOUCH') AND opportunity_type IN ('TARGET','LATERAL_RECEIVE') GROUP BY ALL;

CREATE TABLE coverage_audit AS
SELECT g.game_id,g.season,g.season_type,g.week,g.team,g.opponent,gm.has_result,
 coalesce(b.pbp_rows,0) AS pbp_rows,coalesce(b.has_end_marker,false) AS has_end_marker,
 (SELECT count(*) FROM normalized_stats s WHERE s.game_id=g.game_id AND s.canonical_team=g.team) AS stats_rows,
 (SELECT count(*) FROM snap_counts n WHERE n.game_id=g.game_id AND n.team=g.team) AS snap_rows,
 (SELECT count(*) FROM player_crosswalk x WHERE x.season=g.season AND x.season_type=g.season_type AND x.week=g.week AND x.team=g.team) AS roster_rows,
 (SELECT count(DISTINCT player_key) FROM player_week w WHERE w.game_id=g.game_id AND w.team=g.team) AS players_observed,
 b.observed_home_score,b.observed_away_score,gm.home_score,gm.away_score
FROM game_teams g JOIN games gm USING(game_id)
LEFT JOIN pbp_game_coverage b ON g.game_id=b.game_id;

CREATE TABLE reconciliation_audit (
 category VARCHAR,severity VARCHAR,source VARCHAR,source_row BIGINT,
 season INTEGER,week INTEGER,game_id VARCHAR,team VARCHAR,player_id VARCHAR,
 original_json VARCHAR,canonical_json VARCHAR,detail VARCHAR
);
-- Every historical record is retained in the audit, whether it matches or not.
INSERT INTO reconciliation_audit
SELECT CASE WHEN s._source_row IS NULL THEN 'HISTORICAL_UNMATCHED'
            WHEN h.corrected_targets<>s.targets OR h.corrected_carries<>s.carries THEN 'HISTORICAL_VALUE_MISMATCH'
            WHEN h.team<>team_code(h.team) THEN 'HISTORICAL_TEAM_ALIAS_RESOLVED' ELSE 'HISTORICAL_MATCH' END,
 CASE WHEN s._source_row IS NULL OR h.corrected_targets<>s.targets OR h.corrected_carries<>s.carries THEN 'PENDING' ELSE 'INFO' END,
 'weekly_reconciliation_2026.csv',h._source_row,2026,h.week,h.game_id,team_code(h.team),h.player_id,
 to_json(struct_pack(team:=h.team,targets:=h.corrected_targets,carries:=h.corrected_carries)),
 to_json(struct_pack(team:=s.canonical_team,targets:=s.targets,carries:=s.carries,stats_source_row:=s._source_row)),
 'Join on week, game, canonical team and GSIS; names excluded'
FROM historical_weekly h LEFT JOIN normalized_stats s
 ON h.week=s.week AND h.game_id=s.game_id AND team_code(h.team)=s.canonical_team AND h.player_id=s.player_id;
INSERT INTO reconciliation_audit
SELECT CASE WHEN x.player_id IS NULL THEN 'HISTORICAL_IDENTITY_PENDING' ELSE 'HISTORICAL_IDENTITY_RESOLVED' END,
 CASE WHEN x.player_id IS NULL THEN 'PENDING' ELSE 'INFO' END,'opportunities_corrected_2026.csv',h._source_row,2026,h.week,h.game_id,team_code(h.team),h.player_id,
 to_json(struct_pack(display_name:=h.player_name,player_position:=h.position,team:=h.team)),
 to_json(struct_pack(display_name:=x.display_name,player_position:=x.position,roster_source_row:=x.roster_source_row)),
 'Exact GSIS + season + week + team roster match; no future-week backfill'
FROM historical_opportunities h LEFT JOIN usable_crosswalk x
 ON x.season=2026 AND x.season_type='REG' AND h.week=x.week AND team_code(h.team)=x.team AND h.player_id=x.player_id
WHERE h.position='UNKNOWN' OR h.player_name IS NULL OR trim(h.player_name)='';
INSERT INTO reconciliation_audit
SELECT 'EXCLUDED_'||classification,'INFO','pbp',pbp_source_row,season,week,game_id,team,player_id,
 to_json(struct_pack(play_id:=play_id,opportunity_type:=opportunity_type,attempt_flag:=attempt_flag,two_point_attempt:=two_point_attempt,play_type:=play_type)),
 '{"standard_opportunities":0}','Raw row retained; excluded only from conventional counts'
FROM offensive_opportunities WHERE classification NOT IN ('STANDARD','LATERAL_TOUCH');
INSERT INTO reconciliation_audit
SELECT 'WEEKLY_PBP_'||CASE WHEN coalesce(s.weekly_targets,0)=coalesce(s.targets,0) AND coalesce(s.weekly_carries,0)=coalesce(s.carries,0) THEN 'MATCH' ELSE 'MISMATCH' END,
 CASE WHEN s.weekly_targets=s.targets AND s.weekly_carries=s.carries THEN 'INFO' ELSE 'PENDING' END,
 'player_stats',s.stats_source_row,s.season,s.week,s.game_id,s.team,s.player_id,
 to_json(struct_pack(targets:=s.weekly_targets,carries:=s.weekly_carries)),to_json(struct_pack(targets:=s.targets,carries:=s.carries)),
 'Conventional PBP excludes two-point attempts and nullified/deleted plays; kneels count as carries'
FROM player_week s WHERE s.stats_source_row IS NOT NULL AND s.opportunity_basis='COMPLETE_PBP_OBSERVATION';
INSERT INTO reconciliation_audit
SELECT 'SPECIAL_TEAMS_ONLY','INFO','snap_counts',snap_source_row,season,week,game_id,team,player_id,
 to_json(struct_pack(offense_snaps:=offense_snaps,defense_snaps:=defense_snaps,st_snaps:=st_snaps)),
 '{"participation":"SPECIAL_TEAMS_ONLY"}','Offense=0, defense=0, special teams>0; not offensive participation'
FROM player_week WHERE participation='SPECIAL_TEAMS_ONLY';
INSERT INTO reconciliation_audit
SELECT 'SNAP_ID_UNRESOLVED','PENDING','snap_counts',snap_source_row,season,week,game_id,team,player_id,
 to_json(struct_pack(pfr_id:=pfr_id)),NULL,identity_diagnostic||'; PFR surrogate retained; no name matching or other-week backfill'
FROM snap_counts WHERE player_id IS NULL;
INSERT INTO reconciliation_audit
SELECT 'ROSTER_GSIS_MISSING','PENDING','rosters_weekly',roster_source_row,season,week,NULL,team,player_id,
 to_json(struct_pack(pfr_id:=pfr_id,sleeper_id:=sleeper_id)),NULL,'Raw roster row and names retained; no identity inferred'
FROM player_crosswalk WHERE player_id IS NULL;
INSERT INTO reconciliation_audit
SELECT 'STATS_GSIS_MISSING','PENDING','player_stats',_source_row,season,week,game_id,canonical_team,player_id,
 to_json(struct_pack(source_player_display_name:=player_display_name)),NULL,'Raw stats row retained with STATS surrogate; no name join'
FROM normalized_stats WHERE player_id IS NULL;
INSERT INTO reconciliation_audit
SELECT 'COMPLETED_GAME_COVERAGE_GAP','PENDING','coverage_audit',NULL,season,week,game_id,team,NULL,
 to_json(struct_pack(has_result:=has_result,pbp_rows:=pbp_rows,has_end_marker:=has_end_marker,stats_rows:=stats_rows,snap_rows:=snap_rows,roster_rows:=roster_rows)),NULL,
 'Result present; PBP end marker, player stats, snaps and roster required per team'
FROM coverage_audit WHERE has_result AND (NOT has_end_marker OR stats_rows=0 OR snap_rows=0 OR roster_rows=0);

-- Detailed source coverage. Scopes distinguish raw rows from player-role events.
CREATE TABLE source_coverage AS
SELECT 'schedules' AS source,'TEAM_SCHEDULE_ROWS' AS scope,season,season_type,week,game_id,team,
 NULL::VARCHAR AS player_key,count(*) AS rows_observed FROM game_teams GROUP BY ALL
UNION ALL
SELECT 'player_stats','SOURCE_ROWS',season,season_type,week,game_id,canonical_team,player_key,count(*) FROM normalized_stats GROUP BY ALL
UNION ALL
SELECT 'snap_counts','SOURCE_ROWS',season,season_type,week,game_id,team,player_key,count(*) FROM snap_counts GROUP BY ALL
UNION ALL
SELECT 'rosters_weekly','SOURCE_ROWS',x.season,x.season_type,x.week,g.game_id,x.team,
 coalesce(x.player_id,'ROSTER:'||CAST(x.roster_source_row AS VARCHAR)),count(*)
FROM player_crosswalk x LEFT JOIN game_teams g USING(season,season_type,week,team) GROUP BY ALL
UNION ALL
SELECT 'injuries','SOURCE_ROWS',i.season,i.season_type,i.week,g.game_id,i.team,i.player_id,count(*)
FROM injuries i LEFT JOIN game_teams g USING(season,season_type,week,team) GROUP BY ALL
UNION ALL
SELECT 'pbp','SOURCE_ROWS',season,season_type,week,game_id,team_code(posteam),NULL::VARCHAR,count(*) FROM raw_pbp GROUP BY ALL
UNION ALL
SELECT 'pbp','PLAYER_ROLE_EVENTS',season,season_type,week,game_id,team,player_id,count(*)
FROM (
 SELECT season,season_type,week,game_id,team_code(posteam) AS team,passer_player_id AS player_id FROM raw_pbp WHERE passer_player_id IS NOT NULL
 UNION ALL SELECT season,season_type,week,game_id,team,player_id FROM offensive_opportunities
) GROUP BY ALL;
INSERT INTO reconciliation_audit
SELECT 'NORMALIZED_INCOMPLETE_PASS_YARDS_ZERO','INFO','pbp',pbp_source_row,season,week,game_id,team,player_id,
 to_json(struct_pack(source_yards:=source_yards,receptions:=receptions)),
 '{"yards":0,"basis":"incomplete_pass"}','Known zero receiving yards on incomplete pass; raw null is retained separately'
FROM offensive_opportunities WHERE classification='STANDARD' AND opportunity_type='TARGET' AND receptions=0 AND source_yards IS NULL;
INSERT INTO reconciliation_audit
SELECT 'TWO_POINT_WITHOUT_OFFENSIVE_PLAYER_ID','INFO','pbp',_source_row,season,week,game_id,team_code(posteam),NULL,
 to_json(struct_pack(play_id:=play_id,two_point_attempt:=two_point_attempt)),
 '{"conventional_opportunities":0}','Attempt retained in raw PBP; cannot attribute target/carry without source ID'
FROM raw_pbp WHERE two_point_attempt=1 AND receiver_player_id IS NULL AND rusher_player_id IS NULL;
INSERT INTO reconciliation_audit
SELECT 'HISTORICAL_PARTICIPATION_'||coalesce(w.participation,'UNMATCHED'),
 CASE WHEN w.player_key IS NULL THEN 'PENDING' ELSE 'INFO' END,
 'weekly_participation_2026.csv',h._source_row,2026,h.week,h.game_id,team_code(h.team),h.player_id,
 to_json(struct_pack(evidence:=h.evidence)),
 to_json(struct_pack(participation:=w.participation,offense_snaps:=w.offense_snaps,defense_snaps:=w.defense_snaps,st_snaps:=w.st_snaps,targets:=w.targets,carries:=w.carries)),
 'Historical event evidence compared to current same-game GSIS participation; no availability inferred'
FROM historical_participation h LEFT JOIN player_week w
 ON w.season=2026 AND w.season_type='REG' AND h.week=w.week AND h.game_id=w.game_id AND team_code(h.team)=w.team AND h.player_id=w.player_id;
