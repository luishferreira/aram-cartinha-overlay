"""Preserve conditional build hierarchies without expanding millions of rows in RAM.

Profiles are independently queryable; purchase routes remain children of their
profile, with starters/boots/later items attached to the appropriate route.
"""
import json
from collections import Counter
from pathlib import Path
from .common import read, digest, dumps, entity_id
from .model import stats, metric


SCHEMA='''
CREATE TABLE build_profiles(id TEXT PRIMARY KEY,snapshot_id TEXT REFERENCES snapshots(id),
 champion_id TEXT,augment_id TEXT,selection TEXT,archetype TEXT,patch TEXT,
 artifact TEXT REFERENCES artifacts(sha256),selector TEXT,context_json TEXT,
 metrics_json TEXT,item_set_json TEXT,routes_json TEXT);
CREATE INDEX build_profiles_lookup ON build_profiles(champion_id,augment_id,selection);
CREATE TABLE conditional_item_groups(id TEXT PRIMARY KEY,snapshot_id TEXT REFERENCES snapshots(id),
 champion_id TEXT,augment_id TEXT,patch TEXT,artifact TEXT REFERENCES artifacts(sha256),
 selector TEXT,metrics_json TEXT,data_json TEXT);
CREATE INDEX conditional_items_lookup ON conditional_item_groups(champion_id,augment_id);
'''


def register_conditionals(root,batch,base,patch):
    pointer_path=root/'research/aramkit-data/conditionals-current.json'
    if not pointer_path.exists():return False
    pointer=read(pointer_path);parent=root/'research/aramkit-data';folder=parent/pointer['snapshot']
    if parent.resolve() not in folder.resolve().parents:raise ValueError('Conditional snapshot escaped source')
    manifest_path=folder/'manifest.json';manifest=read(manifest_path)
    if not pointer.get('complete') or not manifest.get('complete'):raise ValueError('Incomplete conditionals')
    if digest(manifest_path.read_bytes())!=pointer['manifest_sha256']:raise ValueError('Changed conditional manifest')
    if manifest['base_url']!=base or manifest['release']!=batch.metadata['release']:
        raise ValueError('Conditional build release differs from champion release')
    expected={str(r['champion_id']) for r in read(parent/'manifest.json')}
    actual=[str(r['champion_id']) for r in manifest['files']]
    if set(actual)!=expected or len(actual)!=len(expected):raise ValueError('Incomplete/duplicate conditional champions')
    batch.artifact(pointer_path,representation='conditional_snapshot_pointer')
    batch.artifact(manifest_path,representation='conditional_snapshot_manifest')
    for row in manifest['files']:
        path=folder/row['file']
        if folder.resolve() not in path.resolve().parents:raise ValueError('Conditional file escaped snapshot')
        artifact=batch.artifact(path,row['url'],row['collected_at'],expected_sha256=row['sha256'])
        batch.build_resources.append({'path':str(path),'artifact':artifact,
            'champion_id':entity_id('champion',row['champion_id']),'patch':patch,'conditional':True})
    batch.metadata['single_augment_resource_champions']=[entity_id('champion',i) for i in sorted(map(int,expected))]
    return True


def checked_stats(row,denominator):
    result=stats(row)
    for key,entry in result.items():
        value=entry['value']
        if key in ('win_rate','pick_rate') and not 0<=value<=1:raise ValueError('Build probability out of range')
        if key=='sample_count' and (not isinstance(value,int) or value<0):raise ValueError('Invalid build sample count')
        if key=='pick_rate':entry['denominator']=denominator
    if row.get('routeCoverageRate') is not None:
        value=row['routeCoverageRate']
        if not 0<=value<=1:raise ValueError('Invalid route coverage')
        result['route_coverage_rate']=metric(value,'proportion','source_reported_route_coverage','profile_sample')
    return result


def item_refs(rows):
    # Zero denotes the source's no-boots option; never create a fictitious item 0.
    return [entity_id('item',r['id']) if r['id'] else None for r in rows]


def item_row(row,denominator):
    refs=item_refs(row.get('items',[row['item']] if 'item' in row else [row]))
    return {'item_ids':refs,'source_item_ids':[int(e.split(':')[-1]) if e else 0 for e in refs],
            'no_item_option':any(e is None for e in refs),'metrics':checked_stats(row,denominator)}


def compile_resources(db,batches):
    db.executescript(SCHEMA)
    counts=Counter();champions=set();conditional_champions=set()
    for batch in batches:
        sid=batch.metadata['snapshot_id']
        for resource in batch.build_resources:
            path=Path(resource['path'])
            if digest(path.read_bytes())!=resource['artifact']:raise ValueError('Build resource changed during compilation')
            data=read(path);cid=resource['champion_id'];conditional=resource['conditional']
            champions.add(cid)
            if conditional:conditional_champions.add(cid)
            groups=(data['builds'] if conditional else
                    [dict(g,selection=s) for s,g in data.get('builds',{}).items()])
            for gi,group in enumerate(groups):
                selection=group.get('selection','single_augment')
                aid=entity_id('augment',group['augmentId']) if conditional else None
                prefix=f'builds[{gi}]' if conditional else f'builds.{selection}'
                for ai,archetype in enumerate(group.get('archetypes',[])):
                    for pi,profile in enumerate(archetype.get('profiles',[])):
                        selector=f'{prefix}.archetypes[{ai}].profiles[{pi}]'
                        context={'archetype_metrics':checked_stats(archetype,'build_group_sample'),
                            'build_group_metrics':checked_stats(group,'champion_or_selection_sample'),
                            'selection_filter_definition':'source_defined_not_inferred',
                            'selection_bias':'completed_builds_and_purchase_routes_are_observational'}
                        routes=[]
                        for ri,route in enumerate(profile.get('routes',[])):
                            children={}
                            for key in ('starters','boots','laterItems'):
                                children[key]=[item_row(r,'route_sample') for r in route.get(key,[])]
                            routes.append({'selector':f'{selector}.routes[{ri}]',
                                'purchase_order':item_refs(route.get('purchaseOrder',[])),
                                'metrics':checked_stats(route,'profile_sample'),**children})
                        values=(digest([sid,resource['artifact'],selector]),sid,cid,aid,selection,
                            archetype['key'],resource['patch'],resource['artifact'],selector,dumps(context),
                            dumps(checked_stats(profile,'archetype_sample')),dumps(item_refs(profile['itemSet'])),dumps(routes))
                        db.execute('INSERT INTO build_profiles VALUES('+','.join('?'*13)+')',values)
                        counts['profiles']+=1;counts['routes']+=len(routes)
                        if aid:counts['conditional_profiles']+=1
                        for route in routes:
                            counts['route_options']+=sum(len(route[k]) for k in ('starters','boots','laterItems'))
            if conditional:
                for gi,group in enumerate(data['items']):
                    aid=entity_id('augment',group['augmentId']);selector=f'items[{gi}]'
                    payload={'all':[item_row(r,'champion_augment_sample') for r in group.get('all',[])],
                        'slots':{str(k):[item_row(r,'champion_augment_slot_sample') for r in rows]
                                 for k,rows in group.get('slots',{}).items()},
                        'denominator_note':'Parent labels describe hierarchy; exact eligibility and slot denominator definitions are unconfirmed.'}
                    db.execute('INSERT INTO conditional_item_groups VALUES(?,?,?,?,?,?,?,?,?)',
                        (digest([sid,resource['artifact'],selector]),sid,cid,aid,resource['patch'],resource['artifact'],
                         selector,dumps(checked_stats(group,'champion_sample')),dumps(payload)))
                    counts['conditional_item_groups']+=1
                    counts['conditional_item_rows']+=len(payload['all'])+sum(map(len,payload['slots'].values()))
            if len(champions)%30==0:print(f'Build normalization: {len(champions)} champions, {counts["profiles"]} profiles',flush=True)
    return {**counts,'champions':len(champions),'conditional_champions':len(conditional_champions)}


def query_builds(output,champion,augment=None,selection='filtered',limit=10,offset=0):
    from .query import connect
    db,directory=connect(output)
    try:
        selection='single_augment' if augment else selection
        args=[champion,selection];where='champion_id=? AND selection=?'
        if augment:where+=' AND augment_id=?';args.append(augment)
        else:where+=' AND augment_id IS NULL'
        total=db.execute('SELECT count(*) FROM build_profiles WHERE '+where,args).fetchone()[0]
        rows=[]
        for r in db.execute('SELECT * FROM build_profiles WHERE '+where+' ORDER BY archetype,selector LIMIT ? OFFSET ?',args+[limit,offset]):
            rows.append({k:json.loads(r[k]) if k.endswith('_json') else r[k] for k in r.keys()})
        groups=[]
        if augment:
            for r in db.execute('SELECT * FROM conditional_item_groups WHERE champion_id=? AND augment_id=?',(champion,augment)):
                groups.append({k:json.loads(r[k]) if k.endswith('_json') else r[k] for k in r.keys()})
        return {'run':directory.name,'champion_id':champion,'augment_id':augment,'selection':selection,
            'total_profiles':total,'offset':offset,'profiles':rows,'conditional_items':groups,
            'note':'Published observational build profiles. No fallback to unconditioned builds, no causal benefit or future win probability inferred.'}
    finally:db.close()
