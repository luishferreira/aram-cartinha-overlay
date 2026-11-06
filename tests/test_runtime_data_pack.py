import copy
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import unittest

from tools.items.static_sets import ROOT, encode, load_export
from tools.live.data_paths import active_pack, load_pack, file_hash
from tools.live.offer_reader import load_names
from tools.live.source_cards import SourceReader, SourceCards
from tools.release.data_pack import keep_observation


class RuntimePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder,cls.manifest = active_pack(ROOT)
        parent = ROOT/'data/test-tmp'
        parent.mkdir(parents=True,exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=parent)
        cls.root = Path(cls.temp.name)
        cls.pack = cls.root/'data/runtime/runs'/cls.manifest['generation']
        cls.pack.mkdir(parents=True)
        for name in [*cls.manifest['files'],'manifest.json']:
            shutil.copyfile(cls.folder/name,cls.pack/name)
        (cls.root/'data/runtime/current.json').write_bytes(encode({
            'generation':cls.manifest['generation'],'manifest_sha256':file_hash(cls.pack/'manifest.json')}))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_self_contained_data_works_without_research_or_pipeline(self):
        self.assertFalse((self.root/'research').exists())
        self.assertFalse((self.root/'data/pipeline').exists())
        original = SourceReader(ROOT)
        compact = SourceReader(self.root,runtime_directory=self.pack)
        try:
            for args in ((18,3078,()),(17,3086,(1030,1098)),(18,1134,(1077,)),(None,3078,())):
                self.assertEqual(original.read(*args),compact.read(*args))
            self.assertEqual(compact.db.execute('PRAGMA query_only').fetchone()[0],1)
            with self.assertRaises(sqlite3.OperationalError):
                compact.db.execute('DELETE FROM observations')
            tables = {r[0] for r in compact.db.execute('SELECT name FROM sqlite_master WHERE type="table"')}
            self.assertNotIn('build_profiles',tables)
            self.assertNotIn('conditional_item_groups',tables)
        finally:
            original.close()
            compact.close()
        bundle,_ = load_export(self.root)
        self.assertEqual(len(bundle['itemSets']),485)
        self.assertEqual(len({s['associatedChampions'][0] for s in bundle['itemSets']}),173)
        self.assertEqual(load_names(ROOT),load_names(self.root))

    def test_async_overlay_uses_pack_without_full_database(self):
        service = SourceCards(self.root)
        try:
            began = time.monotonic()
            card = service.get(18,3078)
            while card is None and time.monotonic()-began<5:
                time.sleep(.01)
                card = service.get(18,3078)
            self.assertIsNotNone(card)
            self.assertNotIn('error',card)
            self.assertEqual(card['sources']['blitz']['metrics']['tier']['value'],'S')
        finally:
            service.close()
            service.thread.join(timeout=1)

    def test_corrupt_resource_is_detected_before_use(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/test-tmp') as temporary:
            folder = Path(temporary)
            value = copy.deepcopy(self.manifest)
            value['files']['cards.sqlite3'] = '0'*64
            (folder/'manifest.json').write_bytes(encode(value))
            for name in value['files']:
                if name!='cards.sqlite3':
                    shutil.copyfile(self.folder/name,folder/name)
            (folder/'cards.sqlite3').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                load_pack(folder)

    def test_path_traversal_in_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/test-tmp') as temporary:
            folder = Path(temporary)
            value = copy.deepcopy(self.manifest)
            value['files'] = {'../outside.sqlite3':'0'*64}
            (folder/'manifest.json').write_bytes(encode(value))
            with self.assertRaisesRegex(ValueError,'Invalid runtime artifact'):
                load_pack(folder)

    def test_research_builder_still_reads_full_database(self):
        reader = SourceReader(ROOT)
        try:
            self.assertIsNone(reader.runtime_generation)
            self.assertGreater(reader.db.execute('SELECT count(*) FROM build_profiles').fetchone()[0],100000)
        finally:
            reader.close()
        research,_ = load_export(ROOT,runtime=False)
        compact,_ = load_export(self.root)
        self.assertEqual(research,compact)

    def test_newer_developer_item_export_takes_precedence_over_old_pack(self):
        pointer = self.root/'data/item-sets/current.json'
        generation = 'a'*24
        directory = pointer.parent/'runs'/generation
        directory.mkdir(parents=True)
        bundle = json.loads((self.pack/'item-sets.json').read_text('utf8'))
        bundle['itemSets'][0]['title'] += ' · teste'
        (directory/'item-sets.json').write_bytes(encode(bundle))
        (directory/'manifest.json').write_bytes(encode({'generation':generation,
            'files':{'item-sets.json':file_hash(directory/'item-sets.json')}}))
        pointer.write_bytes(encode({'generation':generation}))
        try:
            loaded,_ = load_export(self.root)
            self.assertEqual(loaded['generation'],generation)
            self.assertTrue(loaded['itemSets'][0]['title'].endswith(' · teste'))
        finally:
            pointer.unlink()

    def test_filter_keeps_rank_inputs_and_excludes_hidden_historical_or_stage_data(self):
        row = {'source':'aramkit','scope':'champion','context_json':'{}','flags_json':'[]'}
        self.assertTrue(keep_observation(row))
        self.assertFalse(keep_observation({**row,'context_json':'{"stage":"1"}'}))
        self.assertFalse(keep_observation({**row,'context_json':'{"series":"historical"}'}))
        self.assertFalse(keep_observation({**row,'flags_json':'["historical_patch"]'}))
        self.assertTrue(keep_observation({**row,'source':'opgg','flags_json':'["historical_patch"]'}))
        self.assertTrue(keep_observation({**row,'source':'arammayhem','context_json':'{"ranking_scope":"rarity"}'}))


if __name__=='__main__':
    unittest.main()
