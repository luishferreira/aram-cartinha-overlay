"""Verify research coverage, counts and lineage entirely offline; save a reviewable result."""
import hashlib
import json
from collections import Counter
from audit_item_sources import OUT, ROOT, write

def read(path):
    return json.loads(path.read_text('utf8'))

def main():
    verified = 0
    for manifest_path in OUT.rglob('manifest.json'):
        manifest = read(manifest_path)
        records = manifest.get('records', {})
        if isinstance(records, list):
            records = {r['file']: r for r in records}
        for record in records.values():
            path = manifest_path.parent / record['file']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], path
            verified += 1
    records = read(OUT / 'manifest.json')['records']
    expected = read(OUT / 'expansion-plan.json')
    assert set(expected) <= records.keys(), 'An expected champion/build page is missing'
    coverage = read(OUT / 'normalized/coverage.json')
    assert not coverage['parse_errors']
    assert not coverage['unmapped_arammayhem_items']
    assert not coverage['unmapped_lemonnation_champions']
    aram = read(OUT / 'normalized/arammayhem.json')['records']
    lemon = read(OUT / 'normalized/lemonnation.json')['records']
    opgg = read(OUT / 'normalized/opgg.json')['records']
    assert len(aram) == len({r['champion_id'] for r in aram}) == 173
    assert len(lemon) == 66 and len({r['champion_id'] for r in lemon}) == 63
    for record in aram + opgg:
        for rows in record['groups'].values():
            for row in rows:
                assert 0 <= row['pick_rate'] <= 1 and 0 <= row['win_rate'] <= 1
    comparisons = []
    for champion in ['masteryi', 'ashe', 'lulu']:
        pair = [next(r for r in opgg if r['url'] == f'https://op.gg/lol/modes/{mode}/{champion}/items') for mode in ['aram', 'aram-mayhem']]
        a, b = pair
        assert a['query'] == b['query'] == {'region': 'global', 'tier': 'all', 'patch': '16.22'}
        assert a['published_modes'] == ['aram'] and b['published_modes'] == ['aram_mayhem']
        assert set(a['groups']) == set(b['groups']) == {'core', 'boots', 'starting', 'items'}
        comparisons.append({'champion': champion, 'query': a['query'],
            'same_core_item_sequences': [r['item_ids'] for r in a['groups']['core']] == [r['item_ids'] for r in b['groups']['core']],
            'same_complete_groups': a['groups'] == b['groups'],
            'aram_first_core': a['groups']['core'][0], 'mayhem_first_core': b['groups']['core'][0]})
        assert not comparisons[-1]['same_complete_groups']
    write(OUT / 'normalized/opgg-route-comparison.json', comparisons)
    mcp_checks = []
    for champion in ['MasterYi', 'Brand', 'Lulu']:
        response = read(OUT / f'mcp-build-probes/{champion}.json')['result']
        value = response.get('structuredContent')
        if value is None:
            value = next(json.loads(c['text']) for c in response['content'] if c.get('type') == 'text')
        page = next(r for r in aram if r['champion_key'] == champion.lower())
        assert value['patch'] == page['patch'] and value['dataDate'] == page['data_date']
        groups = {}
        for group, rows in value['builds'].items():
            web_rows = page['groups'][group]
            assert len(web_rows) >= len(rows)
            for web, mcp in zip(web_rows, rows):
                assert [i['game_item_id'] for i in web['items']] == [int(i['itemId']) for i in mcp['items']]
                assert abs(web['pick_rate'] - float(mcp['pickRate'].strip('%')) / 100) < 1e-12
                assert abs(web['win_rate'] - float(mcp['winRate'].strip('%')) / 100) < 1e-12
            groups[group] = {'html': len(web_rows), 'mcp': len(rows), 'prefix_and_metrics_equal': True}
        mcp_checks.append({'champion': champion, 'patch': value['patch'], 'data_date': value['dataDate'], 'groups': groups})
    write(OUT / 'normalized/mcp-html-comparison.json', mcp_checks)
    api = OUT / 'mayhemstats-api/filtered-26.21-26.22'
    champs = read(api / 'champion_stats.json')['rows']
    champ_games = {(r['patch'], r['queue_id'], r['champion_id']): r['games'] for r in champs}
    normalized = []
    stats_summary = {}
    for view, kind in [('item_stats', 'final_inventory_slot_occurrences'), ('item_purchase_stats', 'participants_first_purchase_per_item')]:
        data = read(api / (view + '.json'))
        rows = data['rows']
        assert data['complete'] and len(rows) == data['total_reported']
        keys = [(r['patch'], r['queue_id'], r['champion_id'], r['item_id']) for r in rows]
        assert len(set(keys)) == len(rows)
        for row in rows:
            assert row['queue_id'] == 2400 and row['patch'] in {'26.21', '26.22'}
            assert 0 <= row['wins'] <= row['picks'] and row['picks'] > 0
            assert (row['patch'], row['queue_id'], row['champion_id']) in champ_games
            normalized.append({'source': 'mayhemstats', 'view': view, 'patch': row['patch'], 'queue_id': 2400,
                'champion_id': row['champion_id'], 'game_item_id': row['item_id'],
                'count_unit': kind, 'picks': row['picks'], 'wins': row['wins'],
                'win_rate': row['wins'] / row['picks'], 'win_rate_basis': 'derived_from_published_counts',
                **({'avg_first_buy_s': row['avg_first_buy_s']} if view == 'item_purchase_stats' else {}),
                'flags': ['not_augment_conditioned', 'not_a_joint_build_sequence']})
        stats_summary[view] = {'rows': len(rows), 'by_patch': dict(Counter(r['patch'] for r in rows)),
            'entries_with_at_least_20': {p: sum(r['patch'] == p and r['picks'] >= 20 for r in rows) for p in ['26.21', '26.22']}}
    write(OUT / 'normalized/mayhemstats.json', {'schema': 'item-source-research-1', 'metric_unit': 'proportion',
        'artifacts_manifest': str((api / 'manifest.json').relative_to(ROOT)), 'records': normalized})
    stats_summary['champion_appearances'] = {p: sum(r['games'] for r in champs if r['patch'] == p) for p in ['26.21', '26.22']}
    stats_summary['champions_by_patch'] = dict(Counter(r['patch'] for r in champs))
    stats_summary['all_time_community_totals'] = read(api / 'community_totals.json')['rows'][0]
    stats_summary['patch_spans'] = [r for r in read(api / 'community_patch_spans.json')['rows'] if r['patch'] in {'26.21', '26.22'}]
    write(OUT / 'normalized/mayhemstats-summary.json', stats_summary)
    result = {'result': 'passed', 'verified_artifact_hashes': verified, 'expected_pages_present': len(expected),
              'arammayhem_champions': 173, 'lemonnation_builds': 66, 'lemonnation_champions': 63,
              'opgg_paired_champions': 3, 'mcp_html_paired_champions': 3,
              'mayhemstats_item_rows': len(normalized), 'active_data_modified': False}
    write(OUT / 'validation.json', result)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
