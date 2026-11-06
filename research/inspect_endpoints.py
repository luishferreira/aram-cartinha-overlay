"""Snapshot public data routes observed in Mayhem pages/app code; no credentials."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent / 'public-snapshots'
TARGETS = {
    'blitz-champions-bulk-probe': 'https://data.v2.iesdev.com/api/v1/query_objects/prod/lol/aram_mayhem_champion',
    'opgg-augments-ptbr': 'https://lol-api-champion.op.gg/api/meta/aram-augments?hl=pt_BR',
    'opgg-masteryi-stats': 'https://lol-api-champion.op.gg/api/contents/stats/champions/11/aram-augments',
}

def shape(value):
    if isinstance(value, dict):
        return {k: shape(v) for k, v in list(value.items())[:12]}
    if isinstance(value, list):
        return {'length': len(value), 'first_shape': shape(value[0]) if value else None}
    return type(value).__name__

def main():
    summary = {}
    for name, url in TARGETS.items():
        try:
            with urlopen(Request(url, headers={'User-Agent': 'MayhemResearch/0.1', 'Accept-Encoding': 'identity'}), timeout=40) as response:
                data = response.read()
                meta = {'url': url, 'final_url': response.url, 'status': response.status,
                        'collected_at': datetime.now(timezone.utc).isoformat(),
                        'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
            parsed = json.loads(data)
            (ROOT / f'{name}.json').write_bytes(data)
            meta['shape'] = shape(parsed)
            summary[name] = meta
        except Exception as error:
            summary[name] = {'url': url, 'error': str(error)}
    (ROOT / 'endpoint-manifest.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
