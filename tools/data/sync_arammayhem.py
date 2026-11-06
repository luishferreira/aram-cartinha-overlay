"""Download the publisher's index-listed datasets without scraping the website.

Snapshots are versioned by publisher generation time plus index hash. Existing
files are reused and checked; older releases are never overwritten.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PROJECT = Path(__file__).resolve().parents[2]
BASE = PROJECT / 'data' / 'sources' / 'arammayhem'
INDEX_URL = 'https://arammayhem.com/data/v1/index.json'
ATTRIBUTION = 'Data: arammayhem.com'

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def get(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'arammayhem.com':
        raise ValueError(f'Unexpected source origin: {url}')
    request = Request(url, headers={'User-Agent':'MayhemResearch/0.1', 'Accept-Encoding':'identity'})
    with urlopen(request, timeout=45) as response:
        if urlparse(response.url).hostname != 'arammayhem.com':
            raise ValueError('Unexpected redirect origin')
        data = response.read()
        return data, {'url':url, 'final_url':response.url, 'status':response.status,
                      'collected_at':now(), 'bytes':len(data), 'sha256':sha(data),
                      'content_type':response.headers.get('Content-Type')}

def parse(data, extension):
    text = data.decode('utf-8-sig')
    if extension == 'json':
        value = json.loads(text)
        if not isinstance(value, dict) or not isinstance(value.get('rows'), list):
            raise ValueError('Expected publisher JSON envelope with rows')
        return {'rows':len(value['rows']), 'schema_version':value.get('schemaVersion'),
                'meta':value.get('meta'), 'license':value.get('license')}
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError('Expected nonempty CSV data')
    return {'rows':len(rows), 'columns':list(rows[0])}

def jobs(index):
    for entity, formats in index['latest']['files'].items():
        for extension, url in formats.items():
            yield PurePosixPath('latest', f'{entity}.{extension}'), url, extension
    for patch in index.get('patches', []):
        if not re.fullmatch(r'\d{2}-\d{2}', patch['slug']):
            raise ValueError('Unexpected patch slug')
        for entity, formats in patch['files'].items():
            for extension, url in formats.items():
                yield PurePosixPath('history', patch['slug'], f'{entity}.{extension}'), url, extension

def verify(snapshot):
    manifest = json.loads((snapshot/'manifest.json').read_text('utf-8'))
    errors = []
    for entry in manifest['files']:
        p = snapshot/entry['path']
        if not p.is_file() or sha(p.read_bytes()) != entry['sha256']:
            errors.append(entry['path'])
    if errors:
        raise ValueError(f'Hash verification failed: {errors}')
    index = json.loads((snapshot/'index.json').read_text('utf-8'))
    expected = {str(path) for path,_,_ in jobs(index)}
    received = {e['path'] for e in manifest['files'] if e.get('kind') == 'dataset'}
    if expected != received:
        raise ValueError(f'Incomplete snapshot: missing={expected-received}, unexpected={received-expected}')
    by_path = {e['path']:e for e in manifest['files']}
    pairs = 0
    for path in sorted(expected):
        if path.endswith('.json') and path[:-5]+'.csv' in expected:
            if by_path[path]['rows'] != by_path[path[:-5]+'.csv']['rows']:
                raise ValueError(f'JSON/CSV row count mismatch: {path}')
            pairs += 1
    return {'snapshot':str(snapshot), 'files_verified':len(manifest['files']),
            'datasets_verified':len(expected), 'json_csv_pairs_verified':pairs}

def sync():
    data, index_meta = get(INDEX_URL)
    index = json.loads(data)
    stamp = re.sub(r'[^0-9TZ]', '', index['generatedAt'])
    snapshot = BASE/'snapshots'/f'{stamp}-{sha(data)[:12]}'
    snapshot.mkdir(parents=True, exist_ok=True)
    if (snapshot/'manifest.json').exists():
        result = verify(snapshot)
        (BASE/'current.json').write_text(json.dumps({'snapshot':snapshot.relative_to(BASE).as_posix(),
          'release_id':index['releaseId'],'index_sha256':sha(data)}, indent=2), encoding='utf-8')
        print(json.dumps(dict(result, reused=True), indent=2)); return
    (snapshot/'index.json').write_bytes(data)
    records = [dict(index_meta, path='index.json', kind='index')]
    todo = list(jobs(index))
    for number, (relative,url,extension) in enumerate(todo,1):
        if extension not in ('json','csv') or not re.fullmatch(r'[a-z]+\.(json|csv)', relative.name):
            raise ValueError(f'Unexpected file identity: {relative}')
        target = snapshot/str(relative)
        payload, metadata = get(url)
        metadata.update(parse(payload,extension))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        records.append(dict(metadata,path=str(relative),kind='dataset'))
        if number % 8 == 0 or number == len(todo):
            print(f'{number}/{len(todo)} datasets saved',flush=True)
        time.sleep(.15)
    for name,url in [('data-page.html','https://arammayhem.com/data/'),
                     ('ai-access-page.html','https://arammayhem.com/use-with-ai/')]:
        payload, metadata = get(url)
        (snapshot/name).write_bytes(payload)
        records.append(dict(metadata,path=name,kind='documentation'))
    license_data = index['license']
    (snapshot/'LICENSE.source.json').write_text(json.dumps(license_data,ensure_ascii=False,indent=2),encoding='utf-8')
    (snapshot/'ATTRIBUTION.md').write_text(
        '# Attribution\n\nData: [arammayhem.com](https://arammayhem.com/data/)\n\n'
        'Publisher datasets: Creative Commons Attribution 4.0.\n'
        'License: https://creativecommons.org/licenses/by/4.0/\n\n'
        'Raw files are unchanged. Derived catalogs, ID mappings and indexes are identified separately.\n'
        'The publisher declares a limited sample, not worldwide coverage.\n'
        'Historical dates marked estimated remain estimated.\n',encoding='utf-8')
    for name in ('LICENSE.source.json','ATTRIBUTION.md'):
        p=snapshot/name
        records.append({'path':name,'kind':'provenance','bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
    manifest={'publisher':'arammayhem.com','source_index':INDEX_URL,'release_id':index['releaseId'],
              'downloaded_at':now(),'patch':index['latestPatch'],'files':records}
    (snapshot/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    result=verify(snapshot)
    (BASE/'current.json').write_text(json.dumps({'snapshot':snapshot.relative_to(BASE).as_posix(),
      'release_id':index['releaseId'],'index_sha256':sha(data)},indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true',help='Verify current snapshot offline; no network')
    args=parser.parse_args()
    if args.verify:
        pointer=json.loads((BASE/'current.json').read_text('utf-8'))
        print(json.dumps(verify(BASE/pointer['snapshot']),indent=2))
    else:
        sync()
