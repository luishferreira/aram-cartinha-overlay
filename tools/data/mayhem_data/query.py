import json
import sqlite3
from datetime import datetime, timezone
from .common import read
from .rules import evaluate


def connect(output):
    pointer=read(output/'current.json');directory=output/'runs'/pointer['run']
    db=sqlite3.connect(f'file:{(directory/"mayhem.sqlite3").as_posix()}?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    return db,directory


def display_name(db,eid,locale,priority):
    rows=db.execute('SELECT c.names_json,s.source FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id WHERE c.entity_id=?',(eid,)).fetchall()
    rows=sorted(rows,key=lambda row:priority.index(row['source']) if row['source'] in priority else 999)
    for lang in dict.fromkeys([locale,'en-US','pt-BR']):
        for row in rows:
            name=json.loads(row['names_json']).get(lang)
            if name:return {'text':name,'locale':lang,'requested_locale':locale,'fallback':lang!=locale,'source':row['source']}
    return {'text':eid,'locale':None,'requested_locale':locale,'fallback':True,'source':None}


def evidence(output,eid,champion=None,locale='pt-BR',limit=30,source=None):
    db,directory=connect(output)
    try:
        config=read(directory/'config.json')
        sql='SELECT o.*,s.source FROM observations o JOIN snapshots s ON s.id=o.snapshot_id WHERE entity_id=?'
        args=[eid]
        if champion:sql+=' AND (champion_id=? OR champion_id IS NULL)';args.append(champion)
        if source:sql+=' AND s.source=?';args.append(source)
        sql+=' ORDER BY s.source,scope,stage,stats_date DESC LIMIT ?';args.append(limit)
        rows=[]
        for row in db.execute(sql,args):
            rows.append({k:json.loads(row[k]) if k.endswith('_json') else row[k] for k in row.keys()})
        catalogs=[dict(row) for row in db.execute('SELECT c.*,s.source FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id WHERE entity_id=?',(eid,))]
        for row in catalogs:
            for key in ('names_json','descriptions_json','attributes_json'):row[key]=json.loads(row[key])
        return {'entity_id':eid,'name':display_name(db,eid,locale,config['display_name_priority']),
                'catalog_evidence':catalogs,'observations':rows,'limit':limit,
                'note':'Source-specific observations. No averaging, causal interpretation or inferred patch equivalence.'}
    finally:db.close()


def context(output,champion,augments,items,offered,patches,locale='pt-BR',limit=30):
    db,directory=connect(output)
    try:
        selected=set(augments);candidate=selected|set(offered)
        result=[]
        for row in db.execute('SELECT r.data_json,s.source FROM relations r JOIN snapshots s ON s.id=r.snapshot_id WHERE champion_id=?',(champion,)):
            relation=json.loads(row['data_json'])
            if not candidate.intersection(relation['augment_ids']):continue
            result.append({'source':row['source'],'evidence':relation,
                'selected_members':sorted(selected.intersection(relation['augment_ids'])),
                'offered_members':sorted(set(offered).intersection(relation['augment_ids'])),
                'fit':'historical_evidence_not_current' if relation.get('historical_patch') else
                      'evidence_only_unknown_requirements' if relation['member_semantics']=='unspecified' else 'observed_combination_not_causal'})
        matched=[]
        for row in db.execute('SELECT data_json FROM rules'):
            rule=json.loads(row['data_json'])
            for option in offered or [None]:
                match=evaluate(rule,champion,selected,items,patches,option)
                if match:matched.append({'offered':option,**match})
        return {'champion_id':champion,'selected_augments':augments,'offered_augments':offered,
            'rule_matches':matched,'related_evidence':result[:limit],'total_related_evidence':len(result),
            'note':'Retrieval of evidence, not a recommendation ranking. Unspecified bundles are never expanded into automatic positive pairs.'}
    finally:db.close()


def status(output):
    db,directory=connect(output)
    try:
        report=read(directory/'report.json');config=read(directory/'config.json')
        sources={}
        for row in db.execute('SELECT id,metadata_json FROM sources'):
            meta=json.loads(row['metadata_json'])
            dates=[]
            for d in meta.get('stats_dates',[]):
                if not d:continue
                try:dates.append(datetime.strptime(str(d), '%Y%m%d' if len(str(d))==8 else '%Y-%m-%d').replace(tzinfo=timezone.utc))
                except ValueError:pass
            # Unknown dates do not become fresh merely because we imported old evidence today.
            age=(datetime.now(timezone.utc)-max(dates)).days if dates else None
            sources[row['id']]={**report['coverage'][row['id']],
                'age_days':age,'freshness':'unknown' if age is None else 'stale' if age>config['stale_after_days'] else 'within_threshold'}
        return {'run':directory.name,'sources':sources,'validation':report['counts'],
            'translations':report['translations'],'identity_mappings':report['identity_mappings'],
            'tables':{table:db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                for table in ('entities','catalog','observations','relations','rules','patch_notes','change_events','review_queue')}}
    finally:db.close()
