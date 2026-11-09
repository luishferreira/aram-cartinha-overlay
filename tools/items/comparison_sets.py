"""Source-separated native item blocks, using a pinned offline classification release."""
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import re
import uuid

from tools.items.static_sets import encode, digest, items, by_sample, NAMESPACE, LABELS
from tools.live.source_cards import metric

SOURCES = {'aramkit':'ARAMKit', 'opgg':'OP.GG', 'arammayhem':'Mayhem.com', 'lemonnation':'Lemon'}
MAX_CORES = 3
# Only potions, not other consumables or components. Original bundles stay in evidence.
STARTING_POTIONS = frozenset({'2003', '2004', '2031', '2033'})


def coalesce_options(entries):
    """Compact native rows without pooling statistics or changing purchase order."""
    result, seen, boots_index = [], {}, None
    for entry in entries:
        if entry is None:
            continue
        block, origin = copy.deepcopy(entry)
        group = origin.get('option_group')
        if group == 'boots':
            if boots_index is None:
                boots_index = len(result)
                result.append((block, origin))
            else:
                # Prefer the first source (ARAMKit's path when available), not a union of rankings.
                result[boots_index][1].setdefault('undisplayed_alternatives', []).append({
                    'block':block, 'evidence':origin, 'reason':'one_boot_source_per_path'})
            continue
        if group not in ('starting','core'):
            result.append((block, origin))
            continue
        if group == 'starting':
            omitted = [i for i in block['items'] if i['id'] in STARTING_POTIONS]
            if omitted:
                origin['display_omitted_potions'] = omitted
            block['items'] = [i for i in block['items'] if i['id'] not in STARTING_POTIONS]
            if not block['items']:
                continue
        ids = tuple((i['id'],i['count']) for i in block['items'])
        # Starter component order has no purchase-order meaning; core order does.
        key = group, tuple(sorted(ids)) if group=='starting' else ids
        if key not in seen:
            seen[key] = len(result)
            result.append((block, origin))
            continue
        index = seen[key]
        existing, evidence = result[index]
        origins = evidence.get('origins',[evidence]) + [copy.deepcopy(origin)]
        scopes = {e['scope'] for e in origins}
        label = 'Início' if group=='starting' else 'Núcleo'
        if group == 'core':
            sources = ' + '.join(dict.fromkeys(SOURCES[e['source']] for e in origins))
            title = f'{label} · {sources}'
        elif len(scopes)==1:
            sources = ' + '.join(dict.fromkeys(SOURCES[e['source']] for e in origins))
            scope_label = {'path':'caminho','champion_general':'geral','editorial':'editorial'}[origins[0]['scope']]
            title = f'{sources} · {label} · {scope_label}'
        else:
            sources = ' + '.join(dict.fromkeys(SOURCES[e['source']]+' ('+
                {'path':'caminho','champion_general':'geral','editorial':'editorial'}[e['scope']]+')' for e in origins))
            title = f'{label} · {sources}'
        existing['type'] = title
        result[index] = (existing,{'source':'multiple','scope':'source_specific',
                                  'option_group':group,'origins':origins})
    return result


def native(ids):
    return items([f'item:game:{int(i)}' for i in ids])


def percent(value):
    return f'{value*100:.1f}%'.replace('.', ',')


def stats(option):
    return ' · '.join(f'{label} {percent(option[key])}' for key,label in
                     [('pick_rate','escolha'),('win_rate','vitória')] if option.get(key) is not None)


def identity(champion_id, path):
    # Preserve the original UUIDs, including when an inferred path later gains ARAMKit data.
    return f'aramkit:champion:game:{champion_id}:{path}'


def managed_uids(champions):
    return sorted(str(uuid.uuid5(NAMESPACE, identity(c['id'], path)))
                  for c in champions for path in LABELS)


class Comparison:
    def __init__(self, root, data_run):
        pointer = json.loads((root/'data/build-classification/current.json').read_text('utf8'))
        self.release = pointer['release']
        if not re.fullmatch('[0-9a-f]{24}', self.release):
            raise ValueError('Invalid classification release')
        folder = root/'data/build-classification/runs'/self.release
        raw = (folder/'manifest.json').read_bytes()
        if digest(raw) != pointer['manifest_sha256']:
            raise ValueError('Classification manifest changed')
        manifest = json.loads(raw)
        for name, expected in manifest['files'].items():
            if name != Path(name).name or digest((folder/name).read_bytes()) != expected:
                raise ValueError('Classification artifact changed')
        model = json.loads((folder/'model.json').read_text('utf8'))
        if model['data_run'] != data_run:
            raise ValueError('Classification and item source data versions differ')
        self.catalog = model['item_catalog']
        exclusions = root/'data/item-sets/export-exclusions.json'
        self.exclusions = json.loads(exclusions.read_text('utf8'))['item_ids']
        self.source_hashes = {str(exclusions.relative_to(root)):digest(exclusions.read_bytes())}
        self.pages = defaultdict(list)
        self.source_hashes.update(manifest['source_files'])
        for name, expected in manifest['source_files'].items():
            path = (root/name).resolve()
            if not path.is_relative_to(root.resolve()) or digest(path.read_bytes()) != expected:
                raise ValueError('Classification input changed')
            for page in json.loads(path.read_text('utf8'))['records']:
                if page['source'] == 'opgg' and page['published_modes'] != ['aram_mayhem']:
                    continue
                self.pages[page['url']].append(page)
        self.rows = json.loads((folder/'classifications.json').read_text('utf8'))['records']
        self.index = defaultdict(list)
        self.primary = defaultdict(set)
        self.omitted = []
        for row in self.rows:
            ids = {str(i) for i in row['items']}
            ids.update(str(i['game_item_id']) for t in row['source_record'].get('tokens',[])
                       if t['kind']=='choose_one' for i in t['options'])
            invalid = ids & self.exclusions.keys()
            if invalid:
                self.omitted.append({'record_id':row['id'],'source':row['source'],'url':row['url'],
                                     'champion_id':row['champion_id'],'excluded_item_ids':sorted(invalid),
                                     'action':'omit_whole_core_without_replacement'})
                continue
            result = row['classification']
            if result['status'] != 'assigned':
                continue
            self.primary[row['champion_id']].add(result['primary_path'])
            for path in result['assignments']:
                if path in LABELS:
                    self.index[row['champion_id'],path].append(row)

    def label(self, ident):
        return self.catalog.get(str(ident), {}).get('name') or str(ident)

    def compose(self, champion, path, profiles, baseline=None, old_evidence=None):
        key = path['native_key']
        value = copy.deepcopy(baseline) if baseline else {
            'uid':str(uuid.uuid5(NAMESPACE, identity(champion['id'],key))),
            'title':f'Mayhem · {champion["name"]} · {LABELS[key]}',
            'type':'custom','map':'any','mode':'any','priority':False,'sortrank':0,
            'startedFrom':'blank','associatedChampions':[champion['id']],
            'associatedMaps':[12],'preferredItemSlots':[],'blocks':[]}
        rows = self.index[champion['id'],key]
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['source']].append(row)
        # Native blocks and their evidence share positions, so every rendered row is traceable.
        starts, cores, extras = [], defaultdict(list), []
        def block(title, entries, source, scope, **evidence):
            if not entries:
                return None
            return ({'type':title,'items':entries}, {'source':source,'scope':scope, **evidence})

        if baseline:
            for b in baseline['blocks']:
                if b['type']=='Início':
                    starts.append(block('ARAMKit · Início do caminho',b['items'],'aramkit','path',
                                        route=old_evidence['route_selector'],artifact=old_evidence['artifact'],
                                        option_group='starting'))
                elif b['type']!='Núcleo · ordem de compra':
                    extras.append(block('ARAMKit · '+b['type'],b['items'],'aramkit',
                        'champion_general' if b['type'].startswith('Outras opções') else 'path',
                        legacy_provenance=True,option_group='boots' if b['type'].startswith('Botas') else None))
            seen = set()
            for profile in sorted(profiles,key=lambda p: (-(metric(p,'sample_count') or 0),p['id'])):
                route = next((r for r in by_sample(profile['routes']) if r['purchase_order'] and
                              Counter(r['purchase_order'])==Counter(profile['item_set'])),None)
                if not route:
                    continue
                sequence = tuple(route['purchase_order'])
                if sequence in seen:
                    continue
                seen.add(sequence)
                published = {k:metric(profile,k) for k in ['pick_rate','win_rate']}
                cores['aramkit'].append([block('ARAMKit · '+stats(published), items(sequence),'aramkit','path',
                    option_group='core',
                    profile_id=profile['id'],metrics=profile['metrics'],route=route,
                    artifact=profile['artifact'],patch=profile['patch'],
                    metric_subject='unordered_core_profile; displayed_order_is_observed_route')])
                if len(seen)>=MAX_CORES:
                    break

        for source in ('opgg','arammayhem','lemonnation'):
            candidates = sorted(grouped[source], key=lambda r:(
                r['source_record'].get('option',{}).get('source_position',999),r['url'],str(r['source_option'])))
            seen, chosen = set(), []
            for row in candidates:
                tokens = row['source_record'].get('tokens')
                signature = encode(tokens) if tokens is not None else tuple(row['items'])
                if signature in seen:
                    continue
                seen.add(signature)
                chosen.append(row)
                if len(chosen)>=(2 if source=='lemonnation' else MAX_CORES):
                    break
            for row in chosen:
                context = row['source_record']['page_context']
                common = {'record_id':row['id'],'url':row['url'],'patch':row['patch'],
                          'artifact':context['artifact'], 'classification':row['classification'],
                          'source_record':row['source_record'], 'metrics_scope_changed':False}
                if source=='lemonnation':
                    # A native block cannot express OR. Split the original flow at each choice.
                    sequence, flow, step = [], [], 0
                    title = f'Lemon · {context.get("build_key") or "Build"} · {row["source_option"]}'
                    def flush():
                        nonlocal sequence, step
                        if sequence:
                            step += 1
                            flow.append(block(f'{title} · passo {step}',native(sequence),source,'editorial',**common))
                            sequence = []
                    for token in row['source_record']['tokens']:
                        if token['kind']=='item':
                            sequence.append(token['game_item_id'])
                        elif token['kind']=='choose_one':
                            flush()
                            step += 1
                            flow.append(block(f'{title} · passo {step}: escolha 1',
                                native([i['game_item_id'] for i in token['options']]),source,'editorial',
                                choice_group=True,**common))
                    flush()
                    if flow:
                        cores[source].append(flow)
                else:
                    option = row['source_record']['option']
                    cores[source].append([block(f'{SOURCES[source]} · geral · {stats(option)}',
                        native(row['items']),source,'champion_general',option_group='core',**common)])
            if not chosen:
                continue
            # General source lists are displayed as alternatives, never a synthetic observed sequence.
            page = self.pages[chosen[0]['url']][0]
            for group, label in [('starting','Início'),('boots','Botas'),
                                 ('Boots','Botas'),('late','Depois do núcleo'),('items','Itens'),('Options','Opções')]:
                options = page['groups'].get(group,[])
                if not options:
                    continue
                if source=='lemonnation':
                    ids = [t['game_item_id'] for t in options if t['kind']=='item']
                    ids += [i['game_item_id'] for t in options if t['kind']=='choose_one' for i in t['options']]
                    evidence = {'tokens':options}
                else:
                    ranked = sorted(options,key=lambda o:o['source_position'])
                    if group=='starting':
                        ranked = ranked[:1]
                    ids = [i for o in ranked for i in (o['item_ids'] if source=='opgg' else
                                                     [i['game_item_id'] for i in o['items']])]
                    evidence = {'published_options':ranked}
                # Starting bundles keep component counts; other rows are deduplicated ranked alternatives.
                if label!='Início':
                    ids = list(dict.fromkeys(ids))
                    # Keep completed items in the general item row; components remain in source evidence.
                    if group=='items':
                        ids = [i for i in ids if self.catalog.get(str(i),{}).get('cost',0)>=2000]
                    ids = ids[:12]
                ids = [i for i in ids if str(i) not in self.exclusions]
                entry = block(f'{SOURCES[source]} · {label} · '+('geral' if source!='lemonnation' else 'escolha entre'),
                              native(ids),source,'champion_general' if source!='lemonnation' else 'editorial',
                              url=page['url'],patch=page['patch'],artifact=page['artifact'],
                              ordering='published_source_position',
                              option_group='starting' if label=='Início' else ('boots' if label=='Botas' else None),**evidence)
                (starts if label=='Início' else extras).append(entry)

        ordered = list(starts)
        # First comparison from every source is visible before the second from any source.
        for index in range(MAX_CORES):
            for source in SOURCES:
                if index<len(cores[source]):
                    ordered.extend(cores[source][index])
        ordered.extend(extras)
        ordered = coalesce_options(ordered)
        if not ordered:
            raise ValueError('Empty comparison path')
        value['blocks'] = [b for b,_ in ordered]
        return value, {'path_id':path['id'],'champion_key':champion['key'],
            'classifier_release':self.release,'path_origin':'aramkit' if baseline else 'inferred_primary',
            'block_evidence':[e for _,e in ordered], 'aramkit':old_evidence,
            'core_names': old_evidence['core_names'] if old_evidence else
                          [self.label(i) for i in rows[0]['items']]}
