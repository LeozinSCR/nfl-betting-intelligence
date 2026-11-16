import sys
sys.dont_write_bytecode = True
import ast, importlib.util, json, math, os, socket
from pathlib import Path

def deny(event, args):
    if event.startswith(('socket.connect', 'socket.bind', 'subprocess.', 'os.system')):
        raise PermissionError('read-only probe: network/process denied')
    if event == 'open':
        mode, flags = args[1:3]
        if (isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
            raise PermissionError('read-only probe: writes denied')
sys.addaudithook(deny)

def load(name, path):
    tree=ast.parse(Path(path).read_text())
    imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    allowed={'__future__','math','argparse','json','pathlib','sys'}
    for node in imports:
        names=[node.module] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names]
        assert set(names)<=allowed, names
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
m=load('machina_calcs', '/workspace/scratch/task4-machina/src/sports_skills/betting/_calcs.py')
w=load('walrus_calibration', '/workspace/scratch/task4-walrus/skills/calibration-check/scripts/calibration_report.py')
l=load('walrus_leakage', '/workspace/scratch/task4-walrus/skills/leakage-audit/scripts/audit_pregame_features.py')
checks=[]
for odds in (1.01,1.5,1.9,2,3,10,100):
    r=m.convert_odds({'params':{'odds':odds,'from_format':'decimal'}})
    assert abs(r['data']['implied_probability']-1/odds)<=0.00000051
    checks.append('conversion:'+str(odds))
for odds in (float('nan'),float('inf'),-1,1):
    assert m.convert_odds({'params':{'odds':odds,'from_format':'decimal'}})['status'] is False
    checks.append('invalid:'+str(odds))
devig=m.devig({'params':{'odds':[1.9,1.9],'format':'decimal'}})
assert [x['fair_prob'] for x in devig['data']['outcomes']]==[.5,.5]
assert abs(devig['data']['overround']-2/1.9)<.000001
cal=w.metrics({'y':[0,1,0,1],'p':[.1,.9,.2,.8]},'y','p',10)
assert abs(cal['brier']-.025)<1e-12
assert sum(row['n'] for row in cal['calibration_table'])==4
w.add_conservative_assessment(cal,20,False)
assert cal['verdict']=='manual-review-required'
try: l.finding('x','CLEAN','test')
except ValueError: checks.append('leakage_helper_rejects_auto_clean')
else: raise AssertionError('unexpected CLEAN')
try: socket.create_connection(('example.org',443),timeout=.1)
except PermissionError: checks.append('network_block_confirmed')
else: raise AssertionError('network unexpectedly enabled')
print(json.dumps({'fixture':'SYNTHETIC_NO_NFL_PREDICTIONS','checks':checks,'devig':devig,'calibration':cal,'runtime_adoption':False},indent=2))
