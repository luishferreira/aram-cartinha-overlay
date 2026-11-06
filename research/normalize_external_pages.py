import json,re,unicodedata
from collections import Counter,defaultdict
from pathlib import Path
from html_tree import Tree

ROOT=Path(__file__).parent

def clean(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s).lower() if c.isalnum())

def main():
    scripts=json.loads((ROOT/'public-snapshots/blitz-general.scripts.json').read_text('utf-8'))
    s=next(s for s in scripts if '/augments_en_us' in s['attrs'].get('data-url',''))
    catalog=json.loads(json.loads(s['body'])['body'])
    names=defaultdict(set)
    for aid,a in catalog.items():names[clean(a['displayName'])].add(int(aid))
    rows=[];unmatched=[];counts=Counter()
    for path in sorted((ROOT/'external-champions').glob('*.html')):
        source,cid=path.stem.rsplit('-',1);cid=int(cid)
        tree=Tree(path.read_text('utf-8')).root
        if source=='aramgg':
            for n in tree.find('tr',lambda n:'data-row' in n.attrs and 'data-tier' in n.attrs):
                link=next(n.find('a',lambda a:a.attrs.get('data-champion-link-placement')=='augment_table'),None)
                if not link:continue
                aid=int(link.attrs['data-champion-link-target'])
                # Validate numeric ID against English catalog whenever available.
                if str(aid) in catalog and clean(link.text())!=clean(catalog[str(aid)]['displayName']):
                    unmatched.append({'source':source,'champion_id':cid,'id':aid,'name':link.text(),'reason':'id/name conflict'});continue
                rows.append({'source':source,'champion_id':cid,'augment_id':aid,'name':link.text(),
                             'tier_raw':n.attrs['data-tier'],'rank':int(n.text().split()[0]),
                             'rarity_raw':n.attrs.get('data-rarity'),
                             'win_rate':float(n.attrs['data-win-rate']),
                             'pick_rate':float(n.attrs['data-pick-rate'])})
                counts[source]+=1
        elif source=='arammayhem':
            for a in tree.find('a',lambda a:a.attrs.get('href','').startswith('/augments/')):
                rarity=next(a.find('span',lambda n:n.attrs.get('data-recommendation-rank')=='rarity'),None)
                overall=next(a.find('span',lambda n:n.attrs.get('data-recommendation-rank')=='overall'),None)
                if not rarity or not overall:continue
                name_node=next(a.find('div',lambda n:'title' in n.attrs),None)
                if not name_node:continue
                name=name_node.attrs['title'];ids=names.get(clean(name),set())
                # Explicit display-prefix alias; suffix must exactly match a
                # unique catalog name. Do not fuzzy-match mechanical aliases.
                if not ids and name.startswith('Quest: '):
                    ids=names.get(clean(name.removeprefix('Quest: ')),set())
                if len(ids)!=1:
                    unmatched.append({'source':source,'champion_id':cid,'name':name,'reason':'no unique exact normalized English name'});continue
                rm=re.fullmatch(r'([SABCDE][+-]?) · #(\d+)',rarity.text())
                om=re.fullmatch(r'Overall ([SABCDE][+-]?) · #(\d+)',overall.text())
                if not rm or not om:raise ValueError((rarity.text(),overall.text()))
                pick=re.search(r'Appearance rate: ([\d.]+)%',a.text())
                rows.append({'source':source,'champion_id':cid,'augment_id':next(iter(ids)),'name':name,
                             'tier_raw':rm[1],'rank':int(rm[2]),'overall_tier_raw':om[1],'overall_rank':int(om[2]),
                             'pick_rate':float(pick[1])/100 if pick else None,
                             'rarity_raw':catalog[str(next(iter(ids)))].get('rarity')})
                counts[source]+=1
    (ROOT/'external-pages-normalized.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'external-pages-unmatched.json').write_text(json.dumps(unmatched,ensure_ascii=False,indent=2),encoding='utf-8')
    print('rows',dict(counts),'unmatched',len(unmatched))
    print('unmatched names',Counter(x['name'] for x in unmatched))
    print('tiers', {s:dict(Counter(r['tier_raw'] for r in rows if r['source']==s)) for s in counts})

if __name__=='__main__':main()
