"""The compatibility contract must not confuse unknown, weak and impossible."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recommendation_policy',ROOT/'tools/recommendation/policy.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class CompatibilityPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=module.load_policy(ROOT)
        cls.cases=module.read(ROOT/'data/recommendation/scenarios/compatibility-0.1.0.json')['cases']

    def reviewed_context(self,index=0):
        case=self.cases[index];context=copy.deepcopy(case['context']);stamp=module.fingerprint(context)
        context['facts']={k:{'value':v,'review_status':'reviewed','context_fingerprint':stamp,
            'evidence':['fixture://'+case['id']]} for k,v in case['fact_assumptions'].items()}
        return context

    def test_synthetic_scenarios(self):
        for index,case in enumerate(self.cases):
            with self.subTest(case=case['id']):
                self.assertEqual(module.evaluate(self.policy,self.reviewed_context(index))['compatibility'],case['expected'])

    def test_changing_items_invalidates_context_review(self):
        context=self.reviewed_context();context['items'].append('item:game:3508')
        result=module.evaluate(self.policy,context)
        self.assertEqual(result['compatibility'],'unknown')
        self.assertEqual(result['rejected_facts']['interaction_review_complete'],'context_changed')

    def test_new_augment_invalidates_previous_build_veto(self):
        context=self.reviewed_context();context['selected_augments'].append('augment:fixture:ap-bridge')
        result=module.evaluate(self.policy,context)
        self.assertEqual(result['compatibility'],'unknown');self.assertFalse(result['veto_recommendation'])

    def test_changing_champion_invalidates_review(self):
        context=self.reviewed_context();context['champion_id']='champion:fixture:other'
        self.assertEqual(module.evaluate(self.policy,context)['compatibility'],'unknown')

    def test_unreviewed_facts_cannot_create_a_veto(self):
        context=self.reviewed_context()
        for fact in context['facts'].values():fact['review_status']='hypothesis'
        self.assertEqual(module.evaluate(self.policy,context)['compatibility'],'unknown')

    def test_missing_evidence_cannot_create_a_veto(self):
        context=self.reviewed_context();context['facts']['ad_to_ap.has_output_stat_payoff']['evidence']=[]
        self.assertEqual(module.evaluate(self.policy,context)['compatibility'],'unknown')

    def test_unknown_and_false_are_distinct(self):
        context=self.reviewed_context();context['facts']['ad_to_ap.has_output_stat_payoff']['value']=None
        self.assertEqual(module.evaluate(self.policy,context)['compatibility'],'unknown')

    def test_unreviewed_interaction_prevents_definitive_exclusion(self):
        context=self.reviewed_context(8);context['facts']['interaction_review_complete']['value']=False
        self.assertEqual(module.evaluate(self.policy,context)['compatibility'],'unknown')

    def test_reviewed_hard_exclusion_is_candidate_specific(self):
        context=self.reviewed_context(8);context['candidate_id']='augment:game:1205'
        self.assertEqual(module.evaluate(self.policy,context)['compatibility'],'unknown')

    def test_item_order_does_not_change_context_but_quantity_does(self):
        a=self.reviewed_context();a['items']=['item:game:1036','item:game:3508']
        b=copy.deepcopy(a);b['items'].reverse()
        self.assertEqual(module.fingerprint(a),module.fingerprint(b))
        b['items'].append('item:game:1036')
        self.assertNotEqual(module.fingerprint(a),module.fingerprint(b))

    def test_numeric_zero_is_not_reviewed_false(self):
        context=self.reviewed_context();context['facts']['ad_to_ap.has_output_stat_payoff']['value']=0
        self.assertEqual(module.evaluate(self.policy,context)['compatibility'],'unknown')

    def test_source_tiers_never_change_compatibility(self):
        context=self.reviewed_context();before=module.evaluate(self.policy,context)
        context['source_tiers']={'blitz':'S','opgg':'S'};context['win_rate']=.95
        after=module.evaluate(self.policy,context)
        self.assertEqual(before['compatibility'],after['compatibility'])
        self.assertEqual(before['context_fingerprint'],after['context_fingerprint'])
        self.assertTrue(after['veto_recommendation'])


if __name__=='__main__':unittest.main()
