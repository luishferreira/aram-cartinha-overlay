"""Research snapshot for every champion in the local OP.GG game catalog.

Two concurrent public GETs, no account/cookies, no retries or access bypass.
Existing successful snapshots are reused; this is not an application service.
"""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
OUT = ROOT / 'champion-snapshots'
CATALOG = Path(r'C:\Users\Keita\AppData\Roaming\opgg-electron-app\file-cache\lol_meta_champions_pt_BR')

def collect(source, champion):
    cid = champion['id']
    path = OUT / f'{source}-{cid}.json'
    if path.exists():
        previous = json.loads(path.read_text('utf-8'))
        if previous.get('status') == 200:
            return {'source': source, 'champion_id': cid, 'status': 200, 'reused': True}
    url = (f'https://data.v2.iesdev.com/api/v1/query_objects/prod/lol/aram_mayhem_champion?champion_id={cid}'
           if source == 'blitz' else
           f'https://lol-api-champion.op.gg/api/contents/stats/champions/{cid}/aram-augments')
    result = {'source': source, 'champion_id': cid, 'champion_key': champion['key'],
              'url': url, 'collected_at': datetime.now(timezone.utc).isoformat()}
    try:
        with urlopen(Request(url, headers={'User-Agent': 'MayhemResearch/0.1', 'Accept-Encoding': 'identity'}), timeout=25) as response:
            data = response.read()
            result.update(status=response.status, sha256=hashlib.sha256(data).hexdigest(),
                          payload=json.loads(data))
    except Exception as error:
        result['error'] = str(error)
    path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    time.sleep(0.2)
    return {k:v for k,v in result.items() if k not in ('payload','sha256','url')}

def main():
    OUT.mkdir(exist_ok=True)
    data = json.loads(CATALOG.read_text('utf-8'))['data']
    # The catalog also includes Jade_* variants for another mode. Exclude those
    # observed variants rather than treating them as Mayhem champions.
    champions = [{k:c[k] for k in ('id','key','name')} for c in data['data'] if not c['key'].startswith('Jade_')]
    (OUT / 'champion-catalog.json').write_text(json.dumps({'meta': data.get('meta'), 'champions': champions}, ensure_ascii=False), encoding='utf-8')
    results = []
    print(f'Catalog: {len(champions)} champions; {len(champions)*2} bounded GETs', flush=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = [executor.submit(collect, source, c) for c in champions for source in ('blitz','opgg')]
        for job in as_completed(jobs):
            results.append(job.result())
            if len(results) % 40 == 0:
                print(f'{len(results)}/{len(jobs)} collected; errors: {sum(bool(r.get("error")) for r in results)}', flush=True)
    summary = {'collected_at': datetime.now(timezone.utc).isoformat(), 'champion_count':len(champions),
               'results':results}
    (OUT / 'manifest.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'champions':len(champions), 'responses':len(results), 'errors':sum(bool(r.get('error')) for r in results)}), flush=True)

if __name__ == '__main__':
    main()
