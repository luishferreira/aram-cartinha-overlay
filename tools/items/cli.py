"""Generate, inspect or import static ARAM Mayhem item sets."""
import argparse
import json
from pathlib import Path
import threading

from tools.items.static_sets import ROOT, export_all, load_export
from tools.items.lcu import Lcu, ClientUnavailable, LcuError
from tools.items.import_sets import Importer
from tools.items.watcher import ItemSetWatcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export")
    sub.add_parser("status")
    sub.add_parser("watch")
    sync = sub.add_parser("sync")
    sync.add_argument("--champion", required=True, type=int)
    sync.add_argument("--apply", action="store_true", help="Without this flag, only inspect the proposed import")
    restore = sub.add_parser("restore")
    restore.add_argument("backup", type=Path)
    args = parser.parse_args()
    try:
        if args.command=="export":
            manifest = export_all()
            result = {k:v for k,v in manifest.items() if k!="files"}
        elif args.command=="status":
            client = Lcu()
            collection = client.collection(client.account())
            result = {"client_connected":True, "phase":client.request("GET", "/lol-gameflow/v1/gameflow-phase"),
                      "total_sets":len(collection.get("itemSets",[]))}
            status = ROOT/"data/local/item-sets/status.json"
            if status.exists():
                result["watcher"] = json.loads(status.read_text(encoding="utf-8"))
        elif args.command=="watch":
            stop = threading.Event()
            try:
                ItemSetWatcher(stop).run()
            except KeyboardInterrupt:
                stop.set()
            return
        else:
            bundle, _ = load_export()
            importer = Importer(bundle)
            client = Lcu()
            if args.command=="sync":
                if client.request("GET", "/lol-gameflow/v1/gameflow-phase") in ("InProgress", "GameStart", "Reconnect"):
                    raise RuntimeError("Import before the match; in-game shop reload is not assumed")
                result = importer.sync(client, args.champion, dry_run=not args.apply)
            else:
                result = importer.restore(client, args.backup)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (ClientUnavailable, LcuError, ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"{type(error).__name__}: {error}\n")


if __name__=="__main__":
    main()
