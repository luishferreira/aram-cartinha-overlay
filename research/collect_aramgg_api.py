"""Authenticated, read-only ARAMGG acquisition. Key is read from stdin, never saved.

Default: public docs/config and six diagnostic JSON requests (7 credits).
--sync-champions: additionally cache raw files for every listed champion.
Existing successful files are reused, with hashes verified against the manifest.
"""
import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError

BASE='https://data.dtodo.cn/api/v1/en/'
OUT=Path(__file__).parent/'aramgg-api'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Redirect refused for authenticated API acquisition')


def sha(payload):return hashlib.sha256(payload).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    authentication=parser.add_mutually_exclusive_group(required=True)
    authentication.add_argument('--key-stdin',action='store_true')
    authentication.add_argument('--key-prompt',action='store_true',help='Read the credential from a terminal with echo disabled')
    parser.add_argument('--sync-champions',action='store_true')
    args=parser.parse_args()
    if args.key_prompt:
        import getpass
        key=getpass.getpass('ARAMGG key (hidden input): ')
    else:key=sys.stdin.readline().strip()
    if not re.fullmatch(r'hx_live_[a-fA-F0-9]+',key):
        raise SystemExit('Expected an ARAMGG API key on stdin; no credential was displayed or saved.')
    print('Credential accepted in memory.',flush=True)
    opener=build_opener(NoRedirect())
    OUT.mkdir(parents=True,exist_ok=True)
    def public(path):
        with opener.open(Request(BASE+path,headers={'User-Agent':'MayhemResearch/0.2'}),timeout=45) as response:
            return response.read()
    config_bytes=public('config.json');config=json.loads(config_bytes)
    release=config['dataVersion']
    if not re.fullmatch(r'[0-9.]+',release):raise ValueError('Unexpected release identity')
    folder=OUT/release;folder.mkdir(exist_ok=True)
    manifest_path=folder/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {
        'base_url':BASE,'release':release,'game_patch':config['gamePatch'],
        'license':'Authenticated developer access; redistribution rights not established.',
        'credential_policy':'Credential received on stdin, used only in an Authorization header to data.dtodo.cn. Never persisted.',
        'files':{}}
    last_request=0
    remaining=None
    def fetch(remote,filename,cost=0,public_payload=None):
        nonlocal last_request,remaining
        target=folder/filename
        old=manifest['files'].get(filename)
        if public_payload is None and old and target.exists() and sha(target.read_bytes())==old['sha256']:
            return json.loads(target.read_text(encoding='utf-8')) if filename.endswith('.json') else target.read_text(encoding='utf-8')
        if remaining is not None and cost>remaining:raise RuntimeError('Insufficient remaining daily credits')
        time.sleep(max(0,1.25-(time.monotonic()-last_request)))
        headers={'User-Agent':'MayhemResearch/0.2','Accept-Encoding':'identity'}
        if cost:headers['Authorization']='Bearer '+key
        last_request=time.monotonic()
        if public_payload is None:
            try:
                with opener.open(Request(BASE+remote,headers=headers),timeout=60) as response:
                    payload=response.read()
                    credits={h:response.headers.get(h) for h in ('x-credits-cost','x-credits-used-today','x-credits-daily','x-credits-remaining')}
            except HTTPError as error:
                raise RuntimeError(f'HTTP {error.code} for {remote}; credential omitted') from None
        else:payload=public_payload;credits={}
        if key.encode() in payload:raise ValueError('Credential unexpectedly reflected in response; not saving it')
        if filename.endswith('.json'):json.loads(payload)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
        record={'url':BASE+remote,'collected_at':datetime.now(timezone.utc).isoformat(),
            'sha256':sha(payload),'bytes':len(payload),'credit_headers':credits,'advertised_cost':cost}
        manifest['files'][filename]=record;write(manifest_path,manifest)
        if credits.get('x-credits-remaining') is not None:remaining=int(credits['x-credits-remaining'])
        print(f'Saved {filename}: {len(payload)} bytes; credits remaining {remaining}',flush=True)
        return json.loads(payload) if filename.endswith('.json') else payload.decode('utf-8')
    fetch('config.json','config.json',public_payload=config_bytes)
    fetch('docs/cf-data-api.md','docs.md')
    jobs=[('augments.json','augments.json',1),('champions.json','champions.json',1),
          ('items.json','items.json',1),('champions/11.json','expanded/11.json',2),
          ('data/champion-augments/11.json','champions/11.json',1),
          ('data/augments-stats-raw.json','global-raw.json',1)]
    for remote,filename,cost in jobs:fetch(remote,filename,cost)
    if args.sync_champions:
        champions=json.loads((folder/'champions.json').read_text(encoding='utf-8'))['data']
        if not isinstance(champions,list):raise ValueError('Unexpected champion catalog shape')
        for index,champion in enumerate(champions,1):
            cid=int(champion['id'])
            fetch(f'data/champion-augments/{cid}.json',f'champions/{cid}.json',1)
            if index%20==0:print(f'Champion sync {index}/{len(champions)}',flush=True)
        manifest['champion_sync_complete']=True
        manifest['champion_count']=len(champions)
    final_config=json.loads(public('config.json'))
    if final_config['dataVersion']!=release:raise RuntimeError('Release changed during acquisition; do not publish this snapshot')
    manifest['release_rechecked_at']=datetime.now(timezone.utc).isoformat()
    manifest['last_known_credits_remaining']=remaining
    write(manifest_path,manifest)
    write(OUT/'current.json',{'release':release,'snapshot':release,'champion_sync_complete':manifest.get('champion_sync_complete',False)})
    print('Acquisition verified against final public release config; key was not persisted.',flush=True)


if __name__=='__main__':main()
