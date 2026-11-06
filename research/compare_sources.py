"""Normalize collected Mayhem data while preserving source-specific tier scales."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
SNAP = ROOT / 'public-snapshots'

def embedded(name, fragment):
    scripts = json.loads((SNAP / f'{name}.scripts.json').read_text('utf-8'))
    script = next(x for x in scripts if fragment in x['attrs'].get('data-url', ''))
    return json.loads(json.loads(script['body'])['body'])

def main():
    general = embedded('blitz-general', '/aram_mayhem_augments')
    champion = embedded('blitz-masteryi', '/aram_mayhem_champion')['data'][0]
    catalog = json.loads((SNAP / 'opgg-augments-ptbr.json').read_text('utf-8'))
    names = {str(x['id']): x for x in catalog['data']}
    opgg = json.loads((SNAP / 'opgg-masteryi-stats.json').read_text('utf-8'))['data']
    op_by_id = {str(x['id']): x for x in opgg}
    common = set(champion['data']['augments']) & set(op_by_id)
    records = []
    for augment_id in sorted(common, key=int):
        b = champion['data']['augments'][augment_id]
        o = op_by_id[augment_id]
        n = names.get(augment_id, {})
        records.append({'champion_id': 11, 'augment_id': int(augment_id),
                        'name_pt_br': n.get('name'), 'key': n.get('key'),
                        'blitz_tier_raw': b.get('tier'), 'opgg_tier_raw': o.get('tier'),
                        'opgg_popular_raw': o.get('popular'),
                        'opgg_performance_raw': o.get('performance')})
    result = {
        'scope': 'Master Yi is a source-validation sample, not a proposed MVP champion restriction.',
        'warning': 'Tier integers are source-specific. Do not compare without confirmed label mapping. Performance is not established as win rate.',
        'blitz_patch': champion.get('patch'), 'blitz_date': champion.get('dt'),
        'opgg_catalog_version': catalog.get('meta', {}).get('version'),
        'counts': {'blitz_general': len(general['data']),
                   'blitz_masteryi': len(champion['data']['augments']),
                   'opgg_masteryi': len(opgg), 'common_ids': len(common)},
        'blitz_tier_distribution': dict(Counter(x.get('tier') for x in champion['data']['augments'].values())),
        'opgg_tier_distribution': dict(Counter(x.get('tier') for x in opgg)),
        'blitz_champion_fields': list(champion['data']),
        'records': records,
    }
    (ROOT / 'masteryi-source-comparison.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False, indent=2))
    print('Top OP.GG popular:', [(x['name_pt_br'], x['blitz_tier_raw'], x['opgg_tier_raw'], x['opgg_popular_raw']) for x in sorted(records, key=lambda x: x['opgg_popular_raw'] or 0, reverse=True)[:6]])
    for source in ('blitz-general', 'blitz-masteryi', 'opgg-masteryi'):
        text = (SNAP / f'{source}.html').read_text('utf-8')
        import re
        print(source, 'tier label contexts:', [text[max(0,m.start()-80):m.start()+100] for m in list(re.finditer(r'(?:Tier [SABCD]|tier-[sabcf]|tier[0-9]|tier-\d)', text))[:8]])

if __name__ == '__main__':
    main()
