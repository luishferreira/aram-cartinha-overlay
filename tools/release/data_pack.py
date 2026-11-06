"""Compile and validate the data actually queried by today's overlay, without network."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile

from tools.items.static_sets import ROOT, encode, load_export
from tools.live.data_paths import active_pack, file_hash, load_pack
from tools.live.source_cards import SourceReader, panel_rows, combo_rows

VERSION = 'overlay-data-pack-1'
TABLES = ('sources','snapshots','artifacts','entities','catalog','observations','relations')
INDEXES = ('observations_lookup','observations_champion','catalog_entity','relations_champion')


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def connect(path):
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db


def keep_observation(row):
    # The popularity ranking reads all OP.GG champion rows, even if hidden in the panel.
    if row['source']=='opgg' and row['scope']=='champion':
        return True
    context,flags = json.loads(row['context_json']),json.loads(row['flags_json'])
    if context.get('series')=='historical' or any('historical' in f for f in flags):
        return False
    if row['scope']=='champion':
        rarity = row['source']=='arammayhem' and context.get('ranking_scope')=='rarity'
        if (context.get('ranking_scope') and not rarity) or context.get('stage') not in (None,'all'):
            return False
    return True


def source_rows(db, table):
    if table=='observations':
        rows = db.execute('SELECT o.*,s.source FROM observations o JOIN snapshots s ON s.id=o.snapshot_id '
            'WHERE o.entity_id LIKE "augment:game:%" AND (o.champion_id IS NOT NULL OR o.scope="global") ORDER BY o.id')
        for row in rows:
            if keep_observation(row):
                yield tuple(row)[:-1]
    elif table=='relations':
        for row in db.execute('SELECT r.* FROM relations r JOIN snapshots s ON s.id=r.snapshot_id '
            'WHERE (s.source="arammayhem" AND r.kind="editorial_bundle") OR '
            '(s.source IN ("aramkit","aramgg") AND r.kind IN ("observed_pair","observed_trio")) ORDER BY r.id'):
            yield tuple(row)
    else:
        yield from (tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY 1'))


def row_digest(rows):
    digest,count = hashlib.sha256(),0
    for row in rows:
        digest.update(encode(list(row)))
        count += 1
    return count,digest.hexdigest()


def compile_database(source, destination):
    db = sqlite3.connect(destination)
    counts = {}
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA user_version=1')
        for table in TABLES:
            ddl = source.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name=?',(table,)).fetchone()[0]
            db.execute(ddl)
            columns = len(source.execute('PRAGMA table_info('+table+')').fetchall())
            count = 0
            def rows():
                nonlocal count
                for row in source_rows(source,table):
                    count += 1
                    yield row
            db.executemany('INSERT INTO '+table+' VALUES('+','.join('?' for _ in range(columns))+')',rows())
            counts[table] = count
        for index in INDEXES:
            db.execute(source.execute('SELECT sql FROM sqlite_master WHERE name=?',(index,)).fetchone()[0])
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Invalid compact SQLite')
    finally:
        db.close()
    return counts


def compare(root, folder, source=None):
    """Compare all retained records plus rendered/contextual reads across every champion."""
    original = SourceReader(root)
    compact = SourceReader(root,runtime_directory=folder)
    source = source or original.db
    try:
        tables = {}
        for table in TABLES:
            expected = row_digest(source_rows(source,table))
            actual = row_digest(compact.db.execute('SELECT * FROM '+table+' ORDER BY 1'))
            if expected!=actual:
                raise ValueError('Runtime records differ: '+table)
            tables[table] = {'rows':expected[0],'ordered_rows_sha256':expected[1]}
        cases = set()
        champions = {c['id'] for c in read(folder/'champions.json')['champions']}
        augments = {int(e.rsplit(':',1)[1]) for (e,) in original.db.execute(
            'SELECT DISTINCT entity_id FROM catalog WHERE entity_id LIKE "augment:game:%"')}
        # Every published champion, with present and missing data, as well as all no-champion cases.
        for champion in champions:
            row = original.db.execute('SELECT entity_id FROM observations WHERE champion_id=? '
                'AND entity_id LIKE "augment:game:%" ORDER BY id LIMIT 1',(f'champion:game:{champion}',)).fetchone()
            if row:
                cases.add((champion,int(row[0].rsplit(':',1)[1]),()))
            cases.add((champion,999999,()))
        for card in augments:
            cases.add((None,card,()))
        # Exercise every native member of every copied editorial/observed relation, with partial/full context.
        for row in compact.db.execute('SELECT champion_id,data_json FROM relations ORDER BY id'):
            relation = json.loads(row['data_json'])
            members = relation.get('augment_ids',[])
            if not row['champion_id'] or not row['champion_id'].startswith('champion:game:'):
                continue
            champion = int(row['champion_id'].rsplit(':',1)[1])
            native = [int(m.rsplit(':',1)[1]) for m in members if m.startswith('augment:game:')]
            for card in native:
                others = tuple(sorted(m for m in native if m!=card))
                for selected in ((),others[:1],others):
                    cases.add((champion,card,selected))
        output_hash = hashlib.sha256()
        for champion,card,selected in sorted(cases,key=lambda c:(c[0] or 0,c[1],c[2])):
            expected = original.read(champion,card,selected)
            actual = compact.read(champion,card,selected)
            if expected!=actual or panel_rows(expected)!=panel_rows(actual) or combo_rows(expected)!=combo_rows(actual):
                raise ValueError(f'Runtime response differs: {champion}/{card}/{selected}')
            output_hash.update(encode(expected))
        for entity, in original.db.execute('SELECT DISTINCT entity_id FROM catalog ORDER BY entity_id'):
            if original.label(entity)!=compact.label(entity):
                raise ValueError('Runtime label changed: '+entity)
        return {'verified':True,'tables':tables,'champions':len(champions),'response_cases':len(cases),
                'responses_sha256':output_hash.hexdigest(),'languages':['pt-BR','en-US'],
                'scope':'all_retained_rows; all_champions; all_relation_native_members_with_empty_partial_full_context'}
    finally:
        compact.close()
        original.close()


def make_zip(folder, destination):
    manifest = load_pack(folder)
    names = sorted(manifest['files'])+['manifest.json']
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in names:
            info = zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with (folder/name).open('rb') as source,archive.open(info,'w',force_zip64=True) as target:
                shutil.copyfileobj(source,target,1024*1024)


def build(root=ROOT):
    root = Path(root).resolve()
    run = read(root/'data/pipeline/current.json')['run']
    if len(run)!=24 or any(c not in '0123456789abcdef' for c in run):
        raise ValueError('Invalid source data run')
    source_folder = root/'data/pipeline/runs'/run
    source_manifest = read(source_folder/'manifest.json')
    source_path = source_folder/'mayhem.sqlite3'
    original_hash = file_hash(source_path)
    if original_hash!=source_manifest['outputs']['mayhem.sqlite3']:
        raise ValueError('Research database differs from its source manifest')
    bundle,item_manifest = load_export(root,runtime=False)
    # Do not ship local logs/backups, full source manifests, archives or classifier development artifacts.
    output = root/'data/runtime'
    staging = output/'staging'
    staging.mkdir(parents=True,exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='data-',dir=staging)).resolve()
    if not temp.is_relative_to(output.resolve()):
        raise ValueError('Invalid staging directory')
    source = connect(source_path)
    try:
        counts = compile_database(source,temp/'cards.sqlite3')
        inputs = {'champions.json':'research/champion-snapshots/champion-catalog.json',
                  'augments-ptbr.json':'research/public-snapshots/opgg-augments-ptbr.json',
                  'augments-enus.json':'research/public-snapshots/opgg-augments-enus.json'}
        for name,relative in inputs.items():
            shutil.copyfile(root/relative,temp/name)
        # Strip the loader's transient field; the generated item set data is otherwise unchanged.
        native_bundle = {k:v for k,v in bundle.items() if k!='generation'}
        (temp/'item-sets.json').write_bytes(encode(native_bundle))
        files = {p.name:file_hash(p) for p in sorted(temp.iterdir())}
        identity = {'version':VERSION,'data_run':run,'source_sqlite_sha256':original_hash,
                    'source_manifest_sha256':file_hash(source_folder/'manifest.json'),
                    'item_sets_generation':item_manifest['generation'],'files':files}
        generation = hashlib.sha256(encode(identity)).hexdigest()[:24]
        manifest = {'schema_version':1,'kind':'overlay-runtime-data','generation':generation,**identity,
                    'champions':len({c['id'] for c in read(temp/'champions.json')['champions']}),
                    'source_metadata':{k:source_manifest[k] for k in ('run','created_at','sources')},
                    'rows':counts,'excluded_tables':['build_profiles','conditional_item_groups','identity_mappings',
                        'artifact_origins','patch_notes','rules','review_queue','change_events'],
                    'bytes':{p.name:p.stat().st_size for p in temp.iterdir()}}
        (temp/'manifest.json').write_bytes(encode(manifest))
        validation = compare(root,temp,source)
        if file_hash(source_path)!=original_hash:
            raise ValueError('Research database changed during runtime export')
    finally:
        source.close()
    directory = output/'runs'/generation
    directory.parent.mkdir(parents=True,exist_ok=True)
    if directory.exists():
        for name in [*files,'manifest.json']:
            if file_hash(directory/name)!=file_hash(temp/name):
                raise ValueError('Immutable runtime generation differs')
        # Only this freshly generated staging directory is removed, after the workspace check above.
        shutil.rmtree(temp)
    else:
        temp.rename(directory)
    downloads = output/'downloads'
    downloads.mkdir(exist_ok=True)
    archive = downloads/f'data-{generation}.zip'
    make_zip(directory,archive.with_suffix('.tmp'))
    archive.with_suffix('.tmp').replace(archive)
    report = {**validation,'generation':generation,'source_bytes':source_path.stat().st_size,
        'sqlite_bytes':(directory/'cards.sqlite3').stat().st_size,'data_files_bytes':sum(manifest['bytes'].values()),
        'zip_bytes':archive.stat().st_size,'zip_sha256':file_hash(archive),'source_database_unchanged':True}
    (output/'reports').mkdir(exist_ok=True)
    (output/'reports'/f'{generation}.json').write_bytes(encode(report))
    pointer = output/'current.json'
    temporary = pointer.with_suffix('.tmp')
    temporary.write_bytes(encode({'generation':generation,'manifest_sha256':file_hash(directory/'manifest.json')}))
    temporary.replace(pointer)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['build','verify'])
    args = parser.parse_args()
    if args.command=='build':
        result = build()
    else:
        pack = active_pack(ROOT)
        if pack is None:
            raise ValueError('No runtime data pack')
        folder,manifest = pack
        result = compare(ROOT,folder)
        result['generation'] = manifest['generation']
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()
