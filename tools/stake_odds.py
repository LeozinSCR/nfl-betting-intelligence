#!/usr/bin/env python3
"""Stake Sportsbook public read-only snapshot. No betting or account access.
Documentation: https://sportsbook-api.stake.com/
"""
import argparse,csv,datetime,json,math,os,sys
from uuid import uuid4
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from urllib.parse import quote, urlencode

BASE='https://sportsbook-api.stake.com'

def flatten(x):
    if isinstance(x,dict):
        for a in x.values(): yield from flatten(a)
    elif isinstance(x,list):
        for a in x: yield from flatten(a)
    elif isinstance(x,str):
        yield x

def records(payload):
    if isinstance(payload,dict):
        for key in ('data','items','results','matches','tournaments','sports'):
            if isinstance(payload.get(key),list): return payload[key]
        if isinstance(payload.get('data'),dict):
            for key in ('items','results','matches','tournaments','sports'):
                if isinstance(payload['data'].get(key),list):return payload['data'][key]
    return []

class Client:
    def __init__(self,cap,key):self.cap=cap;self.key=key;self.count=0
    def get(self,path):
        if self.count>=self.cap:raise RuntimeError(f'Local request cap reached ({self.cap}). Request more pages later; no silent overrun.')
        url=BASE+path+('?' if '?' not in path else '&')+urlencode({'limit':30,'offset':0})
        heads={'Accept':'application/json','User-Agent':'NFL-Betting-Intelligence/1.0 (read-only)'}
        if self.key:heads['X-API-Key']=self.key
        self.count+=1
        try:
            with urlopen(Request(url,headers=heads),timeout=20) as r:
                result=json.load(r)
        except HTTPError as e:
            body=e.read(400).decode('utf-8','replace');raise RuntimeError(f'HTTP {e.code} {body}') from e
        except URLError as e:raise RuntimeError(f'Connection failed: {e.reason}') from e
        return {'url':url,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'payload':result}

def choose(items,phrases):
    for item in items:
        hay=' '.join(flatten(item)).lower()
        if any(p in hay for p in phrases):return item
    return None

def scalar(o,*keys):
    if not isinstance(o,dict):return ''
    for k in keys:
        val=o.get(k)
        if isinstance(val,(str,int,float,bool)):return val
    return ''

OFFER_FIELDS = ['retrieved_utc', 'observed_at', 'source_updated_at', 'valid_until',
                'provider', 'bookmaker', 'source_url', 'binding_status', 'event_id',
                'event_name', 'starts_at', 'market', 'selection', 'odds_decimal',
                'available', 'event_json', 'offer_json', 'selection_json']


def normalize_offers(snapshot):
    """Export finite numeric prices only. Unmapped export is never a validated Quote.

    Do not fabricate expiry, canonical IDs, player/line mapping or coverage.
    Synthetic fixtures in tests exercise the observed offers/selections schema.
    """
    rows, rejected = [], []
    payload = snapshot['payload']
    for event in records(payload):
        if not isinstance(event, dict):
            continue
        offers = event.get('offers', [])
        if not isinstance(offers, list):
            continue
        for offer in offers:
            if not isinstance(offer, dict) or not isinstance(offer.get('selections'), list):
                continue
            for selection in offer['selections']:
                if not isinstance(selection, dict):
                    continue
                odds = selection.get('decimalOdds', selection.get('odds', selection.get('price')))
                try:
                    valid_price = (not isinstance(odds, bool) and isinstance(odds, (int, float))
                                   and math.isfinite(odds) and odds > 1)
                except OverflowError:
                    valid_price = False
                if not valid_price:
                    rejected.append({'event_id': scalar(event, 'id'), 'market': scalar(offer, 'name'),
                                     'selection': scalar(selection, 'name'), 'reason': 'INVALID_ODDS'})
                    continue
                rows.append({
                    'retrieved_utc': snapshot['retrieved_utc'], 'observed_at': snapshot['retrieved_utc'],
                    'source_updated_at': payload.get('lastUpdatedAt', '') if isinstance(payload, dict) else '',
                    'valid_until': '', 'provider': BASE, 'bookmaker': 'Stake',
                    'source_url': snapshot['url'], 'binding_status': 'UNMAPPED_RESEARCH_ONLY',
                    'event_id': scalar(event, 'id', 'eventId', 'matchId'),
                    'event_name': scalar(event, 'name', 'title', 'eventName'),
                    'starts_at': scalar(event, 'startsAt'), 'market': scalar(offer, 'name', 'title'),
                    'selection': scalar(selection, 'name', 'label', 'title'), 'odds_decimal': odds,
                    'available': offer.get('status') == 'open' and selection.get('available') is True,
                    'event_json': json.dumps(event, ensure_ascii=False),
                    'offer_json': json.dumps(offer, ensure_ascii=False),
                    'selection_json': json.dumps(selection, ensure_ascii=False),
                })
    return rows, rejected


def main():
    p=argparse.ArgumentParser(description='Read-only NFL odds snapshot from documented Stake Sportsbook API')
    p.add_argument('--out',default='stake_snapshot')
    p.add_argument('--sport-id',help='Use previously discovered sport ID to save a request')
    p.add_argument('--tournament-id',help='Use previously discovered NFL tournament ID to save requests')
    p.add_argument('--max-requests',type=int,default=None)
    args=p.parse_args();key=os.environ.get('SPORTSBOOK_API_KEY','').strip()
    max_requests=args.max_requests if args.max_requests is not None else (12 if key else 4)
    if not key and max_requests>4:raise SystemExit('Without a key, --max-requests must be <=4 per hour, per Stake docs.')
    if max_requests<1:raise SystemExit('max requests must be >=1')
    cli=Client(max_requests,key)
    out=Path(args.out)/('stake-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+uuid4().hex)
    out.mkdir(parents=True,exist_ok=False)
    snapshots=[]
    try:
        sport=args.sport_id
        if not sport:
            r=cli.get('/en/sports');snapshots.append(r)
            options=records(r['payload'])
            hit=choose(options,('american football','american-football','futebol americano'))
            if not hit:
                print('No American football found on first sports page. Inspect stake_raw.json for actual ID.');return 2
            sport=scalar(hit,'id')
            if not sport:raise ValueError('American football entry has no id')
        tournament=args.tournament_id
        if not tournament:
            r=cli.get(f'/en/sports/{quote(str(sport),safe="")}/tournaments');snapshots.append(r)
            options=records(r['payload'])
            hit=choose(options,('national football league','nfl'))
            if not hit:
                print('No NFL tournament found on first page. Inspect stake_raw.json for league ID.');return 2
            tournament=scalar(hit,'id')
            if not tournament:raise ValueError('NFL tournament entry has no id')
        r=cli.get(f'/en/sports/{quote(str(sport),safe="")}/tournaments/{quote(str(tournament),safe="")}/matches')
        snapshots.append(r)
        matches=records(r['payload']); print(f'Loaded {len(matches)} matches on first page; {cli.count} requests')
        # Do not assume undocumented JSON schema. Produce full, lossless raw snapshot.
        (out/'stake_raw.json').write_text(json.dumps({'source':BASE,'request_count':cli.count,'snapshots':snapshots},ensure_ascii=False,indent=2),encoding='utf-8')
        rows, rejected = normalize_offers(r)
        (out/'stake_normalization.json').write_text(json.dumps({
            'rejected_odds': rejected, 'normalized_rows': len(rows),
            'binding_status': 'UNMAPPED_RESEARCH_ONLY',
            'player_props_coverage': 'NOT_DEMONSTRATED',
            'financial_approved': False,
        }, indent=2), encoding='utf-8')
        with (out/'stake_offers.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=OFFER_FIELDS);writer.writeheader();writer.writerows(rows)
        print(f'Exported {len(rows)} selections to {out}/stake_offers.csv; raw data: {out}/stake_raw.json')
        if isinstance(r['payload'],dict) and r['payload'].get('pagination',{}).get('hasNextPage'):
            print('More matches exist: only first page fetched. Paginate when rate budget allows.')
        if not rows:print('No offers detected using documented offers/selections fields. Review raw JSON; do not assume NFL props available.')
        return 0
    except Exception as e:
        print(f'ERROR: {e}',file=sys.stderr)
        return 1
    finally:
        if snapshots and not (out/'stake_raw.json').exists():
            (out/'stake_raw.json').write_text(json.dumps({'source':BASE,'snapshots':snapshots},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':sys.exit(main())
