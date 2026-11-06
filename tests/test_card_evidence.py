"""Decision-support presentation must preserve meaning, scope and unknowns."""
import copy
import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/recommendation'))
import card_evidence as cards
import offline


class CardEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bench=offline.Bench(ROOT)
    @classmethod
    def tearDownClass(cls):cls.bench.close()

    def state(self,path='ap'):
        return {'champion_id':'champion:game:22','active_path':path,'selected_augments':[],
                'items':[],'offered_augments':[],'stage':1}

    def test_card_has_localized_effect_and_english_alias(self):
        card=self.bench.assess(self.state(),'augment:game:1022')['evidence_card']
        self.assertEqual(card['identity']['english_name'],'Deft')
        self.assertEqual(card['identity']['effect']['locale'],'pt-BR')
        self.assertIn('60%',card['identity']['effect']['text'])
        self.assertIn('Velocidade de Ataque',card['identity']['effect']['text'])
        self.assertNotIn('<speed>',card['identity']['effect']['text'])

    def test_source_champion_tiers_do_not_change_with_path(self):
        a=self.bench.assess(self.state('ap'),'augment:game:1206')['evidence_card']
        b=self.bench.assess(self.state('on_hit'),'augment:game:1206')['evidence_card']
        self.assertEqual(a['source_tiers'],b['source_tiers'])
        self.assertNotEqual(a['path_evidence']['profile_count'],b['path_evidence']['profile_count'])
        self.assertEqual(a['source_tiers']['blitz']['scope'],'champion_not_build')
        self.assertEqual(a['source_tiers']['blitz']['value'],'A')
        self.assertEqual(a['source_tiers']['opgg']['value'],'B')
        self.assertTrue(a['tier_disagreement']);self.assertIsNone(a['combined_tier'])

    def test_aramkit_exact_stage_is_primary(self):
        card=self.bench.assess(self.state(),'augment:game:1022')['evidence_card']
        performance=next(p for p in card['performance'] if p['source']=='aramkit')
        self.assertEqual(performance['stage'],'1')
        self.assertEqual(performance['scope'],'champion_stage_not_build')
        self.assertEqual(performance['sample_count'],23952)
        self.assertAlmostEqual(performance['win_rate'],.464)

    def test_undefined_opgg_index_never_becomes_win_rate(self):
        state=self.state();assessment=copy.deepcopy(self.bench.assess(state,'augment:game:1206'))
        row=next(r for r in assessment['reference_metrics'] if r['source']=='opgg')
        row['metrics']['performance_raw']['value']=999
        card=cards.describe(self.bench.db,assessment,state,self.bench.popularity[state['champion_id']])
        self.assertNotIn('opgg',[p['source'] for p in card['performance']])
        text=cards.markdown(card,'AP')
        self.assertIn('desempenho 999',text);self.assertNotIn('999%',text)

    def test_missing_profile_is_not_zero_or_a_veto(self):
        card=self.bench.assess(self.state('on_hit'),'augment:game:1205')['evidence_card']
        self.assertIsNone(card['path_evidence']['profile'])
        self.assertFalse(card['compatibility']['veto_recommendation'])
        self.assertIn('Sem perfil específico',cards.markdown(card,'Efeitos ao contato'))

    def test_opgg_unknown_patch_remains_visible(self):
        card=self.bench.assess(self.state(),'augment:game:1206')['evidence_card']
        self.assertFalse(card['source_tiers']['opgg']['stats_patch_known'])
        self.assertIn('patch das estatísticas não informado',cards.markdown(card,'AP'))

    def test_description_fallback_does_not_invent_translation(self):
        info=cards.identity(self.bench.db,'augment:arammayhem:yowch_my_coins')
        self.assertTrue(info['effect']['fallback']);self.assertEqual(info['effect']['locale'],'en-US')

    def test_global_editorial_tier_is_not_a_champion_tier(self):
        card=self.bench.assess(self.state(),'augment:game:1205')['evidence_card']
        self.assertEqual(card['editorial']['global_tier']['scope'],'global_augment_not_champion_or_build')
        self.assertEqual(set(card['source_tiers']),{'blitz','opgg'})


class EvidenceContracts(unittest.TestCase):
    def test_historical_performance_is_not_current_headline(self):
        row={'source':'aramgg','historical':True,'context':{'metric_group':'uploaded_performance'},
             'metrics':{'win_rate':{'value':.9}}}
        self.assertIsNone(cards.reference([row],'aramgg',group='uploaded_performance'))

    def test_stage_fallback_is_explicit_overall_row(self):
        rows=[{'source':'aramkit','stage':'all'},{'source':'aramkit','stage':'2'}]
        self.assertEqual(cards.reference(rows,'aramkit',1)['stage'],'all')
        self.assertEqual(cards.reference(rows,'aramkit',2)['stage'],'2')

    def test_zero_and_missing_rates_render_differently(self):
        self.assertEqual(cards.pct(0),'0.00%');self.assertEqual(cards.pct(None),'sem dado')

    def test_description_html_is_plain_and_unresolved_values_survive(self):
        text=cards.plain('Recebe <scaleAP>?</scaleAP> de AP.<script>bad()</script><br>@Calc_Value@')
        self.assertNotIn('bad()',text);self.assertIn('?',text);self.assertIn('@Calc_Value@',text)
        self.assertNotIn('<',text)
        self.assertIn('&lt;script&gt;',cards.md('<script>'))

    def test_popularity_rank_uses_full_champion_list_and_preserves_ties(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.executescript('CREATE TABLE snapshots(id,source); CREATE TABLE observations(entity_id,metrics_json,snapshot_id,champion_id,scope); INSERT INTO snapshots VALUES("s","opgg");')
        for eid,popular,performance in [('a',10,1),('b',5,1),('c',5,1),('empty',0,0)]:
            metrics={'popular_raw':{'value':popular},'performance_raw':{'value':performance}}
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?)',(eid,json.dumps(metrics),'s','champion','champion'))
        ranks=cards.popularity_ranks(db,'champion')
        self.assertEqual(ranks['a']['rank'],1);self.assertEqual(ranks['b']['rank'],2)
        self.assertEqual(ranks['c']['rank'],2);self.assertEqual(ranks['c']['published_entries'],3)
        self.assertNotIn('empty',ranks)
        db.close()


if __name__=='__main__':unittest.main()
