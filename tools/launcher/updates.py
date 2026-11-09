"""Explicit GitHub release updates; verified downloads, no silent replacement of the app."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import urllib.parse
import urllib.request

from tools.app_paths import local_root
from tools.version import APP_VERSION

REPOSITORY = 'luishferreira/aram-cartinha-overlay'
RELEASES = f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=30'
HOSTS = {'api.github.com','github.com','release-assets.githubusercontent.com',
         'objects.githubusercontent.com','github-releases.githubusercontent.com'}
IDLE_PHASES = {'None','Lobby','EndOfGame','ClientClosed'}


def version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?',value or '')
    if not match:
        raise ValueError('Unsupported release version')
    major,minor,patch,stage,number = match.groups()
    return (int(major),int(minor),int(patch),{'alpha':0,'beta':1,'rc':2,None:3}[stage],int(number or 0))


def checked_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port:
        raise ValueError('Unexpected update download host')
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        checked_url(newurl)
        return super().redirect_request(request,fp,code,msg,headers,newurl)


def fetch(url,limit):
    request = urllib.request.Request(checked_url(url),headers={'User-Agent':'AramCartinhaOverlay/'+APP_VERSION,
                                                             'Accept':'application/vnd.github+json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),SafeRedirect())
    with opener.open(request,timeout=20) as response:
        checked_url(response.url)
        data = response.read(limit+1)
        if len(data)>limit:
            raise ValueError('Update response exceeds size limit')
        return data


def select_release(releases,current=APP_VERSION):
    candidates = []
    for release in releases:
        if release.get('draft'):
            continue
        try:
            key = version(release.get('tag_name'))
        except ValueError:
            continue
        if key<=version(current):
            continue
        tag = release['tag_name']
        expected = f'AramCartinhaOverlay-{tag.removeprefix("v")}-Setup-x64.exe'
        assets = {a['name']:a for a in release.get('assets',[])}
        if expected not in assets or 'SHA256SUMS.txt' not in assets:
            continue
        urls = {}
        for label,name in [('setup',expected),('checksums','SHA256SUMS.txt')]:
            url = assets[name]['browser_download_url']
            checked_url(url)
            if url!=f'https://github.com/{REPOSITORY}/releases/download/{tag}/{name}':
                raise ValueError('Update asset is outside the configured repository')
            urls[label] = url
        candidates.append((key,{'tag':tag,'name':expected,'notes':str(release.get('body') or '')[:4000],
                                'url':f'https://github.com/{REPOSITORY}/releases/tag/{tag}',**urls}))
    return max(candidates,key=lambda c:c[0])[1] if candidates else None


def download(release,folder):
    sums = fetch(release['checksums'],1024*1024).decode('utf8')
    matches = re.findall(r'^([a-fA-F0-9]{64})\s+\*?'+re.escape(release['name'])+r'\s*$',sums,re.M)
    if len(matches)!=1:
        raise ValueError('Installer checksum is missing or ambiguous')
    payload = fetch(release['setup'],150*1024*1024)
    if hashlib.sha256(payload).hexdigest()!=matches[0].lower() or not payload.startswith(b'MZ'):
        raise ValueError('Installer failed integrity verification')
    folder = Path(folder);folder.mkdir(parents=True,exist_ok=True)
    path = folder/release['name']
    temporary = path.with_suffix('.tmp');temporary.write_bytes(payload);temporary.replace(path)
    return path,matches[0].lower()


def may_install(phase,game_running):
    return not game_running and phase in IDLE_PHASES


def install_after_exit(setup,expected_hash,executable):
    from tools.system_process import run
    from tools.items.lcu import Lcu,ClientUnavailable
    # A disconnected LCU cannot establish that an active match has ended.
    tasklist = str(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/tasklist.exe')
    result = run([tasklist,'/FI','IMAGENAME eq League of Legends.exe','/FO','CSV','/NH'],
                 capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Não foi possível verificar se há uma partida aberta.')
    try:
        phase=Lcu().request('GET','/lol-gameflow/v1/gameflow-phase')
    except ClientUnavailable:
        clients=run([tasklist,'/FI','IMAGENAME eq LeagueClientUx.exe','/FO','CSV','/NH'],
                    capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        phase='ClientClosed' if clients.returncode==0 and 'leagueclientux.exe' not in clients.stdout.lower() else None
    if not may_install(phase,'league of legends.exe' in result.stdout.lower()):
        raise RuntimeError('Instale fora de seleção ou partida.')
    setup,executable = Path(setup).resolve(),Path(executable).resolve()
    if hashlib.sha256(setup.read_bytes()).hexdigest()!=expected_hash:
        raise ValueError('Downloaded installer changed')
    def quote(value):
        return "'"+str(value).replace("'","''")+"'"
    folder = local_root()/'updates';folder.mkdir(parents=True,exist_ok=True)
    script = folder/'install-after-exit.ps1'
    # Fixed commands and quoted paths only. Inno's standard GUI remains visible for the user.
    script.write_text(f"$ErrorActionPreference = 'Stop'\n"
        f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue\n"
        f"$setup = Start-Process -FilePath {quote(setup)} -ArgumentList '/NORESTART' -PassThru -Wait\n"
        f"Start-Process -FilePath {quote(executable)} -WindowStyle Hidden\n",encoding='utf-8-sig')
    powershell = str(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe')
    return subprocess.Popen([powershell,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)],
                            creationflags=subprocess.CREATE_NO_WINDOW,close_fds=True)


class UpdateService:
    def __init__(self,root,*,demo=False):
        self.root,self.demo = Path(root),demo
        self.lock = threading.Lock()
        self.value = {'state':'idle','message':''}
        self.busy = False

    def snapshot(self):
        with self.lock:
            return dict(self.value)

    def task(self,action):
        with self.lock:
            if self.busy or self.demo:
                return
            self.busy = True
            previous = dict(self.value)
            self.value = {**previous,'state':'busy','message':'Verificando versões…' if action=='check' else 'Baixando e verificando…'}
        def work():
            try:
                if action=='check':
                    release = select_release(json.loads(fetch(RELEASES,3*1024*1024)))
                    value = {'state':'available' if release else 'current','release':release,
                             'message':f'{release["tag"]} disponível' if release else 'Você está na versão mais recente.'}
                else:
                    release = previous['release']
                    path,checksum = download(release,local_root(self.root)/'updates')
                    value = {'state':'downloaded','release':release,'path':str(path),'sha256':checksum,
                             'message':'Atualização pronta para instalar.'}
            except Exception as error:
                value = {**previous,'state':'error','message':'Falha ao buscar atualização.' if action=='check' else 'Falha no download.',
                         'retry_action':action,'error_type':type(error).__name__}
            with self.lock:
                self.value,self.busy = value,False
        threading.Thread(target=work,daemon=True,name='mayhem-updates').start()
