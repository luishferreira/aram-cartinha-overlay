"""MCP is a data channel, not an AI dependency. Preserve evidence and limits."""
import json
from .common import read, entity_id, digest
from .model import metric, stats


def structured(response):
    result=response.get('result',{})
    if result.get('isError') or response.get('error'):return None
    value=result.get('structuredContent')
    if isinstance(value,dict):return value
    for block in result.get('content',[]):
        if block.get('type')!='text':continue
        try:value=json.loads(block['text'])
        except (KeyError,ValueError):continue
        if isinstance(value,dict):return value
    return None


def selected_folder(root):
    base=root/'research/arammayhem-mcp'
    if (base/'current.json').exists():
        pointer=read(base/'current.json')
        if pointer.get('complete') is False:raise ValueError('MCP snapshot is not complete')
        folder=base/pointer['snapshot']
        if base.resolve() not in folder.resolve().parents:raise ValueError('MCP snapshot escaped its source directory')
        if pointer.get('manifest_sha256') and digest((folder/'manifest.json').read_bytes())!=pointer['manifest_sha256']:
            raise ValueError('MCP manifest differs from its published pointer')
        return folder
    return base


def enrich(batch,identity,root):
    folder=selected_folder(root)
    manifests=list(folder.rglob('manifest.json'))
    origins={}
    for path in manifests:
        manifest=read(path)
        if manifest.get('complete'):
            if manifest.get('release_id')!=batch.metadata['release']:
                batch.issue('mcp_release_differs_from_download',manifest.get('release_id'),'error')
            batch.artifact(path,'https://arammayhem.com/mcp',channel='mcp_manifest',license='unverified_research_only')
            if (path.parent/'tools.json').exists():
                batch.artifact(path.parent/'tools.json','https://arammayhem.com/mcp',channel='mcp_tools',
                    expected_sha256=manifest.get('tools_sha256'))
            batch.metadata['mcp_scope']={'complete_collection':True,
                'champions':manifest['expected_champions'],
                'augment_ids':len(manifest['expected_augment_ids']),
                'requests':manifest['expected_requests']}
        records=manifest.get('files',[])
        if not isinstance(records,list):continue
        for record in records:
            if 'file' in record:origins[(path.parent/record['file']).resolve()]=record
    existing={r.get('url'):r for r in batch.relations}
    for path in sorted(folder.rglob('*.json')):
        response=read(path)
        if 'result' not in response and 'error' not in response:continue
        origin=origins.get(path.resolve(),{})
        data=structured(response)
        if data is None:
            if response.get('result',{}).get('isError') or response.get('error'):
                batch.issue('mcp_unavailable',{'file':path.name,'tool':origin.get('tool')})
                batch.artifact(path,'https://arammayhem.com/mcp',origin.get('collected_at'),
                    expected_sha256=origin.get('sha256'),channel='mcp',license='unverified_research_only',
                    tool=origin.get('tool'),arguments=origin.get('arguments'))
            continue
        artifact=batch.artifact(path,'https://arammayhem.com/mcp',origin.get('collected_at'),
            expected_sha256=origin.get('sha256'),channel='mcp',license='unverified_research_only',
            tool=origin.get('tool'),arguments=origin.get('arguments'))
        patch=data.get('patch');date=data.get('dataDate')
        if 'augmentChanges' in data:
            batch.notes.append({'patch':patch,'date':date,'url':data.get('url'),'artifact':artifact,
                'authority':'third_party_summary','complete':False,'content':data,
                'historical_patch':patch not in batch.metadata['patches']})
            continue
        if patch and patch not in batch.metadata['patches']:
            batch.issue('mcp_patch_differs_from_download',{'file':path.name,'patch':patch})
            continue
        for combo in data.get('combos',[]):
            target=existing.get(combo['url'])
            if target is None:
                target={'native_id':'mcp:'+digest(combo['url'])[:16],
                    'champion_id':identity.champion(combo['championId']),
                    'augment_ids':[identity.augment(a) for a in combo['augmentIds']],
                    'kind':'editorial_bundle','member_semantics':'unspecified','metrics':{},
                    'tags':[],'artifact':artifact,'patch':None,'url':combo['url'],
                    'validation':'hypothesis','truncated':False}
                existing[combo['url']]=target;batch.relations.append(target)
            target.update(explanation=combo.get('description'),editorial_tier=combo.get('tier'),
                explanation_artifact=artifact,response_patch=patch,response_date=date)
        for row in data.get('entries',[]):
            batch.observe(identity.champion(row['championId']),artifact,{'scope':'global'},stats(row,percent=True),patch,date)
        if 'availability' in data and 'id' in data:
            eid=identity.augment(data['id'],data['name'])
            batch.catalog.append({'entity_id':eid,'kind':'augment','native_id':data['id'],'artifact':artifact,
                'names':{'en-US':data['name']},'descriptions':{'en-US':{'description':data.get('description')}},
                'attributes':{'availability':data['availability'],'sourceStatus':data.get('sourceStatus'),'rarity':data.get('rarity')}})
            batch.observe(eid,artifact,{'scope':'global'},
                {**stats({'tier':data.get('tier'),'rank':data.get('rank')}),
                 'pick_rate':metric(float(data['pickRate'])/100 if data.get('pickRate') is not None else None,'proportion','published_popularity')},patch,date)
            for position,champion in enumerate(data.get('topChampionIds',[]),1):
                batch.observe(eid,artifact,{'scope':'augment_champion_association',
                    'champion_id':identity.champion(champion)},
                    {'position':metric(position,'ordinal','published_list_position_not_verified_strength')},patch,date,
                    flags=['association_basis_unconfirmed'])
        if 'builds' in data and 'championId' in data:
            cid=identity.champion(data['championId'])
            for group,rows in data['builds'].items():
                for index,row in enumerate(rows):
                    batch.observe(cid,artifact,{'scope':'champion_build','champion_id':cid,'group':group,
                        'items':[entity_id('item',i['itemId']) for i in row['items']], 'option':index+1},stats(row,percent=True),patch,date,
                        selector=f'builds.{group}[{index}]',flags=['truncated_top3','sample_count_unknown','not_augment_conditioned'])
            for order_index,row in enumerate(data.get('skillOrders',[])):
                context={'scope':'skill_order','champion_id':cid,'order':row['order'],'option':order_index+1}
                batch.observe(cid,artifact,context,stats(row,percent=True),patch,date,
                    selector=f'skillOrders[{order_index}]',flags=['sample_count_unknown'])
                for index,path_row in enumerate(row.get('paths',[])):
                    batch.observe(cid,artifact,{**context,'scope':'skill_path','sequence':path_row['sequence'],
                        'sequence_length':len(path_row['sequence'].split()),'path_option':index+1},stats(path_row,percent=True),patch,date,
                        selector=f'skillOrders[{order_index}].paths[{index}]',
                        flags=['sample_count_unknown','sequence_level_coverage_unconfirmed'])
