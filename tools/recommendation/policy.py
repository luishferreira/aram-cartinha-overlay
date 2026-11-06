"""Offline compatibility policy prototype. Does not infer champion capabilities.

Reviewed context facts are inputs, not conclusions established by this evaluator.
No statistics, source tier or popularity can override its compatibility decisions.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONTEXT_FIELDS=('candidate_id','champion_id','selected_augments','items','stage',
                'build_id','decision_horizon')
FINGERPRINT_FIELDS=CONTEXT_FIELDS+('data_run','policy_version','path_snapshot_id','level','capability_profile_revision')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def fingerprint(context):
    state={k:context.get(k) for k in FINGERPRINT_FIELDS}
    for k in ('selected_augments','items'):
        if isinstance(state[k],list):state[k]=sorted(state[k])
    return hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def load_policy(root=ROOT):
    base=root/'data/recommendation';pointer=read(base/'current.json');path=base/pointer['path']
    if base.resolve() not in path.resolve().parents:raise ValueError('Policy path escaped registry')
    if sha(path)!=pointer['sha256']:raise ValueError('Policy hash mismatch')
    policy=read(path)
    if policy['policy_version']!=pointer['policy_version']:raise ValueError('Policy version mismatch')
    for evidence in policy['source_evidence']:
        source=root/evidence['path']
        if root.resolve() not in source.resolve().parents:raise ValueError('Evidence path escaped workspace')
        if sha(source)!=evidence['sha256']:raise ValueError('Policy evidence changed; review a new policy version')
    policy['_policy_sha256']=pointer['sha256']
    policy['_evaluator_sha256']=sha(Path(__file__))
    return policy


def evaluate(policy,context):
    decisions=[];used={};rejected={};expected=fingerprint(context)

    def fact(name):
        entry=context.get('facts',{}).get(name)
        if not isinstance(entry,dict):rejected[name]='missing';return None
        if type(entry.get('value')) is not bool:rejected[name]='unknown_or_invalid_boolean';return None
        if entry.get('review_status') not in ('reviewed','verified_in_match'):
            rejected[name]='not_reviewed';return None
        if entry.get('context_fingerprint')!=expected:
            rejected[name]='context_changed';return None
        evidence=entry.get('evidence')
        if not isinstance(evidence,list) or not evidence or not all(isinstance(e,str) and e.strip() for e in evidence):
            rejected[name]='evidence_missing';return None
        used[name]=entry
        return entry['value']

    def result(state,reason):
        label=policy['compatibility_labels'][state]
        return {'policy_version':policy['policy_version'],'data_run':policy['data_run'],
            'policy_sha256':policy.get('_policy_sha256'),'evaluator_sha256':policy.get('_evaluator_sha256'),
            'candidate_id':context.get('candidate_id'),'champion_id':context.get('champion_id'),
            'context_fingerprint':expected,'compatibility':state,'label':label['label'],
            'description_pt_BR':label['pt-BR'],'reason':reason,
            'veto_recommendation':state in ('excluded','avoid'),
            'requires_review':state in ('conditional','unknown'),
            'strength_assessed':False,'used_facts':used,'rejected_facts':rejected,
            'note':'Decision assumes submitted fact reviews are correct. It does not validate champion mechanics or estimate win probability.'}

    if any(k not in context for k in CONTEXT_FIELDS):return result('unknown','incomplete_context')
    if not context['candidate_id'] or not context['champion_id'] or not context['build_id']:
        return result('unknown','identity_or_build_unknown')
    if context['decision_horizon'] not in ('current_build','remainder_of_match'):
        return result('unknown','decision_horizon_unknown')
    if fact('interaction_review_complete') is not True:
        return result('unknown','unreviewed_or_unmodeled_interactions')

    trigger=fact('card_effect_can_trigger')
    alternative=fact('card_has_alternative_benefit')
    obtainable=fact('prerequisite_can_be_obtained')
    if trigger is False and alternative is False and obtainable is False:
        return result('excluded','reviewed_no_usable_effect_within_decision_horizon')

    card=policy['conversion_cards'].get(context['candidate_id'])
    if card is None:return result('unknown','no_reviewed_card_specific_policy')
    namespace=card['profile_namespace']
    profile={k:fact(namespace+'.'+k) for k in policy['required_context_facts']}
    if any(value is None for value in profile.values()):
        return result('unknown','conversion_tradeoff_not_fully_reviewed')
    if (profile['has_output_stat_payoff'] is False and profile['has_output_bridge'] is False
            and profile['build_committed'] is True and profile['pivot_feasible'] is False):
        return result('avoid','reviewed_conversion_conflicts_with_committed_build')
    benefits=profile['has_output_stat_payoff'] or profile['has_output_bridge']
    if benefits and profile['depends_on_input_stat'] is False:
        return result('eligible','output_stat_usable_without_reviewed_input_dependency')
    if profile['pivot_feasible'] or (benefits and profile['depends_on_input_stat']):
        return result('conditional','conversion_requires_tradeoff_or_build_adaptation')
    return result('unknown','no_supported_compatibility_conclusion')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',type=Path)
    parser.add_argument('--scenarios',type=Path)
    args=parser.parse_args();policy=load_policy()
    if args.scenarios:
        cases=read(args.scenarios);results=[]
        for case in cases['cases']:
            context=case['context'];stamp=fingerprint(context)
            # Only synthetic fixtures receive generated review stamps. Real contexts
            # must supply their own reviewed evidence and matching fingerprint.
            if cases.get('kind')!='synthetic_contract_fixtures':raise ValueError('Unsupported scenario file')
            context['facts']={k:{'value':v,'review_status':'reviewed','context_fingerprint':stamp,
                'evidence':['fixture://'+case['id']]} for k,v in case['fact_assumptions'].items()}
            actual=evaluate(policy,context)
            results.append({'id':case['id'],'expected':case['expected'],
                'actual':actual['compatibility'],'passed':actual['compatibility']==case['expected']})
        print(json.dumps({'synthetic_only':True,'policy_version':policy['policy_version'],'results':results},indent=2))
        if not all(r['passed'] for r in results):raise SystemExit(1)
    elif args.context:print(json.dumps(evaluate(policy,read(args.context)),ensure_ascii=False,indent=2))
    else:parser.error('Supply --context or --scenarios')


if __name__=='__main__':main()
