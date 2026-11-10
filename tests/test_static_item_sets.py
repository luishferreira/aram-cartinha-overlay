import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tools.items.static_sets import ROOT, load_export, items, build_set, validate_set, order_sets_by_popularity
from tools.items.import_sets import Importer, merge_collection
from tools.items.lcu import champion_context, Connection, LcuError
from tools.items.watcher import ItemSetWatcher


class FakeClient:
    def __init__(self, bundle):
        self.value = {"accountId":77, "timestamp":1, "itemSets":[
            {"uid":"personal", "title":"Minha build", "blocks":[], "extra":{"preserve":True}}]}
        self.catalog = [{"id":int(i["id"])} for s in bundle["itemSets"] for b in s["blocks"] for i in b["items"]]
        self.puts = 0
        self.reads = 0
        self.concurrent = False

    def account(self):
        return 42

    def collection(self, sid):
        self.reads += 1
        value = copy.deepcopy(self.value)
        if self.concurrent and self.reads>=2:
            value["itemSets"][0]["title"] = "Editado agora"
        return value

    def put_collection(self, sid, value):
        self.puts += 1
        self.value = copy.deepcopy(value)

    def request(self, method, path):
        if path.endswith("items.json"):
            return self.catalog
        raise AssertionError(path)


class StaticItemSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle, cls.manifest = load_export()

    def setUp(self):
        parent = ROOT/"data/test-tmp"
        parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.tmp.name)
        self.importer = Importer(self.bundle, self.root)
        self.client = FakeClient(self.bundle)

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_has_all_173_champions_485_paths_and_stable_unique_uids(self):
        sets = self.bundle["itemSets"]
        self.assertEqual(len(sets),485)
        self.assertEqual(len({s["uid"] for s in sets}),485)
        self.assertEqual(len({s["associatedChampions"][0] for s in sets}),173)
        self.assertEqual(len([s for s in sets if s["associatedChampions"]==[11]]),5)
        for value in sets:
            validate_set(value)
            self.assertNotIn("0", {i["id"] for b in value["blocks"] for i in b["items"]})

    def test_native_ids_preserve_mode_variants_and_repeated_components(self):
        self.assertEqual(items(["item:game:1036","item:game:1036","item:game:124011"]),
                         [{"id":"1036","count":2},{"id":"124011","count":1}])
        for bad in (None,"item:game:0","item:other:123"):
            with self.assertRaises(ValueError):
                items([bad])

    def test_expanded_nilah_keeps_general_options_separate_from_sparse_path(self):
        value = next(s for s in self.bundle["itemSets"] if s["associatedChampions"]==[895]
                     and s["title"].endswith("Letalidade"))
        blocks = {b["type"]:b["items"] for b in value["blocks"]}
        cores = [b for b in value['blocks'] if b['type'].startswith('ARAMKit · escolha')]
        self.assertEqual(len(cores[0]['items']),3)
        self.assertEqual(len(blocks["ARAMKit · Depois do núcleo · opções do caminho"]),2)
        self.assertEqual(len(blocks["ARAMKit · Outras opções de Nilah · geral"]),12)
        self.assertFalse(any(b["type"] in ("1º item","2º item","3º item") for b in value["blocks"]))
        specific = {i['id'] for b in value['blocks'] if b['type'].startswith('ARAMKit · ')
                    and not b['type'].startswith('ARAMKit · Outras opções') for i in b['items']}
        self.assertFalse(specific.intersection(i['id'] for i in blocks['ARAMKit · Outras opções de Nilah · geral']))

    def test_expanded_tristana_has_core_alternatives_and_more_later_options(self):
        value = next(s for s in self.bundle["itemSets"] if s["associatedChampions"]==[18]
                     and s["title"].endswith("On-hit"))
        blocks = {b["type"]:b["items"] for b in value["blocks"]}
        self.assertGreater(len(blocks["ARAMKit · Alternativas de núcleo · mesmo caminho"]),0)
        self.assertEqual(len(blocks["ARAMKit · Depois do núcleo · opções do caminho"]),12)

    def test_representative_route_uses_sample_instead_of_highest_winrate(self):
        def profile(name,n,wr,core):
            return {"id":name,"metrics":{"sample_count":{"value":n},"win_rate":{"value":wr}},
                    "item_set":[core],"artifact":"a","patch":"16.21","selector":"profile",
                    "routes":[{"purchase_order":[core],"metrics":{"sample_count":{"value":n}},
                               "selector":"route","starters":[],"boots":[],"laterItems":[]}]}
        value, provenance = build_set({"name":"Yi","key":"MasterYi","id":11},
            {"id":"aramkit:champion:game:11:on_hit","native_key":"on_hit"},
            [profile("high_wr",10,.99,"item:game:3006"),profile("common",100,.5,"item:game:3153")],lambda i:i)
        self.assertEqual(provenance["profile_id"],"common")
        self.assertEqual(value["blocks"][0]["items"][0]["id"],"3153")

    def test_merge_does_not_treat_title_prefix_as_ownership(self):
        foreign = {"uid":"another-app", "title":"Mayhem · My own", "blocks":[]}
        current = {"accountId":77,"itemSets":[foreign]}
        desired = [self.bundle["itemSets"][0]]
        result = merge_collection(current,desired,self.importer.owned)
        self.assertEqual(result["itemSets"][0],foreign)
        self.assertEqual(current["itemSets"],[foreign])

    def test_obsolete_inferred_path_is_removed_while_personal_set_is_kept(self):
        unused = next(uid for uid in self.importer.owned if uid not in {s['uid'] for s in self.bundle['itemSets']})
        obsolete = copy.deepcopy(self.bundle['itemSets'][0])
        obsolete['uid'] = unused
        self.client.value['itemSets'].append(obsolete)
        self.importer.sync(self.client,11)
        self.assertNotIn(unused,{s['uid'] for s in self.client.value['itemSets']})
        self.assertEqual(self.client.value['itemSets'][0]['uid'],'personal')

    def test_dry_run_neither_writes_nor_creates_backup(self):
        result = self.importer.sync(self.client,11,dry_run=True)
        self.assertEqual(result["paths"],5)
        self.assertEqual(self.client.puts,0)
        self.assertFalse((self.root/"data/local/item-sets/backups").exists())

    def test_idempotent_import_preserves_foreign_data_and_verifies_result(self):
        original = copy.deepcopy(self.client.value["itemSets"][0])
        result = self.importer.sync(self.client,11)
        self.assertEqual(self.client.puts,1)
        self.assertEqual(self.client.value["itemSets"][0],original)
        self.assertEqual(len(self.client.value["itemSets"]),6)
        self.assertTrue(all(s['title'].startswith('Keitinha · ') for s in self.client.value['itemSets']
                            if s['uid'] in self.importer.owned))
        self.assertTrue(Path(result["backup"]).exists())
        self.assertFalse(self.importer.sync(self.client,11)["changed"])
        self.assertEqual(self.client.puts,1)

    def test_champion_change_replaces_only_our_prior_champion_paths(self):
        self.importer.sync(self.client,11)
        self.importer.sync(self.client,876)
        self.assertEqual(len(self.client.value["itemSets"]),2)
        self.assertEqual(self.client.value["itemSets"][0]["uid"],"personal")
        self.assertEqual(self.client.value["itemSets"][1]["associatedChampions"],[876])

    def test_restore_retains_new_foreign_sets_added_since_import(self):
        result = self.importer.sync(self.client,11)
        self.client.value["itemSets"].append({"uid":"new-personal","title":"New","blocks":[]})
        restored = self.importer.restore(self.client,result["backup"])
        self.assertTrue(restored["restored"])
        self.assertEqual([s["uid"] for s in self.client.value["itemSets"]],["personal","new-personal"])

    def test_other_account_cannot_restore_backup(self):
        result = self.importer.sync(self.client,11)
        self.client.value["accountId"] = 88
        with self.assertRaises(ValueError):
            self.importer.restore(self.client,result["backup"])

    def test_concurrent_edits_prevent_collection_replacement(self):
        self.client.concurrent = True
        with self.assertRaisesRegex(RuntimeError,"concurrently"):
            self.importer.sync(self.client,11)
        self.assertEqual(self.client.puts,0)

    def test_changed_selection_prevents_write(self):
        with self.assertRaisesRegex(RuntimeError,"selection changed"):
            self.importer.sync(self.client,11,context_guard=lambda:False)
        self.assertEqual(self.client.puts,0)

    def test_missing_installed_item_fails_before_write(self):
        self.client.catalog = []
        with self.assertRaisesRegex(ValueError,"absent"):
            self.importer.sync(self.client,11)
        self.assertEqual(self.client.puts,0)

    def test_order_uses_path_popularity_with_zero_before_unknown_and_ignores_other_selection(self):
        values = copy.deepcopy([s for s in self.bundle['itemSets'] if s['associatedChampions']==[11]][:4])
        evidence = {s['uid']:{'path_id':'source:path:'+key}
                    for s,key in zip(values,('rare','common','zero','unknown'))}
        rows = []
        for key,pop,selection,wr in [('rare',.1,'filtered',.9),('common',.6,'filtered',.4),
                                     ('zero',0,'filtered',.5),('unknown',1,'unfiltered',1)]:
            rows.append({'champion_id':'champion:game:11',
                'context_json':json.dumps({'archetype':key,'selection':selection}),
                'metrics_json':json.dumps({'pick_rate':{'value':pop},'win_rate':{'value':wr}}),
                'patch':'test','artifact':'source','selector':key})
        ordered = order_sets_by_popularity(values,evidence,SimpleNamespace(execute=lambda sql:rows))
        self.assertEqual([evidence[s['uid']]['path_id'].rsplit(':',1)[1] for s in ordered],
                         ['common','rare','zero','unknown'])
        self.assertEqual([s['sortrank'] for s in ordered],[0,1,2,3])
        self.assertEqual(evidence[ordered[2]['uid']]['ordering']['reference']['pick_rate'],0)
        self.assertIsNone(evidence[ordered[3]['uid']]['ordering']['reference'])

    def test_changed_sort_order_is_reimported_without_duplicate_sets_or_foreign_edits(self):
        self.client.value['itemSets'][0]['sortrank']=12
        self.importer.sync(self.client,11)
        expected = {s['uid']:s.get('sortrank',0) for s in self.client.value['itemSets']
                    if s['uid'] in self.importer.owned}
        for value in self.client.value['itemSets']:
            if value['uid'] in self.importer.owned:value['sortrank']=99
        self.assertTrue(self.importer.sync(self.client,11)['changed'])
        actual = {s['uid']:s.get('sortrank',0) for s in self.client.value['itemSets']
                  if s['uid'] in self.importer.owned}
        self.assertEqual(actual,expected)
        self.assertEqual(self.client.value['itemSets'][0]['sortrank'],12)
        self.assertEqual(len(self.client.value['itemSets']),1+len(expected))

    def test_champion_detection_uses_own_cell_and_mayhem_queue(self):
        class Client:
            queue=2400
            phase="ChampSelect"
            def request(self, method, path):
                if path.endswith("gameflow-phase"):return self.phase
                if path.endswith("gameflow/v1/session"):return {"gameData":{"queue":{"id":self.queue,"mapId":12}}}
                return {"localPlayerCellId":7,"myTeam":[{"cellId":2,"championId":22},{"cellId":7,"championId":11}]}
        client=Client()
        self.assertEqual(champion_context(client)["champion_id"],11)
        client.queue=450
        self.assertIsNone(champion_context(client))
        client.phase="InProgress"
        self.assertIsNone(champion_context(client))

    def test_watcher_imports_after_stable_selection_and_again_after_swap(self):
        class Stop:
            tick=0
            def is_set(self):return self.tick>=5
            def wait(self,delay):self.tick+=1
        stop=Stop()
        def context(client):
            return {"champion_id":11 if stop.tick<2 else 876,"map_id":12,"queue_id":2400}
        watcher=ItemSetWatcher(stop,self.root)
        with patch('tools.items.watcher.load_export',return_value=(self.bundle,self.manifest)), \
             patch('tools.items.watcher.Lcu',return_value=self.client), \
             patch('tools.items.watcher.champion_context',side_effect=context), \
             patch('tools.items.watcher.time.monotonic',side_effect=lambda:stop.tick), \
             patch('tools.items.watcher.Importer') as importer:
            importer.return_value.sync.return_value={"changed":True}
            watcher.run()
            calls=importer.return_value.sync.call_args_list
            self.assertEqual([call.args[1] for call in calls],[11,876])
        self.assertEqual(json.loads((self.root/'data/local/item-sets/status.json').read_text())["state"],"imported")

    def test_connection_repr_never_contains_session_token(self):
        self.assertNotIn("private-token",repr(Connection(1234,"private-token")))

    def test_watcher_records_size_failure_without_reporting_import_success(self):
        class Stop:
            tick=0
            def is_set(self):return self.tick>=3
            def wait(self,delay):self.tick+=1
        stop=Stop();events=[]
        failure=LcuError(413,method='PUT',path='/lol-item-sets/v1/item-sets/42/sets',
                         request_bytes=900000,item_sets=300)
        watcher=ItemSetWatcher(stop,self.root,log=lambda kind,**fields:events.append(fields))
        with patch('tools.items.watcher.load_export',return_value=(self.bundle,self.manifest)), \
             patch('tools.items.watcher.Lcu',return_value=self.client), \
             patch('tools.items.watcher.champion_context',return_value={'champion_id':11,'map_id':12}), \
             patch('tools.items.watcher.time.monotonic',side_effect=lambda:stop.tick), \
             patch('tools.items.watcher.Importer') as importer:
            importer.return_value.sync.side_effect=failure
            watcher.run()
        status=json.loads((self.root/'data/local/item-sets/status.json').read_text())
        self.assertEqual(status['state'],'import_error')
        self.assertEqual(status['http_status'],413)
        self.assertEqual(status['request_bytes'],900000)
        self.assertEqual(status['item_sets'],300)
        self.assertNotIn('imported',[event['state'] for event in events])

    def test_watcher_reloads_new_generation_and_reimports_same_champion(self):
        pointer = self.root/'data/item-sets/current.json'
        pointer.parent.mkdir(parents=True)
        pointer.write_text(json.dumps({'generation':self.bundle['generation']}))
        newer = {**self.bundle,'generation':'f'*24}
        class Stop:
            tick=0
            def is_set(self):return self.tick>=5
            def wait(self,delay):
                self.tick+=1
                if self.tick==2:
                    pointer.write_text(json.dumps({'generation':newer['generation']}))
        stop=Stop()
        with patch('tools.items.watcher.load_export',side_effect=[(self.bundle,self.manifest),(newer,self.manifest)]) as load, \
             patch('tools.items.watcher.Lcu',return_value=self.client), \
             patch('tools.items.watcher.champion_context',return_value={'champion_id':11,'map_id':12}), \
             patch('tools.items.watcher.time.monotonic',side_effect=lambda:stop.tick), \
             patch('tools.items.watcher.Importer') as importer:
            importer.return_value.sync.return_value={'changed':True}
            ItemSetWatcher(stop,self.root).run()
            self.assertEqual(load.call_count,2)
            self.assertEqual(importer.call_count,2)
            self.assertEqual(importer.return_value.sync.call_count,2)


if __name__=="__main__":
    unittest.main()
