"""Locate a verified, self-contained distribution data pack; research stays separate."""
import hashlib
import json
from pathlib import Path
import re


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def load_pack(directory, expected_manifest=None, verify_files=True):
    directory = Path(directory)
    manifest_path = directory/'manifest.json'
    if expected_manifest is not None and file_hash(manifest_path)!=expected_manifest:
        raise ValueError('Runtime data manifest changed')
    manifest = json.loads(manifest_path.read_text('utf8'))
    if manifest['schema_version']!=1 or manifest['kind']!='overlay-runtime-data':
        raise ValueError('Unsupported runtime data pack')
    if not re.fullmatch('[0-9a-f]{24}',manifest['generation']):
        raise ValueError('Invalid runtime generation')
    for name, expected in manifest['files'].items():
        if Path(name).name!=name or not re.fullmatch('[0-9a-f]{64}',expected):
            raise ValueError('Invalid runtime artifact')
        if verify_files and file_hash(directory/name)!=expected:
            raise ValueError('Runtime data file changed: '+name)
    required = {'cards.sqlite3','champions.json','augments-ptbr.json','augments-enus.json','item-sets.json'}
    if manifest.get('version') in ('overlay-data-pack-2','overlay-data-pack-3'):
        required.add('launcher.json')
    if manifest.get('version')=='overlay-data-pack-3':
        required.add('champion-portraits.zip')
    if not required<=manifest['files'].keys():
        raise ValueError('Incomplete runtime data pack')
    return manifest


def active_pack(root, verify_files=True):
    pointer = Path(root)/'data/runtime/current.json'
    if not pointer.exists():
        return None
    value = json.loads(pointer.read_text('utf8'))
    if not re.fullmatch('[0-9a-f]{24}',value['generation']):
        raise ValueError('Invalid runtime generation pointer')
    directory = pointer.parent/'runs'/value['generation']
    manifest = load_pack(directory,value['manifest_sha256'],verify_files)
    if manifest['generation']!=value['generation']:
        raise ValueError('Runtime generation mismatch')
    return directory,manifest


def resource(root, name, fallback):
    pack = active_pack(root,verify_files=False)
    if pack is None:
        return Path(root)/fallback
    directory,manifest = pack
    if name not in manifest['files'] or file_hash(directory/name)!=manifest['files'][name]:
        raise ValueError('Runtime resource changed: '+name)
    return directory/name
