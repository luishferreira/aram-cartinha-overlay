from collections import Counter
import json
import unittest
import uuid

from tools.items.static_sets import ROOT, NAMESPACE, load_export
from tools.items.comparison_sets import identity, coalesce_options


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
                if origin['source']=='multiple':
                    for e in origin['origins']:
                        counts[e['source']] += 1
                        self.assertIn('option_group',e)
                    continue
                counts[origin['source']] += 1
                self.assertNotIn('blitz',origin['source'])
                if origin['source'] in ('opgg','arammayhem'):
                    self.assertEqual(origin['scope'],'champion_general')
                    self.assertIn('geral',block['type'])
                if 'record_id' not in origin or origin['source']=='lemonnation':
                    continue
                if origin['source']=='aramkit':
                    continue
                option = origin['source_record']['option']
                ids = option['item_ids'] if origin['source']=='opgg' else [i['game_item_id'] for i in option['items']]
                self.assertEqual(block['items'],[{'id':str(i),'count':1} for i in ids])
                self.assertFalse(origin['metrics_scope_changed'])
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
        first_sources = [e['source'] for e in evidence[:4]]
        self.assertEqual(first_sources,['aramkit','opgg','arammayhem','lemonnation'])

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
        self.assertEqual(merged[0][0]['items'],a[0]['items'])
        self.assertEqual(merged[0][1]['origins'],[a[1],b[1]])
        self.assertIn('ARAMKit (caminho)',merged[0][0]['type'])
        self.assertIn('OP.GG (geral)',merged[0][0]['type'])
        self.assertEqual(a[0]['type'],'aramkit')

    def test_different_counts_and_boot_ranking_do_not_merge(self):
        a = self.entry('opgg','champion_general','starting',[('2003',1)])
        b = self.entry('arammayhem','champion_general','starting',[('2003',2)])
        c = self.entry('opgg','champion_general','boots',[('3006',1),('3158',1)])
        d = self.entry('arammayhem','champion_general','boots',[('3158',1),('3006',1)])
        self.assertEqual(len(coalesce_options([a,b,c,d])),4)

    def test_identical_boots_merge_but_core_rows_remain_separate(self):
        rows = [self.entry(s,'champion_general','boots',[('3006',1)])
                for s in ('opgg','arammayhem','lemonnation')]
        merged = coalesce_options(rows)
        self.assertEqual(len(merged),1)
        self.assertEqual(len(merged[0][1]['origins']),3)
        core = [self.entry(s,'champion_general',None,[('3006',1)]) for s in ('opgg','arammayhem')]
        self.assertEqual(len(coalesce_options(core)),2)


if __name__ == '__main__':
    unittest.main()
