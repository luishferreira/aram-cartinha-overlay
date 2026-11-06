"""Build a versioned, reviewable offline classifier release. No LCU or overlay writes."""
import argparse
from collections import Counter, defaultdict
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3

from tools.items.classification import VERSION, POLICY, Classifier, significant, signature

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'research/item-sources/2026-11-06'
PATH_LABELS = {'ad':'AD', 'ap':'AP', 'bruiser':'Lutador', 'crit':'Crítico', 'hybrid':'Híbrido',
               'lethality':'Letalidade', 'on_hit':'On-hit', 'tank':'Tanque', 'utility':'Utilidade'}


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def load_training(root=ROOT):
    run = read(root / 'data/pipeline/current.json')['run']
    if len(run) != 24 or any(c not in '0123456789abcdef' for c in run):
        raise ValueError('Invalid active run')
    folder = root / 'data/pipeline/runs' / run
    db = sqlite3.connect((folder / 'mayhem.sqlite3').resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    try:
        profiles = [{'id': r['id'], 'champion_id': int(r['champion_id'].rsplit(':', 1)[1]),
                     'path': r['archetype'], 'items': json.loads(r['item_set_json']),
                     'patch': r['patch'], 'artifact': r['artifact'], 'selector': r['selector']}
                    for r in db.execute("SELECT * FROM build_profiles WHERE augment_id IS NULL AND selection='filtered' ORDER BY id")]
        catalog = {}
        for row in db.execute("SELECT c.*,s.source,s.metadata_json FROM catalog c JOIN snapshots s ON s.id=c.snapshot_id WHERE c.entity_id LIKE 'item:game:%' ORDER BY s.source,c.id"):
            ident = row['entity_id'].rsplit(':', 1)[1]
            target = catalog.setdefault(ident, {'origins': []})
            attrs = json.loads(row['attributes_json'])
            if row['source'] == 'aramgg':
                target.update({k: attrs[k] for k in ['categories', 'components', 'upgrades', 'cost'] if k in attrs})
            elif row['source'] == 'arammayhem':
                target['category'] = attrs.get('category')
                if 'cost' not in target:
                    target['cost'] = attrs.get('cost')
            target['name'] = json.loads(row['names_json']).get('pt-BR') or json.loads(row['names_json']).get('en-US') or target.get('name')
            target['origins'].append({'source': row['source'], 'artifact': row['artifact']})
        return {'data_run': run, 'data_manifest_sha256': hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest(),
                'profiles': profiles, 'item_catalog': catalog}
    finally:
        db.close()


def records_from_audit(folder=AUDIT):
    records, origins = [], {}
    for source in ['arammayhem', 'opgg', 'lemonnation']:
        file = folder / 'normalized' / (source + '.json')
        origins[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
        for page in read(file)['records']:
            if source == 'arammayhem':
                options = page['groups']['core']
                for option in options:
                    records.append({'source': source, 'champion_id': page['champion_id'], 'url': page['url'],
                        'patch': page['patch'], 'source_option': option['source_position'],
                        'items': [i['game_item_id'] for i in option['items']], 'source_record': {'page_context': {k: v for k, v in page.items() if k != 'groups'}, 'option': copy.deepcopy(option)}})
            elif source == 'opgg':
                if page['published_modes'] != ['aram_mayhem']:
                    continue
                champion = page['url'].split('/')[-2]
                # Match native champion keys against the audit's 173 known identities.
                identities = {p['champion_key']: p['champion_id'] for p in read(folder/'normalized/arammayhem.json')['records']}
                for option in page['groups']['core']:
                    records.append({'source': source, 'champion_id': identities[champion], 'url': page['url'],
                        'patch': page['patch'], 'source_option': option['source_position'], 'items': option['item_ids'],
                        'source_record': {'page_context': {k: v for k, v in page.items() if k != 'groups'}, 'option': copy.deepcopy(option)}})
            else:
                # Editorial flows contain choices and conditional branches. Do not fabricate combinations.
                for title, tokens in page['groups'].items():
                    if title in {'Start', 'Boots', 'Options'}:
                        continue
                    mandatory = [t['game_item_id'] for t in tokens if t['kind'] == 'item']
                    choices = any(t['kind'] == 'choose_one' for t in tokens)
                    records.append({'source': source, 'champion_id': page['champion_id'], 'url': page['url'],
                        'patch': None, 'source_option': title, 'items': mandatory,
                        'partial_editorial_core': choices, 'source_record': {'page_context': {k:v for k,v in page.items() if k != 'groups'}, 'tokens': copy.deepcopy(tokens)}})
    for row in records:
        row['id'] = digest([row['source'], row['url'], row['source_option']])
    return sorted(records, key=lambda r: r['id']), origins


def evaluate(training):
    """Five folds grouped globally by unordered significant core, including all labels."""
    profiles, catalog = training['profiles'], training['item_catalog']
    cases = {}
    for row in profiles:
        core, _, _ = significant(row['items'], catalog)
        if len(core) < POLICY['minimum_core_items']:
            continue
        key = row['champion_id'], signature(core)
        entry = cases.setdefault(key, {'champion_id': row['champion_id'], 'items': sorted(core), 'labels': set()})
        entry['labels'].add(row['path'])
    def fold(items):
        core, _, _ = significant(items, catalog)
        return int(hashlib.sha256(signature(core).encode()).hexdigest()[:8], 16) % 5
    predictions = []
    for index in range(5):
        train = [p for p in profiles if fold(p['items']) != index]
        model = Classifier(train, catalog)
        held_cores = {signature(significant(p['items'], catalog)[0]) for p in profiles if fold(p['items']) == index}
        assert not held_cores.intersection(signature(p['core']) for p in model.profiles)
        for case in cases.values():
            if fold(case['items']) != index:
                continue
            result = model.classify(case['champion_id'], case['items'])
            predicted, truth = set(result['assignments']), case['labels']
            predictions.append({'champion_id': case['champion_id'], 'items': case['items'], 'truth': sorted(truth),
                'fold': index, 'status': result['status'], 'confidence': result['confidence'],
                'assignments': sorted(predicted), 'compatible_paths': result['compatible_paths'],
                'correct_when_assigned': bool(predicted) and predicted <= truth,
                'truth_in_compatible_paths': bool(truth.intersection(result['compatible_paths']))})
    def summary(rows):
        assigned = [r for r in rows if r['assignments']]
        correct = sum(r['correct_when_assigned'] for r in assigned)
        return {'cases': len(rows), 'assigned': len(assigned), 'correct_assigned': correct,
                'coverage': len(assigned)/len(rows) if rows else 0,
                'agreement_when_assigned': correct/len(assigned) if assigned else None,
                'cases_with_compatible_paths': sum(bool(r['compatible_paths']) for r in rows),
                'truth_in_compatible_paths': sum(r['truth_in_compatible_paths'] for r in rows),
                'status_counts': dict(Counter(r['status'] for r in rows))}
    return {'method': '5_fold_global_unordered_core_groups', 'reference': 'aramkit_labels_not_independent_game_truth',
        'policy_frozen_before_evaluation': POLICY, 'overall': summary(predictions),
        'by_confidence': {c: summary([r for r in predictions if r['confidence'] == c]) for c in ['high','medium','ambiguous','insufficient']},
        'by_path': {p: summary([r for r in predictions if p in r['truth']]) for p in sorted({p['path'] for p in profiles})},
        'predictions': predictions}


def review_files(results, training, summary):
    """Readable source-separated rows; no metrics reinterpreted as pathway statistics."""
    catalog = training['item_catalog']
    output = io.StringIO(newline='')
    fields = ['champion_id','source','source_option','status','confidence','assigned_paths',
              'compatible_paths','items','top_similarity','reference_profile_id','source_url']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    lines = ['# Classificação automática de núcleos', '',
             f'Release: {summary["release"]}. Apenas pesquisa offline; nenhuma importação no cliente.', '',
             'Os rótulos descrevem o caminho, não a força. Compatibilidades ambíguas não são atribuições definitivas.', '',
             '| Fonte | Núcleos/blocos | Classificados | Ambíguos | Sem classificação |',
             '| --- | ---: | ---: | ---: | ---: |']
    for source, data in summary['by_source'].items():
        status = data['statuses']
        lines.append(f'| {source} | {data["records"]} | {status.get("assigned",0)} | {status.get("ambiguous",0)} | {status.get("unclassified",0)} |')
    validation = summary['validation']['overall']
    lines += ['', f'Validação: {validation["correct_assigned"]}/{validation["assigned"]} atribuições únicas concordam com os rótulos de referência '
              f'({validation["agreement_when_assigned"]:.2%}), cobrindo {validation["assigned"]}/{validation["cases"]} casos '
              f'({validation["coverage"]:.2%}). Isto não mede verdade independente em partidas.', '',
              'Alta confiança significa correspondência próxima/exata ao catálogo de referência. A validação com núcleos inteiros ocultos '
              'não produziu casos nessa faixa; sua precisão externa não foi estimada.', '']
    current_champion = None
    for row in sorted(results, key=lambda r: (r['champion_id'], r['source'], str(r['source_option']))):
        result = row['classification']
        if row['champion_id'] != current_champion:
            current_champion = row['champion_id']
            lines += [f'## Campeão {current_champion}', '',
                      '| Fonte/opção | Itens originais | Resultado | Confiança |', '| --- | --- | --- | --- |']
        names = [catalog.get(str(i), {}).get('name') or str(i) for i in row['items']]
        assigned = ', '.join(PATH_LABELS.get(p,p) for p in result['assignments'])
        compatible = ', '.join(PATH_LABELS.get(p,p) for p in result['compatible_paths'])
        label = assigned or ('Ambíguo: '+compatible if compatible else 'Sem classificação')
        names_text = ' → '.join(names)
        if row.get('partial_editorial_core'):
            names_text += ' (apenas itens obrigatórios; alternativas preservadas no JSON)'
        safe = lambda value: str(value).replace('|','/').replace('\n',' ')
        lines.append(f'| [{safe(row["source"])} · {safe(row["source_option"])}]({row["url"]}) | {safe(names_text)} | {label} | {result["confidence"]} |')
        top = result['candidates'][0] if result['candidates'] else {}
        writer.writerow({'champion_id': row['champion_id'], 'source':row['source'], 'source_option':row['source_option'],
            'status':result['status'], 'confidence':result['confidence'], 'assigned_paths':';'.join(result['assignments']),
            'compatible_paths':';'.join(result['compatible_paths']), 'items':';'.join(map(str,row['items'])),
            'top_similarity':top.get('similarity'), 'reference_profile_id':top.get('reference_profile_id'), 'source_url':row['url']})
    return {'review.md': ('\n'.join(lines)+'\n').encode('utf8'), 'classifications.csv': output.getvalue().encode('utf8')}


def classify_record(model, source):
    row = copy.deepcopy(source)
    row['classification'] = model.classify(row['champion_id'], row['items'], row['patch'])
    if row.get('partial_editorial_core'):
        row['classification']['flags'].append('editorial_choices_preserved_only_mandatory_items_classified')
    if row['source'] == 'lemonnation':
        row['classification']['flags'].extend(['editorial_unreviewed', 'source_patch_unknown'])
    row['metrics_scope_changed'] = False
    assert row['source_record'] == source['source_record']
    return row


def publish(root=ROOT, audit=AUDIT):
    training = load_training(root)
    inputs, origins = records_from_audit(audit)
    model = Classifier(training['profiles'], training['item_catalog'])
    results = [classify_record(model, source) for source in inputs]
    validation = evaluate(training)
    code_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   [ROOT/'tools/items/classification.py', ROOT/'tools/items/classification_cli.py']}
    release = digest({'version': VERSION, 'policy': POLICY, 'training': training, 'sources': origins, 'code': code_hashes})[:24]
    directory = root / 'data/build-classification/runs' / release
    summary = {'version': VERSION, 'release': release, 'training_profiles': len(training['profiles']),
        'unique_prototypes': len(model.profiles), 'champions': len(model.by_champion),
        'paths': len({(p['champion_id'],p['path']) for p in training['profiles']}),
        'input_records': len(results), 'by_source': {}, 'validation': {k:v for k,v in validation.items() if k != 'predictions'},
        'production_integration': False}
    for source in sorted({r['source'] for r in results}):
        subset = [r for r in results if r['source'] == source]
        summary['by_source'][source] = {'records': len(subset), 'statuses': dict(Counter(r['classification']['status'] for r in subset)),
            'confidences': dict(Counter(r['classification']['confidence'] for r in subset))}
    payloads = {'model.json': {'version': VERSION, 'policy': POLICY, **training},
                'classifications.json': {'version': VERSION, 'release': release, 'records': results},
                'validation.json': validation, 'summary.json': summary}
    blobs = {name: encoded(value) for name,value in payloads.items()}
    blobs.update(review_files(results, training, summary))
    for name, data in blobs.items():
        path = directory / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError('Existing classifier release differs; bump version rather than overwrite')
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    manifest = {'release': release, 'version': VERSION, 'source_files': origins, 'code_files': code_hashes,
                'files': {n: hashlib.sha256((directory/n).read_bytes()).hexdigest() for n in blobs},
                'notes': ['offline_research_only', 'no_win_rate_or_popularity_in_classification',
                          'no_synthetic_sequences', 'no_general_item_stats_relabelled_as_path_stats']}
    write(directory / 'manifest.json', manifest)
    write(root / 'data/build-classification/current.json', {'release': release, 'version': VERSION,
          'manifest_sha256': hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(), 'production_integration': False})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'inspect', 'verify', 'replay'])
    parser.add_argument('--champion', type=int)
    args = parser.parse_args()
    if args.command == 'build':
        result = publish()
    else:
        pointer = read(ROOT / 'data/build-classification/current.json')
        release = pointer['release']
        if len(release) != 24 or any(c not in '0123456789abcdef' for c in release):
            raise ValueError('Invalid classifier release')
        directory = ROOT / 'data/build-classification/runs' / release
        if hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest() != pointer['manifest_sha256']:
            raise ValueError('Classifier manifest mismatch')
        manifest = read(directory/'manifest.json')
        for name, expected in manifest['files'].items():
            if Path(name).name != name or hashlib.sha256((directory/name).read_bytes()).hexdigest() != expected:
                raise ValueError('Classifier artifact mismatch')
        result = {'verified': True, 'release': release, 'files': len(manifest['files'])}
        if args.command == 'replay':
            saved = read(directory/'model.json')
            if saved['version'] != VERSION or saved['policy'] != POLICY:
                raise ValueError('Replay requires the saved classifier version and policy')
            for name, expected in manifest['code_files'].items():
                if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
                    raise ValueError('Replay requires the recorded source code')
            model = Classifier(saved['profiles'],saved['item_catalog'],saved['policy'])
            rows = read(directory/'classifications.json')['records']
            if [classify_record(model,row) for row in rows] != rows:
                raise ValueError('Replayed classifications differ')
            if evaluate(saved) != read(directory/'validation.json'):
                raise ValueError('Replayed validation differs')
            result['replayed_classifications'] = len(rows)
            result['replayed_validation'] = True
        if args.command == 'inspect':
            if args.champion:
                result = [{'source':r['source'], 'option':r['source_option'], 'items':r['items'],
                           'classification':r['classification']} for r in read(directory/'classifications.json')['records'] if r['champion_id'] == args.champion]
            else:
                result = read(directory/'summary.json')
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
