"""Normalize a saved OP.GG Mayhem item archive without accessing the network."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from normalize_item_source_audit import opgg, write, ROOT
from html_tree import Tree


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    folder = parser.parse_args().folder.resolve()
    archive = json.loads((folder/'manifest.json').read_text('utf8'))['records']
    rows, errors = [], []
    for url, meta in sorted(archive.items()):
        path = folder/meta['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta['sha256']:
            raise ValueError('Archive hash mismatch')
        origin = {'file':path.relative_to(ROOT).as_posix(), 'sha256':meta['sha256'],
                  'collected_at':meta['collected_at']}
        try:
            row = opgg(Tree(path.read_text('utf8')).root, url, origin)
            if row['published_modes'] != ['aram_mayhem']:
                raise ValueError('Wrong or missing game mode')
            rows.append(row)
        except (ValueError, KeyError, StopIteration) as error:
            errors.append({'url':url, 'error':str(error)})
    write(folder/'normalized/opgg.json', {'schema':'item-source-research-1',
          'metric_unit':'proportion', 'records':rows})
    summary = {'pages':len(rows), 'patches':dict(Counter(r['patch'] for r in rows)),
               'groups':dict(sum((Counter({k:len(v) for k,v in r['groups'].items()}) for r in rows), Counter())),
               'errors':errors}
    write(folder/'normalized/coverage.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
