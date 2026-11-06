"""Bounded read-only collection of public Mayhem sources for comparison."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from inspect_public_pages import Page

ROOT = Path(__file__).parent / 'external-snapshots'
TARGETS = {
    'arammayhem-index':'https://arammayhem.com/data/v1/index.json',
    'arammayhem-augments-data':'https://arammayhem.com/data/v1/latest/augments.json',
    'arammayhem-augments':'https://arammayhem.com/augments/',
    'arammayhem-masteryi':'https://arammayhem.com/champions/master-yi/',
    'aramgg-augments':'https://aramgg.com/en/augments',
    'aramgg-config':'https://data.dtodo.cn/api/v1/en/config.json',
    'aramkit-augments':'https://aramkit.com/en-US/augments',
    'aramkit-home':'https://aramkit.com/en-US',
    'leagueofgraphs-augments':'https://www.leagueofgraphs.com/aram-mayhem/augments',
    'metasrc-augments':'https://www.metasrc.com/lol/mayhem/tier-list/augments',
}

def fetch(name,url):
    ROOT.mkdir(exist_ok=True)
    try:
        with urlopen(Request(url,headers={'User-Agent':'MayhemResearch/0.1','Accept-Encoding':'identity'}),timeout=30) as r:
            data=r.read()
            meta={'url':url,'final_url':r.url,'status':r.status,'bytes':len(data),
                  'collected_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(data).hexdigest()}
        ext='json' if data.lstrip().startswith((b'{',b'[')) else 'html'
        (ROOT/f'{name}.{ext}').write_bytes(data)
        if ext=='html':
            p=Page();p.feed(data.decode('utf-8'))
            (ROOT/f'{name}.text.txt').write_text('\n'.join(p.text),encoding='utf-8')
            (ROOT/f'{name}.scripts.json').write_text(json.dumps(p.scripts,ensure_ascii=False),encoding='utf-8')
        return meta
    except Exception as e:
        return {'url':url,'error':str(e)}

if __name__=='__main__':
    result={}
    for name,url in TARGETS.items():
        result[name]=fetch(name,url)
        print(name,json.dumps(result[name]),flush=True)
    (ROOT/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
