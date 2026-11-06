"""Build offline research indexes, without changing the original downloads.

Run sync_arammayhem.py --verify first. Uses only Python's standard library.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/sources/arammayhem'
IDS = {'champions': 'championId', 'augments': 'augmentId',
       'combos': 'comboId', 'items': 'itemId'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    pointer = read(SOURCE / 'current.json')
    snapshot = SOURCE / pointer['snapshot']
    out = ROOT / 'data/derived/arammayhem' / snapshot.name
    datasets = {name: read(snapshot / 'latest' / f'{name}.json') for name in IDS}
    rows = {name: data['rows'] for name, data in datasets.items()}
    errors = []
    pairs = 0
    # Every JSON/CSV pair must identify exactly the same entities, not just counts.
    for path in sorted(snapshot.rglob('*.json')):
        if path.stem not in IDS or not path.with_suffix('.csv').exists():
            continue
        data = read(path)
        key = IDS[path.stem]
        json_ids = [str(row[key]) for row in data['rows']]
        with path.with_suffix('.csv').open(encoding='utf-8-sig', newline='') as handle:
            csv_ids = [row[key] for row in csv.DictReader(handle)]
        if len(json_ids) != len(set(json_ids)):
            errors.append(f'Duplicate IDs: {path.relative_to(snapshot)}')
        if Counter(json_ids) != Counter(csv_ids):
            errors.append(f'JSON/CSV ID mismatch: {path.relative_to(snapshot)}')
        for row in data['rows']:
            rate = row.get('pickRate')
            if rate is not None and not 0 <= rate <= 100:
                errors.append(f'Invalid pickRate: {path.relative_to(snapshot)}:{row[key]}')
        pairs += 1
    by_champion, by_augment = defaultdict(list), defaultdict(list)
    champion_ids = {r['championId'] for r in rows['champions']}
    augment_ids = {r['augmentId'] for r in rows['augments']}
    orphan_champions, orphan_augments = set(), set()
    for combo in rows['combos']:
        by_champion[combo['championId']].append(combo['comboId'])
        if combo['championId'] not in champion_ids:
            orphan_champions.add(combo['championId'])
        for augment in combo['augmentIds']:
            by_augment[augment].append(combo['comboId'])
            if augment not in augment_ids:
                orphan_augments.add(augment)
    history = defaultdict(lambda: defaultdict(list))
    for folder in sorted((snapshot / 'history').iterdir()):
        for name in ('champions', 'augments'):
            data = read(folder / f'{name}.json')
            for row in data['rows']:
                history[name][row[IDS[name]]].append({
                    'patch': data['meta'].get('patch'),
                    'statsDate': data['meta'].get('statsDate'),
                    'statsDateSource': data['meta'].get('statsDateSource'),
                    'pickRatePercent': row.get('pickRate'),
                    'pickRateRank': row.get('pickRateRank'),
                })
    audit = {
        'counts': {name: len(value) for name, value in rows.items()},
        'validatedJsonCsvPairs': pairs,
        'errors': errors,
        'championsWithCombos': len(by_champion),
        'championsWithoutCombos': sorted(champion_ids - set(by_champion)),
        'augmentsReferencedByCombos': len(by_augment),
        'augmentsWithoutCombos': sorted(augment_ids - set(by_augment)),
        'orphanComboChampionIds': sorted(orphan_champions),
        'orphanComboAugmentIds': sorted(orphan_augments),
        'comboAugmentCountDistribution': dict(Counter(len(r['augmentIds']) for r in rows['combos'])),
        'editorialTagCounts': dict(Counter(tag for r in rows['combos'] for tag in r['types'])),
        'augmentRarities': dict(Counter(r['rarity'] for r in rows['augments'])),
        'augmentsWithRetiredPatch': [r['augmentId'] for r in rows['augments'] if r.get('retiredPatch')],
        'itemsWithoutGameItemId': [r['itemId'] for r in rows['items'] if not r.get('gameItemId')],
        'itemsWithoutCost': [r['itemId'] for r in rows['items'] if r.get('cost') is None],
        'nameLocales': sorted(set().union(*(r['name'].keys() for r in rows['augments']))),
        'historyPatchCount': len(list((snapshot / 'history').iterdir())),
    }
    provenance = {
        'source': 'https://arammayhem.com/data/',
        'attribution': 'Data: arammayhem.com',
        'license': 'CC BY 4.0',
        'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
        'sourceSnapshot': snapshot.relative_to(ROOT).as_posix(),
        'releaseId': pointer['release_id'],
        'transformations': 'ID dictionaries, reverse combo indexes, historical series and coverage audit. Original values retained.',
        'semantics': {
            'pickRate': 'Percent, not fraction. Augment denominator not specified by the publisher; do not assume offered-choice rate.',
            'pickRateChange': 'Percentage points, not relative percent.',
            'combos': 'Editorial tags, not measured synergy or win rate. No per-combo patch/date provided.',
            'missingCombo': 'Unknown, not negative synergy.',
            'identifiers': 'Namespaced source IDs. Augment IDs are not Riot numeric IDs.',
            'history': 'Preserve statsDateSource: estimated is not a verified measurement date.',
        },
    }
    write(out / 'catalog.json', {
        'provenance': provenance,
        'datasetMetadata': {name: data['meta'] for name, data in datasets.items()},
        **{name: {str(r[IDS[name]]): r for r in value} for name, value in rows.items()},
    })
    write(out / 'combo-index.json', {'provenance': provenance,
        'byChampion': dict(sorted(by_champion.items())),
        'byAugment': dict(sorted(by_augment.items()))})
    write(out / 'popularity-history.json', {'provenance': provenance, 'series': history})
    write(out / 'audit.json', audit)
    write(out / 'provenance.json', provenance)
    if errors:
        raise SystemExit(json.dumps(errors))
    write(out.parent / 'current.json', {'snapshot': out.name, 'release_id': pointer['release_id']})
    print(json.dumps(audit, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
