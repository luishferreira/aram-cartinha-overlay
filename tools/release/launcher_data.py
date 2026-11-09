"""Compile champion and spell aggregates from pinned research; never synthesize a tier."""
import hashlib
import json


def compile_launcher(root, db, bundle):
    champions = json.loads((root/'research/champion-snapshots/champion-catalog.json').read_text('utf8'))['champions']
    output = {str(c['id']):{**c,'sources':{},'summoners':{},'paths':[]} for c in champions}
    for item_set in bundle['itemSets']:
        output[str(item_set['associatedChampions'][0])]['paths'].append(item_set['title'].rsplit(' · ',1)[-1])
    for row in db.execute('SELECT o.*,s.source FROM observations o JOIN snapshots s ON s.id=o.snapshot_id '
                          'WHERE o.entity_id LIKE "champion:game:%" AND o.scope="global" ORDER BY o.id'):
        if row['source'] not in ('aramkit','arammayhem'):
            continue
        if json.loads(row['context_json']).get('series')=='historical':
            continue
        metrics = json.loads(row['metrics_json'])
        if not all(metrics.get(k,{}).get('value') is not None for k in ('tier','win_rate')):
            continue
        target = output[row['entity_id'].rsplit(':',1)[1]]
        target['sources'][row['source']] = {'patch':row['patch'],'date':row['stats_date'],
            'artifact':row['artifact'], 'metrics':metrics}
    manifest_path = root/'research/aramkit-data/manifest.json'
    manifest = json.loads(manifest_path.read_text('utf8'))
    origins = {str(r['champion_id']):r for r in manifest if r.get('status')==200}
    for ident, champion in output.items():
        path = root/'research/aramkit-data/champion-details'/f'{ident}.json'
        origin = origins[ident]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=origin['sha256']:
            raise ValueError('ARAMKit spell source changed: '+ident)
        raw = json.loads(path.read_text('utf8'))
        rows = []
        for row in raw.get('summoners',[]):
            ids = [s['id'] for s in row['spells']]
            if len(ids)!=2 or any(type(i) is not int or i<=0 for i in ids):
                raise ValueError('Invalid summoner spell pair')
            rows.append({'ids':ids,'rank':row.get('rank'),'pick_rate':row.get('pickRate'),
                         'win_rate':row.get('winRate'),'sample_count':row.get('sampleCount')})
        champion['summoners']['aramkit'] = {'rows':rows,'collected_at':origin['at'],
                                           'sha256':origin['sha256'],'url':origin['url']}
        champion['sources']['aramkit']['collected_at'] = origin['at']
    if any(set(c['sources'])!={'aramkit','arammayhem'} for c in output.values()):
        raise ValueError('Incomplete launcher champion coverage')
    return {'schema_version':1,'champions':output,'sources':{'aramkit':'ARAMKit','arammayhem':'Mayhem.com'},
            'spell_source':'aramkit','aramkit_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
