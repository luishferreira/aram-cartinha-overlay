"""Immutable raw archives, validation, SQLite compilation and atomic publication."""
import os
import shutil
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from . import SCHEMA_VERSION
from .adapters import load_all
from .changes import catalog_state, changes, review_queue
from .common import ROOT, atomic_json, digest, file_digest, dumps, entity_id, now, read, write
from .model import SOURCES
from .validation import validate

SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE sources(id TEXT PRIMARY KEY, family TEXT NOT NULL, metadata_json TEXT NOT NULL);
CREATE TABLE snapshots(id TEXT PRIMARY KEY,source TEXT NOT NULL REFERENCES sources(id),metadata_json TEXT NOT NULL);
CREATE TABLE artifacts(sha256 TEXT PRIMARY KEY,archive_path TEXT NOT NULL,bytes INTEGER NOT NULL);
CREATE TABLE artifact_origins(snapshot_id TEXT REFERENCES snapshots(id),sha256 TEXT REFERENCES artifacts(sha256),metadata_json TEXT NOT NULL,PRIMARY KEY(snapshot_id,sha256));
CREATE TABLE entities(id TEXT PRIMARY KEY,kind TEXT NOT NULL,catalog_status TEXT NOT NULL);
CREATE TABLE catalog(id TEXT PRIMARY KEY,snapshot_id TEXT REFERENCES snapshots(id),entity_id TEXT REFERENCES entities(id),native_id TEXT NOT NULL,artifact TEXT REFERENCES artifacts(sha256),names_json TEXT NOT NULL,descriptions_json TEXT NOT NULL,attributes_json TEXT NOT NULL);
CREATE TABLE identity_mappings(source TEXT,native_id TEXT,entity_id TEXT REFERENCES entities(id),method TEXT,evidence_json TEXT,PRIMARY KEY(source,native_id));
CREATE TABLE observations(id TEXT PRIMARY KEY,snapshot_id TEXT REFERENCES snapshots(id),entity_id TEXT REFERENCES entities(id),artifact TEXT REFERENCES artifacts(sha256),scope TEXT NOT NULL,champion_id TEXT,stage TEXT,patch TEXT,stats_date TEXT,context_json TEXT NOT NULL,metrics_json TEXT NOT NULL,flags_json TEXT NOT NULL,selector TEXT);
CREATE TABLE relations(id TEXT PRIMARY KEY,snapshot_id TEXT REFERENCES snapshots(id),champion_id TEXT,kind TEXT,artifact TEXT REFERENCES artifacts(sha256),data_json TEXT NOT NULL);
CREATE TABLE rules(id TEXT PRIMARY KEY,data_json TEXT NOT NULL);
CREATE TABLE patch_notes(id TEXT PRIMARY KEY,snapshot_id TEXT REFERENCES snapshots(id),patch TEXT,artifact TEXT REFERENCES artifacts(sha256),data_json TEXT NOT NULL);
CREATE TABLE change_events(id INTEGER PRIMARY KEY,data_json TEXT NOT NULL);
CREATE TABLE review_queue(id INTEGER PRIMARY KEY,data_json TEXT NOT NULL);
CREATE INDEX observations_lookup ON observations(entity_id,champion_id,scope);
CREATE INDEX observations_champion ON observations(champion_id,scope);
CREATE INDEX observations_snapshot ON observations(snapshot_id);
CREATE INDEX relations_champion ON relations(champion_id);
CREATE INDEX catalog_entity ON catalog(entity_id);
CREATE INDEX catalog_source ON catalog(snapshot_id,native_id);
'''


def entity_universe(batches):
    ids=set()
    for b in batches:
        ids.update(r['entity_id'] for r in b.catalog)
        for row in b.observations:
            ids.add(row['entity_id'])
            c=row['context']
            ids.update(c[k] for k in ('champion_id','augment_id') if c.get(k))
            ids.update(c.get('items',[]))
        for r in b.relations:
            ids.add(r['champion_id']);ids.update(r['augment_ids'])
    return ids


def archive_artifacts(batches, output):
    for batch in batches:
        for sha,meta in batch.artifacts.items():
            dest=output/'raw'/sha[:2]/sha
            if dest.exists():
                if digest(dest.read_bytes())!=sha:raise ValueError(f'Corrupt raw archive {dest}')
            else:
                dest.parent.mkdir(parents=True,exist_ok=True)
                temp=dest.with_suffix('.tmp')
                shutil.copyfile(meta['local_path'],temp)
                if digest(temp.read_bytes())!=sha:raise ValueError('Input changed during archive')
                os.replace(temp,dest)
            meta['archive_path']=dest.relative_to(output).as_posix()


def compile_database(path,batches,identity,rules,events,queue,ids):
    catalog_ids={r['entity_id'] for b in batches for r in b.catalog}
    db=sqlite3.connect(path)
    try:
        db.executescript(SCHEMA)
        db.executemany('INSERT INTO entities VALUES(?,?,?)',
            [(eid,eid.split(':')[0],'known' if eid in catalog_ids else 'unresolved') for eid in sorted(ids)])
        for batch in batches:
            db.execute('INSERT INTO sources VALUES(?,?,?)',(batch.source,SOURCES[batch.source]['family'],dumps(batch.metadata)))
            sid=batch.metadata['snapshot_id']
            db.execute('INSERT INTO snapshots VALUES(?,?,?)',(sid,batch.source,dumps(batch.metadata)))
            for sha,meta in batch.artifacts.items():
                db.execute('INSERT OR IGNORE INTO artifacts VALUES(?,?,?)',(sha,meta['archive_path'],meta['bytes']))
                db.execute('INSERT INTO artifact_origins VALUES(?,?,?)',(sid,sha,dumps(meta)))
            db.executemany('INSERT INTO catalog VALUES(?,?,?,?,?,?,?,?)',
                [(digest([sid,row]),sid,row['entity_id'],row['native_id'],row['artifact'],
                  dumps(row['names']),dumps(row['descriptions']),dumps(row['attributes'])) for row in batch.catalog])
            db.executemany('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                [(digest([sid,row]),sid,row['entity_id'],row['artifact'],row['context']['scope'],
                  row['context'].get('champion_id'),row['context'].get('stage'),row['patch'],row['stats_date'],
                  dumps(row['context']),dumps(row['metrics']),dumps(row['flags']),row['selector']) for row in batch.observations])
            db.executemany('INSERT INTO relations VALUES(?,?,?,?,?,?)',
                [(digest([sid,row['native_id']]),sid,row['champion_id'],row['kind'],row['artifact'],dumps(row)) for row in batch.relations])
            db.executemany('INSERT INTO patch_notes VALUES(?,?,?,?,?)',
                [(digest([sid,note]),sid,note['patch'],note['artifact'],dumps(note)) for note in batch.notes])
        db.executemany('INSERT INTO identity_mappings VALUES(?,?,?,?,?)',
            [(r['source'],r['native_id'],r['entity_id'],r['method'],dumps(r)) for r in identity.mapping_evidence])
        db.executemany('INSERT INTO rules VALUES(?,?)',[(r['id'],dumps(r)) for r in rules])
        db.executemany('INSERT INTO change_events(data_json) VALUES(?)',[(dumps(e),) for e in events])
        db.executemany('INSERT INTO review_queue(data_json) VALUES(?)',[(dumps(e),) for e in queue])
        from .builds import compile_resources
        build_coverage=compile_resources(db,batches)
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('SQLite foreign key check failed')
        return build_coverage
    finally:db.close()


def translation_report(batches):
    locales=defaultdict(set)
    for b in batches:
        for row in b.catalog:locales[row['entity_id']].update(k for k,v in row['names'].items() if v)
    augments={eid for eid in locales if eid.startswith('augment:')}
    return {'augment_entities':len(augments),'with_pt_BR':sum('pt-BR' in locales[eid] for eid in augments),
        'with_en_US':sum('en-US' in locales[eid] for eid in augments),
        'missing_pt_BR':sorted(eid for eid in augments if 'pt-BR' not in locales[eid]),
        'missing_en_US':sorted(eid for eid in augments if 'en-US' not in locales[eid]),
        'fallback_policy':'Requested locale, then en-US, then pt-BR, then native ID. Always report fallback.'}


def verify_run(output, run):
    directory=output/'runs'/run
    manifest=read(directory/'manifest.json')
    for filename,sha in manifest['outputs'].items():
        if file_digest(directory/filename)!=sha:raise ValueError(f'Output hash mismatch: {filename}')
    for artifact in manifest['artifacts'].values():
        path=output/artifact['archive_path']
        if file_digest(path)!=artifact['sha256']:raise ValueError(f'Archive hash mismatch: {path}')
    db=sqlite3.connect(f'file:{(directory/"mayhem.sqlite3").as_posix()}?mode=ro',uri=True)
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('SQLite foreign key check failed')
    finally:db.close()
    return {'run':run,'output_hashes':len(manifest['outputs']),'raw_artifacts':len(manifest['artifacts']),'verified':True}


def build(root=ROOT, output=None):
    root=Path(root);output=Path(output) if output else root/'data/pipeline'
    output.mkdir(parents=True,exist_ok=True)
    if (root/'intake.json').exists() and read(root/'intake.json')['status']!='complete':
        raise ValueError('Intake is incomplete. Resume acquisition; last good publication is unchanged.')
    config=read(root/'data/config/pipeline.json');rules=read(root/'data/config/rules.json')['rules']
    identity,batches=load_all(root)
    batches=[b for b in batches if b.source in config['enabled_sources']]
    if any(b.source in config['excluded_augment_sources'] for b in batches):raise ValueError('Excluded source')
    ids=entity_universe(batches)
    expected=set(identity.champions.values())
    report=validate(batches,expected,rules,ids,config['primary_sources'])
    for row in identity.mapping_evidence:
        if row['method']=='unresolved':report['issues'].append({'source':row['source'],'severity':'warning','code':'unresolved_identity','detail':row})
    report['counts']=dict(Counter(r['severity'] for r in report['issues']))
    if not report['publishable']:
        write(output/'last-failure.json',{'at':now(),'report':report})
        raise ValueError(f'Validation rejected publication: {report["counts"]}. See {output / "last-failure.json"}')
    # Source snapshot identities include metadata and exact input bytes; generated timestamps are not identities.
    for batch in batches:
        batch.metadata['snapshot_id']=batch.source+':'+digest({'metadata':batch.metadata,'artifacts':sorted(batch.artifacts)})[:20]
    code_hash=digest({p.name:digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))})
    run=digest({'schema':SCHEMA_VERSION,'code':code_hash,'config':config,'rules':rules,
                'sources':{b.source:b.metadata['snapshot_id'] for b in batches}})[:24]
    directory=output/'runs'/run
    if (directory/'manifest.json').exists():
        result=verify_run(output,run)
        atomic_json(output/'current.json',{'run':run,'published_at':now(),'schema_version':SCHEMA_VERSION})
        return {**result,'reused':True}
    archive_artifacts(batches,output)
    current=read(output/'current.json') if (output/'current.json').exists() else None
    previous_dir=output/'runs'/current['run'] if current else None
    previous=read(previous_dir/'catalog-state.json') if previous_dir else None
    previous_metadata=read(previous_dir/'source-state.json') if previous_dir else {}
    state=catalog_state(batches);metadata={b.source:b.metadata for b in batches}
    events=changes(previous,state,previous_metadata,metadata)
    queue=review_queue(events,batches,rules)
    # A new build or a spelling edit must not silently approve an invalidated rule.
    rule_versions={r['id']:r.get('review_revision',0) for r in rules}
    for entry in queue:
        if entry['target']=='rule':entry['review_revision_when_flagged']=rule_versions[entry['id']]
    if previous_dir:
        for entry in read(previous_dir/'review-queue.json'):
            if entry['target']=='rule' and entry['id'] in rule_versions and rule_versions[entry['id']]<=entry.get('review_revision_when_flagged',0):
                if not any(r.get('id')==entry['id'] and r['target']=='rule' for r in queue):queue.append(entry)
    blocked_rules={r['id'] for r in queue if r['target']=='rule'}
    rules=[{**r,'pending_review':r['id'] in blocked_rules} for r in rules]
    # Patch-note changes signal review, not automatic mechanical edits or official authority.
    note_state={b.source:[digest(n) for n in b.notes] for b in batches}
    previous_notes=read(previous_dir/'note-state.json') if previous_dir else {}
    for source,notes in note_state.items():
        if previous_dir and previous_notes.get(source)!=notes:
            events.append({'kind':'patch_notes_changed','source':source,'requires_review':True})
            queue.append({'target':'patch_notes','source':source,'reason':'Changed third-party summary; check primary notes.'})
    directory.mkdir(parents=True,exist_ok=False)
    try:
        report['builds']=compile_database(directory/'mayhem.sqlite3',batches,identity,rules,events,queue,ids)
        report['translations']=translation_report(batches)
        report['identity_mappings']={'total':len(identity.mapping_evidence),
            'unresolved':sum(r['method']=='unresolved' for r in identity.mapping_evidence)}
        report['same_family_channels_count_as_one_source']=True
        report['source_patch_aliases']=config['patch_aliases']
        write(directory/'report.json',report)
        write(directory/'catalog-state.json',state)
        write(directory/'source-state.json',metadata)
        write(directory/'note-state.json',note_state)
        write(directory/'changes.json',events)
        write(directory/'review-queue.json',queue)
        write(directory/'identity-mappings.json',identity.mapping_evidence)
        write(directory/'config.json',config)
        from .analysis import analyze
        analyze(directory,identity.mapping_evidence)
        artifacts={sha:meta for batch in batches for sha,meta in batch.artifacts.items()}
        manifest={'schema_version':SCHEMA_VERSION,'run':run,'created_at':now(),
            'parent_run':current['run'] if current else None,'code_hash':code_hash,
            'sources':metadata,'artifacts':artifacts,
            'outputs':{p.name:file_digest(p) for p in directory.iterdir() if p.is_file()}}
        write(directory/'manifest.json',manifest)
        result=verify_run(output,run)
    except Exception:
        # Keep diagnostic staging evidence. It is never published and cannot replace the last good version.
        write(directory/'FAILED.json',{'at':now(),'published':False})
        raise
    atomic_json(output/'current.json',{'run':run,'published_at':now(),'schema_version':SCHEMA_VERSION})
    return {**result,'sources':{b.source:len(b.observations) for b in batches},
        'entities':len(ids),'relations':sum(len(b.relations) for b in batches),
        'changes':len(events),'review_queue':len(queue),'warnings':report['counts'].get('warning',0)}
