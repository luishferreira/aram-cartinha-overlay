import json
from pathlib import Path
from collections import Counter
from compare_external_sources import spearman,VALUES

ROOT=Path(__file__).parent

def expand(groups):
    return {int(i):t for t,ids in groups.items() for i in ids.split(',') if i}

def main():
    scripts=json.loads((ROOT/'public-snapshots/blitz-general.scripts.json').read_text('utf-8'))
    x=next(s for s in scripts if '/aram_mayhem_augments' in s['attrs'].get('data-url',''))
    blitz={int(r['augment_id']):r['stats']['tier']-1 for r in json.loads(json.loads(x['body'])['body'])['data']}
    ark={r['id']:r for r in json.loads((ROOT/'aramkit-data/augment-rankings.json').read_text('utf-8'))['all']}
    meta=expand(json.loads((ROOT/'browser-metasrc-global.json').read_text())['groups'])
    # Fold S+ into S for coarse letters. Preserve raw groups in source artifact.
    ids=sorted(set(meta)&set(blitz)&set(ark));score=[-VALUES[meta[i][0]] for i in ids]
    global_result={'scope':'global only; not compared directly to OP.GG champion tiers',
                   'metasrc_cards':len(meta),'matched_three_sources':len(ids),
                   'spearman_vs_blitz_tier':spearman(score,[-blitz[i] for i in ids]),
                   'spearman_vs_aramkit_tier':spearman(score,[-VALUES[ark[i]['tier']] for i in ids]),
                   'spearman_vs_aramkit_rank':spearman(score,[-ark[i]['rank'] for i in ids]),
                   'spearman_vs_aramkit_pick_rate':spearman(score,[ark[i]['pickRate'] for i in ids]),
                   'spearman_vs_aramkit_win_rate':spearman(score,[ark[i]['winRate'] for i in ids])}
    yi=expand(json.loads((ROOT/'browser-metasrc-masteryi.json').read_text())['groups'])
    base={r['augment_id']:r for r in json.loads((ROOT/'all-champion-comparison.json').read_text('utf-8')) if r['champion_id']==11}
    ids=sorted(set(yi)&set(base));closer=Counter()
    for i in ids:
        v,b,o=VALUES[yi[i][0]],VALUES[base[i]['blitz_tier']],VALUES[base[i]['opgg_tier']]
        if b!=o:closer['blitz' if abs(v-b)<abs(v-o) else 'opgg' if abs(v-o)<abs(v-b) else 'tie']+=1
    yi_result={'scope':'Master Yi diagnostic example only, not all-champion validation',
               'cards':len(yi),'matched_both_baselines':len(ids),'closer_when_baselines_disagree':dict(closer),
               'spearman_vs_blitz_tier':spearman([-VALUES[yi[i][0]] for i in ids],[-VALUES[base[i]['blitz_tier']] for i in ids]),
               'spearman_vs_opgg_tier':spearman([-VALUES[yi[i][0]] for i in ids],[-VALUES[base[i]['opgg_tier']] for i in ids]),
               'spearman_vs_opgg_popular':spearman([-VALUES[yi[i][0]] for i in ids],[base[i]['opgg_popular_raw'] for i in ids]),
               'spearman_vs_opgg_performance':spearman([-VALUES[yi[i][0]] for i in ids],[base[i]['opgg_performance_raw'] for i in ids]),
               'examples':[{'augment_id':i,'name_ptbr':base[i]['name_pt_br'],'metasrc':yi[i],'blitz':base[i]['blitz_tier'],'opgg':base[i]['opgg_tier']} for i in (1029,1336,1087)]}
    log=json.loads((ROOT/'browser-leagueofgraphs-classes.json').read_text())['groups']
    situational=json.loads((ROOT/'browser-leagueofgraphs-situational.json').read_text())['groups']
    log_result={'scope':'class tiers, not champion tiers; no direct baseline vote',
                'classes':{},'situational_flags':sum(len(s.split(',')) for s in situational.values()),
                'distinct_cards':len(set().union(*(set(expand(g)) for g in log.values())))}
    for role,groups in log.items():
        cards=expand(groups)
        assert sum(len(s.split(',')) for s in groups.values())==len(cards),role
        log_result['classes'][role]={'cards':len(cards),'tiers':dict(Counter(cards.values()))}
    result={'metasrc_global':global_result,'metasrc_masteryi':yi_result,'leagueofgraphs':log_result}
    (ROOT/'browser-source-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
