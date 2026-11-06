"""Explicit rule matching. This module never infers synergy from a list of cards."""
VALID_STATUSES={'hypothesis','reviewed','verified_in_match'}


def validate_rules(rules, entity_ids):
    errors=[];seen=set()
    for rule in rules:
        rid=rule.get('id')
        if not rid or rid in seen:errors.append(f'Duplicate/missing rule id: {rid}')
        seen.add(rid)
        if rule.get('status') not in VALID_STATUSES:errors.append(f'{rid}: invalid status')
        if not rule.get('evidence'):errors.append(f'{rid}: evidence required')
        if not rule.get('explanation',{}).get('en-US') or not rule.get('explanation',{}).get('pt-BR'):
            errors.append(f'{rid}: explanations required in pt-BR and en-US')
        if rule.get('status')!='hypothesis' and not rule.get('validated_patches'):
            errors.append(f'{rid}: reviewed rule requires source-specific validated_patches')
        if rule.get('status')!='hypothesis' and (not isinstance(rule.get('review_revision'),int) or rule['review_revision']<1):
            errors.append(f'{rid}: reviewed rule requires positive review_revision')
        references=[*rule.get('champions',[]),*rule.get('required_augments',[]),
            *rule.get('required_items',[]),*rule.get('conflicting_augments',[]),
            *[item for group in rule.get('alternative_augment_groups',[]) for item in group]]
        for eid in references:
            if eid not in entity_ids:errors.append(f'{rid}: unknown entity {eid}')
    return errors


def evaluate(rule, champion, augments, items, patches, offered=None):
    """Return explainable fit; patch maps stay source-specific and exact."""
    augments=set(augments);items=set(items)
    if offered:augments.add(offered)
    if rule.get('champions') and champion not in rule['champions']:return None
    if augments.intersection(rule.get('conflicting_augments',[])):
        return {'rule_id':rule['id'],'fit':'conflict','status':rule['status']}
    missing_aug=sorted(set(rule.get('required_augments',[]))-augments)
    missing_items=sorted(set(rule.get('required_items',[]))-items)
    alternatives=[group for group in rule.get('alternative_augment_groups',[]) if not augments.intersection(group)]
    patch_ok=bool(rule.get('validated_patches')) and all(patches.get(source)==patch
        for source,patch in rule.get('validated_patches',{}).items())
    if rule.get('pending_review'):fit='needs_review'
    elif not patch_ok:fit='needs_patch_review'
    elif rule['status']=='hypothesis':fit='hypothesis'
    elif rule.get('context_requirements'):fit='needs_context_review'
    elif missing_aug or missing_items or alternatives:fit='conditional'
    else:fit='active'
    return {'rule_id':rule['id'],'fit':fit,'status':rule['status'],'missing_augments':missing_aug,
        'missing_items':missing_items,'missing_alternative_groups':alternatives,
        'context_requirements':rule.get('context_requirements',[]),
        'explanation':rule['explanation'],'evidence':rule['evidence']}
