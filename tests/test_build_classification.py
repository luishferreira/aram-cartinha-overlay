import copy
import unittest

from tools.items.classification import Classifier, significant
from tools.items.classification_cli import evaluate, classify_record


def catalog():
    return {str(i): {'categories': tags, 'cost': 3000, 'upgrades': []} for i, tags in {
        1:['SpellDamage'], 2:['SpellDamage','Mana'], 3:['SpellDamage','MagicPenetration'],
        4:['Damage','CriticalStrike'], 5:['Damage','AttackSpeed','CriticalStrike'], 6:['Damage','CriticalStrike'],
        7:['SpellDamage','AbilityHaste'], 8:['Armor','Health'], 9:['SpellBlock','Health'],
        10:['Boots','SpellDamage'], 11:['Consumable'], 12:['Trinket'], 13:['SpellDamage'],
    }.items()} | {'14': {'categories':['SpellDamage'], 'cost':400, 'upgrades':[1], 'category':'starter'}}


def profile(ident, path, items, champion=22):
    return {'id': ident, 'champion_id':champion, 'path':path, 'items':items, 'patch':'16.21'}


class BuildClassificationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog()
        self.profiles = [profile('ap','ap',[1,2,3]), profile('crit','crit',[4,5,6])]

    def test_unique_exact_core_is_high_and_order_invariant(self):
        model = Classifier(self.profiles, self.catalog)
        a = model.classify(22,[1,2,3])
        b = model.classify(22,[3,2,1])
        self.assertEqual(a,b)
        self.assertEqual(a['assignments'],['ap'])
        self.assertEqual(a['confidence'],'high')

    def test_boots_consumables_starters_and_duplicates_do_not_change_identity(self):
        model = Classifier(self.profiles,self.catalog)
        result = model.classify(22,[1,2,3,3,10,11,12,14])
        self.assertEqual(result['assignments'],['ap'])
        self.assertEqual(result['significant_item_ids'],[1,2,3])
        self.assertEqual(len(result['ignored_items']),4)

    def test_aramkit_does_not_override_item_identity_when_only_one_path_exists(self):
        result = Classifier(self.profiles[:1],self.catalog).classify(22,[4,5,6])
        self.assertEqual(result['primary_path'],'crit')
        self.assertNotIn('ap',result['assignments'])
        self.assertIn('some_paths_not_published_for_champion_in_reference',result['flags'])

    def test_item_properties_can_resolve_ambiguous_reference_labels(self):
        profiles = [profile('a','ap',[1,2,3]),profile('b','on_hit',[3,2,1])]
        result = Classifier(profiles,self.catalog).classify(22,[1,2,3])
        self.assertEqual(result['primary_path'],'ap')
        self.assertEqual({c['path'] for c in result['prototype_candidates']},{'ap','on_hit'})

    def test_duplicates_popularity_and_winrate_do_not_increase_a_vote(self):
        original = Classifier(self.profiles,self.catalog).classify(22,[1,2,7])
        duplicate = {**self.profiles[0], 'id':'duplicate', 'games':999999, 'win_rate':1.0}
        changed = Classifier(self.profiles+[duplicate]*20,self.catalog).classify(22,[1,2,7])
        self.assertEqual(original,changed)

    def test_other_champion_does_not_supply_a_matching_core(self):
        result = Classifier(self.profiles,self.catalog).classify(99,[1,2,3])
        self.assertEqual(result['primary_path'],'ap')
        self.assertFalse(result['prototype_candidates'])
        self.assertTrue(result['feature_suggestions'])
        self.assertIn('no_same_champion_references',result['flags'])

    def test_unknown_native_ids_preserved_without_confident_guess(self):
        core,_,unknown = significant([9001,9002],self.catalog)
        self.assertEqual(core,{9001,9002})
        self.assertEqual(unknown,[9001,9002])
        result = Classifier(self.profiles,self.catalog).classify(22,[9001,9002])
        self.assertFalse(result['assignments'])

    def test_one_item_is_insufficient_even_when_it_matches_a_path(self):
        result = Classifier(self.profiles,self.catalog).classify(22,[1,10,14])
        self.assertEqual(result['status'],'unclassified')
        self.assertIn('insufficient_core_items',result['flags'])

    def test_malformed_native_id_rejected(self):
        for ident in [0,-1,True,None,'item:other:1']:
            with self.subTest(ident=ident),self.assertRaises(ValueError):
                significant([ident],self.catalog)

    def test_input_data_not_mutated_and_patch_not_silently_normalized(self):
        saved = copy.deepcopy(self.profiles)
        result = Classifier(self.profiles,self.catalog).classify(22,[1,2,3],source_patch='26.22')
        self.assertEqual(saved,self.profiles)
        self.assertIn('native_patch_equality_not_established',result['flags'])

    def test_validation_hides_identical_cores_across_labels_and_champions(self):
        profiles = self.profiles + [profile('ap-copy','ap',[3,1,2],champion=99),
                                   profile('hybrid-copy','hybrid',[2,3,1])]
        validation = evaluate({'profiles':profiles,'item_catalog':self.catalog})
        cases = [r for r in validation['predictions'] if set(r['items'])=={1,2,3}]
        self.assertEqual(len({r['fold'] for r in cases}),1)
        self.assertTrue(all(r['primary_path']=='ap' for r in cases))
        self.assertEqual(validation['reference'],'aramkit_labels_not_independent_game_truth')

    def test_source_metrics_remain_identical_and_cannot_change_category(self):
        model = Classifier(self.profiles,self.catalog)
        source = {'source':'opgg','champion_id':22,'items':[1,2,3],'patch':'16.21',
                  'source_record':{'option':{'pick_rate':0.01,'win_rate':0.99,'sample_games':100}}}
        before = copy.deepcopy(source)
        first = classify_record(model,source)
        self.assertEqual(source,before)
        self.assertEqual(first['source_record'],source['source_record'])
        self.assertFalse(first['metrics_scope_changed'])
        other = copy.deepcopy(source)
        other['source_record']['option'] = {'pick_rate':0.99,'win_rate':0.01,'sample_games':2}
        self.assertEqual(first['classification'],classify_record(model,other)['classification'])

    def test_crit_and_lethality_affinities_overlap_without_summing_to_100(self):
        data = self.catalog | {'20':{'categories':['Damage','CriticalStrike','ArmorPenetration'],
            'description':'<stats>50 Attack Damage 10 Lethality 25% Critical Strike Chance</stats>', 'cost':3000}}
        result = Classifier([],data).item_affinity(20)
        self.assertEqual([result['affinities'][p] for p in ['ad','crit','lethality']],[1,1,1])

    def test_one_crit_item_does_not_turn_a_whole_ad_build_into_crit(self):
        data = self.catalog | {str(i):{'categories':['Damage'], 'cost':3000} for i in [21,22,23,24]}
        result = Classifier([],data).classify(22,[4,21,22,23,24])
        self.assertEqual(result['primary_path'],'ad')
        self.assertNotIn('crit',result['assignments'])
        self.assertEqual(result['affinity_percentages']['crit'],20)

    def test_alternative_group_has_one_slot_and_does_not_fabricate_a_sequence(self):
        model = Classifier([],self.catalog)
        result = model.classify(22,[1,2],choice_groups=[[3,4]])
        self.assertEqual(result['relevant_slots'],3)
        group = next(s for s in result['item_contributions'] if s['kind']=='choose_one')
        self.assertEqual([i['item_id'] for i in group['options']],[3,4])
        self.assertAlmostEqual(result['affinity_percentages']['ap'],83.33)
        self.assertEqual(result['significant_item_ids'],[1,2])

    def test_transform_family_only_unifies_explicit_mapping_and_preserves_native_ids(self):
        data = self.catalog | {'30':{'name':'Before','transforms_into_name':'After','categories':['Damage'],'cost':3000},
                              '31':{'name':'After','categories':['Damage'],'cost':3000}}
        result = Classifier([],data).classify(22,[30,31,4])
        self.assertEqual(result['comparison_item_families'],[4,30])
        self.assertEqual(result['significant_item_ids'],[4,30,31])

    def test_support_ap_does_not_turn_a_healing_build_into_offensive_ap(self):
        data = self.catalog | {str(i):{'categories':['SpellDamage','ManaRegen'],
            'description':'<stats>45 Ability Power 12% Heal and Shield Power</stats>','cost':3000} for i in [40,41,42]}
        result = Classifier([],data).classify(22,[40,41,42,1])
        self.assertEqual(result['primary_path'],'utility')
        self.assertGreater(result['affinity_percentages']['utility'],result['affinity_percentages']['ap'])


if __name__ == '__main__':
    unittest.main()
