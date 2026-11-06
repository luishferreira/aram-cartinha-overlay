"""Import only the selected Mayhem champion, before the match starts."""
import json
from pathlib import Path
import time

from tools.items.static_sets import ROOT, load_export, encode
from tools.items.lcu import Lcu, ClientUnavailable, LcuError, champion_context
from tools.items.import_sets import Importer


class ItemSetWatcher:
    def __init__(self, stop, root=ROOT, log=lambda *a, **k: None):
        self.stop, self.root, self.log = stop, Path(root), log
        self.status_signature = None

    def status(self, state, **fields):
        value = {"state":state, **fields}
        signature = json.dumps(value, sort_keys=True)
        if signature != self.status_signature:
            folder = self.root/"data/local/item-sets"
            folder.mkdir(parents=True, exist_ok=True)
            temporary = folder/"status.tmp"
            temporary.write_bytes(encode(value))
            temporary.replace(folder/"status.json")
            self.log("item_sets_status", **value)
            self.status_signature = signature

    def run(self):
        client = None
        pending, began, synced = None, 0, None
        try:
            bundle, manifest = load_export(self.root)
            importer = Importer(bundle, self.root)
            self.status("ready", champions=manifest["champions"], paths=manifest["sets"])
        except (OSError, ValueError, KeyError) as error:
            self.status("export_unavailable", error_type=type(error).__name__)
            return
        while not self.stop.is_set():
            delay = 1
            try:
                pointer = self.root/'data/item-sets/current.json'
                if pointer.exists() and json.loads(pointer.read_text('utf8'))['generation'] != bundle['generation']:
                    bundle, manifest = load_export(self.root)
                    importer = Importer(bundle, self.root)
                    pending, synced = None, None
                    self.status('ready',champions=manifest['champions'],paths=manifest['sets'],
                                generation=bundle['generation'])
                client = client or Lcu()
                context = champion_context(client)
                if context is None:
                    pending, synced = None, None
                    self.status("waiting_for_mayhem_champion")
                else:
                    key = (context["champion_id"], context["map_id"])
                    if pending != key:
                        pending, began = key, time.monotonic()
                    elif key != synced and time.monotonic()-began >= .8:
                        result = importer.sync(client, *key,
                            context_guard=lambda: not self.stop.is_set() and champion_context(client)==context)
                        synced = key
                        self.status("imported", **{k:v for k,v in result.items() if k!="backup"})
            except ClientUnavailable:
                client = None
                pending, synced = None, None
                delay = 3
                self.status("client_unavailable")
            except (LcuError, ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
                delay = 8
                self.status("import_error", error_type=type(error).__name__, detail=str(error))
            self.stop.wait(delay)
