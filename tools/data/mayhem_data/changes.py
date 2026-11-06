"""Source-local change detection: missing catalog entry is never called retired."""
from .common import dumps


def catalog_state(batches):
    state={}
    for batch in batches:
        groups={}
        for row in batch.catalog:
            key=f'{batch.source}|{row["kind"]}|{row["native_id"]}'
            value={k:row[k] for k in ('entity_id','kind','native_id','names','descriptions','attributes')}
            groups.setdefault(key,[]).append(value)
        # No content hash/path in the state: a snapshot refresh is not a mechanical change.
        for key,rows in groups.items():state[key]=sorted(rows,key=dumps)
    return state


def distinct(rows, field):
    return sorted({dumps(r[field]) for r in rows})


def effects_changed(before,after):
    # Adding another language does not imply a gameplay change. Compare shared locales.
    old_locales={locale for row in before for locale in row['names']}
    new_locales={locale for row in after for locale in row['names']}
    for locale in old_locales & new_locales:
        old={dumps(row['descriptions'].get(locale,{})) for row in before if locale in row['names']}
        new={dumps(row['descriptions'].get(locale,{})) for row in after if locale in row['names']}
        if old!=new:return True
    return False


def changes(previous, current, previous_metadata, current_metadata):
    if previous is None:
        return [{'kind':'baseline_created','source':source,'requires_review':False}
                for source in sorted(current_metadata)]
    events=[]
    for key in sorted(set(previous)|set(current)):
        source=key.split('|')[0]
        before=previous.get(key);after=current.get(key)
        if before==after:continue
        eid=(after or before)[0]['entity_id']
        if before is None:kind='catalog_entry_added'
        elif after is None:kind='catalog_entry_missing'
        elif {r['entity_id'] for r in before}!={r['entity_id'] for r in after}:kind='identity_changed'
        elif effects_changed(before,after):kind='effect_text_changed'
        elif distinct(before,'attributes')!=distinct(after,'attributes'):kind='attributes_changed'
        else:kind='localization_changed'
        events.append({'kind':kind,'source':source,'entity_id':eid,'key':key,'before':before,'after':after,
            'requires_review':kind!='localization_changed'})
    for source,meta in current_metadata.items():
        before=previous_metadata.get(source,{})
        if before.get('patches')!=meta.get('patches') or before.get('stats_patch')!=meta.get('stats_patch'):
            events.append({'kind':'source_patch_changed','source':source,'before':before.get('patches'),
                'after':meta.get('patches'),'requires_review':True})
        if before.get('catalog_patch')!=meta.get('catalog_patch'):
            events.append({'kind':'catalog_patch_changed','source':source,'before':before.get('catalog_patch'),
                'after':meta.get('catalog_patch'),'requires_review':True})
        if before.get('release')!=meta.get('release'):
            events.append({'kind':'source_release_changed','source':source,'before':before.get('release'),
                'after':meta.get('release'),'requires_review':False})
    return events


def review_queue(events, batches, rules):
    affected={e['entity_id'] for e in events if e.get('requires_review') and e.get('entity_id')}
    for event in events:
        if event.get('requires_review'):
            affected.update(r['entity_id'] for r in (event.get('before') or []) if isinstance(r,dict) and 'entity_id' in r)
    patches={e['source'] for e in events if e['kind'] in ('source_patch_changed','catalog_patch_changed')}
    result=[{'target':'new_augment','source':e['source'],'entity_id':e['entity_id'],
             'reason':'New catalog entry; inspect availability, effects and mappings.'}
            for e in events if e['kind']=='catalog_entry_added' and e['entity_id'].startswith('augment:')]
    for batch in batches:
        for relation in batch.relations:
            if batch.source in patches or affected.intersection(relation['augment_ids']+[relation['champion_id']]):
                result.append({'target':'relation','source':batch.source,'native_id':relation['native_id'],
                    'reason':'patch_or_catalog_changed','action':'Review before promoting to a mechanical rule.'})
    for rule in rules:
        dependencies=set(rule.get('required_augments',[])+rule.get('required_items',[])+rule.get('champions',[]))
        dependencies.update(rule.get('conflicting_augments',[]))
        dependencies.update(x for group in rule.get('alternative_augment_groups',[]) for x in group)
        if dependencies.intersection(affected) or patches.intersection(rule.get('validated_patches',{})):
            result.append({'target':'rule','id':rule['id'],'reason':'patch_or_catalog_changed','action':'Revalidate'})
    return result
