"""Read-only public item-source research; isolated snapshots, no active data writes."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/item-sources/2026-11-06'
HOSTS = {'arammayhem.com', 'mayhemstats.com', 'op.gg', 'lol-api-champion.op.gg', 'lemonnation.gg',
         'lmzenzxbhotszvwsnhlm.supabase.co', 'api.github.com', 'raw.githubusercontent.com'}

def now():
    return datetime.now(timezone.utc).isoformat()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    tmp.replace(path)

class Archive:
    def __init__(self, out=OUT):
        self.out = out
        self.path = out / 'manifest.json'
        self.manifest = json.loads(self.path.read_text('utf8')) if self.path.exists() else {
            'started_at': now(), 'purpose': 'Item reference research, not active overlay data',
            'records': {}, 'errors': []}
        self.last = 0

    def get(self, url, headers=None):
        if urlparse(url).scheme != 'https' or urlparse(url).hostname not in HOSTS:
            raise ValueError('Unexpected source origin')
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.out / 'raw' / (key + '.bin')
        saved = self.manifest['records'].get(url)
        if saved and path.exists():
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != saved['sha256']:
                raise ValueError('Archived source hash mismatch')
            return raw
        time.sleep(max(0, 1.15 - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        req = Request(url, headers={'User-Agent': 'MayhemResearch/0.3', 'Accept-Encoding': 'identity', **(headers or {})})
        try:
            with urlopen(req, timeout=35) as response:
                raw = response.read()
                meta = dict(url=url, final_url=response.url, status=response.status,
                            content_type=response.headers.get('Content-Type'), content_range=response.headers.get('Content-Range'), collected_at=now(),
                            sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), file=str(path.relative_to(self.out)))
            if urlparse(meta['final_url']).hostname not in HOSTS:
                raise ValueError('Unexpected redirect origin')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.manifest['records'][url] = meta
            write(self.path, self.manifest)
            return raw
        except Exception as error:
            self.manifest['errors'].append(dict(url=url, at=now(), error=str(error)))
            write(self.path, self.manifest)
            raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('urls', nargs='*')
    parser.add_argument('--list', type=Path)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    urls = args.urls + (json.loads(args.list.read_text('utf8')) if args.list else [])
    archive = Archive(args.output)
    for i, url in enumerate(dict.fromkeys(urls), 1):
        try:
            raw = archive.get(url)
            print(f'{i}/{len(urls)} {url} {len(raw)} bytes', flush=True)
        except HTTPError as error:
            print(f'{i}/{len(urls)} HTTP {error.code}: {url}', flush=True)
            if error.code == 429:
                print('Rate limited; stopped. Resume later from archive.', flush=True)
                break
        except Exception as error:
            print(f'{i}/{len(urls)} {type(error).__name__}: {url}', flush=True)

if __name__ == '__main__':
    main()
