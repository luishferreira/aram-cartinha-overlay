import math
from collections import Counter
from .rules import validate_rules


def validate(batches, expected_champions, rules, entity_ids, primary_sources):
    issues=[];coverage={}
    for batch in batches:
        issues.extend(batch.issues)
        if len(set(p for p in batch.metadata.get('patches',[]) if p))>1:
            issues.append({'source':batch.source,'code':'mixed_current_patches','severity':'error',
                'detail':batch.metadata['patches']})
        covered={r['context']['champion_id'] for r in batch.observations
            if r['context'].get('scope')=='champion' and r['entity_id'].startswith('augment:')}
        coverage[batch.source]={'champions':len(covered),'expected_champions':len(expected_champions),
            'missing_champions':sorted(expected_champions-covered), 'catalog_rows':len(batch.catalog),
            'observations':len(batch.observations),'relations':len(batch.relations),
            'artifacts':len(batch.artifacts),'metadata':batch.metadata}
        # Editorial coverage may legitimately be partial; the three statistical primary sources must be complete.
        if batch.source in primary_sources and batch.source!='arammayhem' and covered!=expected_champions:
            issues.append({'source':batch.source,'code':'missing_primary_champions','severity':'error',
                           'detail':sorted(expected_champions-covered)})
        if not batch.observations:
            issues.append({'source':batch.source,'code':'empty_source','severity':'error','detail':'No observations'})
        for artifact in batch.artifacts.values():
            if artifact.get('expected_sha256') and artifact['expected_sha256']!=artifact['sha256']:
                issues.append({'source':batch.source,'code':'artifact_hash_mismatch','severity':'error','detail':artifact['local_path']})
        seen=set()
        for row in batch.observations:
            # The contract includes provenance in the identity: different public channels remain separate evidence.
            from .common import dumps
            key=(row['entity_id'],row['artifact'],dumps(row['context']),row['patch'])
            if key in seen:
                issues.append({'source':batch.source,'code':'duplicate_observation','severity':'error','detail':str(key)})
            seen.add(key)
            for name,m in row['metrics'].items():
                value=m['value']
                if value is None:continue
                valid=True
                if isinstance(value,(int,float)) and not math.isfinite(value):valid=False
                if m['unit']=='proportion' and (not isinstance(value,(int,float)) or not 0<=value<=1):valid=False
                if m['unit']=='count' and (not isinstance(value,int) or value<0):valid=False
                if not valid:issues.append({'source':batch.source,'code':'invalid_metric','severity':'error',
                    'detail':{'entity':row['entity_id'],'metric':name,'value':value}})
        for row in batch.catalog:
            attrs=row['attributes']
            if any('@Calc_' in str(v) for v in row['descriptions'].values()):
                issues.append({'source':batch.source,'code':'unresolved_effect_tokens','severity':'warning','detail':row['entity_id']})
            if attrs.get('availability')=='retired' and attrs.get('sourceStatus')=='live':
                issues.append({'source':batch.source,'code':'availability_fields_differ','severity':'warning','detail':row['entity_id']})
    for error in validate_rules(rules,entity_ids):
        issues.append({'source':'local_rules','code':'invalid_rule','severity':'error','detail':error})
    return {'coverage':coverage,'issues':issues,'counts':dict(Counter(r['severity'] for r in issues)),
            'publishable':not any(r['severity']=='error' for r in issues)}
