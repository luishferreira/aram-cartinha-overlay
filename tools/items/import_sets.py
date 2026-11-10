"""Merge only this project's selected champion sets; retain foreign collections."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from tools.items.static_sets import ROOT, encode, digest, validate_set, TITLE_PREFIX, LEGACY_TITLE_PREFIXES
from tools.app_paths import local_root


def projection(value):
    return {"uid":value.get("uid"), "title":value.get("title"),
            "sortrank":value.get("sortrank",0),
            "associatedChampions":sorted(value.get("associatedChampions", [])),
            "associatedMaps":sorted(value.get("associatedMaps", [])),
            "blocks":[{"type":b["type"], "items":[{"id":str(i["id"]), "count":i.get("count",1)}
                                                      for i in b.get("items",[])]}
                      for b in value.get("blocks",[])]}


def validate_collection(value):
    if not isinstance(value, dict) or not isinstance(value.get("itemSets"), list) or not value.get("accountId"):
        raise ValueError("Unexpected LCU item set collection")
    uids = [s.get("uid") for s in value["itemSets"]]
    if any(not isinstance(uid,str) or not uid for uid in uids) or len(uids)!=len(set(uids)):
        raise ValueError("Ambiguous existing item set identities")


def merge_collection(current, desired, owned_uids):
    validate_collection(current)
    for value in desired:
        validate_set(value)
        if value["uid"] not in owned_uids:
            raise ValueError("Attempt to manage a foreign UID")
    if len({s["uid"] for s in desired}) != len(desired):
        raise ValueError("Duplicate generated item set UID")
    result = copy.deepcopy(current)
    result["itemSets"] = [s for s in result["itemSets"] if s["uid"] not in owned_uids]+copy.deepcopy(desired)
    return result


def state_signature(collection):
    return digest(encode({"accountId":collection["accountId"], "itemSets":collection["itemSets"]}))


class Importer:
    def __init__(self, bundle, root=ROOT):
        self.bundle = bundle
        self.folder = local_root(root)/'item-sets'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.owned = set(bundle.get('managed_uids', [s['uid'] for s in bundle['itemSets']]))
        if not {s['uid'] for s in bundle['itemSets']} <= self.owned:
            raise ValueError('Generated item set outside managed identities')

    def sync(self, client, champion_id, map_id=12, dry_run=False, context_guard=None):
        sid = client.account()
        desired = [copy.deepcopy(s) for s in self.bundle["itemSets"] if s["associatedChampions"]==[champion_id]]
        if not desired:
            raise ValueError("No predefined paths for this champion")
        desired.sort(key=lambda value:(value.get('sortrank',0), value['title'].casefold(), value['uid']))
        for value in desired:
            value["associatedMaps"] = [map_id]
            # Keep packaged snapshots usable and migrate our existing UIDs in place.
            for prefix in LEGACY_TITLE_PREFIXES:
                if value["title"].startswith(prefix):
                    value["title"] = TITLE_PREFIX+value["title"][len(prefix):]
                    break
        # Current game catalog validates IDs, including Mayhem-specific variants.
        catalog = client.request("GET", "/lol-game-data/assets/v1/items.json")
        if not isinstance(catalog, list):
            raise ValueError("Unexpected client item catalog")
        known = {str(item["id"]) for item in catalog if isinstance(item,dict) and "id" in item}
        ids = {i["id"] for s in desired for b in s["blocks"] for i in b["items"]}
        if ids-known:
            raise ValueError("Some generated item IDs are absent from the installed client: "+",".join(sorted(ids-known)))
        before = client.collection(sid)
        validate_collection(before)
        merged = merge_collection(before, desired, self.owned)
        owned_before = {s["uid"]:projection(s) for s in before["itemSets"] if s["uid"] in self.owned}
        wanted = {s["uid"]:projection(s) for s in desired}
        result = {"champion_id":champion_id, "paths":len(desired),
                  "foreign_preserved":sum(s["uid"] not in self.owned for s in before["itemSets"]),
                  "changed":owned_before!=wanted, "generation":self.bundle["generation"] if "generation" in self.bundle else None}
        if not result["changed"] or dry_run:
            return {**result,"dry_run":dry_run}
        # Detect concurrent edits before the whole-collection PUT.
        latest = client.collection(sid)
        validate_collection(latest)
        if state_signature(latest)!=state_signature(before):
            raise RuntimeError("Item sets changed concurrently; retry without replacing the new collection.")
        account_hash = hashlib.sha256(str(before["accountId"]).encode()).hexdigest()[:16]
        directory = self.folder/"backups"/account_hash
        directory.mkdir(parents=True, exist_ok=True)
        backup = directory/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")+".json")
        backup.write_bytes(encode({"before":before,"owned_uids":sorted(self.owned), "written":desired}))
        # Revalidate the account and selection immediately before writing.
        if client.account()!=sid:
            raise RuntimeError("LoL account changed before import")
        if context_guard is not None and not context_guard():
            raise RuntimeError("Champion selection changed before import; waiting for the new selection")
        merged["timestamp"] = max(int(time.time()*1000), int(before.get("timestamp",0))+1)
        client.put_collection(sid, merged)
        after = client.collection(sid)
        validate_collection(after)
        actual = {s["uid"]:s for s in after["itemSets"]}
        if after["accountId"]!=before["accountId"] or any(
            uid not in actual or projection(actual[uid])!=value for uid,value in wanted.items()):
            raise RuntimeError("Client did not preserve the imported paths; backup saved: "+str(backup))
        foreign = [s for s in before["itemSets"] if s["uid"] not in self.owned]
        if any(s["uid"] not in actual or projection(actual[s["uid"]])!=projection(s) for s in foreign):
            raise RuntimeError("Foreign item sets verification failed; backup saved: "+str(backup))
        result["backup"] = str(backup)
        (self.folder/"last-import.json").write_bytes(encode(result))
        return result

    def restore(self, client, backup):
        path = Path(backup).resolve()
        if (self.folder/"backups").resolve() not in path.parents:
            raise ValueError("Restore only accepts this project's local backups")
        saved = json.loads(path.read_text(encoding="utf-8"))
        sid = client.account()
        current = client.collection(sid)
        validate_collection(current)
        if current["accountId"]!=saved["before"]["accountId"]:
            raise ValueError("Backup belongs to another account")
        owned = set(saved["owned_uids"])
        if not owned<=self.owned:
            raise ValueError("Backup includes unknown managed identities")
        previous = [s for s in saved["before"]["itemSets"] if s["uid"] in owned]
        # Restore our prior sets while retaining current personal/other-app sets.
        merged = merge_collection(current, previous, owned)
        latest = client.collection(sid)
        if state_signature(latest)!=state_signature(current):
            raise RuntimeError("Collection changed concurrently before restore")
        merged["timestamp"] = int(time.time()*1000)
        client.put_collection(sid, merged)
        after = client.collection(sid)
        validate_collection(after)
        expected = {s["uid"]:projection(s) for s in merged["itemSets"]}
        actual = {s["uid"]:projection(s) for s in after["itemSets"]}
        if expected != actual:
            raise RuntimeError("Restoration verification failed")
        return {"restored":True, "managed_sets":len(previous), "total_sets":len(actual)}
