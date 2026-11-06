"""Summarize preserved MCP probes offline; no inferred game mechanics."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(__file__).parent / 'arammayhem-mcp/complement-2026-10-30'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def structured(path):
    result = load(path)['result']
    return result.get('structuredContent') or json.loads(result['content'][0]['text'])


def main():
    manifest = load(BASE / 'manifest.json')
    for entry in manifest['files']:
        assert hashlib.sha256((BASE / entry['file']).read_bytes()).hexdigest() == entry['sha256']
        assert not entry['isError'] and not entry['rpcError'], entry
    derived = ROOT / 'data/derived/arammayhem'
    catalog = load(derived / load(derived / 'current.json')['snapshot'] / 'catalog.json')
    entries = [row for f in sorted(BASE.glob('tiers-*.json')) for row in structured(f)['entries']]
    unique = {r['championId'] for r in entries}
    assert len(entries) == len(unique) == 173
    matches = sum(float(e['pickRate'].rstrip('%')) == catalog['champions'][e['championId']]['pickRate'] for e in entries)
    combos = []
    for f in sorted(BASE.glob('combos-*.json')):
        data = structured(f)
        champion = f.stem.removeprefix('combos-')
        raw = [r for r in catalog['combos'].values() if r['championId'] == champion]
        combos.append({'champion':champion,'mcpTotal':data['total'],
            'returned':len(data['combos']),'downloadTotal':len(raw),
            'sameUrls':{r['url'] for r in raw} == {r['url'] for r in data['combos']}})
    augments = []
    for f in sorted(BASE.glob('augment-*.json')):
        data = structured(f)
        raw = catalog['augments'].get(data['id'], {})
        augments.append({'id':data['id'],'availability':data['availability'],
            'sourceStatus':data['sourceStatus'],'tier':data['tier'],
            'mcpRank':data['rank'],'downloadPopularityRank':raw.get('pickRateRank'),
            'unresolvedDescriptionTokens':'@' in data.get('description',''),
            'hasWinRate':'winRate' in data,'topChampionCount':len(data.get('topChampionIds',[]))})
    builds=[]
    for f in sorted(BASE.glob('build-*.json')):
        data=structured(f)
        builds.append({'champion':data['championId'],
            'groups':{k:len(v) for k,v in data['builds'].items()},
            'topLevelFields':list(data),
            'hasAugmentCondition':any('augment' in k.lower() for k in data)})
    report={'verifiedResponseFiles':len(manifest['files']),
        'completeChampionTiers':len(entries),'championPopularityMatchesDownload':matches,
        'comboProbes':combos,'augmentProbes':augments,'buildProbes':builds,
        'scope':'Complete champion tier list; examples only for other tools, not full coverage.'}
    (BASE/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()
