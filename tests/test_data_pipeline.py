"""Meaningful contract and publication regressions; no internet required."""
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/data'))
from mayhem_data.common import entity_id, read, write
from mayhem_data.model import Batch, Identity, metric, stats
from mayhem_data.changes import changes, review_queue
from mayhem_data.pipeline import build, verify_run
from mayhem_data.query import display_name
from mayhem_data.rules import evaluate, validate_rules
from mayhem_data.validation import validate
from mayhem_data.fetch import Http, safe_url, replace_bytes

CHAMPION=entity_id('champion',11)
A=entity_id('augment',1001)
B=entity_id('augment',1002)
ITEM=entity_id('item',3508)


def rule():
    return {'id':'fixture','status':'reviewed','review_revision':1,'champions':[CHAMPION],
        'required_augments':[A],'required_items':[ITEM],'alternative_augment_groups':[[B]],
        'conflicting_augments':[],'validated_patches':{'aramkit':'16.21'},
        'evidence':['fixture://research'],'explanation':{'pt-BR':'Exemplo de teste','en-US':'Test fixture'}}


class Semantics(unittest.TestCase):
    def test_rates_convert_only_explicit_units(self):
        self.assertEqual(stats({'winRate':'54.49%'},percent=True)['win_rate']['value'],.5449)
        self.assertEqual(stats({'winRate':.5449})['win_rate']['value'],.5449)

    def test_ambiguous_names_stay_namespaced(self):
        ids=Identity();ids.add_name('Same',1);ids.add_name('Same!',2)
        self.assertEqual(ids.augment('same','Same'), 'augment:arammayhem:same')

    def test_exact_alias_and_explicit_quest_prefix(self):
        ids=Identity();ids.add_name('Steel Your Heart',1)
        self.assertEqual(ids.augment('quest','Quest: Steel Your Heart'),'augment:game:1')

    def test_patch_suffix_not_equivalence(self):
        self.assertEqual(evaluate(rule(),CHAMPION,[A,B],[ITEM],{'aramkit':'26.21'})['fit'],'needs_patch_review')

    def test_rule_requires_items_and_alternatives(self):
        result=evaluate(rule(),CHAMPION,[A],[],{'aramkit':'16.21'})
        self.assertEqual(result['fit'],'conditional');self.assertEqual(result['missing_items'],[ITEM])
        self.assertEqual(result['missing_alternative_groups'],[[B]])

    def test_offered_card_can_complete_reviewed_rule(self):
        self.assertEqual(evaluate(rule(),CHAMPION,[A],[ITEM],{'aramkit':'16.21'},B)['fit'],'active')

    def test_pending_review_blocks_same_patch_activation(self):
        self.assertEqual(evaluate({**rule(),'pending_review':True},CHAMPION,[A,B],[ITEM],{'aramkit':'16.21'})['fit'],'needs_review')

    def test_conflict_and_other_champion(self):
        self.assertIsNone(evaluate(rule(),'champion:game:1',[A,B],[ITEM],{'aramkit':'16.21'}))
        result=evaluate({**rule(),'conflicting_augments':[B]},CHAMPION,[A,B],[ITEM],{'aramkit':'16.21'})
        self.assertEqual(result['fit'],'conflict')

    def test_reviewed_rules_need_provenance_and_both_languages(self):
        r=rule();r['evidence']=[];r['explanation'].pop('en-US')
        self.assertEqual(len(validate_rules([r],{CHAMPION,A,B,ITEM})),2)

    def test_missing_catalog_is_not_retirement(self):
        old={'aramkit|augment|1001':[{'entity_id':A,'kind':'augment','native_id':'1001','names':{},'descriptions':{},'attributes':{}}]}
        events=changes(old,{}, {'aramkit':{}},{'aramkit':{}})
        self.assertEqual(events[0]['kind'],'catalog_entry_missing')

    def test_catalog_patch_does_not_become_stats_patch(self):
        events=changes({}, {},{'opgg':{'catalog_patch':'16.20','stats_patch':None}},
            {'opgg':{'catalog_patch':'16.21','stats_patch':None}})
        self.assertEqual([e['kind'] for e in events],['catalog_patch_changed'])

    def test_added_translation_is_not_mechanical_change(self):
        row={'entity_id':A,'kind':'augment','native_id':'1001','names':{'pt-BR':'Nome'},
             'descriptions':{'pt-BR':{'tooltip':'Efeito'}},'attributes':{'rarity':'gold'}}
        english={**row,'names':{'en-US':'Name'},'descriptions':{'en-US':{'tooltip':'Effect'}}}
        events=changes({'opgg|augment|1001':[row]},{'opgg|augment|1001':[row,english]}, {'opgg':{}},{'opgg':{}})
        self.assertEqual(events[0]['kind'],'localization_changed');self.assertFalse(events[0]['requires_review'])

    def test_rule_review_includes_alternative_and_conflict_dependencies(self):
        queue=review_queue([{'kind':'effect_text_changed','entity_id':B,'requires_review':True}],[],[rule()])
        self.assertEqual(queue[0]['id'],'fixture')

    def test_no_baseline_mass_removal_events(self):
        self.assertEqual(changes(None,{}, {},{'blitz':{}})[0]['kind'],'baseline_created')

    def test_unknown_performance_is_not_checked_as_probability(self):
        b=Batch('opgg');b.observe(A,'fixture',{'scope':'global'},
            {'performance_raw':metric(123.4,'unknown','not_win_rate')})
        self.assertTrue(validate([b],set(),[],{A},[])['publishable'])

    def test_invalid_probability_rejected(self):
        b=Batch('aramkit');b.observe(A,'fixture',{'scope':'global'},stats({'winRate':1.2}))
        self.assertFalse(validate([b],set(),[],{A},[])['publishable'])

    def test_mid_collection_patch_rollover_rejected(self):
        b=Batch('blitz',{'patches':['16.21','16.22']})
        b.observe(A,'fixture',{'scope':'global'},{'tier':metric('S','source_label','test')})
        self.assertFalse(validate([b],set(),[],{A},[])['publishable'])

    def test_external_host_is_rejected(self):
        with self.assertRaises(ValueError):safe_url('https://example.com/private')
        with self.assertRaises(ValueError):safe_url('https://user:pass@arammayhem.com/mcp')


class Publication(unittest.TestCase):
    def setUp(self):
        self.temp_base=(Path(__file__).resolve().parents[1]/'data/test-tmp').resolve()
        self.temp_base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.temp_base);self.root=Path(self.temp.name);self.output=self.root/'output'
        self.config={'enabled_sources':['blitz'],'excluded_augment_sources':['leagueofgraphs'],
            'primary_sources':['blitz'],'patch_aliases':{},'display_name_priority':['blitz'],'stale_after_days':7}
        write(self.root/'data/config/pipeline.json',self.config)
        write(self.root/'data/config/rules.json',{'rules':[]})
        artifact=self.root/'fixture.json';write(artifact,{'public':'fixture'})
        self.batch=Batch('blitz',{'patches':['16.21']});a=self.batch.artifact(artifact,'https://blitz.gg/fixture')
        self.batch.catalog_row('augment',1001,a,{'en-US':'English only'},attributes={'enabled':True})
        self.batch.observe(A,a,{'scope':'champion','champion_id':CHAMPION},{'tier':metric('S','source_label','test')},'16.21')
        self.identity=Identity();self.identity.champions={'MasterYi':CHAMPION}

    def tearDown(self):
        assert self.temp_base in self.root.resolve().parents
        self.temp.cleanup()

    def publish(self,batch=None):
        with patch('mayhem_data.pipeline.load_all',return_value=(self.identity,[copy.deepcopy(batch or self.batch)])):
            return build(self.root,self.output)

    def test_reproducible_publication_and_hash_verification(self):
        first=self.publish();second=self.publish()
        self.assertEqual(first['run'],second['run']);self.assertTrue(second['reused'])
        self.assertTrue(verify_run(self.output,first['run'])['verified'])

    def test_failed_update_preserves_last_good_pointer(self):
        self.publish();pointer=(self.output/'current.json').read_bytes()
        bad=copy.deepcopy(self.batch);bad.observations[0]['metrics']=stats({'winRate':2})
        with self.assertRaises(ValueError):self.publish(bad)
        self.assertEqual(pointer,(self.output/'current.json').read_bytes())

    def test_missing_champion_blocks_publication(self):
        self.identity.champions['Annie']='champion:game:1'
        with self.assertRaises(ValueError):self.publish()
        self.assertFalse((self.output/'current.json').exists())

    def test_changed_effect_creates_review_event(self):
        self.publish();new=copy.deepcopy(self.batch)
        new.catalog[0]['descriptions']={'en-US':{'tooltip':'Changed effect'}}
        # Actual input hash changes with the publisher's data, not just the adapter object.
        path=self.root/'changed.json';write(path,{'effect':'new'})
        sha=new.artifact(path);new.catalog[0]['artifact']=sha
        latest=self.publish(new)
        events=read(self.output/'runs'/latest['run']/'changes.json')
        self.assertEqual(events[0]['kind'],'effect_text_changed')

    def test_translation_fallback_reports_itself(self):
        result=self.publish();db=sqlite3.connect(self.output/'runs'/result['run']/'mayhem.sqlite3');db.row_factory=sqlite3.Row
        try:
            name=display_name(db,A,'pt-BR',['blitz'])
            self.assertTrue(name['fallback']);self.assertEqual(name['locale'],'en-US')
        finally:db.close()

    def test_raw_corruption_detected(self):
        result=self.publish();manifest=read(self.output/'runs'/result['run']/'manifest.json')
        archive=next(iter(manifest['artifacts'].values()))
        (self.output/archive['archive_path']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):verify_run(self.output,result['run'])

    def test_incomplete_intake_is_never_published(self):
        write(self.root/'intake.json',{'status':'failed'})
        with self.assertRaises(ValueError):self.publish()
        self.assertFalse((self.output/'current.json').exists())

    def test_http_resume_checks_payload_hash(self):
        http=Http(self.root);url='https://arammayhem.com/data/v1/index.json'
        from mayhem_data.common import digest
        data=b'{"fixture":true}';cache=self.root/'http'/digest(url);replace_bytes(cache,data)
        http.checkpoint['requests'][digest(url)]={'sha256':digest(data),'url':url}
        with patch('mayhem_data.fetch.urlopen',side_effect=AssertionError('Network should not be used')):
            self.assertEqual(http.get(url)[0],data)

    def test_rule_review_persists_until_explicit_revision(self):
        artifact=next(iter(self.batch.artifacts))
        self.batch.observe(B,artifact,{'scope':'global'},{'tier':metric('A','source_label','test')})
        self.batch.observe(ITEM,artifact,{'scope':'global'},{'tier':metric('A','source_label','test')})
        r=rule();r['validated_patches']={'blitz':'16.21'}
        write(self.root/'data/config/rules.json',{'rules':[r]})
        self.publish()
        new=copy.deepcopy(self.batch)
        path=self.root/'effect-change.json';write(path,{'effect':'changed'})
        new.catalog[0]['artifact']=new.artifact(path)
        new.catalog[0]['descriptions']={'en-US':{'tooltip':'new effect'}}
        result=self.publish(new)
        def pending(run):
            db=sqlite3.connect(self.output/'runs'/run/'mayhem.sqlite3')
            try:return json.loads(db.execute('SELECT data_json FROM rules').fetchone()[0])['pending_review']
            finally:db.close()
        self.assertTrue(pending(result['run']))
        write(self.root/'data/config/pipeline.json',{**self.config,'notes':'unrelated config change'})
        result=self.publish(new)
        self.assertTrue(pending(result['run']))
        r['review_revision']=2;write(self.root/'data/config/rules.json',{'rules':[r]})
        result=self.publish(new)
        self.assertFalse(pending(result['run']))


if __name__=='__main__':unittest.main()
