"""Read-only research collection of explicitly selected public Mayhem pages."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
TARGETS = {
    'blitz-general': 'https://blitz.gg/lol/aram-mayhem-augments',
    'blitz-masteryi': 'https://blitz.gg/lol/champions/MasterYi/aram-mayhem',
    'opgg-masteryi': 'https://op.gg/lol/modes/aram-mayhem/masteryi/augments',
}

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.active = None
        self.text = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script':
            self.active = {'attrs': a, 'body': ''}
        if tag in ('script', 'style'):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag == 'script' and self.active is not None:
            self.scripts.append(self.active)
            self.active = None
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
    def handle_data(self, data):
        if self.active is not None:
            self.active['body'] += data
        if not self.skip and data.strip():
            self.text.append(data.strip())

def main():
    out = ROOT / 'public-snapshots'
    out.mkdir(exist_ok=True)
    summary = {}
    for name, url in TARGETS.items():
        try:
            with urlopen(Request(url, headers={'User-Agent': 'MayhemResearch/0.1', 'Accept-Encoding': 'identity'}), timeout=40) as response:
                data = response.read()
                meta = {'url': url, 'final_url': response.url, 'status': response.status,
                        'collected_at': datetime.now(timezone.utc).isoformat(),
                        'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
            (out / f'{name}.html').write_bytes(data)
            page = Page()
            page.feed(data.decode('utf-8'))
            (out / f'{name}.text.txt').write_text('\n'.join(page.text), encoding='utf-8')
            (out / f'{name}.scripts.json').write_text(json.dumps(page.scripts, ensure_ascii=False), encoding='utf-8')
            meta['scripts'] = [{'attrs': x['attrs'], 'chars': len(x['body'])} for x in page.scripts]
            summary[name] = meta
        except Exception as error:
            summary[name] = {'url': url, 'error': str(error)}
    (out / 'manifest.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({name: {k:v for k,v in meta.items() if k != 'scripts'} for name,meta in summary.items()}, indent=2))

if __name__ == '__main__':
    main()
