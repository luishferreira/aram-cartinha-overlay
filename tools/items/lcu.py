"""Local League client transport. Session credentials remain only in memory."""
import base64
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import urllib.error
import urllib.request
from tools.system_process import run as run_system


class ClientUnavailable(RuntimeError):
    pass


class LcuError(RuntimeError):
    def __init__(self, status, *, method=None, path=None, request_bytes=None, item_sets=None):
        self.status = status
        self.method = method
        self.path = re.sub(r'(/lol-item-sets/v1/item-sets/)\d+', r'\1{summonerId}', path) if path else None
        self.request_bytes = request_bytes
        self.item_sets = item_sets
        detail = f" [{method} {self.path}; request_bytes={request_bytes}; item_sets={item_sets}]" if method else ""
        super().__init__(f"LCU request failed ({status})"+detail)


@dataclass(repr=False)
class Connection:
    port: int
    token: str = field(repr=False)

    def __repr__(self):
        return "Connection(localhost, credentials hidden)"


def discover():
    # Query process metadata, not game memory. Never print the command line.
    command = "Get-CimInstance Win32_Process -Filter \"name='LeagueClientUx.exe'\" | Select-Object CommandLine,ExecutablePath | ConvertTo-Json -Compress"
    try:
        executable = Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
        result = run_system([str(executable), "-NoProfile", "-Command", command],
                                capture_output=True, encoding="utf-8", errors="replace", timeout=8,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        rows = json.loads(result.stdout.lstrip("\ufeff") or "[]")
        rows = [rows] if isinstance(rows, dict) else rows
        for row in rows:
            line = row.get("CommandLine") or ""
            port = re.search(r'--app-port[= ]([0-9]+)', line)
            token = re.search(r'--remoting-auth-token[= ]([^\s"]+)', line)
            if port and token and 0<int(port[1])<65536:
                return Connection(int(port[1]), token[1])
            executable = row.get("ExecutablePath")
            if executable:
                lock = Path(executable).parent/"lockfile"
                if lock.exists():
                    parts = lock.read_text(encoding="utf-8").strip().split(":")
                    if len(parts)==5 and parts[4]=="https" and 0<int(parts[2])<65536:
                        return Connection(int(parts[2]), parts[3])
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    raise ClientUnavailable("Cliente do LoL indisponível; abra e faça login.")


class Lcu:
    def __init__(self, connection=None):
        self.connection = connection or discover()
        # The self-signed certificate exception is restricted to localhost; do
        # not route authenticated local requests through system HTTP proxies.
        context = ssl._create_unverified_context()
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, message, headers, url):
                return None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                                  urllib.request.HTTPSHandler(context=context))

    def request(self, method, path, body=None):
        if not path.startswith("/") or ".." in path or "?" in path or "#" in path:
            raise ValueError("Invalid local endpoint")
        auth = base64.b64encode(("riot:"+self.connection.token).encode()).decode()
        # The endpoint replaces the whole collection, including other apps' sets.
        # Compact UTF-8 reduces wire size while preserving every field and set.
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8') if body is not None else None
        request = urllib.request.Request(f"https://127.0.0.1:{self.connection.port}{path}",
                                         data=data,
                                         headers={"Authorization":"Basic "+auth, "Content-Type":"application/json"},
                                         method=method)
        try:
            with self.opener.open(request, timeout=4) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            sets = body.get('itemSets') if isinstance(body, dict) else None
            raise LcuError(error.code, method=method, path=path, request_bytes=len(data) if data is not None else 0,
                           item_sets=len(sets) if isinstance(sets, list) else None) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ClientUnavailable("A conexão local do LoL foi encerrada.") from None

    def account(self):
        account = self.request("GET", "/lol-summoner/v1/current-summoner")
        sid = account.get("summonerId")
        if not str(sid).isdigit() or int(sid)<=0:
            raise ClientUnavailable("Cliente aberto, aguardando login.")
        return int(sid)

    def collection(self, sid):
        return self.request("GET", f"/lol-item-sets/v1/item-sets/{int(sid)}/sets")

    def put_collection(self, sid, value):
        return self.request("PUT", f"/lol-item-sets/v1/item-sets/{int(sid)}/sets", value)


def champion_context(client):
    phase = client.request("GET", "/lol-gameflow/v1/gameflow-phase")
    if phase != "ChampSelect":
        return None
    gameflow = client.request("GET", "/lol-gameflow/v1/session")
    queue = gameflow.get("gameData", {}).get("queue", {})
    if queue.get("id") != 2400:
        return None
    session = client.request("GET", "/lol-champ-select/v1/session")
    own = [member for member in session.get("myTeam", []) if member.get("cellId")==session.get("localPlayerCellId")]
    if len(own)!=1 or not isinstance(own[0].get("championId"), int) or own[0]["championId"]<=0:
        return None
    map_id = gameflow.get("map", {}).get("id") or queue.get("mapId") or 12
    return {"champion_id":own[0]["championId"], "map_id":int(map_id), "queue_id":2400}
