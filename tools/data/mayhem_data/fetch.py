"""Bounded public acquisition into an isolated workspace; never mutates research.

Known public HTTP routes only. Browser-only secondary sources stay explicitly stale.
"""
import json
import re
import shutil
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from .common import atomic_json, digest, now, read, write

HOSTS={'blitz.gg','data.v2.iesdev.com','utils.iesdev.com','lol-api-champion.op.gg',
       'aramkit.com','data.aramkit.com','arammayhem.com'}


def safe_url(url):
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise ValueError(f'Unexpected public origin: {url}')
    return url


def replace_bytes(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.download')
    temp.write_bytes(payload);temp.replace(path)


class Http:
    def __init__(self,workspace,resume=False):
        self.workspace=workspace
        self.path=workspace/'fetch-checkpoint.json'
        self.checkpoint=read(self.path) if resume and self.path.exists() else {'requests':{},'errors':[]}
        self.last_request=0

    def get(self,url):
        safe_url(url)
        key=digest(url);cached=self.checkpoint['requests'].get(key)
        cache=self.workspace/'http'/key
        if cached and cache.exists() and digest(cache.read_bytes())==cached['sha256']:
            return cache.read_bytes(),cached
        delay=max(0,1.2-(time.monotonic()-self.last_request))
        time.sleep(delay)
        try:
            self.last_request=time.monotonic()
            with urlopen(Request(url,headers={'User-Agent':'MayhemResearch/0.2','Accept-Encoding':'identity'}),timeout=45) as response:
                safe_url(response.url)
                payload=response.read()
                meta={'url':url,'final_url':response.url,'status':response.status,
                    'collected_at':now(),'sha256':digest(payload),'bytes':len(payload)}
            replace_bytes(cache,payload)
            self.checkpoint['requests'][key]=meta
            atomic_json(self.path,self.checkpoint)
            return payload,meta
        except Exception as error:
            self.checkpoint['errors'].append({'url':url,'at':now(),'error':str(error)})
            atomic_json(self.path,self.checkpoint)
            raise

    def json_to(self,url,path):
        payload,meta=self.get(url);json.loads(payload)
        replace_bytes(path,payload)
        return json.loads(payload),meta


def seed_workspace(root,workspace):
    # Copy only acquired public inputs and project data config, never installed apps or credentials.
    patterns=['research/champion-snapshots/*.json','research/public-snapshots/*.json',
        'research/aramkit-data/*.json','research/aramkit-data/champion-details/*.json',
        'research/aramkit-data/conditional-snapshots/**/*.json',
        'research/external-champions/aramgg-*.html','research/external-champions/aramgg-*.meta.json',
        'research/arammayhem-mcp/**/*.json','research/aramgg-api/**/*','data/config/*.json','data/sources/arammayhem/**/*']
    for pattern in patterns:
        for path in root.glob(pattern):
            if not path.is_file():continue
            target=workspace/path.relative_to(root)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    path=root/'research/external-pages-normalized.json'
    shutil.copy2(path,workspace/path.relative_to(root))
    # HTML parser is a normal repository module, not an acquired artifact; adapters import it from the project.


def champion_catalog(workspace):
    known=read(workspace/'research/champion-snapshots/champion-catalog.json')['champions']
    result={int(c['id']):c for c in known}
    for cid,row in read(workspace/'research/aramkit-data/champions-en-US.json').items():
        if int(cid) not in result:
            result[int(cid)]={'id':int(cid),'key':row['riotId'],'name':row['name'],'locale':'en-US'}
    return [result[k] for k in sorted(result)]


def fetch_rankings(workspace,http,source,champions):
    out=workspace/'research/champion-snapshots'
    records=[]
    for index,c in enumerate(champions,1):
        cid=c['id']
        url=(f'https://data.v2.iesdev.com/api/v1/query_objects/prod/lol/aram_mayhem_champion?champion_id={cid}'
             if source=='blitz' else f'https://lol-api-champion.op.gg/api/contents/stats/champions/{cid}/aram-augments')
        payload,meta=http.get(url);data=json.loads(payload)
        atomic_json(out/f'{source}-{cid}.json',{**meta,'source':source,'champion_id':cid,'champion_key':c['key'],'payload':data})
        records.append(meta)
        if index%30==0:print(f'{source}: {index}/{len(champions)}',flush=True)
    if source=='opgg':
        http.json_to('https://lol-api-champion.op.gg/api/meta/aram-augments?hl=pt_BR',
                     workspace/'research/public-snapshots/opgg-augments-ptbr.json')
        _,meta=http.json_to('https://lol-api-champion.op.gg/api/meta/aram-augments?hl=en_US',
                     workspace/'research/public-snapshots/opgg-augments-enus.json')
        atomic_json(workspace/'research/public-snapshots/opgg-augments-enus.meta.json',meta)
    else:
        sample=read(out/f'blitz-{champions[0]["id"]}.json')['payload']['data'][0]
        patch=sample['patch']
        url=f'https://utils.iesdev.com/static/json/lol/mayham/{patch}/augments_en_us'
        data,_=http.get(url);json.loads(data)
        script=[{'attrs':{'data-url':url},'body':json.dumps({'body':data.decode('utf-8-sig')})}]
        atomic_json(workspace/'research/public-snapshots/blitz-general.scripts.json',script)
    return {'requests':len(records),'completed_at':now()}


def fetch_aramkit(workspace,http):
    payload,meta=http.get('https://aramkit.com/en-US')
    html=payload.decode('utf-8')
    # Read committed config literals without executing third-party JavaScript.
    match=re.search(r'version:"([\d.]+)",dataPath:"(data/[\w.\-]+)",resourcePath:"(resources/[\w.\-]+)"',html)
    if not match:raise ValueError('ARAMKit release schema changed; acquisition stopped.')
    patch,data_path,resource_path=match.groups()
    base='https://data.aramkit.com/'+data_path+'/stats/all/'
    replace_bytes(workspace/'research/external-snapshots/aramkit-home.html',payload)
    for file,remote in [('augments-en-US.json','augments'),('champions-en-US.json','champions')]:
        http.json_to(f'https://data.aramkit.com/{resource_path}/en-US/resources/{remote}.json',workspace/'research/aramkit-data'/file)
    champions=champion_catalog(workspace);records=[]
    http.json_to(base+'augment-rankings.json',workspace/'research/aramkit-data/augment-rankings.json')
    for index,c in enumerate(champions,1):
        _,meta=http.json_to(base+f'champion-details/{c["id"]}.json',workspace/f'research/aramkit-data/champion-details/{c["id"]}.json')
        records.append({**meta,'champion_id':c['id'],'at':meta['collected_at']})
        if index%30==0:print(f'aramkit: {index}/{len(champions)}',flush=True)
    atomic_json(workspace/'research/aramkit-data/manifest.json',records)
    # Refresh the one optional resource already supported, without claiming all-champion coverage.
    http.json_to(base+'champion-details/11-single-augments.json',workspace/'research/aramkit-data/masteryi-single-augments.json')
    return {'release':data_path,'patch':patch,'champions':len(champions),'completed_at':now()}


def fetch_arammayhem(workspace,http):
    import sync_arammayhem as downloads
    # This writes only to the isolated, independently copied workspace.
    previous_base=downloads.BASE;downloads.BASE=workspace/'data/sources/arammayhem'
    try:downloads.sync()
    finally:downloads.BASE=previous_base
    snapshot=workspace/'data/sources/arammayhem'/read(workspace/'data/sources/arammayhem/current.json')['snapshot']
    augments={r['augmentId'] for r in read(snapshot/'latest/augments.json')['rows']}
    for historical in snapshot.glob('history/*/augments.json'):
        augments.update(r['augmentId'] for r in read(historical)['rows'])
    for combo in read(snapshot/'latest/combos.json')['rows']:augments.update(combo['augmentIds'])
    champions=read(snapshot/'latest/champions.json')['rows']
    probes=[]
    for c in champions:
        probes.extend([(f'combos-{c["championId"]}','get_top_combos',{'champion':c['championId'],'limit':30}),
                       (f'build-{c["championId"]}','get_champion_build',{'champion':c['championId']})])
    probes.extend((f'augment-{aug}','get_augment',{'augment':aug}) for aug in sorted(augments))
    probes.extend((f'tiers-{offset}','get_tier_list',{'offset':offset,'limit':30}) for offset in range(0,len(champions),30))
    probes.append(('patch-latest','get_patch_notes',{}))
    index=read(snapshot/'index.json')
    for patch in index['patches']:
        version=patch['slug'].replace('-','.')
        if version!=index['latestPatch']:
            probes.append((f'patch-{patch["slug"]}','get_patch_notes',{'patch':version}))
    probes.append(('site-links','get_site_links',{}))
    # urllib needs no external MCP installation; initialize once, retain only a transient session ID.
    import requests
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'research'))
    from inspect_arammayhem_mcp import decode
    session=requests.Session();session.headers.update({'Accept':'application/json, text/event-stream','Content-Type':'application/json'})
    response=session.post('https://arammayhem.com/mcp',json={'jsonrpc':'2.0','id':1,'method':'initialize',
        'params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'mayhem-local-data','version':'1'}}},timeout=45)
    decode(response)
    if response.headers.get('Mcp-Session-Id'):session.headers['Mcp-Session-Id']=response.headers['Mcp-Session-Id']
    session.post('https://arammayhem.com/mcp',json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=45).raise_for_status()
    # Replace seeded diagnostic MCP responses with the coherent bulk acquisition; raw research originals are untouched.
    folder=workspace/'research/arammayhem-mcp'
    checkpoint=http.checkpoint.setdefault('mcp',{})
    if not checkpoint:
        if workspace.resolve() not in folder.resolve().parents:raise ValueError('MCP workspace escaped intake')
        for path in folder.rglob('*.json'):
            if folder.resolve() not in path.resolve().parents:raise ValueError('MCP file escaped intake')
            path.unlink()
    bulk=folder/'bulk';bulk.mkdir(parents=True,exist_ok=True)
    discovery=decode(session.post('https://arammayhem.com/mcp',json={'jsonrpc':'2.0','id':2,
        'method':'tools/list','params':{}},timeout=45))
    atomic_json(bulk/'tools.json',discovery)
    records=[]
    for number,(label,name,args) in enumerate(probes,3):
        args['locale']='en';target=bulk/f'{label}.json'
        saved=checkpoint.get(label)
        if saved and target.exists() and digest(target.read_bytes())==saved['sha256']:
            records.append(saved);continue
        result=None
        for attempt in range(4):
            time.sleep(1.25)
            try:
                response=session.post('https://arammayhem.com/mcp',json={'jsonrpc':'2.0','id':number,
                    'method':'tools/call','params':{'name':name,'arguments':args}},timeout=45)
                if response.status_code in (429,500,502,503,504) and attempt<3:
                    delay=min(60,max(5,int(response.headers.get('Retry-After','60'))))
                    print(f'arammayhem MCP: transient HTTP {response.status_code}, retry in {delay}s',flush=True)
                    time.sleep(delay);continue
                result=decode(response);break
            except (requests.Timeout,requests.ConnectionError):
                if attempt==3:raise
                print(f'arammayhem MCP: connection interrupted, retry {attempt+1}/3',flush=True)
                time.sleep(5*(attempt+1))
        error_text=str(result.get('result',{}).get('content',[])).lower()
        unavailable=(name in ('get_champion_build','get_augment','get_patch_notes') and
            result.get('result',{}).get('isError') and any(t in error_text for t in ('not found','unavailable','no build','not published')))
        if (result.get('error') or result.get('result',{}).get('isError')) and not unavailable:
            raise ValueError(f'MCP failed for {label}: {str(result)[:400]}')
        atomic_json(target,result)
        record={'file':label+'.json','tool':name,'arguments':args,'collected_at':now(),'sha256':digest(target.read_bytes()),'unavailable':unavailable}
        records.append(record);checkpoint[label]=record;atomic_json(http.path,http.checkpoint)
        if (number-2)%30==0:print(f'arammayhem MCP: {number-2}/{len(probes)}',flush=True)
    final_index,_=http.get('https://arammayhem.com/data/v1/index.json')
    if digest(final_index)!=digest((snapshot/'index.json').read_bytes()):
        raise ValueError('Publisher release changed during MCP acquisition; do not publish mixed data.')
    atomic_json(bulk/'manifest.json',{'files':records,'endpoint':'https://arammayhem.com/mcp',
        'release_id':index['releaseId'],'expected_champions':len(champions),
        'expected_augment_ids':sorted(augments),'expected_requests':len(probes),
        'complete':True,'tools_sha256':digest((bulk/'tools.json').read_bytes()),
        'reuse_status':'MCP research; download CC BY scope not assumed.'})
    return {'mcp_requests':len(records),'champions':len(champions),'augment_ids':len(augments),'completed_at':now()}


def fetch_sources(root,workspace,sources,resume=False):
    root=Path(root).resolve();workspace=Path(workspace).resolve()
    intended=(root/'data/intake').resolve()
    if intended not in workspace.parents:raise ValueError(f'Workspace must be a child of {intended}')
    marker=workspace/'intake.json'
    if workspace.exists() and not (resume and marker.exists()):
        raise ValueError('Use a new workspace, or --resume with a previous intake workspace.')
    if not marker.exists():
        workspace.mkdir(parents=True)
        seed_workspace(root,workspace)
        atomic_json(marker,{'created_at':now(),'sources':sources,'completed':{},'status':'pending'})
    state=read(marker)
    if sorted(state['sources'])!=sorted(sources):raise ValueError('Resume requires the same source selection.')
    http=Http(workspace,resume)
    try:
        # Discover a new champion catalog before fetching champion-specific rankings.
        for source in sorted(sources,key=lambda s:0 if s=='aramkit' else 1):
            if source in state['completed']:continue
            if source=='aramkit':result=fetch_aramkit(workspace,http)
            elif source=='arammayhem':result=fetch_arammayhem(workspace,http)
            else:result=fetch_rankings(workspace,http,source,champion_catalog(workspace))
            state['completed'][source]=result;atomic_json(marker,state)
        state['status']='complete';atomic_json(marker,state)
    except Exception as error:
        state.update(status='failed',error=str(error),failed_at=now());atomic_json(marker,state)
        raise
    return {'workspace':str(workspace),'sources':state['completed'],
        'next':f'python tools/data/pipeline.py build --input-root "{workspace}"',
        'note':'No publication yet. Unselected sources retain their original dates and coverage.'}
