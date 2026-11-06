"""Audit complete ARAMGG API acquisition offline; no credentials needed."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).parent
BASE=ROOT/'aramgg-api'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    pointer=read(BASE/'current.json');folder=BASE/pointer['snapshot'];manifest=read(folder/'manifest.json')
    if not manifest.get('champion_sync_complete'):raise SystemExit('Champion sync incomplete; no complete report generated.')
    for name,meta in manifest['files'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Raw hash mismatch: '+name)
    catalog=read(folder/'augments.json')['data'];champions=read(folder/'champions.json')['data']
    scripts=read(ROOT/'public-snapshots/blitz-general.scripts.json')
    blitz=json.loads(json.loads(next(s for s in scripts if '/augments_en_us' in s['attrs'].get('data-url',''))['body'])['body'])
    mismatches=[r['id'] for r in catalog if str(r['id']) in blitz and r.get('key')!=blitz[str(r['id'])]['name']]
    totals=Counter(); per_champion=[];origins=Counter();regions=Counter();dates=Counter(); patches=Counter();trio_patches=Counter(); anomalies=[];trios=[]
    for c in champions:
        payload=read(folder/f'champions/{c["id"]}.json')
        if len(payload)!=1 or str(payload[0][0])!=str(c['id']):raise ValueError('Champion identity mismatch')
        data=json.loads(payload[0][1]);counts=Counter()
        for aid,row in data['augments'].items():
            counts['cards']+=1
            totals['champion_card_rows']+=1
            origin=row.get('win_rate_source');origins[str(origin)]+=1;regions[str(row.get('win_rate_region'))]+=1
            dates[str(row.get('win_rate_date'))]+=1
            patches[str(row.get('win_rate_game_patch'))]+=1
            rate=row.get('win_rate');n=row.get('num_games');wins=row.get('num_win_games')
            if rate is not None:
                counts['cards_with_win_rate']+=1;totals['cards_with_win_rate']+=1
                if n is None or wins is None:anomalies.append({'kind':'rate_without_counts','champion':c['id'],'augment':aid})
                elif int(n)<=0 or not 0<=int(wins)<=int(n):anomalies.append({'kind':'invalid_counts','champion':c['id'],'augment':aid})
                elif abs(float(rate)-int(wins)/int(n))>.00015:anomalies.append({'kind':'rate_count_mismatch','champion':c['id'],'augment':aid})
                minimum=row.get('win_rate_minimum_games')
                if minimum and n is not None and int(n)<minimum:anomalies.append({'kind':'below_minimum_sample','champion':c['id'],'augment':aid})
        for ids,row in data.get('augment_trios',{}).items():
            trio_patches[str(row.get('game_patch'))]+=1
            counts['trios']+=1;totals['trios']+=1
            n=int(row['num_games']);wins=int(row['num_win_games']);rate=float(row['win_rate'])
            minimum=data.get('match_history',{}).get('minimum_augment_trio_games')
            if not 0<=wins<=n or n<=0 or abs(rate-wins/n)>.00015:
                anomalies.append({'kind':'trio_count_mismatch','champion':c['id'],'ids':ids})
            if minimum and n<minimum:anomalies.append({'kind':'trio_below_minimum','champion':c['id'],'ids':ids})
            trios.append({'champion':c['id'],'augment_ids':ids.split(':'),'games':n,'wins':wins,'win_rate':rate})
        per_champion.append({'id':c['id'],**counts})
    expanded=read(folder/'expanded/11.json')['data'];raw_yi=json.loads(read(folder/'champions/11.json')[0][1])
    expanded_cards={str(r['id']):r for r in expanded['augments']}
    match=all(expanded_cards[aid]['stats']['rank']==int(row['rank'])
        and expanded_cards[aid]['stats']['winRate']==(float(row['win_rate']) if row.get('win_rate') is not None else None)
        for aid,row in raw_yi['augments'].items())
    credit_records=[meta['credit_headers'] for meta in manifest['files'].values() if meta.get('credit_headers',{}).get('x-credits-used-today')]
    report={
        'release':manifest['release'],'game_patch':manifest['game_patch'],'files_verified':len(manifest['files']),
        'champions':len(champions),'catalog_augments':len(catalog),'items':len(read(folder/'items.json')['data']),
        'catalog_augments_with_stats':sum(r.get('statsAvailable') is True for r in catalog),
        'catalog_augments_without_stats':[r['id'] for r in catalog if not r.get('statsAvailable')],
        'catalog_augments_with_stage_rows':sum(bool(r.get('stages')) for r in catalog),
        'shared_numeric_ids_with_blitz':sum(str(r['id']) in blitz for r in catalog),
        'internal_key_conflicts_with_blitz':mismatches,'totals':dict(totals),
        'champions_with_trios':sum(r.get('trios',0)>0 for r in per_champion),
        'trio_sample_range':[min(r['games'] for r in trios),max(r['games'] for r in trios)] if trios else [],
        'winrate_origins':dict(origins),'winrate_regions':dict(regions),'winrate_dates':dict(dates),
        'winrate_patches':dict(patches),'trio_patches':dict(trio_patches),
        'per_champion':per_champion,'anomalies':anomalies,
        'raw_vs_expanded_yi_card_stats_equal':match,
        'yi_cards':len(raw_yi['augments']),'yi_trios':len(raw_yi.get('augment_trios',{})),
        'yi_build_queue_ids':sorted(set(b['queueId'] for b in expanded['builds'])),
        'build_policy':'Queue 450 examples excluded from Mayhem evidence until mode is established.',
        'riot_queue_reference':'https://static.developer.riotgames.com/docs/lol/queues.json',
        'credits_used_today':max(int(r['x-credits-used-today']) for r in credit_records),
        'credits_remaining':manifest.get('last_known_credits_remaining'),
        'limitations':['Top five trios are a selected subset, not all possible combinations.',
            'Uploaded sample independence and representativeness are provider claims, not independently audited.',
            'Tencent recommendation/popularity and uploaded WORLD performance have different provenance.',
            'No causal synergy estimate or selection-adjusted counterfactual is supplied.',
            'Current release contains no augment stage rows, despite schema support.']}
    (folder/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='per_champion'},ensure_ascii=True,indent=2))


if __name__=='__main__':main()
