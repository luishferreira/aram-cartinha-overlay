"""Source agreement, preserving metric distinctions and shared coverage."""
import json,math
from collections import Counter,defaultdict
from itertools import combinations
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).parent
VALUES={'S':0,'A':1,'B':2,'C':3,'D':4,'E':5}

def ranks(values):
    groups=defaultdict(list)
    for i,v in enumerate(values):groups[v].append(i)
    result=[0]*len(values);pos=1
    for v,indices in sorted(groups.items()):
        r=pos+(len(indices)-1)/2
        for i in indices:result[i]=r
        pos+=len(indices)
    return result

def spearman(a,b):
    a,b=ranks(a),ranks(b);am,bm=mean(a),mean(b)
    da=sum((x-am)**2 for x in a);db=sum((x-bm)**2 for x in b)
    return sum((x-am)*(y-bm) for x,y in zip(a,b))/math.sqrt(da*db) if da and db else None

def main():
    base={(r['champion_id'],r['augment_id']):r for r in json.loads((ROOT/'all-champion-comparison.json').read_text('utf-8'))}
    observations=json.loads((ROOT/'external-pages-normalized.json').read_text('utf-8'))+json.loads((ROOT/'aramkit-data/normalized.json').read_text('utf-8'))
    sources=defaultdict(list)
    for r in observations:
        b=base.get((r['champion_id'],r['augment_id']))
        if b:sources[r['source']].append((r,b))
    output={}
    for source,data in sources.items():
        by_champion=defaultdict(list)
        for row,b in data:by_champion[row['champion_id']].append((row,b))
        result={'matched_observations':len(data),'champions':len(by_champion)}
        if source!='aramgg':
            closer=Counter();exact=Counter();distance=Counter();champ_votes=[]
            for cid,group in by_champion.items():
                local=Counter()
                for r,b in group:
                    t=VALUES[(r.get('tier') or r['tier_raw'])[0]]
                    bv,ov=VALUES[b['blitz_tier']],VALUES[b['opgg_tier']]
                    distance['blitz']+=abs(t-bv);distance['opgg']+=abs(t-ov)
                    exact['blitz']+=t==bv;exact['opgg']+=t==ov
                    if bv!=ov:
                        v='blitz' if abs(t-bv)<abs(t-ov) else 'opgg' if abs(t-ov)<abs(t-bv) else 'tie'
                        closer[v]+=1;local[v]+=1
                if local:champ_votes.append('blitz' if local['blitz']>local['opgg'] else 'opgg' if local['opgg']>local['blitz'] else 'tie')
            result['letter_comparison']={'same_letter':dict(exact),'mean_absolute_letter_distance':{k:v/len(data) for k,v in distance.items()},
                                         'closer_when_baselines_disagree':dict(closer),'champion_majority':dict(Counter(champ_votes))}
        result['ordering_metrics']={}
        for metric,sign in [('rank',-1),('pick_rate',1),('win_rate',1)]:
            if not any(r.get(metric) is not None for r,b in data):continue
            conflicts=Counter();correlations=defaultdict(list)
            for cid,group in by_champion.items():
                good=[(r,b) for r,b in group if r.get(metric) is not None]
                if len(good)>=5:
                    corr_groups=[good]
                    if source=='arammayhem' and metric=='rank':
                        cg=defaultdict(list)
                        for r,b in good:cg[r.get('rarity_raw')].append((r,b))
                        corr_groups=[v for v in cg.values() if len(v)>=5]
                    for name,getter in [('blitz_tier',lambda b:-VALUES[b['blitz_tier']]),('opgg_tier',lambda b:-VALUES[b['opgg_tier']]),('opgg_popular',lambda b:b['opgg_popular_raw']),('opgg_performance',lambda b:b['opgg_performance_raw'])]:
                        local_rhos=[]
                        for cg in corr_groups:
                            if any(getter(b) is None for r,b in cg):continue
                            rho=spearman([sign*r[metric] for r,b in cg],[getter(b) for r,b in cg])
                            if rho is not None:local_rhos.append(rho)
                        if local_rhos:correlations[name].append(mean(local_rhos))
                # Compare only same-rarity card pairs where baseline tiers order
                # the two cards in strictly opposite directions.
                for (a,ba),(b,bb) in combinations(good,2):
                    if a.get('rarity',a.get('rarity_raw'))!=b.get('rarity',b.get('rarity_raw')):continue
                    db=VALUES[ba['blitz_tier']]-VALUES[bb['blitz_tier']]
                    do=VALUES[ba['opgg_tier']]-VALUES[bb['opgg_tier']]
                    if db*do>=0:continue
                    dx=sign*(a[metric]-b[metric])
                    conflicts['tie' if dx==0 else 'blitz' if dx*db<0 else 'opgg']+=1
            result['ordering_metrics'][metric]={'inverted_baseline_pairs_same_rarity':dict(conflicts),
                'correlation_scope':'within rarity, averaged per champion' if source=='arammayhem' and metric=='rank' else 'within champion',
                'mean_spearman_per_champion':{k:{'rho':mean(v),'champions':len(v)} for k,v in correlations.items()}}
        output[source]=result
    (ROOT/'external-comparison-summary.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
