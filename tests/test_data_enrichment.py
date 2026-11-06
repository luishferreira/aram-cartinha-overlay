"""Regressions for build context, source eligibility and conservative rule interpretation."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/data'))
from mayhem_data.common import write,digest,dumps,file_digest
from mayhem_data.builds import compile_resources,checked_stats,item_row,register_conditionals
from mayhem_data.model import Batch
from mayhem_data.pipeline import SCHEMA
from mayhem_data.analysis import spearman,wilson,comparison_rows,relation_statistics
from mayhem_data.rules import evaluate
from mayhem_data.adapters import identity_from_research


class Enrichment(unittest.TestCase):
    def test_no_boots_is_not_a_fictitious_item(self):
        row=item_row({'item':{'id':0},'pickRate':.4},'route_sample')
        self.assertEqual(row['item_ids'],[None]);self.assertTrue(row['no_item_option'])
        self.assertEqual(row['metrics']['pick_rate']['denominator'],'route_sample')

    def test_duplicate_starter_components_are_preserved(self):
        row=item_row({'items':[{'id':1036},{'id':1036}]},'route_sample')
        self.assertEqual(row['item_ids'],['item:game:1036']*2)

    def test_build_probability_validation(self):
        with self.assertRaises(ValueError):checked_stats({'winRate':52},'fixture')
        with self.assertRaises(ValueError):checked_stats({'sampleCount':-1},'fixture')

    def test_tied_ranks_and_constant_inputs(self):
        self.assertAlmostEqual(spearman([1,1,2,3],[4,4,5,6]),1)
        self.assertIsNone(spearman([1,1,1],[2,3,4]))
        self.assertIsNone(spearman([1,2],[2,1]))

    def test_intervals_remain_unknown_without_samples(self):
        self.assertIsNone(wilson(.7,None));self.assertIsNone(wilson(None,100))
        lo,hi=wilson(.7,100)
        self.assertLess(lo,.7);self.assertGreater(hi,.7)

    def test_context_conditions_prevent_reviewed_rule_activation(self):
        r={'id':'fixture','status':'reviewed','validated_patches':{'aramkit':'16.21'},
           'required_augments':['augment:game:1'],'context_requirements':['tank ally'],
           'explanation':{},'evidence':['fixture']}
        self.assertEqual(evaluate(r,'champion:game:1',['augment:game:1'],[],{'aramkit':'16.21'})['fit'],'needs_context_review')

    def test_reviewed_aliases_keep_historical_effects_separate(self):
        root=Path(__file__).resolve().parents[1];identity=identity_from_research(root)
        self.assertEqual(identity.augment('double_defense','Double Defense'),'augment:game:2144')
        self.assertEqual(identity.augment('rabble_rousing','Rabble Rousing'),'augment:game:1067')
        self.assertEqual(identity.augment('void_immolation','Void Immolation'),'augment:game:1361')
        self.assertEqual(identity.augment('totally_unknown','Totally Unknown'),'augment:arammayhem:totally_unknown')

    def test_hierarchy_stays_attached_to_conditional_profile(self):
        base=Path(__file__).resolve().parents[1]/'data/test-tmp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            path=Path(tmp)/'fixture.json'
            write(path,{'items':[{'augmentId':1058,'all':[{'id':3508,'winRate':.6}], 'slots':{}}],
                'builds':[{'augmentId':1058,'archetypes':[{'key':'crit','profiles':[
                    {'itemSet':[{'id':3508}],'sampleCount':100,'winRate':.6,'routes':[
                        {'purchaseOrder':[{'id':3508}],'sampleCount':50,'pickRate':.5,'boots':[{'item':{'id':0},'pickRate':.4}],
                         'starters':[{'items':[{'id':1036},{'id':1036}]}]}]}]}]}]})
            batch=Batch('aramkit',{'snapshot_id':'fixture'});sha=batch.artifact(path)
            self.assertEqual(file_digest(path),digest(path.read_bytes()))
            batch.build_resources=[{'path':str(path),'artifact':sha,'champion_id':'champion:game:11','conditional':True,'patch':'16.21'}]
            db=sqlite3.connect(':memory:');db.executescript(SCHEMA)
            db.execute('INSERT INTO sources VALUES(?,?,?)',('aramkit','aramkit','{}'))
            db.execute('INSERT INTO snapshots VALUES(?,?,?)',('fixture','aramkit','{}'))
            db.execute('INSERT INTO artifacts VALUES(?,?,?)',(sha,'fixture',1))
            report=compile_resources(db,[batch])
            row=db.execute('SELECT augment_id,metrics_json,routes_json FROM build_profiles').fetchone()
            self.assertEqual(row[0],'augment:game:1058');routes=json.loads(row[2])
            self.assertEqual(routes[0]['boots'][0]['item_ids'],[None])
            self.assertEqual(routes[0]['starters'][0]['item_ids'],['item:game:1036']*2)
            self.assertEqual(report['routes'],1);self.assertEqual(report['conditional_item_groups'],1)
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'changed during compilation'):compile_resources(sqlite3.connect(':memory:'),[batch])
            db.close()

    def test_stage_and_historical_metrics_do_not_leak_into_comparisons(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;db.executescript(SCHEMA)
        db.execute('INSERT INTO sources VALUES(?,?,?)',('aramkit','aramkit','{}'))
        db.execute('INSERT INTO snapshots VALUES(?,?,?)',('s','aramkit','{}'))
        db.execute('INSERT INTO entities VALUES(?,?,?)',('augment:game:1','augment','known'))
        db.execute('INSERT INTO artifacts VALUES(?,?,?)',('a','fixture',1))
        for index,(stage,flags) in enumerate([('all',[]),('1',[]),('all',['historical_performance_patch'])]):
            db.execute('INSERT INTO observations VALUES('+','.join('?'*13)+')',
                (str(index),'s','augment:game:1','a','champion','champion:game:11',stage,'16.21',None,
                 dumps({'stage':stage}),dumps({'win_rate':{'value':.6}}),dumps(flags),None))
        rows,duplicates=comparison_rows(db)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['aramkit_win_rate'],.6)
        self.assertEqual(duplicates,{})
        db.close()


if __name__=='__main__':unittest.main()
