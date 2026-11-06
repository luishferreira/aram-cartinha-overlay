"""Acquire all single-augment resources from the already pinned ARAMKit release.

Resumable, sequential public requests. Nothing is published until all expected
champions have a schema-valid, hashed payload. Does not discover a new patch.
"""
import argparse
import sys
from pathlib import Path
from mayhem_data.common import ROOT, read, atomic_json, digest, now
from mayhem_data.fetch import Http


def collect(root=ROOT):
    records = read(root/'research/aramkit-data/manifest.json')
    bases = {r['url'].split('champion-details/')[0] for r in records}
    if len(bases) != 1:
        raise ValueError('Mixed releases in champion manifest')
    base = bases.pop()
    release = base.split('/data/')[1].split('/')[0]
    workspace = root/'data/intake'/('aramkit-conditionals-'+release)
    workspace.mkdir(parents=True, exist_ok=True)
    http = Http(workspace, resume=True)
    entries = []
    for index, row in enumerate(records, 1):
        cid = row['champion_id']
        target = workspace/'payloads'/f'{cid}.json'
        data, meta = http.json_to(base+f'champion-details/{cid}-single-augments.json', target)
        if not isinstance(data.get('items'), list) or not isinstance(data.get('builds'), list):
            raise ValueError(f'Unexpected conditional resource schema: {cid}')
        if any(not isinstance(g.get('augmentId'), int) for k in ('items','builds') for g in data[k]):
            raise ValueError(f'Missing augment identity: {cid}')
        entries.append({**meta, 'champion_id':cid, 'file':f'{cid}.json'})
        if index % 10 == 0 or index == 1 or index == len(records):
            print(f'ARAMKit conditionals: {index}/{len(records)}, {sum(e["bytes"] for e in entries)/1024**2:.1f} MiB', flush=True)
    # Re-read pinned input to detect a local release change during collection.
    if read(root/'research/aramkit-data/manifest.json') != records:
        raise ValueError('Pinned release manifest changed during collection')
    manifest = {'release':release,'base_url':base,'complete':True,'champions':len(entries),
                'files':entries,'collected_at':now()}
    snapshot = digest([{k:v for k,v in e.items() if k in ('champion_id','sha256')} for e in entries])[:20]
    folder = root/'research/aramkit-data/conditional-snapshots'/snapshot
    folder.mkdir(parents=True, exist_ok=True)
    import shutil
    for entry in entries:
        src=workspace/'payloads'/entry['file']; dst=folder/entry['file']
        if digest(src.read_bytes()) != entry['sha256']:
            raise ValueError(f'Changed payload: {src}')
        if dst.exists() and digest(dst.read_bytes()) != entry['sha256']:
            raise ValueError(f'Immutable snapshot conflict: {dst}')
        if not dst.exists(): shutil.copyfile(src,dst)
    manifest_path=folder/'manifest.json'
    if not manifest_path.exists(): atomic_json(manifest_path, manifest)
    atomic_json(root/'research/aramkit-data/conditionals-current.json',
                {'snapshot':'conditional-snapshots/'+snapshot,'release':release,
                 'manifest_sha256':digest(manifest_path.read_bytes()),'complete':True})
    print({'complete':True,'champions':len(entries),'bytes':sum(e['bytes'] for e in entries),'snapshot':snapshot}, flush=True)


if __name__=='__main__':
    collect()
