"""Inspect the site's documented public read-only MCP without installing it."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import requests

OUT=Path(__file__).parent/'arammayhem-mcp'
URL='https://arammayhem.com/mcp'

def decode(response):
    response.raise_for_status()
    if not response.content:return None
    try:return response.json()
    except ValueError:
        values=[]
        for line in response.text.splitlines():
            if line.startswith('data: '):values.append(json.loads(line[6:]))
        if len(values)!=1:raise ValueError('Unexpected SSE response framing')
        return values[0]

def main():
    OUT.mkdir(exist_ok=True)
    session=requests.Session()
    session.headers.update({'Accept':'application/json, text/event-stream','Content-Type':'application/json','User-Agent':'MayhemResearch/0.1'})
    response=session.post(URL,json={'jsonrpc':'2.0','id':1,'method':'initialize',
        'params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'mayhem-local-research','version':'0.1'}}},timeout=30)
    init=decode(response)
    if response.headers.get('Mcp-Session-Id'):session.headers['Mcp-Session-Id']=response.headers['Mcp-Session-Id']
    (OUT/'initialize.json').write_text(json.dumps(init,ensure_ascii=False,indent=2),encoding='utf-8')
    response=session.post(URL,json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=30)
    response.raise_for_status()
    result=decode(session.post(URL,json={'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},timeout=30))
    (OUT/'tools.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for request_id, name, arguments in [
        (3, 'get_champion_build', {'champion':'Teemo','locale':'en'}),
        (4, 'get_top_combos', {'champion':'Teemo','locale':'en','limit':30}),
    ]:
        sample=decode(session.post(URL,json={'jsonrpc':'2.0','id':request_id,'method':'tools/call',
            'params':{'name':name,'arguments':arguments}},timeout=30))
        (OUT/f'{name}-teemo.json').write_text(json.dumps(sample,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'provenance.json').write_text(json.dumps({'url':URL,'collected_at':datetime.now(timezone.utc).isoformat(),
      'scope':'Public read-only discovery. No client configuration changes. No credentials.',
      'reuse_status':'Research reference. Download dataset CC BY scope is not assumed to cover all MCP responses.'},indent=2),encoding='utf-8')
    print('Saved tool discovery and two Teemo samples. No application configuration changed.')

if __name__=='__main__':main()
