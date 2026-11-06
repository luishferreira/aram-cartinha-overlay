"""Auditable coverage, editorial triage and source comparisons, entirely offline."""
import csv
import json
import math
import re
import sqlite3
from collections import Counter,defaultdict
from itertools import combinations
from .common import write, read


def ranked(values):
    positions=defaultdict(list)
    for index,value in enumerate(sorted(values),1):positions[value].append(index)
    return [sum(positions[v])/len(positions[v]) for v in values]


def spearman(xs,ys):
    if len(xs)<3:return None
    a=ranked(xs);b=ranked(ys);am=sum(a)/len(a);bm=sum(b)/len(b)
    denom=math.sqrt(sum((x-am)**2 for x in a)*sum((y-bm)**2 for y in b))
    return sum((x-am)*(y-bm) for x,y in zip(a,b))/denom if denom else None


def wilson(rate,n):
    if rate is None or not n or n<=0:return None
    z=1.959963984540054;den=1+z*z/n
    mid=(rate+z*z/(2*n))/den
    half=z*math.sqrt(rate*(1-rate)/n+z*z/(4*n*n))/den
    return [max(0,mid-half),min(1,mid+half)]


def metric_value(metrics,key):
    return metrics.get(key,{}).get('value')


def canonical_catalog(db,mappings):
    records={}
    unresolved={r['entity_id']:r for r in mappings if r['method']=='unresolved'}
    for row in db.execute('SELECT c.*,s.source FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id WHERE entity_id LIKE "augment:%"'):
        eid=row['entity_id'];entry=records.setdefault(eid,{'entity_id':eid,'names':{},'sources':{},'issues':[]})
        attrs=json.loads(row['attributes_json']);names=json.loads(row['names_json'])
        source=entry['sources'].setdefault(row['source'],{'catalog_entries':[],'metric_coverage':{}})
        source['catalog_entries'].append({'native_id':row['native_id'],'names':names,
            'attributes':attrs,'artifact':row['artifact']})
        for lang,name in names.items():entry['names'].setdefault(lang,[]).append({'source':row['source'],'name':name})
        if attrs.get('availability')=='retired' and attrs.get('sourceStatus')=='live':
            entry['issues'].append('availability_fields_disagree_within_source')
        descriptions=json.loads(row['descriptions_json'])
        if re.search(r'@[^@\s]+@',json.dumps(descriptions)):
            entry['issues'].append('unresolved_effect_tokens')
    for row in db.execute('SELECT o.entity_id,s.source,o.scope,o.context_json,o.patch,o.flags_json,o.metrics_json FROM observations o JOIN snapshots s ON s.id=o.snapshot_id WHERE o.entity_id LIKE "augment:%"'):
        eid=row['entity_id'];entry=records.setdefault(eid,{'entity_id':eid,'names':{},'sources':{},'issues':[]})
        source=entry['sources'].setdefault(row['source'],{'catalog_entries':[],'metric_coverage':{}})
        context=json.loads(row['context_json']);historical=context.get('series')=='historical' or 'historical_performance_patch' in json.loads(row['flags_json'])
        for metric,details in json.loads(row['metrics_json']).items():
            if details['value'] is None:continue
            key='|'.join([row['scope'],str(context.get('stage','')),metric,str(row['patch']), 'historical' if historical else 'snapshot'])
            source['metric_coverage'][key]=source['metric_coverage'].get(key,0)+1
    for eid,entry in records.items():
        site=entry['sources'].get('arammayhem',{}).get('catalog_entries',[])
        mcp=[r for r in site if 'availability' in r['attributes']]
        downloads=[r for r in site if 'introducedPatch' in r['attributes']]
        statuses=sorted({r['attributes']['availability'] for r in mcp})
        entry['availability']={'arammayhem_claims':statuses,'present_in_latest_download':bool(downloads),
            'game_selectability':'unconfirmed','policy':'Source claims and statistical presence are not proof of in-game selectability.'}
        entry['metadata_status']='catalogued' if any(s['catalog_entries'] for s in entry['sources'].values()) else 'statistics_only'
        if entry['metadata_status']=='statistics_only':entry['issues'].append('no_catalog_metadata')
        if 'live' in statuses and not downloads:entry['issues'].append('source_live_but_absent_latest_popularity_download')
        if eid in unresolved:
            entry['identity']={'status':'unresolved','mapping':unresolved[eid],
                'classification':'source_retired' if statuses==['retired'] else 'source_live_without_canonical_match' if 'live' in statuses else 'unknown'}
        else:entry['identity']={'status':'canonical_game_id'}
        if not any('pt-BR' in r['names'] for s in entry['sources'].values() for r in s['catalog_entries']):
            entry['issues'].append('pt_BR_name_missing')
        entry['issues']=sorted(set(entry['issues']))
    return sorted(records.values(),key=lambda r:r['entity_id'])


def comparison_rows(db):
    """Match only champion-wide rows. Per-stage, rarity and historical rows stay out."""
    rows=defaultdict(dict)
    duplicates=Counter()
    for r in db.execute('SELECT o.*,s.source FROM observations o JOIN snapshots s ON s.id=o.snapshot_id WHERE o.scope="champion" AND o.entity_id LIKE "augment:game:%"'):
        c=json.loads(r['context_json']);flags=json.loads(r['flags_json']);s=r['source']
        if c.get('ranking_scope') or c.get('stage') not in (None,'all') or 'historical_performance_patch' in flags:continue
        if s not in ('blitz','opgg','aramkit','aramgg'):continue
        group=c.get('metric_group','main');key=(r['champion_id'],r['entity_id'])
        if (s,group) in rows[key]:duplicates[s]+=1;continue
        rows[key][s,group]={'patch':r['patch'],'date':r['stats_date'],'metrics':json.loads(r['metrics_json']),
            'artifact':r['artifact'],'region':c.get('region'),'upstream_source':c.get('upstream_source')}
    flat=[]
    for (champion,augment),sources in sorted(rows.items()):
        row={'champion_id':champion,'augment_id':augment}
        for (source,group),evidence in sources.items():
            prefix=source+('_performance' if group=='uploaded_performance' else '')
            for k in ('patch','date','artifact','region','upstream_source'):row[prefix+'_'+k]=evidence[k]
            for k,m in evidence['metrics'].items():row[prefix+'_'+k]=m['value']
            if source in ('aramkit','aramgg') and 'win_rate' in evidence['metrics']:
                ci=wilson(metric_value(evidence['metrics'],'win_rate'),metric_value(evidence['metrics'],'sample_count'))
                if ci:row[prefix+'_wr_interval_low'],row[prefix+'_wr_interval_high']=ci
        b=row.get('blitz_tier');o=row.get('opgg_tier')
        if b is not None and o is not None:
            row['blitz_opgg_label_equal']=b==o
            row['blitz_opgg_patch_alignment']='unknown_opgg_stats_patch'
        row['aramkit_aramgg_patch_alignment']=('exact_label_match' if row.get('aramkit_patch') and
            row['aramkit_patch']==row.get('aramgg_performance_patch') else 'unconfirmed_or_missing')
        flat.append(row)
    return flat,dict(duplicates)


def compare_summary(rows):
    # Strength order within each site's vocabulary; never a merged score.
    order={'S':6,'A':5,'B':4,'C':3,'D':2,'E':1}
    dimensions={
        'blitz_tier':lambda r:order.get(r.get('blitz_tier')),
        'opgg_tier':lambda r:order.get(r.get('opgg_tier')),
        'opgg_popularity':lambda r:r.get('opgg_popular_raw'),
        'opgg_performance_index':lambda r:r.get('opgg_performance_raw'),
        'aramkit_win_rate':lambda r:r.get('aramkit_win_rate'),
        'aramkit_popularity':lambda r:r.get('aramkit_pick_rate'),
        'aramgg_win_rate':lambda r:r.get('aramgg_performance_win_rate')}
    results=[]
    groups=defaultdict(list)
    for row in rows:groups[row['champion_id']].append(row)
    for a,b in combinations(dimensions,2):
        coefficients=[];count=0
        for champion,group in groups.items():
            eligible=[]
            for row in group:
                x=dimensions[a](row);y=dimensions[b](row)
                if x is None or y is None:continue
                # Two published zeros are unavailable, not a ranking signal.
                if ('opgg_' in a or 'opgg_' in b) and row.get('opgg_popular_raw')==0 and row.get('opgg_performance_raw')==0:continue
                eligible.append((x,y))
            count+=len(eligible)
            coefficient=spearman([x for x,y in eligible],[y for x,y in eligible])
            if coefficient is not None:coefficients.append({'champion_id':champion,'n':len(eligible),'rho':coefficient})
        # Per-champion mean is descriptive, not an independence-weighted vote or significance test.
        results.append({'dimensions':[a,b],'matched_rows':count,'champions_with_nonconstant_ranks':len(coefficients),
            'mean_within_champion_spearman':sum(c['rho'] for c in coefficients)/len(coefficients) if coefficients else None,
            'patch_alignment':'unknown_opgg_stats_patch' if any(k.startswith('opgg') for k in (a,b)) else 'source_labels_preserved_see_rows',
            'per_champion':coefficients})
    return results


def combo_candidates(db,catalog):
    lookup={e['entity_id']:e for e in catalog};result=[]
    for r in db.execute('SELECT data_json FROM relations WHERE kind="editorial_bundle"'):
        c=json.loads(r[0]);issues=['requirements_not_structured','mechanics_not_verified_in_match']
        if len(c['augment_ids'])>1:issues.append('listed_members_are_not_proven_AND_requirements')
        if any(lookup.get(e,{}).get('identity',{}).get('status')=='unresolved' for e in c['augment_ids']):issues.append('unresolved_member_identity')
        if any('retired' in lookup.get(e,{}).get('availability',{}).get('arammayhem_claims',[]) for e in c['augment_ids']):issues.append('source_retired_member')
        if not c.get('explanation') or c['explanation'].strip().lower()=='nothing.':issues.append('insufficient_explanation')
        result.append({'id':'arammayhem:'+c['native_id'],'champion_id':c['champion_id'],
            'listed_augments':c['augment_ids'],'required_augments':None,'alternative_augment_groups':None,
            'required_items':None,'conflicts':None,'source_url':c.get('url'),'source_tier':c.get('editorial_tier'),
            'explanation_original':c.get('explanation'),'artifact':c.get('explanation_artifact',c['artifact']),
            'status':'needs_semantic_review','issues':issues})
    return result


def relation_statistics(db,rows):
    baselines={(r['champion_id'],r['augment_id']):r for r in rows}
    result=[]
    for record in db.execute('SELECT r.data_json,s.source FROM relations r JOIN snapshots s ON s.id=r.snapshot_id WHERE kind IN ("observed_pair","observed_trio")'):
        relation=json.loads(record['data_json']);source=record['source'];metrics=relation['metrics']
        wr=metric_value(metrics,'win_rate');n=metric_value(metrics,'sample_count')
        members=[]
        for aid in relation['augment_ids']:
            baseline=baselines.get((relation['champion_id'],aid),{})
            prefix='aramgg_performance' if source=='aramgg' else source
            compatible=baseline.get(prefix+'_patch')==relation.get('patch') and bool(relation.get('patch'))
            if source=='aramgg':
                compatible=compatible and all(baseline.get(prefix+'_'+key)==relation.get(key)
                    for key in ('region','upstream_source')) and baseline.get(prefix+'_date')==relation.get('stats_date')
            member_wr=baseline.get(prefix+'_win_rate') if compatible else None
            members.append({'augment_id':aid,'matched_member_win_rate':member_wr,
                'combination_minus_member_pp':100*(wr-member_wr) if wr is not None and member_wr is not None else None,
                'baseline_status':'matched_source_context' if member_wr is not None else 'missing_or_incompatible'})
        result.append({'source':source,'evidence':relation,'wr_interval_95':wilson(wr,n),
            'member_baselines':members,'current_eligibility':'historical_only' if relation.get('historical_patch') else 'snapshot_patch',
            'interpretation':'Descriptive overlapping samples; differences are not causal synergy, incremental value or an adjusted effect.',
            'selection':'Only source-published top combinations; absence is not negative evidence.'})
    return result


def analyze(directory,mappings):
    db=sqlite3.connect(directory/'mayhem.sqlite3');db.row_factory=sqlite3.Row
    try:
        catalog=canonical_catalog(db,mappings);rows,duplicates=comparison_rows(db)
        comparisons=compare_summary(rows);combos=combo_candidates(db,catalog)
        relations=relation_statistics(db,rows)
        summary={'augment_entities':len(catalog),'identity_status':dict(Counter(e['identity']['status'] for e in catalog)),
            'metadata_status':dict(Counter(e['metadata_status'] for e in catalog)),
            'unresolved_classifications':dict(Counter(e['identity']['classification'] for e in catalog if e['identity']['status']=='unresolved')),
            'issues':dict(Counter(i for e in catalog for i in e['issues'])),
            'comparison_rows':len(rows),'comparison_duplicate_rows_skipped':duplicates,
            'editorial_candidates':len(combos),'editorial_review_reasons':dict(Counter(i for c in combos for i in c['issues'])),
            'rules_by_status':{r[0]:r[1] for r in db.execute('SELECT json_extract(data_json,"$.status"),count(*) FROM rules GROUP BY 1')},
            'statistical_relations':len(relations),
            'limitations':['Selectability is not confirmed by catalog presence or source live status.',
                'Correlations are descriptive within champions, not causal and not a combined recommendation score.',
                'Five source families do not imply five independent match populations.',
                'Wilson intervals assume binomial independent outcomes and ignore collection/selection bias; rounded source rates are used.',
                'No sample counts are summed across sources, slots, stages, build profiles or routes.']}
        write(directory/'canonical-augments.json',catalog)
        write(directory/'data-quality.json',summary)
        write(directory/'source-comparisons.json',{'summary':comparisons,'limitations':summary['limitations']})
        write(directory/'combo-review.json',combos)
        write(directory/'relation-statistics.json',relations)
        headers=sorted({k for r in rows for k in r})
        with (directory/'source-comparisons.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(rows)
        return summary
    finally:db.close()
