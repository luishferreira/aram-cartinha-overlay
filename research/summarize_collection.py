import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / 'champion-snapshots'
BLITZ_LABELS = {1:'S',2:'A',3:'B',4:'C',5:'D'}
OPGG_LABELS = {0:'S',1:'A',2:'B',3:'C',4:'D',5:'E'}

def main():
    catalog = json.loads((OUT/'champion-catalog.json').read_text('utf-8'))['champions']
    op_catalog = {str(c['id']):c for c in json.loads((ROOT/'public-snapshots/opgg-augments-ptbr.json').read_text('utf-8'))['data']}
    names = {i:c['name'] for i,c in op_catalog.items()}
    scripts = json.loads((ROOT/'public-snapshots/blitz-general.scripts.json').read_text('utf-8'))
    catalog_script = next(s for s in scripts if '/augments_en_us' in s['attrs'].get('data-url',''))
    blitz_catalog = json.loads(json.loads(catalog_script['body'])['body'])
    shared_catalog_ids = set(blitz_catalog)&set(op_catalog)
    mismatches = [i for i in shared_catalog_ids if blitz_catalog[i]['name'] != op_catalog[i]['key']]
    if mismatches:
        raise ValueError(f'Cannot compare source IDs with conflicting keys: {mismatches}')
    rows, coverage = [], []
    for c in catalog:
        pair = {}
        for source in ('blitz','opgg'):
            p = OUT/f'{source}-{c["id"]}.json'
            pair[source] = json.loads(p.read_text('utf-8')) if p.exists() else {}
        bdata = pair['blitz'].get('payload',{}).get('data',[])
        b = bdata[0].get('data',{}).get('augments',{}) if bdata else {}
        o = {str(x['id']):x for x in pair['opgg'].get('payload',{}).get('data',[])}
        common = set(b)&set(o)
        coverage.append({'champion_id':c['id'],'key':c['key'],
                         'blitz_entries':len(b),'opgg_entries':len(o),'common_entries':len(common),
                         'opgg_zero_both':sum(x.get('popular')==0 and x.get('performance')==0 for x in o.values()),
                         'blitz_patch':bdata[0].get('patch') if bdata else None,
                         'errors':{s:x.get('error') for s,x in pair.items() if x.get('error') or not x}})
        for aid in common:
            bt,ot = b[aid].get('tier'),o[aid].get('tier')
            if bt not in BLITZ_LABELS or ot not in OPGG_LABELS:
                continue
            rows.append({'champion_id':c['id'],'champion':c['key'],'augment_id':int(aid),
                         'name_pt_br':names.get(aid),'blitz_tier':BLITZ_LABELS[bt],
                         'opgg_tier':OPGG_LABELS[ot],'tier_gap':abs((bt-1)-ot),
                         'opgg_popular_raw':o[aid].get('popular'),
                         'opgg_performance_raw':o[aid].get('performance'),
                         'opgg_zero_both':o[aid].get('popular')==0 and o[aid].get('performance')==0})
    active = [r for r in rows if not r['opgg_zero_both']]
    summary = {'champions_in_catalog':len(catalog),
               'blitz_catalog_cards':len(blitz_catalog), 'opgg_catalog_cards':len(op_catalog),
               'shared_catalog_ids_with_matching_keys':len(shared_catalog_ids),
               'champions_with_blitz_data':sum(c['blitz_entries']>0 for c in coverage),
               'champions_with_opgg_data':sum(c['opgg_entries']>0 for c in coverage),
               'common_champion_augment_pairs':len(rows),
               'common_pairs_excluding_opgg_both_zero':len(active),
               'tier_gap_distribution_all':dict(Counter(r['tier_gap'] for r in rows)),
               'tier_gap_distribution_excluding_opgg_both_zero':dict(Counter(r['tier_gap'] for r in active)),
               'patches_blitz':dict(Counter(c['blitz_patch'] for c in coverage)),
               'coverage':coverage,
               'limitations':['Not raw matches. No causal synergy estimate.',
                              'Blitz and OP.GG tier definitions are not established as equivalent despite matching letter labels.',
                              'OP.GG performance is not established as win rate; values can exceed 100.',
                              'OP.GG both-zero flag is descriptive; it does not prove no games or a missing observation.',
                              'Cross-source patch identity of OP.GG stats is unconfirmed: response lacks patch metadata.',
                              'Blitz mapping confirmed from rendered HTML and general JSON: 1=S,2=A,3=B,4=C,5=D. OP.GG mapping confirmed in installed UI code: 0=S through 5=E.']}
    (ROOT/'coverage-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'all-champion-comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('coverage','limitations')},indent=2))
    print('Master Yi examples:',json.dumps([r for r in rows if r['champion_id']==11 and r['augment_id'] in (1001,1087,1336,1098)],ensure_ascii=False))

if __name__ == '__main__':
    main()
