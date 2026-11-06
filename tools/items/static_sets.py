"""Reproducible static item sets from published ARAMKit paths and purchase routes."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import uuid

from tools.live.source_cards import SourceReader, metric

ROOT = Path(__file__).resolve().parents[2]
VERSION = "static-item-sets-3"
NAMESPACE = uuid.UUID("2e701da9-4d06-478c-9443-a2fe6965c886")
LABELS = {"ad":"AD", "ap":"AP", "bruiser":"Lutador", "crit":"Crítico", "hybrid":"Híbrido",
          "lethality":"Letalidade", "on_hit":"On-hit", "tank":"Tanque", "utility":"Utilidade"}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def item_id(entity):
    if not isinstance(entity, str) or not re.fullmatch(r"item:game:[1-9]\d*", entity):
        raise ValueError("Invalid game item identity")
    return entity.rsplit(":", 1)[1]


def items(entities):
    # Preserve repeated starter components as native item counts.
    counts = Counter(item_id(i) for i in entities)
    return [{"id": i, "count": count} for i, count in counts.items()]


def by_sample(rows):
    return sorted(rows, key=lambda r: (-(metric(r,"sample_count") or 0),
                                       json.dumps(r, sort_keys=True, ensure_ascii=True)))


def build_set(champion, path, profiles, label, champion_options=()):
    """One largest-sample profile and one coherent route, never maximum WR."""
    chosen = None
    for profile in sorted(profiles, key=lambda p: (-(metric(p,"sample_count") or 0), p["id"])):
        for route in by_sample(profile["routes"]):
            if route["purchase_order"] and Counter(route["purchase_order"]) == Counter(profile["item_set"]):
                chosen = profile, route
                break
        if chosen:
            break
    if not chosen:
        raise ValueError(f'No coherent purchase route: {path["id"]}')
    profile, route = chosen
    core = route["purchase_order"]
    blocks = []
    starters = by_sample(route["starters"])
    if starters:
        blocks.append({"type":"Início", "items":items(starters[0]["item_ids"])})
    blocks.append({"type":"Núcleo · ordem de compra", "items":items(core)})
    valid_profiles = []
    evidence = {}
    for candidate in profiles:
        routes = [r for r in candidate["routes"] if r["purchase_order"] and
                  Counter(r["purchase_order"])==Counter(candidate["item_set"])]
        if routes:
            valid_profiles.append((candidate, routes))
    def collect(key, exclude, limit):
        candidates = {}
        for candidate, routes in valid_profiles:
            for observed_route in routes:
                for option in observed_route[key]:
                    for entity in option["item_ids"]:
                        if not entity or entity in exclude:
                            continue
                        entry = {"profile_id":candidate["id"], "route_selector":observed_route["selector"],
                                 "artifact":candidate["artifact"], "sample_count":metric(option,"sample_count")}
                        evidence.setdefault(entity, []).append(entry)
                        candidates[entity] = max(candidates.get(entity,0), metric(option,"sample_count") or 0)
        # Duplicated appearances across routes are not summed as independent games.
        return sorted(candidates, key=lambda entity:(-candidates[entity],entity))[:limit]

    boots = collect("boots", set(core), 5)
    if boots:
        blocks.append({"type":"Botas · opções do caminho", "items":items(boots)})
    alternate_core = []
    for candidate, _ in sorted(valid_profiles,key=lambda pair: (-(metric(pair[0],"sample_count") or 0),pair[0]["id"])):
        for entity in candidate["item_set"]:
            if entity not in core and entity not in boots and entity not in alternate_core:
                alternate_core.append(entity)
    if alternate_core:
        blocks.append({"type":"Alternativas de núcleo · mesmo caminho", "items":items(alternate_core[:8])})
    excluded = set(core+boots+alternate_core[:8])
    later = collect("laterItems", excluded, 12)
    if later:
        blocks.append({"type":"Depois do núcleo · opções do caminho", "items":items(later)})
    excluded.update(later)
    general = []
    for row in by_sample(champion_options):
        if row["entity_id"] not in excluded:
            general.append(row)
            excluded.add(row["entity_id"])
        if len(general)>=12:
            break
    if general:
        blocks.append({"type":f'Outras opções de {champion["name"]} · geral',
                       "items":items([row["entity_id"] for row in general])})
    uid = str(uuid.uuid5(NAMESPACE, path["id"]))
    result = {"uid":uid, "title":f'Mayhem · {champion["name"]} · {LABELS.get(path["native_key"],path["native_key"])}',
              "type":"custom", "map":"any", "mode":"any", "priority":False, "sortrank":0,
              "startedFrom":"blank", "associatedChampions":[champion["id"]], "associatedMaps":[12],
              "preferredItemSlots":[], "blocks":blocks}
    validate_set(result)
    provenance = {"path_id":path["id"], "champion_key":champion["key"], "source":"aramkit",
                  "profile_id":profile["id"], "profile_metrics":profile["metrics"],
                  "artifact":profile["artifact"], "patch":profile["patch"], "selector":profile["selector"],
                  "route_selector":route["selector"], "route_metrics":route["metrics"],
                  "route":route, "sample_selection":"largest_sample_not_maximum_win_rate",
                  "alternate_profile_ids":[p["id"] for p,_ in valid_profiles],
                  "option_evidence":{entity:evidence[entity] for entity in boots+later},
                  "general_champion_options":general,
                  "option_scope":"path_profiles_plus_separately_labeled_champion_general",
                  "core_names":[label(i) for i in core], "no_boots_observed":any(
                      r.get("no_item_option") for r in route["boots"])}
    return result, provenance


def validate_set(value):
    uuid.UUID(value["uid"])
    if not value["title"].startswith("Mayhem · ") or not value["blocks"]:
        raise ValueError("Invalid managed item set")
    if len(value["associatedChampions"]) != 1 or value["associatedChampions"][0] <= 0:
        raise ValueError("Invalid champion association")
    for block in value["blocks"]:
        if not block["items"] or not block["type"]:
            raise ValueError("Empty item block")
        for entry in block["items"]:
            if not re.fullmatch(r"[1-9]\d*", entry["id"]) or type(entry["count"]) is not int or not 1<=entry["count"]<=99:
                raise ValueError("Invalid native item entry")


def export_all(root=ROOT):
    root = Path(root)
    reader = SourceReader(root)
    try:
        registry = json.loads((root/f"data/recommendation/registries/build-paths-{reader.run}.json").read_text(encoding="utf-8"))
        if registry["data_run"] != reader.run:
            raise ValueError("Registry and data version differ")
        source_manifest = root/f"data/pipeline/runs/{reader.run}/manifest.json"
        if digest(source_manifest.read_bytes()) != registry["data_manifest_sha256"]:
            raise ValueError("Source manifest changed")
        catalog = json.loads((root/"research/champion-snapshots/champion-catalog.json").read_text(encoding="utf-8"))["champions"]
        champions = {f'champion:game:{c["id"]}':c for c in catalog}
        from tools.items.comparison_sets import Comparison, managed_uids, identity
        comparison = Comparison(root, reader.run)
        paths = list(registry['paths'])
        existing = {(int(p['champion_id'].rsplit(':',1)[1]),p['native_key']) for p in paths}
        for champion in sorted(catalog,key=lambda c:c['id']):
            for key in sorted(comparison.primary[champion['id']]):
                if key in LABELS and (champion['id'],key) not in existing:
                    paths.append({'id':identity(champion['id'],key),
                                  'champion_id':f'champion:game:{champion["id"]}', 'native_key':key})
        # Only completed legendary items enter the separate general-champion row.
        legendary = {row["entity_id"] for row in reader.db.execute(
            'SELECT entity_id,attributes_json FROM catalog WHERE entity_id LIKE "item:game:%"')
            if json.loads(row["attributes_json"]).get("category")=="legendary"}
        general_cache = {}
        sets, evidence, files = [], {}, {}
        for path in paths:
            champion = champions[path["champion_id"]]
            if not re.fullmatch(r"[A-Za-z0-9]+", champion["key"]):
                raise ValueError("Invalid champion key")
            profiles = []
            for row in reader.db.execute(
                'SELECT id,metrics_json,item_set_json,routes_json,artifact,patch,selector FROM build_profiles '
                'WHERE champion_id=? AND archetype=? AND augment_id IS NULL AND selection="filtered"',
                (path["champion_id"], path["native_key"])):
                profile = dict(row)
                for field in ("metrics", "item_set", "routes"):
                    profile[field] = json.loads(profile.pop(field+"_json"))
                profiles.append(profile)
            if path["champion_id"] not in general_cache:
                general_cache[path["champion_id"]] = []
                for row in reader.db.execute(
                    'SELECT o.entity_id,o.context_json,o.metrics_json,o.artifact,o.selector,o.patch '
                    'FROM observations o JOIN snapshots s ON s.id=o.snapshot_id '
                    'WHERE s.source="aramkit" AND o.champion_id=? AND o.scope="champion_item"',
                    (path["champion_id"],)):
                    context = json.loads(row["context_json"])
                    if context.get("selection")=="filtered" and context.get("slot")=="all" and row["entity_id"] in legendary:
                        general_cache[path["champion_id"]].append({"entity_id":row["entity_id"],
                            "metrics":json.loads(row["metrics_json"]), "artifact":row["artifact"],
                            "selector":row["selector"], "patch":row["patch"], "scope":"champion_general_not_path"})
            baseline, old_evidence = (build_set(champion, path, profiles, reader.label,
                                     general_cache[path['champion_id']]) if profiles else (None,None))
            value, provenance = comparison.compose(champion,path,profiles,baseline,old_evidence)
            validate_set(value)
            filename = f'champions/{champion["key"]}/mayhem-{path["native_key"]}.json'
            files[filename] = encode(value)
            sets.append(value)
            evidence[value["uid"]] = provenance
        actual = {value["associatedChampions"][0] for value in sets}
        if actual != {c["id"] for c in catalog} or len(sets) != len(paths):
            raise ValueError("Incomplete champion/path coverage")
        bundle = {"schema_version":2, "generator":VERSION, "data_run":reader.run,
                  "classifier_release":comparison.release, "managed_uids":managed_uids(catalog), "itemSets":sets}
        files["item-sets.json"] = encode(bundle)
        files["provenance.json"] = encode(evidence)
        files['omitted-source-cores.json'] = encode(comparison.omitted)
        rows = ["# Arsenais comparáveis de ARAM Mayhem", "", f"{len(sets)} caminhos · {len(actual)} campeões", "",
                "ARAMKit: métricas do caminho. OP.GG e Mayhem.com: métricas gerais do campeão, agrupadas por afinidade dos itens. Lemon: editorial.",
                "Percentuais de fontes/patches distintos não são diretamente equivalentes. Alternativas não formam uma sequência de compra.", ""]
        for s in sorted(sets,key=lambda s:s['title']):
            rows.extend(['## '+s['title'], '', '| Bloco | Itens |','| --- | --- |'])
            for b in s['blocks']:
                names = [comparison.label(i['id'])+(f' ×{i["count"]}' if i['count']>1 else '') for i in b['items']]
                rows.append(f'| {b["type"].replace("|","/")} | {" · ".join(names)} |')
            rows.append('')
        files["preview.md"] = ("\n".join(rows)+"\n").encode("utf-8")
        hashes = {name:digest(data) for name, data in files.items()}
        generation = digest(encode(hashes))[:24]
        directory = root/"data/item-sets/runs"/generation
        directory.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            target = directory/name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                raise ValueError("Immutable generated file changed")
            target.write_bytes(data)
        manifest = {"generation":generation, "data_run":reader.run, "generator":VERSION,
                    "champions":len(actual), "sets":len(sets), "files":hashes,
                    "classifier_release":comparison.release,"source_files":comparison.source_hashes}
        (directory/"manifest.json").write_bytes(encode(manifest))
        pointer = root/"data/item-sets/current.json"
        temporary = pointer.with_suffix(".tmp")
        temporary.write_bytes(encode({"generation":generation}))
        temporary.replace(pointer)
        return manifest
    finally:
        reader.close()


def load_export(root=ROOT, *, runtime=True):
    root = Path(root)
    if runtime:
        from tools.live.data_paths import active_pack
        pack = active_pack(root)
        if pack:
            directory,manifest = pack
            research_pointer = root/'data/item-sets/current.json'
            # Developer exports may be newer than the last distribution pack.
            if not research_pointer.exists() or json.loads(research_pointer.read_text('utf8'))['generation']==manifest['item_sets_generation']:
                bundle = json.loads((directory/'item-sets.json').read_text('utf8'))
                bundle['generation'] = manifest['item_sets_generation']
                validate_bundle(bundle)
                return bundle,{'generation':bundle['generation'],'champions':manifest['champions'],
                               'sets':len(bundle['itemSets']),'runtime_generation':manifest['generation']}
    generation = json.loads((root/"data/item-sets/current.json").read_text(encoding="utf-8"))["generation"]
    if not re.fullmatch(r"[0-9a-f]{24}",generation):
        raise ValueError("Invalid generated item set version")
    directory = root/"data/item-sets/runs"/generation
    manifest = json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    if manifest["generation"] != generation:
        raise ValueError("Item set manifest mismatch")
    if digest((directory/"item-sets.json").read_bytes()) != manifest["files"]["item-sets.json"]:
        raise ValueError("Generated item sets changed")
    bundle = json.loads((directory/"item-sets.json").read_text(encoding="utf-8"))
    bundle["generation"] = generation
    validate_bundle(bundle)
    return bundle, manifest


def validate_bundle(bundle):
    for value in bundle['itemSets']:
        validate_set(value)
    if 'managed_uids' in bundle:
        managed = set(bundle['managed_uids'])
        for uid in managed:
            uuid.UUID(uid)
        if not {s['uid'] for s in bundle['itemSets']} <= managed:
            raise ValueError('Item sets outside managed identities')
