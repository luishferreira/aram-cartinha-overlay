"""Audit BEES (numeric game ID 3086) across saved patch-21 sources."""
import json
from collections import Counter
from pathlib import Path
from statistics import mean,median
from html_tree import Tree

ROOT=Path(__file__).parent
ID=3086

def main():
    champions=json.loads((ROOT/'champion-snapshots/champion-catalog.json').read_text('utf-8'))['champions']
    names={c['id']:c['key'] for c in champions}
    result={}
    bdist=Counter();odist=Counter();op=[]
    for c in champions:
        b=json.loads((ROOT/f'champion-snapshots/blitz-{c["id"]}.json').read_text('utf-8'))['payload']['data']
        a=b[0]['data']['augments'].get(str(ID)) if b else None
        bdist[a.get('tier') if a else 'missing']+=1
        allop=json.loads((ROOT/f'champion-snapshots/opgg-{c["id"]}.json').read_text('utf-8'))['payload']['data']
        o=next((r for r in allop if r['id']==ID),None)
        odist[o.get('tier') if o else 'missing']+=1
        if o:
            op.append(dict(champion=c['key'],champion_id=c['id'],**o,
                           popularity_rank=1+sum(r.get('popular',0)>o['popular'] for r in allop),
                           performance_rank=1+sum(r.get('performance',0)>o['performance'] for r in allop)))
    result['blitz_champion_tier_raw_counts']=dict(bdist)
    result['opgg_champion_tier_raw_counts']=dict(odist)
    result['opgg_by_champion']=op
    result['opgg_summary']={'champions':len(op),'popularity_rank_1':sum(r['popularity_rank']==1 for r in op),
                            'popularity_rank_top3':sum(r['popularity_rank']<=3 for r in op),
                            'performance_rank_top3':sum(r['performance_rank']<=3 for r in op),
                            'median_popularity_rank':median(r['popularity_rank'] for r in op),
                            'median_performance_rank':median(r['performance_rank'] for r in op)}
    ark=json.loads((ROOT/'aramkit-data/augment-rankings.json').read_text('utf-8'))
    result['aramkit_global']=next(r for r in ark['all'] if r['id']==ID)
    result['aramkit_global_pick_rank']=1+sum(r['pickRate']>result['aramkit_global']['pickRate'] for r in ark['all'])
    resources=json.loads((ROOT/'aramkit-data/augments-en-US.json').read_text('utf-8'))
    if isinstance(resources,list):rarities={r['id']:r.get('rarity') for r in resources}
    elif isinstance(resources,dict):
        rr=resources.get('data',resources)
        rarities={int(k):v.get('rarity') for k,v in rr.items()} if isinstance(rr,dict) else {r['id']:r.get('rarity') for r in rr}
    myrarity=rarities.get(ID)
    result['aramkit_global_gold_rank']=1+sum(r['rank']<result['aramkit_global']['rank'] and rarities.get(r['id'])==myrarity for r in ark['all'])
    result['aramkit_stages']={k:next((r for r in rows if r['id']==ID),None) for k,rows in ark['stages'].items()}
    bees=[]
    for c in champions:
        d=json.loads((ROOT/f'aramkit-data/champion-details/{c["id"]}.json').read_text('utf-8'))
        a=next((r for r in d['augments']['all'] if r['id']==ID),None)
        if not a:continue
        baseline=d['champion']['stats']['winRate']
        bees.append(dict(champion=c['key'],champion_id=c['id'],baseline_win_rate=baseline,
                         descriptive_lift=a['winRate']-baseline,**a))
    result['aramkit_champions']={'count':len(bees),'tiers':dict(Counter(r['tier'] for r in bees)),
                                'rank_1':sum(r['rank']==1 for r in bees),
                                'positive_descriptive_lift':sum(r['descriptive_lift']>0 for r in bees),
                                'median_descriptive_lift':median(r['descriptive_lift'] for r in bees),
                                'sum_sample_count':sum(r['sampleCount'] for r in bees),
                                'weighted_win_rate_from_champions':sum(r['winRate']*r['sampleCount'] for r in bees)/sum(r['sampleCount'] for r in bees),
                                'top_lift':sorted(bees,key=lambda r:r['descriptive_lift'],reverse=True)[:10],
                                'examples':[r for r in bees if r['champion_id'] in [17,11,90,887,223,245,145,22,63,910]]}
    combos=json.loads((ROOT/'aramkit-data/combinations.json').read_text('utf-8'))
    result['aramkit_combo_schema_sample']=combos[:1]
    # Other sources use their own popularity denominators; preserve raw numbers.
    aramgg=[]
    external=json.loads((ROOT/'external-pages-normalized.json').read_text('utf-8'))
    for r in external:
        if r['augment_id']==ID:
            if r['source']=='aramgg':aramgg.append(r)
    result['aramgg_champion_published']={'count':len(aramgg),
       'min_win_rate':min(r['win_rate'] for r in aramgg),'max_win_rate':max(r['win_rate'] for r in aramgg),
       'mean_win_rate_unweighted':mean(r['win_rate'] for r in aramgg),
       'examples':[dict(champion=names[r['champion_id']],**r) for r in aramgg if r['champion_id'] in [17,11,90,887,223,245,145,22,63,910]]}
    for source in ['metasrc-global','leagueofgraphs-classes']:
        d=json.loads((ROOT/f'browser-{source}.json').read_text())['groups']
        if source=='metasrc-global':result['metasrc_global_tier']=next(t for t,ids in d.items() if str(ID) in ids.split(','))
        else:result['leagueofgraphs_class_tiers']={role:next((t for t,ids in tiers.items() if str(ID) in ids.split(',')),None) for role,tiers in d.items()}
    am=json.loads((ROOT/'external-snapshots/arammayhem-augments-data.json').read_text('utf-8'))
    result['arammayhem_public_dataset']=next(r for r in am['rows'] if r['augmentId']=='bees')
    (ROOT/'bees-analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    compact={k:v for k,v in result.items() if k not in ['opgg_by_champion','aramkit_champions','aramgg_champion_published','aramkit_combo_schema_sample']}
    compact['aramkit_champions']={k:v for k,v in result['aramkit_champions'].items() if k not in ['top_lift','examples']}
    compact['aramgg_champion_published']={k:v for k,v in result['aramgg_champion_published'].items() if k!='examples'}
    print(json.dumps(compact,indent=2,ensure_ascii=False))
    print('ARKEXAMPLES',[(r['champion'],r['tier'],r['rank'],r['winRate'],r['baseline_win_rate'],r['descriptive_lift']) for r in bees if r['champion_id'] in [17,11,90,887,223,245,145,22,63,910]])

if __name__=='__main__':main()
