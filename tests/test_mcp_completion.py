import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/data'))
from mayhem_data.common import write,digest
from mayhem_data.mcp import structured,enrich,selected_folder
from mayhem_data.model import Batch,Identity
from mayhem_data.completion import audit,promote


class McpEvidence(unittest.TestCase):
    def setUp(self):
        self.base=(Path(__file__).resolve().parents[1]/'data/test-tmp').resolve();self.base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.base);self.root=Path(self.temp.name)
        self.folder=self.root/'research/arammayhem-mcp';self.folder.mkdir(parents=True)
        self.batch=Batch('arammayhem',{'release':'fixture','patches':['26.21']})
        self.identity=Identity();self.identity.champions['Teemo']='champion:game:17'
        self.identity.add_name('Mystic Punch',1058)

    def tearDown(self):
        assert self.base in self.root.resolve().parents
        self.temp.cleanup()

    def response(self,name,data):write(self.folder/name,{'result':{'structuredContent':data}})

    def test_text_encoded_json_is_supported_without_execution(self):
        response={'result':{'content':[{'type':'text','text':'{"patch":"26.21","name":"Example"}'}]}}
        self.assertEqual(structured(response)['patch'],'26.21')
        self.assertIsNone(structured({'result':{'content':[{'type':'text','text':'not JSON'}]}}))

    def test_build_priority_and_full_skill_paths_are_preserved(self):
        self.response('build-Teemo.json',{'patch':'26.21','dataDate':'2026-10-29','championId':'Teemo',
            'builds':{'core':[{'items':[{'itemId':'3085'}],'pickRate':'12.5%','winRate':'50%'}]},
            'skillOrders':[{'order':'Q>E>W','pickRate':'30%','winRate':'51%',
                'paths':[{'sequence':'Q W E Q','pickRate':'5%','winRate':'52%'}]}]})
        enrich(self.batch,self.identity,self.root)
        scopes={row['context']['scope']:row for row in self.batch.observations}
        self.assertEqual(set(scopes),{'champion_build','skill_order','skill_path'})
        self.assertEqual(scopes['champion_build']['metrics']['pick_rate']['value'],.125)
        self.assertEqual(scopes['skill_path']['context']['sequence'],'Q W E Q')
        self.assertIn('not_augment_conditioned',scopes['champion_build']['flags'])

    def test_historical_patch_notes_are_kept(self):
        self.response('patch-26-20.json',{'patch':'26.20','dataDate':'2026-10-07','augmentChanges':[]})
        enrich(self.batch,self.identity,self.root)
        self.assertEqual(self.batch.notes[0]['patch'],'26.20')
        self.assertTrue(self.batch.notes[0]['historical_patch'])
        self.assertEqual(self.batch.observations,[])

    def test_mismatched_current_data_is_not_silently_imported(self):
        self.response('tiers.json',{'patch':'26.20','entries':[{'championId':'Teemo','tier':'S'}]})
        enrich(self.batch,self.identity,self.root)
        self.assertEqual(self.batch.observations,[])
        self.assertEqual(self.batch.issues[0]['code'],'mcp_patch_differs_from_download')

    def test_champion_association_does_not_claim_measured_synergy(self):
        self.response('augment.json',{'patch':'26.21','id':'mystic_punch','name':'Mystic Punch',
            'availability':'live','sourceStatus':'live','rarity':'prismatic','description':'Example effect',
            'tier':'S','rank':1,'pickRate':'12','topChampionIds':['Teemo']})
        enrich(self.batch,self.identity,self.root)
        association=next(r for r in self.batch.observations if r['context']['scope']=='augment_champion_association')
        self.assertNotIn('win_rate',association['metrics'])
        self.assertIn('association_basis_unconfirmed',association['flags'])
        self.assertEqual(self.batch.relations,[])

    def test_unknown_editorial_combo_is_retained_without_guessing_requirements(self):
        self.response('combos.json',{'patch':'26.21','combos':[{'championId':'Teemo',
            'augmentIds':['mystic_punch'],'tier':'S','description':'Runaan example',
            'url':'https://arammayhem.com/combo/fixture'}]})
        enrich(self.batch,self.identity,self.root)
        relation=self.batch.relations[0]
        self.assertEqual(relation['member_semantics'],'unspecified')
        self.assertEqual(relation['validation'],'hypothesis')
        self.assertIsNone(relation['patch'])
        self.assertEqual(relation['response_patch'],'26.21')

    def test_request_provenance_and_hashes_are_attached(self):
        self.response('tiers.json',{'patch':'26.21','entries':[]})
        sha=digest((self.folder/'tiers.json').read_bytes())
        write(self.folder/'manifest.json',{'files':[{'file':'tiers.json','tool':'get_tier_list',
            'arguments':{'offset':0,'limit':30},'collected_at':'2026-10-30T00:00:00Z','sha256':sha}]})
        enrich(self.batch,self.identity,self.root)
        artifact=self.batch.artifacts[sha]
        self.assertEqual(artifact['tool'],'get_tier_list')
        self.assertEqual(artifact['expected_sha256'],sha)
        self.assertEqual(artifact['collected_at'],'2026-10-30T00:00:00Z')

    def test_selected_complete_snapshot_excludes_old_diagnostics(self):
        self.response('old-error.json',{'patch':'26.20'})
        write(self.folder/'current.json',{'snapshot':'snapshots/fixture'})
        write(self.folder/'snapshots/fixture/tiers.json',{'result':{'structuredContent':{'patch':'26.21','entries':[]}}})
        enrich(self.batch,self.identity,self.root)
        self.assertEqual(len(self.batch.artifacts),1)

    def test_snapshot_path_cannot_escape_source_directory(self):
        write(self.folder/'current.json',{'snapshot':'../../outside'})
        with self.assertRaises(ValueError):selected_folder(self.root)


class FullCollectionAudit(unittest.TestCase):
    def setUp(self):
        self.base=(Path(__file__).resolve().parents[1]/'data/test-tmp').resolve();self.base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.base);self.root=Path(self.temp.name)
        self.workspace=self.root/'intake';self.folder=self.workspace/'research/arammayhem-mcp/bulk'
        write(self.workspace/'intake.json',{'status':'complete'})
        source=self.workspace/'data/sources/arammayhem'
        write(source/'current.json',{'snapshot':'snapshots/source','release_id':'fixture'})
        snap=source/'snapshots/source'
        write(snap/'index.json',{'releaseId':'fixture','latestPatch':'26.21','patches':[{'patch':'26.21'}]})
        write(snap/'latest/champions.json',{'rows':[{'championId':'Teemo'}]})
        write(snap/'latest/augments.json',{'rows':[{'augmentId':'mystic_punch'}]})
        combo={'championId':'Teemo','augmentIds':['mystic_punch'],'url':'https://arammayhem.com/combo/fixture',
            'description':'Editorial explanation','tier':'S'}
        write(snap/'latest/combos.json',{'rows':[combo]})
        responses=[
            ('build','get_champion_build',{'champion':'Teemo'},{'championId':'Teemo','builds':{},'skillOrders':[]}),
            ('combos','get_top_combos',{'champion':'Teemo'},{'total':1,'combos':[combo]}),
            ('augment','get_augment',{'augment':'mystic_punch'},{'id':'mystic_punch','availability':'live'}),
            ('tiers','get_tier_list',{'offset':0},{'entries':[{'championId':'Teemo'}]}),
            ('notes','get_patch_notes',{}, {'augmentChanges':[]}),
            ('links','get_site_links',{}, {'links':[]})]
        files=[]
        for name,tool,args,data in responses:
            file=name+'.json';write(self.folder/file,{'result':{'structuredContent':{'patch':'26.21',**data}}})
            files.append({'file':file,'tool':tool,'arguments':args,'sha256':digest((self.folder/file).read_bytes()),'unavailable':False})
        write(self.folder/'tools.json',{'result':{'tools':[]}})
        self.manifest={'complete':True,'release_id':'fixture','expected_requests':6,'expected_champions':1,
            'expected_augment_ids':['mystic_punch'],'files':files,'tools_sha256':digest((self.folder/'tools.json').read_bytes())}
        write(self.folder/'manifest.json',self.manifest)

    def tearDown(self):
        assert self.base in self.root.resolve().parents
        self.temp.cleanup()

    def rewrite(self,filename,data):
        write(self.folder/filename,{'result':{'structuredContent':{'patch':'26.21',**data}}})
        for row in self.manifest['files']:
            if row['file']==filename:row['sha256']=digest((self.folder/filename).read_bytes())
        write(self.folder/'manifest.json',self.manifest)

    def test_complete_collection_promotes_without_deleting_old_research(self):
        write(self.root/'research/arammayhem-mcp/old-probe.json',{'research':'preserved'})
        result=promote(self.workspace,self.root)
        self.assertEqual(result['responses'],6)
        self.assertTrue((self.root/'research/arammayhem-mcp/old-probe.json').exists())
        self.assertTrue((selected_folder(self.root)/'manifest.json').exists())

    def test_missing_combo_explanation_response_blocks_promotion(self):
        self.rewrite('combos.json',{'total':0,'combos':[]})
        self.assertFalse(audit(self.workspace)['complete_requests'])
        with self.assertRaises(ValueError):promote(self.workspace,self.root)

    def test_endpoint_truncation_is_explicit_and_blocks_promotion(self):
        self.rewrite('combos.json',{'total':31,'combos':[]})
        report=audit(self.workspace)
        self.assertEqual(len(report['truncated']),1)
        self.assertFalse(report['complete_requests'])

    def test_historical_data_cannot_masquerade_as_current_build(self):
        self.rewrite('build.json',{'patch':'26.20','championId':'Teemo','builds':{}})
        self.assertTrue(any(e['reason']=='current_response_patch_mismatch' for e in audit(self.workspace)['errors']))

    def test_response_corruption_is_detected(self):
        (self.folder/'augment.json').write_bytes(b'changed')
        with self.assertRaises(ValueError):audit(self.workspace)

    def test_incomplete_intake_does_not_promote(self):
        write(self.workspace/'intake.json',{'status':'pending'})
        with self.assertRaises(ValueError):promote(self.workspace,self.root)


if __name__=='__main__':unittest.main()
