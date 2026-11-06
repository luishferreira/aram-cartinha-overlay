"""Offline adapters for the acquired public evidence. No implicit patch inference."""
import json
from pathlib import Path
from .common import ROOT, read, entity_id, normalized_name
from .model import Batch, Identity, SOURCES, metric, stats


def blitz_catalog(path):
    script = next(s for s in read(path) if '/augments_en_us' in s['attrs'].get('data-url',''))
    return json.loads(json.loads(script['body'])['body'])


def identity_from_research(root=ROOT):
    identity = Identity()
    champions = read(root/'research/champion-snapshots/champion-catalog.json')['champions']
    for row in champions:
        identity.champions[row['key']] = entity_id('champion', int(row['id']))
        identity.champions[str(row['id'])] = entity_id('champion', int(row['id']))
    for cid,row in read(root/'research/aramkit-data/champions-en-US.json').items():
        identity.champions[row['riotId']]=entity_id('champion',int(cid))
        identity.champions[str(cid)]=entity_id('champion',int(cid))
    for key, row in blitz_catalog(root/'research/public-snapshots/blitz-general.scripts.json').items():
        identity.add_name(row['displayName'], key)
    for key, row in read(root/'research/aramkit-data/augments-en-US.json').items():
        identity.add_name(row['name'], key)
    english=root/'research/public-snapshots/opgg-augments-enus.json'
    if english.exists():
        for row in read(english)['data']:identity.add_name(row['name'],row['id'])
    aliases=root/'data/config/identity-aliases.json'
    if aliases.exists():
        opgg={str(r['id']):r for r in read(english)['data']}
        for native,alias in read(aliases).get('arammayhem',{}).items():
            target=opgg.get(alias['entity_id'].split(':')[-1],{})
            if target.get('key')!=alias['expected_internal_key']:
                raise ValueError(f'Reviewed identity alias no longer matches catalog: {native}')
            identity.reviewed_aliases[native]={**alias,'catalog_path':str(english.relative_to(root)),
                'catalog_sha256':__import__('hashlib').sha256(english.read_bytes()).hexdigest()}
    return identity


def import_blitz(root, identity):
    batch=Batch('blitz', {'coverage':'all_catalog_champions','license':'unverified_research_only'})
    path=root/'research/public-snapshots/blitz-general.scripts.json'
    artifact=batch.artifact(path, 'https://blitz.gg/lol/aram-mayhem-augments')
    catalog=blitz_catalog(path)
    for aid,row in catalog.items():
        batch.catalog_row('augment',aid,artifact,{'en-US':row['displayName']},
            {'en-US':{'description':row.get('description'),'tooltip':row.get('tooltip')}},
            {'internal_key':row['name'],'enabled':row.get('enabled'),
             'rarity':{0:'silver',1:'gold',2:'prismatic'}.get(row.get('rarity')),
             'effect_values':row.get('spellDataValues')})
    patches=set(); dates=set()
    for path in sorted((root/'research/champion-snapshots').glob('blitz-*.json')):
        envelope=read(path)
        a=batch.artifact(path,envelope.get('url'),envelope.get('collected_at'),representation='research_envelope')
        if envelope.get('status')!=200:
            batch.issue('fetch_failed',path.name,'error'); continue
        rows=envelope['payload']['data']
        if len(rows)!=1:raise ValueError(f'Unexpected Blitz schema: {path}')
        data=rows[0]; patch=data.get('patch'); date=data.get('dt'); patches.add(patch); dates.add(date)
        cid=entity_id('champion',envelope['champion_id'])
        for group,kind in [('augments','augment'),('items','item')]:
            for aid,row in data['data'][group].items():
                label=SOURCES['blitz']['tier_scale'].get(str(row['tier']))
                if label is None:batch.issue('unknown_tier',row,'error')
                batch.observe(entity_id(kind,aid),a,{'scope':'champion','champion_id':cid},
                    {'tier':metric(label,'source_label','source_specific_strength_classification'),
                     'tier_raw':metric(row['tier'],'source_number','original_tier')},patch,date,
                    f'payload.data[0].data.{group}.{aid}')
        batch.observe(cid,a,{'scope':'global'},
            {'tier':metric(SOURCES['blitz']['tier_scale'].get(str(data['data']['tier'])),'source_label','champion_tier')},patch,date)
    batch.metadata.update(patches=sorted(patches,key=str),stats_dates=sorted(dates,key=str))
    return batch


def import_opgg(root, identity):
    batch=Batch('opgg',{'coverage':'all_catalog_champions','stats_patch':None,'license':'unverified_research_only'})
    cp=root/'research/champion-snapshots/champion-catalog.json'; ca=batch.artifact(cp)
    for c in read(cp)['champions']:
        batch.catalog_row('champion',int(c['id']),ca,{'pt-BR':c['name']},attributes={'key':c['key']})
    path=root/'research/public-snapshots/opgg-augments-ptbr.json'; data=read(path)
    a=batch.artifact(path,'https://lol-api-champion.op.gg/api/meta/aram-augments?hl=pt_BR')
    batch.metadata['catalog_patch']=data.get('meta',{}).get('version')
    bc=blitz_catalog(root/'research/public-snapshots/blitz-general.scripts.json')
    for row in data['data']:
        aid=str(row['id'])
        if aid in bc and bc[aid]['name']!=row['key']:
            batch.issue('identity_conflict',{'id':aid,'keys':[bc[aid]['name'],row['key']]},'error')
        batch.catalog_row('augment',aid,a,{'pt-BR':row['name']},
            {'pt-BR':{'description':row.get('desc'),'tooltip':row.get('tooltip')}},
            {'internal_key':row['key'],'rarity':{1:'silver',4:'gold',8:'prismatic'}.get(row.get('rarity'))})
    english=root/'research/public-snapshots/opgg-augments-enus.json'
    if english.exists():
        data_en=read(english)
        meta_path=english.with_name('opgg-augments-enus.meta.json')
        origin=read(meta_path) if meta_path.exists() else {}
        ea=batch.artifact(english,'https://lol-api-champion.op.gg/api/meta/aram-augments?hl=en_US',
            origin.get('collected_at'),expected_sha256=origin.get('sha256'))
        if data_en.get('meta',{}).get('version')!=batch.metadata['catalog_patch']:
            batch.issue('locale_patch_mismatch','OP.GG English and Portuguese catalogs have different versions.','error')
        portuguese={str(r['id']):r for r in data['data']}
        for row in data_en['data']:
            if str(row['id']) in portuguese and row['key']!=portuguese[str(row['id'])]['key']:
                batch.issue('locale_identity_conflict',row['id'],'error')
            batch.catalog_row('augment',row['id'],ea,{'en-US':row['name']},
                {'en-US':{'description':row.get('desc'),'tooltip':row.get('tooltip')}},
                {'internal_key':row['key'],'rarity':{1:'silver',4:'gold',8:'prismatic'}.get(row.get('rarity'))})
    for path in sorted((root/'research/champion-snapshots').glob('opgg-*.json')):
        envelope=read(path);a=batch.artifact(path,envelope.get('url'),envelope.get('collected_at'),representation='research_envelope')
        if envelope.get('status')!=200:batch.issue('fetch_failed',path.name,'error');continue
        for row in envelope['payload']['data']:
            label=SOURCES['opgg']['tier_scale'].get(str(row['tier']))
            if label is None:batch.issue('unknown_tier',row,'error')
            batch.observe(entity_id('augment',row['id']),a,
                {'scope':'champion','champion_id':entity_id('champion',envelope['champion_id'])},
                {'tier':metric(label,'source_label','source_specific_strength_classification'),
                 'tier_raw':metric(row['tier'],'source_number','original_tier'),
                 'popular_raw':metric(row['popular'],'unknown','source_popularity_undefined_denominator'),
                 'performance_raw':metric(row['performance'],'unknown','source_performance_not_win_rate')},
                flags=['patch_unknown']+(['both_metrics_zero'] if row['popular']==row['performance']==0 else []))
    batch.issue('unknown_stats_patch','Catalog version is not proof of statistics patch.')
    return batch


def import_aramkit(root, identity):
    batch=Batch('aramkit',{'coverage':'all_catalog_champions','license':'unverified_research_only'})
    records=read(root/'research/aramkit-data/manifest.json')
    manifest={str(r['champion_id']):r for r in records}
    base=records[0]['url'].split('champion-details/')[0]
    release=base.split('/data/')[1].split('/')[0]; patch=release.split('-')[0]
    batch.metadata.update(release=release,patches=[patch],population='all',stats_dates=[release.split('-')[1]])
    for file,kind in [('augments-en-US.json','augment'),('champions-en-US.json','champion')]:
        path=root/'research/aramkit-data'/file;a=batch.artifact(path)
        for aid,row in read(path).items():
            batch.catalog_row(kind,aid,a,{'en-US':row['name']},
                {'en-US':{'tooltip':row.get('tooltip')}} if kind=='augment' else {},
                {k:row[k] for k in ('rarity','roles','balance','riotId') if k in row})
    path=root/'research/aramkit-data/augment-rankings.json';a=batch.artifact(path,base+'augment-rankings.json')
    for row in read(path)['all']:
        batch.observe(entity_id('augment',row['id']),a,{'scope':'global'},stats(row),patch,selector='all')
    for path in sorted((root/'research/aramkit-data/champion-details').glob('*.json')):
        data=read(path); cid=entity_id('champion',int(path.stem));meta=manifest[path.stem]
        a=batch.artifact(path,meta['url'],meta.get('at'),expected_sha256=meta.get('sha256'))
        champion=data['champion']
        batch.observe(cid,a,{'scope':'global'},stats({**champion['stats'],'tier':champion.get('tier'),'rank':champion.get('rank')}),patch)
        for stage,rows in [('all',data['augments']['all']),*data['augments'].get('stages',{}).items()]:
            for row in rows:
                context={'scope':'champion','champion_id':cid,'stage':str(stage)}
                metrics=stats(row)
                # Global references in champion rows are intentionally not mixed into champion observations.
                batch.observe(entity_id('augment',row['id']),a,context,metrics,patch,selector=f'augments.{stage}:{row["id"]}')
        for row in data.get('augmentCombinations',[]):
            batch.relations.append({'native_id':f'{path.stem}:{row["rank"]}', 'champion_id':cid,
                'augment_ids':[entity_id('augment',i) for i in row['augmentIds']],
                'kind':'observed_pair','member_semantics':'observed_together',
                'metrics':stats(row),'explanation':None,'artifact':a,'patch':patch,
                'validation':'observed_not_causal','truncated':True})
        import_aramkit_items(batch,data,cid,a,patch)
        batch.build_resources.append({'path':str(path),'artifact':a,'champion_id':cid,'patch':patch,'conditional':False})
        for selection,group in data.get('builds',{}).items():
            for row in group.get('archetypes',[]):
                batch.observe(cid,a,{'scope':'champion_build','champion_id':cid,'selection':selection,
                    'archetype':row['key']},stats(row),patch,selector=f'builds.{selection}.archetypes.{row["key"]}')
        for row in data.get('skills',[]):
            batch.observe(cid,a,{'scope':'skill_order','champion_id':cid,'order':row['order']},stats(row),patch)
    from .builds import register_conditionals
    if register_conditionals(root,batch,base,patch):return batch
    # Backwards compatibility with the initial one-champion acquisition.
    path=root/'research/aramkit-data/masteryi-single-augments.json'
    if path.exists():
        a=batch.artifact(path,base+'champion-details/11-single-augments.json')
        import_aramkit_items(batch,read(path),entity_id('champion',11),a,patch,conditional=True)
        batch.build_resources.append({'path':str(path),'artifact':a,'champion_id':entity_id('champion',11),'patch':patch,'conditional':True})
        batch.metadata['single_augment_resource_champions']=[entity_id('champion',11)]
    return batch


def import_aramkit_items(batch,data,cid,artifact,patch,conditional=False):
    groups = data.get('items',[]) if conditional else [dict(group,selection=selection)
        for selection,group in data.get('items',{}).items()]
    for group in groups:
        sections=[('all',group.get('all',[])), *[(str(k),v) for k,v in group.get('slots',{}).items()]]
        for slot,rows in sections:
            for row in rows:
                context={'scope':'champion_item','champion_id':cid,'slot':slot,
                    'selection':group.get('selection','single_augment')}
                if conditional:context['augment_id']=entity_id('augment',group['augmentId'])
                batch.observe(entity_id('item',row['id']),artifact,context,stats(row),patch)
                for aug in row.get('augmentSpecific',[]):
                    batch.observe(entity_id('item',row['id']),artifact,
                        {**context,'scope':'champion_augment_item','augment_id':entity_id('augment',aug['id'])},
                        stats(aug),patch)


def import_arammayhem(root, identity):
    batch=Batch('arammayhem',{'family':'arammayhem','download_license':'CC-BY-4.0'})
    aliases=root/'data/config/identity-aliases.json'
    if aliases.exists():batch.artifact(aliases,representation='reviewed_identity_aliases')
    base=root/'data/sources/arammayhem';ptr=read(base/'current.json');snapshot=base/ptr['snapshot']
    manifest=read(snapshot/'manifest.json'); records={r['path']:r for r in manifest['files']}
    batch.metadata.update(release=ptr['release_id'],patches=[manifest['patch']],stats_dates=[])
    batch.metadata['stats_dates']=[read(snapshot/'latest/augments.json')['meta'].get('statsDate')]
    # Register even documentation/license files so the imported snapshot is independently auditable.
    artifacts={}
    for rel,meta in records.items():
        artifacts[rel]=batch.artifact(snapshot/rel,meta.get('url'),meta.get('collected_at'),
            expected_sha256=meta['sha256'],license='CC-BY-4.0' if meta.get('kind')=='dataset' else None)
    for kind,file,key in [('champion','champions','championId'),('augment','augments','augmentId'),('item','items','itemId')]:
        rel=f'latest/{file}.json';data=read(snapshot/rel);a=artifacts[rel]
        for row in data['rows']:
            native=row[key]
            if kind=='champion':eid=identity.champion(native)
            elif kind=='augment':eid=identity.augment(native,row['name']['en'])
            else:
                eid=entity_id('item',row['gameItemId']) if row.get('gameItemId') else entity_id('item',native,'arammayhem')
                identity.site_items[native]=eid
            names={('en-US' if k=='en' else k):v for k,v in row['name'].items()}
            batch.catalog.append({'entity_id':eid,'kind':kind,'native_id':str(native),
                'artifact':a,'names':names,'descriptions':{},
                'attributes':{k:row[k] for k in ('rarity','introducedPatch','retiredPatch','category','cost') if k in row}})
    # Include the original historical dates and patches, not the current snapshot's patch.
    for rel in sorted(artifacts):
        if not rel.endswith('.json') or not rel.startswith(('latest/','history/')):continue
        if Path(rel).stem not in ('champions','augments'):continue
        data=read(snapshot/rel);meta=data['meta'];kind='champion' if Path(rel).stem=='champions' else 'augment'
        for row in data['rows']:
            eid=identity.champion(row['championId']) if kind=='champion' else identity.augment(row['augmentId'],row['name']['en'])
            batch.observe(eid,artifacts[rel],{'scope':'global','series':'latest' if rel.startswith('latest/') else 'historical'},
                {'pick_rate':metric(row.get('pickRate')/100 if row.get('pickRate') is not None else None,'proportion','published_popularity'),
                 'popularity_rank':metric(row.get('pickRateRank'),'ordinal','popularity_ranking')},
                meta.get('patch'),meta.get('statsDate'),flags=['stats_date_estimated'] if meta.get('statsDateSource')=='estimated' else [])
    rel='latest/combos.json'
    for row in read(snapshot/rel)['rows']:
        names=row.get('augmentNames',[])
        ids=[identity.augment(aid,names[i].get('en') if i<len(names) else None) for i,aid in enumerate(row['augmentIds'])]
        batch.relations.append({'native_id':str(row['comboId']),'champion_id':identity.champion(row['championId']),
            'augment_ids':ids,'kind':'editorial_bundle','member_semantics':'unspecified',
            'metrics':{},'tags':row['types'],'explanation':None,'artifact':artifacts[rel],
            'patch':None,'url':row['url'],'validation':'hypothesis','truncated':False})
    # One source family, with independently archived channel provenance.
    from .mcp import enrich
    enrich(batch,identity,root)
    # The already acquired HTML champion recommendations contain additional champion-specific evidence.
    path=root/'research/external-pages-normalized.json'
    if path.exists():
        a=batch.artifact(path,representation='derived_research_extract')
        for row in read(path):
            if row['source']!='arammayhem':continue
            batch.observe(entity_id('augment',row['augment_id']),a,
                {'scope':'champion','champion_id':entity_id('champion',row['champion_id']),'ranking_scope':'rarity'},
                {'tier':metric(row['tier_raw'],'source_label','champion_rarity_tier'),
                 'rank':metric(row['rank'],'ordinal','champion_rarity_ranking'),
                 'pick_rate':metric(row.get('pick_rate'),'proportion','published_appearance_rate')},flags=['truncated_top6_per_rarity','patch_unknown','prior_research_extract'])
    return batch


def import_secondary(root, identity, source):
    if source=='aramgg' and (root/'research/aramgg-api/current.json').exists():
        pointer=read(root/'research/aramgg-api/current.json')
        if pointer.get('champion_sync_complete'):
            from .aramgg import import_api
            return import_api(root,identity)
    batch=Batch(source,{'license':'unverified_research_only','coverage':SOURCES[source]['coverage']})
    if source=='aramgg':
        batch.metadata['coverage']='published_top20_per_champion'
        # Parse original HTML at build time; do not silently depend on an old derived file.
        import sys
        sys.path.insert(0,str(ROOT/'research'))
        from html_tree import Tree
        catalog=blitz_catalog(root/'research/public-snapshots/blitz-general.scripts.json')
        for path in sorted((root/'research/external-champions').glob('aramgg-*.html')):
            meta=read(path.with_suffix('.meta.json'));a=batch.artifact(path,meta.get('url'),meta.get('collected_at'),expected_sha256=meta.get('sha256'))
            cid=entity_id('champion',int(path.stem.split('-')[1]))
            for node in Tree(path.read_text(encoding='utf-8')).root.find('tr',lambda n:'data-row' in n.attrs and 'data-tier' in n.attrs):
                link=next(node.find('a',lambda n:n.attrs.get('data-champion-link-placement')=='augment_table'),None)
                if not link:continue
                aid=link.attrs['data-champion-link-target']
                if aid in catalog and normalized_name(link.text())!=normalized_name(catalog[aid]['displayName']):
                    batch.issue('identity_conflict',{'id':aid,'name':link.text()},'error');continue
                batch.observe(entity_id('augment',aid),a,{'scope':'champion','champion_id':cid},
                    {'tier_raw':metric(node.attrs['data-tier'],'source_label','unmapped_T_scale'),
                     'win_rate':metric(float(node.attrs['data-win-rate']),'proportion','observed_win_rate'),
                     'pick_rate':metric(float(node.attrs['data-pick-rate']),'proportion','published_popularity')},
                    flags=['truncated_top20','patch_unknown'])
    else:
        for name in ['browser-metasrc-global.json','browser-metasrc-masteryi.json']:
            path=root/'research'/name;data=read(path);a=batch.artifact(path,data['url'],data.get('collected_date'),channel='browser')
            for tier,ids in data['groups'].items():
                for aid in ids.split(','):
                    context={'scope':'champion','champion_id':entity_id('champion',data['champion_id'])} if 'champion_id' in data else {'scope':'global'}
                    batch.observe(entity_id('augment',aid),a,context,
                        {'tier':metric(tier,'source_label','source_specific_classification')},data.get('patch'))
        batch.issue('partial_champion_coverage','Only Master Yi browser snapshot; not all champions.')
    return batch


def load_all(root=ROOT):
    identity=identity_from_research(root)
    config=read(root/'data/config/pipeline.json')
    enabled=set(config['enabled_sources'])-set(config.get('excluded_augment_sources',[]))
    adapters={'blitz':import_blitz,'opgg':import_opgg,'aramkit':import_aramkit,'arammayhem':import_arammayhem}
    batches=[]
    for source in ('blitz','opgg','aramkit','arammayhem','aramgg','metasrc'):
        if source not in enabled:continue
        batches.append(adapters[source](root,identity) if source in adapters else import_secondary(root,identity,source))
    return identity,batches
