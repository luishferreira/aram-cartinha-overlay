import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools.app_paths import app_root
from tools.launcher.state import ChampionData,select_snapshot,read_snapshot,import_status,tier_key
from tools.launcher.updates import select_release,version,checked_url,download,may_install

ROOT=app_root()


class SelectionTests(unittest.TestCase):
    def session(self):
        return {'localPlayerCellId':7,'benchEnabled':True,
                'myTeam':[{'cellId':0,'championId':22},{'cellId':7,'championId':103,'spell1Id':4,'spell2Id':32}],
                'benchChampions':[{'championId':11},{'championId':145},{'championId':11},{'championId':0},{}],
                'chatDetails':{'secret':'not retained'}}

    def test_bench_and_own_champion_are_distinct_and_private_fields_are_not_retained(self):
        value=select_snapshot(self.session(),2400)
        self.assertEqual(value['champion_id'],103)
        self.assertEqual(value['bench'],[11,145])
        self.assertEqual(value['spells'],[4,32])
        self.assertNotIn('secret',json.dumps(value))

    def test_other_queue_and_missing_own_cell_do_not_fabricate_a_champion(self):
        self.assertEqual(select_snapshot(self.session(),450)['state'],'other_queue')
        session=self.session();session['localPlayerCellId']=88
        self.assertIsNone(select_snapshot(session,2400)['champion_id'])
        session['benchEnabled']=False
        self.assertEqual(select_snapshot(session,2400)['bench'],[])

    def test_empty_team_slots_preserve_the_client_order_and_own_position(self):
        session=self.session()
        session['myTeam'].insert(1,{'cellId':2,'championId':0})
        slots=select_snapshot(session,2400)['team_slots']
        self.assertEqual([s['champion_id'] for s in slots],[22,None,103])
        self.assertEqual([s['is_self'] for s in slots],[False,False,True])

    def test_no_old_choices_survive_when_selection_ends_during_read(self):
        class Client:
            phase=0
            def request(inner,method,path):
                self.assertEqual(method,'GET')
                if path.endswith('gameflow-phase'):
                    inner.phase+=1;return 'ChampSelect' if inner.phase==1 else 'GameStart'
                if path.endswith('gameflow/v1/session'):return {'gameData':{'queue':{'id':2400}}}
                return self.session()
        value=read_snapshot(Client())
        self.assertEqual(value['state'],'transition')
        self.assertEqual(value['bench'],[])

    def test_success_must_match_champion_generation_and_running_importer(self):
        snapshot={'state':'select','champion_id':103}
        status={'state':'imported','champion_id':103,'generation':'new','paths':1,'owner_pid':123}
        self.assertEqual(import_status(status,snapshot,'new',123)[0],'Arsenais prontos')
        for changes in ({'champion_id':11},{'generation':'old'},{'owner_pid':456}):
            self.assertNotEqual(import_status({**status,**changes},snapshot,'new',123)[0],'Arsenais prontos')


class ChampionTests(unittest.TestCase):
    def test_all_champions_have_distinct_source_metrics_and_sorted_spell_popularity(self):
        data=ChampionData(ROOT)
        self.assertEqual(len(data.champions),173)
        for c in data.champions.values():
            for source in ('aramkit','arammayhem'):
                self.assertIn(data.metrics(c['id'],source)['tier'][:1],list('SABCD'))
                self.assertTrue(0<=data.metrics(c['id'],source)['win_rate']<=1)
            spells=data.spells(c['id'])
            rates=[r.get('pick_rate') or 0 for r in spells]
            self.assertEqual(rates,sorted(rates,reverse=True))
        self.assertEqual(data.metrics(103,'aramkit')['win_rate'],.5224)
        self.assertEqual(data.spells(103)[0]['ids'],[4,32])
        self.assertNotEqual(data.metrics(103,'aramkit'),data.metrics(103,'arammayhem'))

    def test_subtiers_keep_their_source_order(self):
        expected=['S+','S','S-','A+','A','A-','B','C','D']
        self.assertEqual(sorted(reversed(expected),key=tier_key),expected)


class UpdateTests(unittest.TestCase):
    def release(self,tag):
        name=f'AramCartinhaOverlay-{tag.removeprefix("v")}-Setup-x64.exe'
        return {'tag_name':tag,'prerelease':True,'draft':False,'assets':[
            {'name':n,'browser_download_url':f'https://github.com/luishferreira/aram-cartinha-overlay/releases/download/{tag}/{n}'}
            for n in [name,'SHA256SUMS.txt']]}

    def test_semver_and_prereleases_work_without_github_latest(self):
        self.assertLess(version('0.1.0-alpha.9'),version('0.1.0-alpha.10'))
        self.assertLess(version('0.1.0-rc.1'),version('0.1.0'))
        self.assertEqual(select_release([self.release('v0.1.0-alpha.10')],'0.1.0-alpha.4')['tag'],'v0.1.0-alpha.10')
        self.assertIsNone(select_release([self.release('v0.1.0-alpha.3')],'0.1.0-alpha.4'))

    def test_drafts_missing_installer_and_foreign_downloads_are_rejected(self):
        release=self.release('v0.1.0-alpha.5');release['draft']=True
        self.assertIsNone(select_release([release],'0.1.0-alpha.4'))
        release['draft']=False;release['assets']=[]
        self.assertIsNone(select_release([release],'0.1.0-alpha.4'))
        release=self.release('v0.1.0-alpha.5')
        release['assets'][0]['browser_download_url']='https://github.com/other/repo/malware.exe'
        with self.assertRaises(ValueError):select_release([release],'0.1.0-alpha.4')
        for url in ['http://github.com/a','https://github.com.evil.example/a','https://user:pass@github.com/a']:
            with self.assertRaises(ValueError):checked_url(url)

    def test_verified_installer_download_is_atomic_and_corruption_does_not_replace_it(self):
        release=select_release([self.release('v0.1.0-alpha.5')],'0.1.0-alpha.4')
        payload=b'MZexample installer';checksum=hashlib.sha256(payload).hexdigest()
        sums=(checksum+'  '+release['name']+'\n').encode()
        parent=ROOT/'data/test-tmp';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temp:
            with patch('tools.launcher.updates.fetch',side_effect=[sums,payload]):
                path,actual=download(release,temp)
            self.assertEqual(path.read_bytes(),payload)
            self.assertEqual(actual,checksum)
            with patch('tools.launcher.updates.fetch',side_effect=[sums,b'MZcorrupt']):
                with self.assertRaises(ValueError):download(release,temp)
            self.assertEqual(path.read_bytes(),payload)

    def test_installation_never_interrupts_champ_select_queue_or_game(self):
        for phase in ['ChampSelect','Matchmaking','ReadyCheck','InProgress','Reconnect',None]:
            self.assertFalse(may_install(phase,False))
        self.assertFalse(may_install('None',True))
        self.assertTrue(may_install('None',False))
        self.assertTrue(may_install('ClientClosed',False))


if __name__=='__main__':unittest.main()
