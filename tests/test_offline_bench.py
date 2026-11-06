"""Native-path coverage and replay invariants, not synthetic recommendation truth."""
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/recommendation'))
import offline
import policy


class OfflineBench(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=policy.load_policy(ROOT);cls.bench=offline.Bench(ROOT,cls.policy)
        cls.suite=offline.read(ROOT/'data/recommendation/scenarios/build-paths-0.2.1.json')

    @classmethod
    def tearDownClass(cls):cls.bench.close()

    def state(self,path='ap'):
        return {'champion_id':'champion:game:22','active_path':path,'selected_augments':[],
                'items':[],'offered_augments':['augment:game:1205'],'stage':1}

    def test_registry_covers_all_173_champions_without_inventing_paths(self):
        actual={(p['champion_id'],p['native_key']) for p in self.bench.registry['paths']}
        source=set(self.bench.db.execute('SELECT DISTINCT champion_id,archetype FROM build_profiles WHERE augment_id IS NULL AND selection="filtered"'))
        self.assertEqual(actual,{tuple(r) for r in source})
        self.assertEqual(len({c for c,k in actual}),173)

    def test_switch_does_not_reduce_available_paths(self):
        before=self.bench.snapshot(self.state('ap'));after=self.bench.snapshot(self.state('on_hit'))
        self.assertEqual(before['available_paths'],after['available_paths'])
        self.assertEqual(len(after['available_paths']),4)

    def test_switch_keeps_owned_items_and_selected_augments(self):
        replay=self.bench.replay(self.suite['scenarios'][1]);before=replay['steps'][-2];after=replay['steps'][-1]
        self.assertEqual(before['state']['items'],after['state']['items'])
        self.assertEqual(before['state']['selected_augments'],after['state']['selected_augments'])
        self.assertEqual(before['state']['offered_augments'],after['state']['offered_augments'])
        self.assertNotEqual(before['active_path']['id'],after['active_path']['id'])
        self.assertTrue(after['context_review_invalidated'])

    def test_path_specific_profiles_really_change(self):
        ap=self.bench.assess(self.state('ap'),'augment:game:1205')
        on_hit=self.bench.assess(self.state('on_hit'),'augment:game:1205')
        self.assertGreater(ap['conditional_profile_count'],0)
        self.assertEqual(ap['representative_profile']['archetype'],'ap')
        self.assertEqual(on_hit['conditional_profile_count'],0)
        self.assertIsNone(on_hit['representative_profile'])
        self.assertEqual(on_hit['evidence_scope'],'champion_only')
        self.assertFalse(on_hit['compatibility']['veto_recommendation'])

    def test_unknown_is_not_overridden_by_actual_build_win_rate(self):
        result=self.bench.assess(self.state(),'augment:game:1205')
        self.assertIsNotNone(result['representative_profile'])
        self.assertEqual(result['compatibility']['compatibility'],'unknown')

    def test_synthetic_review_is_invalidated_after_path_switch(self):
        state=self.state();candidate='augment:game:1205';path=self.bench.get_path(state['champion_id'],'ap')
        context={'candidate_id':candidate,'champion_id':state['champion_id'],'build_id':path['id'],
            'items':[],'selected_augments':[],'stage':1,'decision_horizon':'remainder_of_match',
            'data_run':self.policy['data_run'],'policy_version':self.policy['policy_version'],'path_snapshot_id':path['snapshot_id']}
        assumptions={'interaction_review_complete':True,'ad_to_ap.depends_on_input_stat':True,
            'ad_to_ap.has_output_stat_payoff':False,'ad_to_ap.has_output_bridge':False,
            'ad_to_ap.build_committed':True,'ad_to_ap.pivot_feasible':False}
        facts={k:{'value':v,'review_status':'reviewed','context_fingerprint':policy.fingerprint(context),
            'evidence':['fixture://synthetic_assumptions_not_ashe_mechanics']} for k,v in assumptions.items()}
        self.assertEqual(self.bench.assess(state,candidate,facts)['compatibility']['compatibility'],'avoid')
        state['active_path']='on_hit'
        result=self.bench.assess(state,candidate,facts)['compatibility']
        self.assertEqual(result['compatibility'],'unknown')
        self.assertEqual(result['rejected_facts']['interaction_review_complete'],'context_changed')

    def test_cannot_select_another_champions_or_custom_path(self):
        with self.assertRaises(ValueError):self.bench.get_path('champion:game:22','utility')
        with self.assertRaises(ValueError):self.bench.get_path('champion:game:22','custom_items')

    def test_owned_augments_are_not_claimed_as_joint_profile_evidence(self):
        state=self.state();state['selected_augments']=['augment:game:3086']
        result=self.bench.assess(state,'augment:game:1205')
        self.assertFalse(result['selected_augments_jointly_conditioned'])
        self.assertFalse(result['current_items_conditioned'])

    def test_invalid_pick_does_not_silently_change_ownership(self):
        scenario=copy.deepcopy(self.suite['scenarios'][0])
        scenario['events']=[{'action':'pick','augment':'augment:game:1058'}]
        with self.assertRaisesRegex(ValueError,'not offered'):self.bench.replay(scenario)
        self.assertEqual(scenario['initial_state']['selected_augments'],[])

    def test_review_suite_respects_known_rarities(self):
        for scenario in self.suite['scenarios']:
            for event in scenario['events']:
                if event['action']=='offer':
                    self.assertEqual(len({self.bench.rarities[a] for a in event['augments']}),1)
        scenario=copy.deepcopy(self.suite['scenarios'][0])
        scenario['events']=[{'action':'offer','augments':['augment:game:1205','augment:game:3086']}]
        with self.assertRaisesRegex(ValueError,'mixed rarities'):self.bench.replay(scenario)

    def test_simulated_purchases_preserve_duplicate_components(self):
        scenario=copy.deepcopy(self.suite['scenarios'][0])
        scenario['events']=[{'action':'buy','item':'item:game:1036'}]*2
        replay=self.bench.replay(scenario)
        self.assertEqual(replay['steps'][-1]['state']['items'],['item:game:1036']*2)

    def test_no_fake_strength_tier_or_final_recommendation(self):
        snapshot=self.bench.snapshot(self.state())
        self.assertIsNone(snapshot['strength_tier']);self.assertIsNone(snapshot['final_recommendation'])

    def test_code_and_data_epochs_change_review_fingerprint(self):
        context={'candidate_id':'augment:game:1205','policy_version':'0.1.0','data_run':'old'}
        before=policy.fingerprint(context);context['policy_version']='0.2.0'
        self.assertNotEqual(before,policy.fingerprint(context))

    def test_replay_report_is_reproducible_and_preserves_human_judgments(self):
        base=ROOT/'data/test-tmp';base.mkdir(parents=True,exist_ok=True)
        real_bench=offline.Bench
        with tempfile.TemporaryDirectory(dir=base) as temp:
            target=Path(temp)
            with patch.object(offline.compatibility,'load_policy',return_value=self.policy),patch.object(offline,'Bench',side_effect=lambda root,p:real_bench(ROOT,p)):
                first=offline.run_suite(target,ROOT/'data/recommendation/scenarios/build-paths-0.2.1.json')
                folder=target/'data/recommendation/reviews'/first['review_run']
                judgments=offline.read(folder/'judgments.json');judgments['entries'][0]['reason']='Human note to preserve'
                offline.write(folder/'judgments.json',judgments)
                second=offline.run_suite(target,ROOT/'data/recommendation/scenarios/build-paths-0.2.1.json')
                self.assertEqual(first['review_run'],second['review_run'])
                self.assertEqual(offline.read(folder/'judgments.json')['entries'][0]['reason'],'Human note to preserve')


class RepresentativeProfile(unittest.TestCase):
    def test_largest_sample_not_maximum_win_rate(self):
        bench=offline.Bench.__new__(offline.Bench);bench.lookup={};bench.profiles={}
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;bench.db=db
        db.execute('CREATE TABLE build_profiles(id,champion_id,augment_id,selection,archetype,patch,artifact,selector,context_json,metrics_json,item_set_json)')
        for pid,n,wr in [('rare_high_wr',10,.9),('larger_sample',1000,.6)]:
            db.execute('INSERT INTO build_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (pid,'champion:fixture:1','augment:fixture:1','single_augment','ap','fixture','a','selector','{}',
                 json.dumps({'sample_count':{'value':n},'win_rate':{'value':wr}}),'[]'))
        profiles=bench.get_profiles('champion:fixture:1','ap','augment:fixture:1')
        self.assertEqual(profiles[0]['id'],'larger_sample')
        db.close()


if __name__=='__main__':unittest.main()
