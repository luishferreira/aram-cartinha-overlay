"""Fresh, bounded MCP build checks; never republish the active data snapshot."""
import hashlib
import json
import time
import requests
from audit_item_sources import OUT, now, write
from inspect_arammayhem_mcp import decode

def main():
    out = OUT / 'mcp-build-probes'
    if (out / 'manifest.json').exists():
        saved = json.loads((out / 'manifest.json').read_text('utf8'))['records']
        if len(saved) == 3:
            for row in saved:
                if hashlib.sha256((out / row['file']).read_bytes()).hexdigest() != row['sha256']:
                    raise ValueError('Archived MCP evidence hash mismatch')
            print('Existing complete MCP probe verified; preserved without new requests.')
            return
    endpoint = 'https://arammayhem.com/mcp'
    session = requests.Session()
    session.headers.update({'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'})
    response = session.post(endpoint, json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
        'params': {'protocolVersion': '2025-03-26', 'capabilities': {},
                   'clientInfo': {'name': 'item-source-audit', 'version': '1'}}}, timeout=35)
    write(out / 'initialize.json', decode(response))
    if response.headers.get('Mcp-Session-Id'):
        session.headers['Mcp-Session-Id'] = response.headers['Mcp-Session-Id']
    session.post(endpoint, json={'jsonrpc': '2.0', 'method': 'notifications/initialized'}, timeout=35).raise_for_status()
    records = []
    for i, champion in enumerate(['MasterYi', 'Brand', 'Lulu'], 2):
        time.sleep(1.2)
        arguments = {'champion': champion, 'locale': 'en'}
        response = session.post(endpoint, json={'jsonrpc': '2.0', 'id': i, 'method': 'tools/call',
            'params': {'name': 'get_champion_build', 'arguments': arguments}}, timeout=35)
        result = decode(response)
        file = champion + '.json'
        write(out / file, result)
        records.append({'file': file, 'tool': 'get_champion_build', 'arguments': arguments,
                        'collected_at': now(), 'sha256': hashlib.sha256((out / file).read_bytes()).hexdigest()})
        write(out / 'manifest.json', {'endpoint': endpoint, 'records': records})
        print(champion, 'archived', flush=True)

if __name__ == '__main__':
    main()
