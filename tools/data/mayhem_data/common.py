import hashlib
import json
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def now():
    return datetime.now(timezone.utc).isoformat()


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else dumps(value).encode('utf-8')).hexdigest()


def file_digest(path):
    """Hash large published databases with bounded memory."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    write(temp, value)
    os.replace(temp, path)


def normalized_name(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold() if c.isalnum())


def entity_id(kind, native, namespace='game'):
    return f'{kind}:{namespace}:{native}'
