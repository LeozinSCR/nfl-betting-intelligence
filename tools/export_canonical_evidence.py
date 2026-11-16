"""Version review evidence without committing large immutable database snapshots."""
import argparse
import json
from pathlib import Path
import shutil
from nfl_betting.canonical import open_database, rows
from nfl_betting.provenance import sha256


def export(folder, output):
    folder=Path(folder).resolve();output=Path(output)
    manifest=json.loads((folder/'build_manifest.json').read_text())
    snapshot=Path(manifest['source_snapshot_path'])
    output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(folder/'build_manifest.json',output/'build_manifest.json')
    shutil.copyfile(snapshot/'manifest.json',output/'ingestion_manifest.json')
    with open_database(folder) as con:
        queries={
          'historical_focus.csv': "SELECT * FROM reconciliation_audit WHERE category IN ('HISTORICAL_TEAM_ALIAS_RESOLVED','HISTORICAL_IDENTITY_RESOLVED','HISTORICAL_TD_ATTRIBUTION_RESOLVED') ORDER BY category,source_row",
          'unresolved_snap_ids.csv': "SELECT season,week,game_id,team,pfr_id,position,identity_status,identity_diagnostic,offense_snaps,defense_snaps,st_snaps,snap_source_row FROM snap_counts WHERE player_id IS NULL ORDER BY week,game_id,team,pfr_id",
          'historical_participation.csv': "SELECT source_row,week,game_id,team,player_id,json_extract_string(original_json,'$.evidence') old_evidence,json_extract_string(canonical_json,'$.participation') participation,json_extract(canonical_json,'$.offense_snaps') offense_snaps,json_extract(canonical_json,'$.defense_snaps') defense_snaps,json_extract(canonical_json,'$.st_snaps') st_snaps FROM reconciliation_audit WHERE category LIKE 'HISTORICAL_PARTICIPATION_%' ORDER BY source_row",
          'coverage_by_game_team.csv': "SELECT * FROM coverage_audit ORDER BY week,game_id,team",
        }
        for name,sql in queries.items():
            escaped=str(output.resolve()/name).replace("'","''")
            con.execute(f"COPY ({sql}) TO '{escaped}' (HEADER, DELIMITER ',')")
        overview={
          'unresolved_snap_diagnostics':rows(con,"SELECT identity_diagnostic,count(*) records FROM snap_counts WHERE player_id IS NULL GROUP BY identity_diagnostic"),
          'snap_coverage':rows(con,"SELECT week,count(*) records,count(distinct game_id) games,count(*) FILTER(WHERE player_id IS NOT NULL) mapped_records FROM snap_counts GROUP BY week ORDER BY week"),
          'player_key_types':rows(con,'SELECT identity_type,count(*) records FROM players GROUP BY identity_type'),
          'historical_positions_recovered':rows(con,"SELECT json_extract_string(canonical_json,'$.player_position') AS recovered_position,count(*) records FROM reconciliation_audit WHERE category='HISTORICAL_IDENTITY_RESOLVED' GROUP BY 1"),
          'two_point_affected_historical':rows(con,"SELECT opportunity_type,count(*) events FROM offensive_opportunities o WHERE classification='TWO_POINT_CONVERSION' AND EXISTS(SELECT 1 FROM reconciliation_audit a WHERE a.source='weekly_reconciliation_2026.csv' AND a.week=o.week AND a.game_id=o.game_id AND a.team=o.team AND a.player_id=o.player_id) GROUP BY opportunity_type"),
        }
    overview.update({'exporter_sha256':sha256(__file__),'database_folder':str(folder),'full_audit_rows':manifest['tables']['reconciliation_audit']['rows'],
        'full_audit_csv_sha256':manifest['audit_csv']['sha256'],
        'note':'Focused CSVs are explicit subsets; complete audit and all raw/canonical tables remain in immutable run/artifact',
        'files':{p.name:sha256(p) for p in sorted(output.iterdir())}})
    (output/'evidence_index.json').write_text(json.dumps(overview,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return overview


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--out',required=True);a=p.parse_args()
    print(json.dumps(export(a.folder,a.out),indent=2,ensure_ascii=False))
