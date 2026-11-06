"""Rebuild offline research derivatives. Does not write overlay/pipeline/item-set state."""
import hashlib
import json
import re
from collections import Counter
from urllib.parse import urlparse, parse_qs
from audit_item_sources import OUT, ROOT, write
from html_tree import Tree, Node

def children(node):
    return [c for c in node.children if isinstance(c, Node)]

def clean_text(node):
    if isinstance(node, str):
        return node
    if 'tooltip' in node.attrs.get('class', '') or node.tag in {'script', 'style'}:
        return ''
    return ''.join(clean_text(c) for c in node.children)

def flights(tree):
    chunks = []
    for script in tree.find('script'):
        text = ''.join(c for c in script.children if isinstance(c, str))
        if text.startswith('self.__next_f.push('):
            value = json.loads(text[len('self.__next_f.push('):-1])
            if len(value) > 1 and isinstance(value[1], str):
                chunks.append(value[1])
    records = []
    for line in ''.join(chunks).splitlines():
        try:
            records.append(json.JSONDecoder().raw_decode(line.split(':', 1)[1])[0])
        except (ValueError, IndexError):
            pass  # Flight import/reference/text records are not JSON model records.
    return records

def walk(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)

def arammayhem(tree, url, origin, item_map, champion_ids):
    groups = {}
    labels = {'Starting Items': 'starting', 'Boots': 'boots', 'Core Builds': 'core', 'Other completed items': 'late'}
    for label, group in labels.items():
        titles = list(tree.find('div', predicate=lambda n: n.attrs.get('class') == 'font-semibold mb-3' and n.text() == label))
        if len(titles) != 1:
            raise ValueError(f'{url}: expected one group heading for {label}, got {len(titles)}')
        section = titles[0].parent
        container = next(n for n in children(section) if n is not titles[0])
        options = []
        for row in children(container):
            anchors = list(row.find('a', lambda n: n.attrs.get('href', '').startswith('/items/')))
            if not anchors:
                continue
            text = row.text()
            pick = re.search(r'Pick Rate\s*([\d.]+)%', text)
            win = re.search(r'Win Rate\s*([\d.]+)%', text)
            if not (pick and win):
                raise ValueError(f'Missing metrics in {url} / {group}')
            items = []
            for anchor in anchors:
                native = anchor.attrs['href'].strip('/').split('/')[-1]
                items.append({'native_id': native, 'game_item_id': item_map.get(native),
                              'name': anchor.attrs.get('title', anchor.text())})
            options.append({'source_position': len(options) + 1, 'items': items,
                'pick_rate': float(pick.group(1)) / 100, 'win_rate': float(win.group(1)) / 100,
                'sample_games': None})
        groups[group] = options
    text = tree.text()
    patch = re.search(r'Patch:\s*(\d+\.\d+)', text)
    date = re.search(r'Data date\s*(\d{4}-\d{2}-\d{2})', text)
    key = urlparse(url).path.strip('/').split('/')[-1]
    return {'source': 'arammayhem', 'url': url, 'artifact': origin, 'champion_key': key,
            'champion_id': champion_ids.get(key), 'patch': patch.group(1) if patch else None,
            'data_date': date.group(1) if date else None, 'mode_basis': 'source_page_declares_mayhem',
            'groups': groups, 'flags': ['sample_count_unknown', 'not_augment_conditioned', 'source_options_bounded',
                                      'not_an_independent_source_from_mcp']}

def opgg(tree, url, origin):
    objects = [o for record in flights(tree) for o in walk(record)]
    components = [o for o in objects if isinstance(o.get('data'), list) and o['data'] and
                  isinstance(o['data'][0], dict) and 'ids' in o['data'][0]]
    groups = {}
    modes = set()
    for component in components:
        row = component['data'][0]
        if 'metaBuildItems' in row:
            group = 'core'
        elif 'metaStarterItems' in row:
            group = 'starting'
        elif 'metaItem' in row:
            group = 'boots' if 'boots' not in groups else 'items'
        else:
            raise ValueError('Unknown OP.GG item table')
        if group in groups:
            raise ValueError('Repeated OP.GG item table')
        modes.add(component.get('mode'))
        groups[group] = []
        for row in component['data']:
            groups[group].append({'source_position': len(groups[group]) + 1, 'item_ids': row['ids'],
                'pick_rate': row['pick_rate'] / 100, 'win_rate': row['win_rate'] / 100,
                'sample_games': int(row['play'].replace(',', '')), 'published': row})
    query = next((o['query'] for o in objects if isinstance(o.get('query'), dict) and 'patch' in o['query']), {})
    return {'source': 'opgg', 'url': url, 'artifact': origin, 'query': query,
            'patch': query.get('patch'),
            'published_modes': sorted(m for m in modes if m), 'groups': groups,
            'flags': ['source_options_bounded', 'upstream_sample_origin_unverified', 'not_augment_conditioned']}

def lemon_item(node):
    img = next(node.find('img', lambda n: re.search(r'/items/\d+\.png', n.attrs.get('src', ''))), None)
    if img is None:
        raise ValueError('LemonNation item without native image ID')
    item_id = int(re.search(r'/items/(\d+)\.png', img.attrs['src']).group(1))
    name = next(node.find('b'), None)
    return {'game_item_id': item_id, 'name': name.text() if name else img.attrs.get('alt')}

def lemon(tree, url, origin):
    groups = {}
    for section in tree.find(predicate=lambda n: 'build-section' in n.attrs.get('class', '').split()):
        heading = next(section.find('h2'), None)
        if heading is None:
            continue
        group = heading.text()
        row = next(section.find(predicate=lambda n: 'item-row' in n.attrs.get('class', '').split()), None)
        if row is None:
            continue
        tokens = []
        for node in children(row):
            cls = node.attrs.get('class')
            if cls == 'item-flow-separator':
                tokens.append({'kind': 'separator', 'text': node.text()})
            elif cls == 'item-choice-group':
                choices = [lemon_item(n) for n in children(node) if n.attrs.get('class') == 'item-choice-entry']
                tokens.append({'kind': 'choose_one', 'options': choices, 'source_label': node.attrs.get('aria-label')})
            elif cls == 'item-step':
                tokens.append({'kind': 'item', **lemon_item(node)})
            else:
                raise ValueError(f'Unknown LemonNation item token {cls}')
        if group in groups:
            raise ValueError(f'Repeated LemonNation item group {group}')
        groups[group] = tokens
    augments = []
    for node in tree.find(predicate=lambda n: 'augment-entry' in n.attrs.get('class', '').split()):
        image = next(node.find('img', lambda n: '/augments/' in n.attrs.get('src', '')), None)
        native_id = re.search(r'/augments/(\d+)\.png', image.attrs['src']).group(1) if image else None
        bold = next(node.find('b'), None)
        augments.append({'native_id': native_id, 'name': bold.text() if bold else None,
                         'rarity': node.attrs.get('data-rarity'),
                         'priority': node.attrs.get('data-priority') == 'true',
                         'super_tier': node.attrs.get('data-super-tier'), 'review_status': 'unreviewed_editorial'})
    notes = [clean_text(n).strip() for n in tree.find(predicate=lambda n: n.attrs.get('class') == 'build-note')]
    ld = [json.loads(n.text()) for n in tree.find('script', lambda n: n.attrs.get('type') == 'application/ld+json')]
    article = next((r for r in ld if r.get('@type') == 'Article'), {})
    return {'source': 'lemonnation', 'url': url, 'artifact': origin,
            'champion_key': urlparse(url).path.split('/')[-1], 'build_key': parse_qs(urlparse(url).query).get('build', [None])[0],
            'title': (next(tree.find('h1'), None).text() if next(tree.find('h1'), None) else article.get('headline')),
            'date_modified': article.get('dateModified'), 'patch': None,
            'author': article.get('author'), 'intro': article.get('description'), 'groups': groups,
            'augments': augments, 'notes': notes, 'flags': ['editorial_not_win_rate', 'patch_unknown',
                'author_updates_on_hiatus', 'rules_not_verified_in_game']}

def main():
    records = {}
    for path in OUT.rglob('manifest.json'):
        manifest = json.loads(path.read_text('utf8'))
        if not isinstance(manifest.get('records'), dict):
            continue
        for url, record in manifest['records'].items():
            raw_path = path.parent / record['file']
            if hashlib.sha256(raw_path.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError(f'Corrupted archive: {raw_path}')
            records[url] = (raw_path, record)
    item_url = 'https://arammayhem.com/data/v1/latest/items.json'
    item_map = {r['itemId']: int(r['gameItemId']) for r in json.loads(records[item_url][0].read_text('utf8'))['rows'] if r.get('gameItemId')}
    catalog = json.loads((ROOT / 'research/champion-snapshots/champion-catalog.json').read_text('utf8'))['champions']
    champion_ids = {c['key'].lower(): c['id'] for c in catalog}
    fold = lambda text: re.sub(r'[^a-z0-9]', '', text.lower())
    champion_aliases = {fold(c[field]): c['id'] for c in catalog for field in ['name', 'key']}
    output = {'arammayhem': [], 'opgg': [], 'lemonnation': []}
    errors = []
    for url, (path, meta) in sorted(records.items()):
        source = None
        if url.startswith('https://arammayhem.com/build/'):
            source = 'arammayhem'
        elif url.startswith('https://op.gg/lol/modes/') and url.endswith('/items'):
            source = 'opgg'
        elif url.startswith('https://lemonnation.gg/builds/') and '?build=' in url:
            source = 'lemonnation'
        if source is None:
            continue
        origin = {'file': str(path.relative_to(ROOT)), 'sha256': meta['sha256'], 'collected_at': meta['collected_at']}
        tree = Tree(path.read_text('utf8')).root
        try:
            row = arammayhem(tree, url, origin, item_map, champion_ids) if source == 'arammayhem' else (
                opgg(tree, url, origin) if source == 'opgg' else lemon(tree, url, origin))
            if source == 'lemonnation':
                row['champion_id'] = champion_aliases.get(fold(row['champion_key']))
            output[source].append(row)
        except Exception as error:
            errors.append({'source': source, 'url': url, 'error': str(error)})
    for source, rows in output.items():
        write(OUT / 'normalized' / (source + '.json'), {'schema': 'item-source-research-1', 'metric_unit': 'proportion', 'records': rows})
    summary = {'sources': {}, 'parse_errors': errors}
    for source, rows in output.items():
        group_counts = Counter()
        for row in rows:
            group_counts.update({k: len(v) for k, v in row['groups'].items()})
        summary['sources'][source] = {'pages': len(rows), 'group_entries': dict(group_counts),
            'patches': dict(Counter(r.get('patch') for r in rows))}
    summary['sources']['lemonnation']['champions'] = len({r['champion_key'] for r in output['lemonnation']})
    summary['sources']['lemonnation']['augment_recommendations'] = sum(len(r['augments']) for r in output['lemonnation'])
    summary['sources']['lemonnation']['notes'] = sum(len(r['notes']) for r in output['lemonnation'])
    summary['sources']['lemonnation']['choice_groups'] = sum(t['kind'] == 'choose_one' for r in output['lemonnation'] for ts in r['groups'].values() for t in ts)
    summary['unmapped_arammayhem_items'] = sorted({i['native_id'] for r in output['arammayhem'] for rows in r['groups'].values() for row in rows for i in row['items'] if i['game_item_id'] is None})
    summary['unmapped_lemonnation_champions'] = [r['champion_key'] for r in output['lemonnation'] if r['champion_id'] is None]
    write(OUT / 'normalized/coverage.json', summary)
    print(json.dumps({**summary, 'parse_errors': errors[:8], 'parse_error_count': len(errors)}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
