"""Read-only MCP research: complete champion tiers and diverse schema probes.

The examples probe data semantics; they do not limit future champion coverage.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from inspect_arammayhem_mcp import decode, URL

OUT = Path(__file__).parent / 'arammayhem-mcp/complement-2026-10-30'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({'Accept': 'application/json, text/event-stream',
                            'Content-Type': 'application/json'})
    init = session.post(URL, json={'jsonrpc':'2.0','id':1,'method':'initialize',
        'params':{'protocolVersion':'2025-03-26','capabilities':{},
                  'clientInfo':{'name':'mayhem-complement-research','version':'0.1'}}}, timeout=40)
    decode(init)
    if init.headers.get('Mcp-Session-Id'):
        session.headers['Mcp-Session-Id'] = init.headers['Mcp-Session-Id']
    session.post(URL,json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=40).raise_for_status()
    probes = [(f'tiers-{offset}', 'get_tier_list', {'limit':30,'offset':offset})
              for offset in range(0,180,30)]
    probes += [(f'combos-{champ}', 'get_top_combos', {'champion':champ,'limit':30})
               for champ in ['Brand','MasterYi','Ashe','Ahri','Lulu','Gangplank','Nautilus','Xayah']]
    probes += [(f'build-{champ}', 'get_champion_build', {'champion':champ})
               for champ in ['Brand','MasterYi','Ashe','Lulu','Nautilus']]
    probes += [(f'augment-{aug}', 'get_augment', {'augment':aug})
               for aug in ['mystic_punch','marksmage','dropkick','cerberus','clown_college','bees']]
    probes += [('search-haste','search',{'query':'ability haste','limit':30}),
               ('patch-latest','get_patch_notes',{})]
    records=[]
    for number,(label,name,args) in enumerate(probes,2):
        args['locale']='en'
        response=session.post(URL,json={'jsonrpc':'2.0','id':number,'method':'tools/call',
            'params':{'name':name,'arguments':args}},timeout=40)
        result=decode(response)
        payload=json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8')
        (OUT/f'{label}.json').write_bytes(payload)
        records.append({'file':f'{label}.json','tool':name,'arguments':args,
            'collectedAt':datetime.now(timezone.utc).isoformat(),
            'sha256':hashlib.sha256(payload).hexdigest(),'httpStatus':response.status_code,
            'isError':result.get('result',{}).get('isError',False),'rpcError':result.get('error')})
        print(f'{number-1}/{len(probes)} {label}',flush=True)
        time.sleep(1.15)
    (OUT/'manifest.json').write_text(json.dumps({'endpoint':URL,'scope':'Read-only research probes; not a complete combo/build/augment collection.',
        'reuseStatus':'Download CC BY license not assumed to cover these responses.',
        'files':records},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
