"""Versioned runtime consensus: one equally weighted input per available source."""
from collections import Counter
import math
import re

MODEL_VERSION='1.0.0'
NAME='Keitinha Score'
TIER_POINTS={'S':90,'A':70,'B':50,'C':30,'D':10}
TIER_INPUTS=(('aramkit','aramkit'),('blitz','blitz'),('arammayhem','arammayhem_champion_tier'))


def tier_points(tier):
    if not isinstance(tier,str):return None
    match=re.fullmatch(r'([SABCD])([+-]?)',tier.strip().upper())
    if not match:return None
    letter,subtier=match.groups()
    return TIER_POINTS[letter]+{'+':5,'-':-5,'':0}[subtier]


def popularity_percentiles(rankings):
    """Use the full champion population, with midranks for ties; never just an offer."""
    n=len(rankings)
    if not n:return {}
    for row in rankings.values():
        rank=row.get('rank')
        if (type(rank) is not int or not 1<=rank<=n or row.get('published_entries')!=n):return {}
    ties=Counter(row['rank'] for row in rankings.values())
    # Competition ranks must agree with the sizes of the tied groups.
    position=1
    for rank,size in sorted(ties.items()):
        if rank!=position:return {}
        position+=size
    result={}
    for candidate,row in rankings.items():
        rank=row['rank'];tied=ties[rank]
        midrank=rank+(tied-1)/2
        points=50.0 if n==1 else 100*(n-midrank)/(n-1)
        result[candidate]={'points':points,'rank':rank,'published_entries':n,'tied_entries':tied,
                           'method':'champion_published_population_midrank_0_100'}
    return result


def calculate(sources,popularity=None):
    """Do not score OP.GG tier, global fallbacks, samples, WR or combo hypotheses."""
    components=[]
    for source,key in TIER_INPUTS:
        row=sources.get(key)
        if not row or row.get('scope')!='champion':continue
        if source=='arammayhem' and row.get('context',{}).get('ranking_scope')!='rarity':continue
        tier=row.get('metrics',{}).get('tier',{}).get('value')
        points=tier_points(tier)
        if points is not None:components.append({'source':source,'indicator':'tier','raw_value':tier,'points':points})
    if popularity:
        points=popularity.get('points')
        if type(points) in (int,float) and math.isfinite(points) and 0<=points<=100:
            components.append({'source':'opgg','indicator':'popularity_percentile',
                               'points':points,'normalization':dict(popularity)})
    n=len(components)
    for component in components:component['weight']=1/n
    value=sum(c['points'] for c in components)/n if n else None
    return {'name':NAME,'model_version':MODEL_VERSION,'value':value,'scale':[0,100],
            'available_sources':n,'expected_sources':4,'components':components,
            'scope':'champion_source_consensus_not_build_or_synergy','is_win_rate':False}
