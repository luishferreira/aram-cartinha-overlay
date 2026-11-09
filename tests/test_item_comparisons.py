from collections import Counter
import json
import unittest
import uuid

from tools.items.static_sets import ROOT, NAMESPACE, load_export
from tools.items.comparison_sets import identity, coalesce_options, STARTING_POTIONS


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle, cls.manifest = load_export()
        cls.folder = ROOT/'data/item-sets/runs'/cls.manifest['generation']
        cls.evidence = json.loads((cls.folder/'provenance.json').read_text('utf8'))

    def test_every_block_has_source_evidence_and_original_metric_scope(self):
        counts = Counter()
        for value in self.bundle['itemSets']:
            evidence = self.evidence[value['uid']]['block_evidence']
            self.assertEqual(len(value['blocks']),len(evidence))
            for block, origin in zip(value['blocks'],evidence):
                origins = origin['origins'] if origin['source']=='multiple' else [origin]
                for original in origins:
                    counts[original['source']] += 1
                    self.assertNotIn('blitz',original['source'])
                    if original['source'] in ('opgg','arammayhem'):
                        self.assertEqual(original['scope'],'champion_general')
                        if origin['source']!='multiple':
                            self.assertIn('geral',block['type'])
                    if original.get('option_group')!='core':
                        continue
                    if original['source']=='aramkit':
                        ids = [i.rsplit(':',1)[1] for i in original['route']['purchase_order']]
                    else:
                        option = original['source_record']['option']
                        ids = option['item_ids'] if original['source']=='opgg' else [i['game_item_id'] for i in option['items']]
                        self.assertFalse(original['metrics_scope_changed'])
                    self.assertEqual(block['items'],[{'id':str(i),'count':1} for i in ids])
        self.assertEqual(set(counts),{'aramkit','opgg','arammayhem','lemonnation'})

    def test_editorial_choice_remains_a_separate_native_block(self):
        value = next(s for s in self.bundle['itemSets'] if s['associatedChampions']==[21]
                     and s['title'].endswith('Letalidade'))
        blocks = value['blocks']
        evidence = self.evidence[value['uid']]['block_evidence']
        choice_index = next(i for i,e in enumerate(evidence) if e.get('choice_group'))
        self.assertIn('escolha 1',blocks[choice_index]['type'])
        self.assertEqual({i['id'] for i in blocks[choice_index]['items']},{'3033','3036'})
        self.assertEqual([i['id'] for i in blocks[choice_index-1]['items']],['126697','6696','3031'])

    def test_compact_layout_for_all_paths_and_ahri_regression(self):
        for value in self.bundle['itemSets']:
            origins = self.evidence[value['uid']]['block_evidence']
            groups = [e.get('option_group') for e in origins]
            self.assertLessEqual(groups.count('boots'),1)
            initial = groups.count('starting')
            self.assertEqual(groups[:initial],['starting']*initial)
            signatures = []
            for block, origin in zip(value['blocks'],origins):
                if origin.get('option_group')=='starting':
                    self.assertFalse(STARTING_POTIONS & {i['id'] for i in block['items']})
                if origin.get('option_group')=='core':
                    signatures.append(tuple((i['id'],i['count']) for i in block['items']))
            self.assertEqual(len(signatures),len(set(signatures)))
        ahri = next(s for s in self.bundle['itemSets'] if s['associatedChampions']==[103]
                    and s['title'].endswith(' AP'))
        evidence = self.evidence[ahri['uid']]['block_evidence']
        self.assertEqual(sum(e.get('option_group')=='core' for e in evidence),4)
        self.assertEqual(sum(e.get('option_group')=='starting' for e in evidence),2)
        luden = next(e for b,e in zip(ahri['blocks'],evidence)
                     if [i['id'] for i in b['items']]==['6655','4645','3089'])
        self.assertEqual({e['source'] for e in luden['origins']},{'aramkit','opgg','arammayhem'})
        self.assertEqual(evidence[0]['option_group'],'starting')

    def test_inferred_paths_use_the_same_stable_identity_as_reference_paths(self):
        value = next(s for s in self.bundle['itemSets'] if s['associatedChampions']==[11] and s['title'].endswith(' AD'))
        self.assertEqual(value['uid'],str(uuid.uuid5(NAMESPACE,identity(11,'ad'))))
        self.assertEqual(self.evidence[value['uid']]['path_origin'],'inferred_primary')
        old = json.loads((ROOT/'data/item-sets/runs/18c122b5e8dbceba152107c6/item-sets.json').read_text('utf8'))
        self.assertTrue({s['uid'] for s in old['itemSets']} <= {s['uid'] for s in self.bundle['itemSets']})

    def test_unavailable_editorial_item_omits_whole_core(self):
        omitted = json.loads((self.folder/'omitted-source-cores.json').read_text('utf8'))
        self.assertEqual(len(omitted),1)
        self.assertEqual(omitted[0]['excluded_item_ids'],['3097'])
        self.assertEqual(omitted[0]['action'],'omit_whole_core_without_replacement')
        self.assertNotIn('3097',{i['id'] for s in self.bundle['itemSets'] for b in s['blocks'] for i in b['items']})


class OptionCoalescingTests(unittest.TestCase):
    def entry(self,source,scope,group,ids):
        return ({'type':source,'items':[{'id':i,'count':n} for i,n in ids]},
                {'source':source,'scope':scope,'option_group':group,'artifact':source+'-raw'})

    def test_same_starters_merge_across_sources_and_keep_original_scopes(self):
        a = self.entry('aramkit','path','starting',[('1001',1),('2003',2)])
        b = self.entry('opgg','champion_general','starting',[('2003',2),('1001',1)])
        merged = coalesce_options([a,b])
        self.assertEqual(len(merged),1)
        self.assertEqual(merged[0][0]['items'],[{'id':'1001','count':1}])
        self.assertEqual([e['source'] for e in merged[0][1]['origins']],['aramkit','opgg'])
        self.assertEqual(merged[0][1]['origins'][0]['display_omitted_potions'],[{'id':'2003','count':2}])
        self.assertIn('ARAMKit (caminho)',merged[0][0]['type'])
        self.assertIn('OP.GG (geral)',merged[0][0]['type'])
        self.assertEqual(a[0]['type'],'aramkit')

    def test_different_component_counts_stay_separate_and_only_first_boot_source_is_used(self):
        a = self.entry('opgg','champion_general','starting',[('1001',1)])
        b = self.entry('arammayhem','champion_general','starting',[('1001',2)])
        c = self.entry('opgg','champion_general','boots',[('3006',1),('3158',1)])
        d = self.entry('arammayhem','champion_general','boots',[('3158',1),('3006',1)])
        result = coalesce_options([a,b,c,d])
        self.assertEqual(len(result),3)
        self.assertEqual(result[-1][0],c[0])
        self.assertEqual(result[-1][1]['source'],'opgg')
        self.assertEqual(result[-1][1]['undisplayed_alternatives'][0]['block'],d[0])

    def test_one_boot_source_and_identical_core_rows_merge_without_pooling_metrics(self):
        rows = [self.entry(s,'champion_general','boots',[('3006',1)])
                for s in ('opgg','arammayhem','lemonnation')]
        merged = coalesce_options(rows)
        self.assertEqual(len(merged),1)
        self.assertEqual(len(merged[0][1]['undisplayed_alternatives']),2)
        core = [self.entry(s,'champion_general','core',[('6655',1),('4645',1)]) for s in ('opgg','arammayhem')]
        core[0][1]['metrics'] = {'win_rate':.51}
        core[1][1]['metrics'] = {'win_rate':.60}
        result = coalesce_options(core)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0][1]['origins'],[e for _,e in core])
        self.assertNotIn('metrics',result[0][1])

    def test_core_order_and_editorial_choice_boundaries_are_preserved(self):
        a = self.entry('opgg','champion_general','core',[('6655',1),('4645',1)])
        b = self.entry('arammayhem','champion_general','core',[('4645',1),('6655',1)])
        choice = self.entry('lemonnation','editorial',None,[('6655',1),('4645',1)])
        choice[1]['choice_group'] = True
        result = coalesce_options([a,b,choice])
        self.assertEqual(len(result),3)
        self.assertEqual(result[-1],choice)

    def test_potion_only_starters_never_create_an_empty_native_row(self):
        a = self.entry('opgg','champion_general','starting',[('2031',1)])
        b = self.entry('aramkit','path','starting',[('3802',1)])
        c = self.entry('opgg','champion_general','starting',[('3802',1),('2031',1)])
        result = coalesce_options([a,b,c])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0][0]['items'],[{'id':'3802','count':1}])


if __name__ == '__main__':
    unittest.main()
