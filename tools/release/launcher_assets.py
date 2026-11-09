"""Collect Riot portraits once; offline builds verify and bundle the pinned files."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import zipfile

from tools.app_paths import app_root
from tools.items.static_sets import encode


def sha(data):
    return hashlib.sha256(data).hexdigest()


def collect_spells(root,version):
    """Add the official, localized spell icons to the pinned launcher assets."""
    from PIL import Image
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid asset version')
    folder=root/'research/launcher-assets'/version
    pointer=json.loads((folder.parent/'current.json').read_text('utf8'))
    raw_manifest=(folder/'manifest.json').read_bytes()
    if pointer['version']!=version or sha(raw_manifest)!=pointer['manifest_sha256']:
        raise ValueError('Launcher asset manifest changed')
    manifest=json.loads(raw_manifest)
    def fetch(url):
        with urllib.request.urlopen(url,timeout=25) as response:
            if not response.url.startswith('https://ddragon.leagueoflegends.com/'):
                raise ValueError('Unexpected Riot asset redirect')
            data=response.read(2*1024*1024+1)
            if len(data)>2*1024*1024:raise ValueError('Riot asset exceeds size limit')
            return data
    url=f'https://ddragon.leagueoflegends.com/cdn/{version}/data/pt_BR/summoner.json'
    raw=fetch(url)
    spells={}
    for spell in json.loads(raw)['data'].values():
        ident=str(int(spell['key']));name=spell['image']['full']
        if not re.fullmatch(r'[A-Za-z0-9_]+\.png',name):raise ValueError('Invalid spell filename')
        image_url=f'https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{name}'
        path=folder/f'spell-{ident}.png'
        data=path.read_bytes() if path.exists() else fetch(image_url)
        with Image.open(io.BytesIO(data)) as image:
            if image.format!='PNG' or image.width!=image.height or not 32<=image.width<=512:
                raise ValueError('Unexpected Riot spell icon')
            image.verify()
        path.write_bytes(data)
        spells[ident]={'name':spell['name'],'file':path.name,'url':image_url,'sha256':sha(data),'bytes':len(data)}
    (folder/'summoner.json').write_bytes(raw)
    manifest.update(spells=spells,spells_source_url=url,spells_source_sha256=sha(raw))
    encoded=encode(manifest)
    (folder/'manifest.json').write_bytes(encoded)
    (folder.parent/'current.json').write_bytes(encode({'version':version,'manifest_sha256':sha(encoded)}))
    return {'version':version,'spells':len(spells)}


def collect(root,version):
    from PIL import Image
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Invalid asset version')
    folder=root/'research/launcher-assets'/version
    folder.mkdir(parents=True,exist_ok=True)
    catalog=root/'research/champion-snapshots/champion-catalog.json'
    champions=json.loads(catalog.read_text('utf8'))['champions']
    def fetch(url):
        request=urllib.request.Request(url,headers={'User-Agent':'AramCartinhaOverlay asset collector'})
        with urllib.request.urlopen(request,timeout=25) as response:
            if not response.url.startswith('https://ddragon.leagueoflegends.com/'):
                raise ValueError('Unexpected Riot asset redirect')
            data=response.read(2*1024*1024)
            return data
    url=f'https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json'
    raw=fetch(url)
    source={int(c['key']):c for c in json.loads(raw)['data'].values()}
    (folder/'champion.json').write_bytes(raw)
    def one(champion):
        ident=champion['id'];name=source[ident]['image']['full']
        if not re.fullmatch(r'[A-Za-z0-9]+\.png',name):raise ValueError('Invalid portrait filename')
        image_url=f'https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{name}'
        path=folder/f'{ident}.png'
        data=path.read_bytes() if path.exists() else fetch(image_url)
        with Image.open(io.BytesIO(data)) as image:
            if image.format!='PNG' or image.width!=image.height or not 64<=image.width<=512:
                raise ValueError('Unexpected Riot portrait')
            image.verify()
        path.write_bytes(data)
        return str(ident),{'url':image_url,'file':path.name,'sha256':sha(data),'bytes':len(data)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        portraits=dict(pool.map(one,champions))
    manifest={'schema_version':1,'version':version,'catalog_sha256':sha(catalog.read_bytes()),
              'source_url':url,'source_sha256':sha(raw),'portraits':portraits}
    (folder/'manifest.json').write_bytes(encode(manifest))
    (folder.parent/'current.json').write_bytes(encode({'version':version,'manifest_sha256':sha(encode(manifest))}))
    return {'version':version,'portraits':len(portraits)}


def archive(root,destination):
    pointer=json.loads((root/'research/launcher-assets/current.json').read_text('utf8'))
    if not re.fullmatch(r'\d+\.\d+\.\d+',pointer['version']):raise ValueError('Invalid asset pointer')
    folder=root/'research/launcher-assets'/pointer['version']
    raw=(folder/'manifest.json').read_bytes()
    if sha(raw)!=pointer['manifest_sha256']:raise ValueError('Portrait manifest changed')
    manifest=json.loads(raw)
    catalog=root/'research/champion-snapshots/champion-catalog.json'
    if sha(catalog.read_bytes())!=manifest['catalog_sha256']:raise ValueError('Champion catalog changed')
    ids={str(c['id']) for c in json.loads(catalog.read_text('utf8'))['champions']}
    if ids!=set(manifest['portraits']):raise ValueError('Incomplete portrait coverage')
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_STORED) as zipped:
        entries={'manifest.json':raw}
        for ident in sorted(ids,key=int):
            entry=manifest['portraits'][ident]
            if entry['file']!=f'{ident}.png':raise ValueError('Invalid portrait path')
            data=(folder/entry['file']).read_bytes()
            if sha(data)!=entry['sha256']:raise ValueError('Portrait changed: '+ident)
            entries[f'{ident}.png']=data
        for ident,entry in sorted(manifest.get('spells',{}).items(),key=lambda item:int(item[0])):
            if entry['file']!=f'spell-{int(ident)}.png':raise ValueError('Invalid spell path')
            data=(folder/entry['file']).read_bytes()
            if sha(data)!=entry['sha256']:raise ValueError('Spell icon changed: '+ident)
            entries[entry['file']]=data
        for name,data in entries.items():
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.external_attr=0o644<<16
            zipped.writestr(info,data)
    return manifest


def verify_archive(root,path):
    pointer=json.loads((root/'research/launcher-assets/current.json').read_text('utf8'))
    folder=root/'research/launcher-assets'/pointer['version']
    raw=(folder/'manifest.json').read_bytes()
    if sha(raw)!=pointer['manifest_sha256']:raise ValueError('Portrait source manifest changed')
    manifest=json.loads(raw)
    with zipfile.ZipFile(path) as zipped:
        if zipped.read('manifest.json')!=raw:raise ValueError('Bundled portrait origins differ')
        expected={'manifest.json'}|{f'{ident}.png' for ident in manifest['portraits']}
        expected|={f'spell-{int(ident)}.png' for ident in manifest.get('spells',{})}
        if len(zipped.namelist())!=len(expected) or set(zipped.namelist())!=expected:
            raise ValueError('Incomplete portrait archive')
        for ident,entry in manifest['portraits'].items():
            if sha(zipped.read(f'{ident}.png'))!=entry['sha256']:
                raise ValueError('Bundled portrait changed: '+ident)
        for ident,entry in manifest.get('spells',{}).items():
            if sha(zipped.read(f'spell-{int(ident)}.png'))!=entry['sha256']:
                raise ValueError('Bundled spell changed: '+ident)
    return len(manifest['portraits'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['collect','spells']);parser.add_argument('--version',required=True)
    args=parser.parse_args()
    print(json.dumps((collect_spells if args.command=='spells' else collect)(app_root(),args.version)))
