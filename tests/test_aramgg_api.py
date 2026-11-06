import json
import sys
import unittest
import tempfile
import hashlib
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/data'))
from mayhem_data.aramgg import decode_champion,client_metrics,ranking_metrics,import_api
from mayhem_data.changes import changes
from mayhem_data.common import write
from mayhem_data.model import Identity


class AramggContract(unittest.TestCase):
    def test_tuple_champion_identity_is_verified(self):
        with self.assertRaises(ValueError):decode_champion([['12','{"augments":{}}','16.21','2026-10-28']],11)

    def test_tuple_decodes_stringified_json_and_preserves_date(self):
        payload=[['11',json.dumps({'augments':{'1058':{'tier':'1'}}}),'16.21','2026-10-28']]
        data,patch,date=decode_champion(payload,11)
        self.assertEqual(data['augments']['1058']['tier'],'1')
        self.assertEqual((patch,date),('16.21','2026-10-28'))

    def test_missing_performance_is_not_zero(self):
        m=client_metrics({'win_rate':None,'num_games':None,'num_win_games':None})
        self.assertIsNone(m['win_rate']['value']);self.assertIsNone(m['sample_count']['value'])

    def test_counts_and_proportions_have_explicit_units(self):
        m=client_metrics({'win_rate':'0.7059','num_games':'204','num_win_games':'144'})
        self.assertEqual(m['sample_count']['value'],204)
        self.assertEqual(m['win_rate']['value'],.7059)
        self.assertEqual(m['wins']['value'],144)

    def test_tencent_rank_does_not_claim_uploaded_performance(self):
        m=ranking_metrics({'tier':'1','rank':'3','total':'132','pick_rate':'0.1','win_rate':'0.8','num_games':'500'})
        self.assertNotIn('win_rate',m);self.assertNotIn('sample_count',m)
        self.assertEqual(m['tier_raw']['value'],'1')

    def test_api_release_change_is_distinct_from_game_patch(self):
        events=changes({}, {},{'aramgg':{'release':'16.21.4','patches':['16.21']}},
            {'aramgg':{'release':'16.21.5','patches':['16.21']}})
        self.assertEqual([e['kind'] for e in events],['source_release_changed'])
        self.assertFalse(events[0]['requires_review'])


class AramggAdapter(unittest.TestCase):
    def setUp(self):
        self.base=(Path(__file__).resolve().parents[1]/'data/test-tmp').resolve();self.base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.base);self.root=Path(self.temp.name)
        self.folder=self.root/'research/aramgg-api/16.21.4'
        self.meta={'schemaVersion':1,'dataVersion':'16.21.4','gamePatch':'16.21'}
        write(self.folder.parent/'current.json',{'snapshot':'16.21.4','champion_sync_complete':True})
        write(self.folder/'config.json',self.meta)
        stats={'tier':'1','rank':'1','total':'1','pick_rate':'0.1','win_rate':'0.6',
            'num_games':'300','num_win_games':'180','win_rate_source':'aramgg-client-upload',
            'win_rate_region':'WORLD','win_rate_minimum_games':255,'win_rate_game_patch':'16.21','win_rate_date':'2026-10-29'}
        self.data={'augments':{'1058':stats},'source':'tencent','region':'CN','augment_trios':{},'match_history':{}}
        self.files={
            'augments.json':{'meta':self.meta,'data':[{'id':1058,'name':'Mystic Punch','key':'ARAM_MysticPunch',
                'rarityName':'prismatic','enabled':True,'statsAvailable':False}]},
            'champions.json':{'meta':self.meta,'data':[{'id':11,'name':'MasterYi','title':'Master Yi','stats':{}}]},
            'items.json':{'meta':self.meta,'data':[]},
            'expanded/11.json':{'meta':self.meta,'data':{'builds':[{'queueId':450,'patch':'16.21'}]}},
            'champions/11.json':[['11',json.dumps(self.data),'16.21','2026-10-28']]}
        self.save()

    def save(self):
        records={}
        for name,data in self.files.items():
            write(self.folder/name,data)
            records[name]={'url':'https://data.dtodo.cn/api/v1/en/'+name,
                'sha256':hashlib.sha256((self.folder/name).read_bytes()).hexdigest()}
        write(self.folder/'manifest.json',{'files':records,'champion_sync_complete':True})

    def tearDown(self):
        assert self.base in self.root.resolve().parents
        self.temp.cleanup()

    def test_winrate_and_rank_keep_separate_origin_date_and_region(self):
        batch=import_api(self.root,Identity())
        rows=[r for r in batch.observations if r['context']['scope']=='champion']
        rank=next(r for r in rows if 'rank' in r['metrics'])
        win=next(r for r in rows if 'win_rate' in r['metrics'])
        self.assertEqual((rank['context']['upstream_source'],rank['context']['region'],rank['stats_date']),('tencent','CN','2026-10-28'))
        self.assertEqual((win['context']['upstream_source'],win['context']['region'],win['stats_date']),('aramgg-client-upload','WORLD','2026-10-29'))
        self.assertNotIn('win_rate',rank['metrics'])

    def test_standard_aram_build_is_not_published_as_mayhem(self):
        batch=import_api(self.root,Identity())
        self.assertTrue(any(r['code']=='build_excluded_unconfirmed_mayhem_queue' for r in batch.issues))
        self.assertFalse(any(r['context']['scope']=='champion_build' for r in batch.observations))

    def test_version_mismatch_blocks_import(self):
        self.files['items.json']['meta']={**self.meta,'dataVersion':'16.20.1'};self.save()
        with self.assertRaises(ValueError):import_api(self.root,Identity())

    def test_incomplete_api_snapshot_is_rejected(self):
        write(self.folder/'manifest.json',{'files':{},'champion_sync_complete':False})
        with self.assertRaises(ValueError):import_api(self.root,Identity())

    def test_older_performance_keeps_its_patch_and_is_flagged(self):
        self.data['augments']['1058']['win_rate_game_patch']='16.19'
        self.files['champions/11.json'][0][1]=json.dumps(self.data);self.save()
        batch=import_api(self.root,Identity())
        win=next(r for r in batch.observations if r['context'].get('metric_group')=='uploaded_performance')
        self.assertEqual(win['patch'],'16.19');self.assertIn('historical_performance_patch',win['flags'])
        self.assertEqual(batch.metadata['historical_performance_rows'],1)


if __name__=='__main__':unittest.main()
