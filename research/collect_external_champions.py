"""Collect publicly linked champion pages; no protected API access."""
import hashlib,json,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from html_tree import Tree

ROOT=Path(__file__).parent
OUT=ROOT/'external-champions'

def collect(job):
    source,cid,url=job
    dest=OUT/f'{source}-{cid}.html'
    meta={'source':source,'champion_id':cid,'url':url}
    if dest.exists():return dict(meta,status=200,reused=True)
    try:
        with urlopen(Request(url,headers={'User-Agent':'MayhemResearch/0.1','Accept-Encoding':'identity'}),timeout=30) as r:
            data=r.read();meta.update(status=r.status,final_url=r.url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),collected_at=datetime.now(timezone.utc).isoformat())
        dest.write_bytes(data)
    except Exception as e:meta['error']=str(e)
    (OUT/f'{source}-{cid}.meta.json').write_text(json.dumps(meta),encoding='utf-8')
    time.sleep(.2)
    return meta

def main():
    OUT.mkdir(exist_ok=True)
    catalog=json.loads((ROOT/'champion-snapshots/champion-catalog.json').read_text('utf-8'))['champions']
    ids={c['key']:c['id'] for c in catalog}
    tree=Tree((ROOT/'external-snapshots/aramgg-home.html').read_text('utf-8')).root
    routes={a.attrs['href'] for a in tree.find('a') if a.attrs.get('href','').startswith('/en/champion-stats/')}
    jobs=[('aramgg',int(route.rstrip('/').split('/')[-1]),'https://aramgg.com'+route) for route in sorted(routes)]
    rows=json.loads((ROOT/'external-snapshots/arammayhem-champions-data.json').read_text('utf-8'))['rows']
    jobs += [('arammayhem',ids[r['championId']],r['url']) for r in rows if r['championId'] in ids]
    result=[]
    print('Jobs',len(jobs),flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(collect,j) for j in jobs]
        for f in as_completed(futures):
            result.append(f.result())
            if len(result)%40==0:print(len(result),'/',len(jobs),'errors',sum('error' in r for r in result),flush=True)
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Completed',len(result),'errors',sum('error' in r for r in result),flush=True)

if __name__=='__main__':main()
