"""Read-only champion select snapshots. No account identifiers or chat payloads retained."""
import copy
import json
from pathlib import Path
import threading
import time

from tools.items.lcu import Lcu, ClientUnavailable, LcuError
from tools.live.data_paths import resource

SPELLS = {1:'Purificar',3:'Exaustão',4:'Flash',6:'Fantasma',7:'Curar',11:'Golpear',
          12:'Teleporte',13:'Clareza',14:'Incendiar',21:'Barreira',32:'Marca'}
ACTIVE_GAME = {'GameStart','InProgress','Reconnect','WaitingForStats','PreEndOfGame'}


def tier_key(tier):
    match = str(tier or '')
    return ({'S':0,'A':1,'B':2,'C':3,'D':4}.get(match[:1],33)*3+
            {'+':0,'':1,'-':2}.get(match[1:],1))


def percent(value):
    return '—' if value is None else f'{value*100:.2f}%'.replace('.',',')


def positive(value):
    return value if type(value) is int and value>0 else None


def select_snapshot(session, queue_id):
    if queue_id!=2400:
        return {'state':'other_queue','phase':'ChampSelect','queue_id':queue_id,
                'champion_id':None,'bench':[],'team':[],'spells':[]}
    own = next((p for p in session.get('myTeam',[]) if p.get('cellId')==session.get('localPlayerCellId')), {})
    bench = list(dict.fromkeys(i for b in session.get('benchChampions',[])
                              if isinstance(b,dict) and (i:=positive(b.get('championId')))))
    return {'state':'select','phase':'ChampSelect','queue_id':queue_id,
            'champion_id':positive(own.get('championId')),
            'bench':bench if session.get('benchEnabled',False) else [],
            'team':[i for p in session.get('myTeam',[]) if (i:=positive(p.get('championId')))],
            'team_slots':[{'champion_id':positive(p.get('championId')),
                           'is_self':p.get('cellId')==session.get('localPlayerCellId')}
                          for p in session.get('myTeam',[])[:5]],
            'spells':[own.get('spell1Id'),own.get('spell2Id')]}


def read_snapshot(client):
    phase = client.request('GET','/lol-gameflow/v1/gameflow-phase')
    if phase!='ChampSelect':
        return {'state':'game' if phase in ACTIVE_GAME else 'connected','phase':phase,
                'champion_id':None,'bench':[],'team':[],'spells':[]}
    flow = client.request('GET','/lol-gameflow/v1/session')
    queue_id = flow.get('gameData',{}).get('queue',{}).get('id')
    session = client.request('GET','/lol-champ-select/v1/session')
    # Reject a select that ended while reading, rather than presenting stale choices.
    if client.request('GET','/lol-gameflow/v1/gameflow-phase')!='ChampSelect':
        return {'state':'transition','phase':None,'champion_id':None,'bench':[],'team':[],'spells':[]}
    return select_snapshot(session,queue_id)


class SelectionService:
    def __init__(self,stop,root,*,demo=False):
        self.stop,self.root,self.demo = stop,Path(root),demo
        self.lock = threading.Lock()
        self.value = {'state':'connecting','phase':None,'champion_id':None,'bench':[],'team':[],'spells':[]}
        if demo:
            self.value = {'state':'select','phase':'ChampSelect','queue_id':2400,'champion_id':103,
                          'bench':[11,21,145,17,81,22,40,45],'team':[103,222,12,99,64],'spells':[4,32]}
        else:
            threading.Thread(target=self.run,daemon=True,name='mayhem-select').start()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.value)

    def run(self):
        client = None
        while not self.stop.is_set():
            try:
                client = client or Lcu()
                value = read_snapshot(client)
            except ClientUnavailable:
                client = None
                value = {'state':'offline','phase':None,'champion_id':None,'bench':[],'team':[],'spells':[]}
            except (LcuError,ValueError,KeyError,TypeError,OSError):
                client = None
                value = {'state':'unavailable','phase':None,'champion_id':None,'bench':[],'team':[],'spells':[]}
            with self.lock:
                self.value = {**value,'observed_at':time.monotonic()}
            self.stop.wait(1 if client else 3)


class ChampionData:
    def __init__(self,root):
        path = resource(root,'launcher.json','data/launcher/current.json')
        self.data = json.loads(path.read_text('utf8'))
        if self.data.get('schema_version')!=1:
            raise ValueError('Unsupported launcher data')
        self.champions = self.data['champions']

    def champion(self,ident):
        return self.champions.get(str(ident))

    def metrics(self,ident,source):
        champion = self.champion(ident) or {}
        return {k:v.get('value') for k,v in champion.get('sources',{}).get(source,{}).get('metrics',{}).items()}

    def spells(self,ident):
        champion = self.champion(ident) or {}
        return sorted(champion.get('summoners',{}).get('aramkit',{}).get('rows',[]),
                      key=lambda r:-(r.get('pick_rate') or 0))


def import_status(status,snapshot,generation,owner_pid=None):
    """Never carry an old champion's or old export's success into the current select."""
    if snapshot.get('state')!='select':
        return ('Arsenais automáticos','Na seleção de Mayhem, importamos os caminhos do seu campeão.')
    if (status.get('state')=='imported' and status.get('champion_id')==snapshot.get('champion_id')
            and status.get('generation')==generation and (owner_pid is None or status.get('owner_pid')==owner_pid)):
        return ('Arsenais prontos',f'{status.get("paths",0)} caminhos conferidos no cliente.')
    if status.get('state') in ('import_error','export_unavailable'):
        return ('Importação pendente','Não foi possível importar. O app tentará novamente.')
    return ('Preparando arsenais','Aguardando confirmar o campeão selecionado.')
