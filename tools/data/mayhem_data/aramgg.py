"""Official developer API adapter. Metric origins are deliberately separate."""
import json
from .common import read, entity_id
from .model import Batch, metric


def numeric(value, integer=False):
    if value is None or value=='':return None
    return int(value) if integer else float(value)


def client_metrics(row):
    return {
        'win_rate':metric(numeric(row.get('win_rate')),'proportion','observed_win_rate'),
        'sample_count':metric(numeric(row.get('num_games'),True),'count','published_uploaded_game_sample'),
        'wins':metric(numeric(row.get('num_win_games'),True),'count','published_uploaded_wins'),
    }


def decode_champion(payload, expected_id):
    if not isinstance(payload,list) or len(payload)!=1 or len(payload[0])<4:
        raise ValueError('Unexpected ARAMGG raw champion tuple schema')
    row=payload[0]
    if str(row[0])!=str(expected_id):raise ValueError('ARAMGG champion identity mismatch')
    stats=json.loads(row[1])
    if not isinstance(stats.get('augments'),dict):raise ValueError('Missing ARAMGG augment dictionary')
    return stats,row[2],row[3]


def ranking_metrics(row):
    # The T scale is not silently mapped to the S/A scale of another source.
    return {'tier_raw':metric(row.get('tier'),'source_label','tencent_recommendation_classification'),
        'rank':metric(numeric(row.get('rank'),True),'ordinal','tencent_recommendation_order'),
        'rank_total':metric(numeric(row.get('total'),True),'count','number_of_ranked_augments'),
        'pick_rate':metric(numeric(row.get('pick_rate')),'proportion','source_popularity_denominator_unconfirmed')}


def expanded_data(path,config):
    envelope=read(path);meta=envelope['meta']
    if meta.get('schemaVersion')!=1 or meta.get('dataVersion')!=config['dataVersion'] or meta.get('gamePatch')!=config['gamePatch']:
        raise ValueError('ARAMGG envelope version does not match acquisition config')
    return envelope['data']


def import_api(root,identity):
    base=root/'research/aramgg-api';pointer=read(base/'current.json');folder=base/pointer['snapshot']
    manifest=read(folder/'manifest.json');config=read(folder/'config.json')
    if not manifest.get('champion_sync_complete'):raise ValueError('ARAMGG API snapshot is incomplete')
    batch=Batch('aramgg',{'coverage':'complete_api_champion_catalog','channel':'official_developer_api',
        'release':config['dataVersion'],'patches':[config['gamePatch']],
        'upstream_families':['tencent','aramgg-client-upload','iesdev_builds_excluded'],
        'license':'Authenticated developer access; redistribution rights unverified.'})
    artifacts={}
    for rel,meta in manifest['files'].items():
        artifacts[rel]=batch.artifact(folder/rel,meta['url'],meta.get('collected_at'),
            expected_sha256=meta['sha256'],channel='developer_api')
    patch=config['gamePatch'];dates=set();historical_performance=0;historical_trios=0
    for row in expanded_data(folder/'augments.json',config):
        batch.catalog_row('augment',row['id'],artifacts['augments.json'],{'en-US':row['name']},
            {'en-US':{'description':row.get('description'),'tooltip':row.get('tooltip')}},
            {'rarity':row.get('rarityName'),'enabled':row.get('enabled'),
             'stats_available':row.get('statsAvailable'),'internal_key':row.get('key')})
        s=row.get('stats') or {}
        if row.get('statsAvailable'):
            batch.observe(entity_id('augment',row['id']),artifacts['augments.json'],
                {'scope':'global','upstream_source':s.get('source'),'region':s.get('region')},
                {'tier_raw':metric(s.get('tier'),'source_number','source_specific_classification'),
                 'win_rate':metric(s.get('winRate'),'proportion','observed_global_win_rate'),
                 'pick_rate':metric(s.get('pickRate'),'proportion','published_popularity')},
                s.get('gamePatch'),s.get('date'),flags=['global_sample_count_unknown'])
        # Stage rows are conditional on publication; in this release all are empty.
        if row.get('stages'):batch.issue('unparsed_stage_data',row['id'])
    champions=expanded_data(folder/'champions.json',config)
    for row in champions:
        cid=entity_id('champion',row['id']);s=row.get('stats') or {}
        batch.catalog_row('champion',row['id'],artifacts['champions.json'],{'en-US':row.get('title') or row['name']},
            attributes={'key':row.get('alias'),'roles':row.get('roles')})
        batch.observe(cid,artifacts['champions.json'],{'scope':'global','upstream_source':s.get('source'),'region':s.get('region')},
            {'tier_raw':metric(s.get('tier'),'source_number','source_specific_classification'),
             'win_rate':metric(s.get('winRate'),'proportion','observed_champion_win_rate'),
             'pick_rate':metric(s.get('pickRate'),'proportion','published_popularity')},
            s.get('gamePatch'),s.get('date'),flags=['global_sample_count_unknown'])
        rel=f'champions/{row["id"]}.json'
        data,source_patch,source_date=decode_champion(read(folder/rel),row['id'])
        if source_patch!=patch:batch.issue('mixed_api_patches',{'champion':row['id'],'patch':source_patch},'error')
        if source_date:dates.add(source_date)
        a=artifacts[rel]
        for aid,s in data['augments'].items():
            eid=entity_id('augment',aid)
            batch.observe(eid,a,{'scope':'champion','champion_id':cid,
                'upstream_source':data.get('source'),'region':data.get('region'),'metric_group':'recommendation_and_popularity'},
                ranking_metrics(s),source_patch,source_date,selector=f'augments.{aid}',flags=['popularity_denominator_unknown'])
            origin=s.get('win_rate_source')
            # The uploaded WR can describe another region/date than the Tencent rank.
            if origin:
                if s.get('win_rate_date'):dates.add(s['win_rate_date'])
                c={'scope':'champion','champion_id':cid,'upstream_source':origin,
                    'region':s.get('win_rate_region'),'metric_group':'uploaded_performance',
                    'minimum_games':s.get('win_rate_minimum_games')}
                metrics=client_metrics(s)
                sample=metrics['sample_count']['value'];wr=metrics['win_rate']['value']
                minimum=c['minimum_games']
                flags=[]
                if s.get('win_rate_game_patch')!=source_patch:
                    flags.append('historical_performance_patch');historical_performance+=1
                if wr is not None and sample is not None and minimum and sample<minimum:
                    flags.append('below_published_threshold');batch.issue('below_published_threshold',{'champion':row['id'],'augment':aid})
                batch.observe(eid,a,c,metrics,s.get('win_rate_game_patch'),s.get('win_rate_date'),
                    selector=f'augments.{aid}',flags=flags)
            elif s.get('win_rate') is not None:
                batch.issue('unconfirmed_winrate_origin',{'champion':row['id'],'augment':aid})
        for combo,stats in data.get('augment_trios',{}).items():
            ids=combo.split(':')
            if len(ids)!=3 or len(set(ids))!=3:raise ValueError('Unexpected ARAMGG trio identity')
            historical=stats.get('game_patch')!=patch
            historical_trios+=int(historical)
            batch.relations.append({'native_id':f'{row["id"]}:{combo}','champion_id':cid,
                'augment_ids':[entity_id('augment',aid) for aid in ids],
                'kind':'observed_trio','member_semantics':'observed_together','metrics':{
                    **client_metrics(stats),'pick_rate':metric(numeric(stats.get('pick_rate')),'proportion','published_trio_popularity')},
                'explanation':None,'artifact':a,'patch':stats.get('game_patch'),
                'stats_date':stats.get('date'),'upstream_source':stats.get('source'),
                'region':stats.get('region'),'minimum_games':data.get('match_history',{}).get('minimum_augment_trio_games'),
                'validation':'observed_not_causal','historical_patch':historical,
                'truncated':True,'published_max_per_champion':5})
    for row in expanded_data(folder/'items.json',config):
        batch.catalog_row('item',row['id'],artifacts['items.json'],{'en-US':row['name']},
            {'en-US':{'description':row.get('description')}},
            {'cost':row.get('priceTotal'),'components':row.get('from'),'upgrades':row.get('to'),
             'in_store':row.get('inStore'),'categories':row.get('categories')})
    for path in (folder/'expanded').glob('*.json'):
        expanded=expanded_data(path,config)
        for build in expanded.get('builds',[]):
            batch.issue('build_excluded_unconfirmed_mayhem_queue',{'champion':path.stem,
                'queue_id':build.get('queueId'),'patch':build.get('patch'),'reason':'Queue 450 is normal ARAM; not assumed to be Mayhem.'})
    batch.metadata['stats_dates']=sorted(dates)
    batch.metadata['historical_performance_rows']=historical_performance
    batch.metadata['historical_trios']=historical_trios
    if historical_performance or historical_trios:
        batch.issue('historical_performance_in_current_release',{'card_rows':historical_performance,'trios':historical_trios})
    return batch
