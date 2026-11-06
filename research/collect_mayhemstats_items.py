"""Archive only aggregate read queries exposed by the MayhemStats public frontend."""
import argparse
import json
import re
from urllib.parse import urlencode
from audit_item_sources import OUT, Archive, write

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--patch', action='append', default=[])
    parser.add_argument('--page-size', type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.page_size <= 1000:
        raise ValueError('Page size must be between 1 and 1000')
    seeds = Archive()
    bundle_url = 'https://mayhemstats.com/assets/index-C25j1dkp.js'
    bundle = seeds.get(bundle_url).decode('utf8')
    host = re.search(r'Yg="(https://[a-z]+\.supabase\.co)"', bundle).group(1)
    # This is the published frontend anon-role key, not a user's credential.
    # Keep request headers in memory and never include them in manifests or output.
    anon = re.search(r'Mm="([^"]+)"', bundle).group(1)
    headers = {'apikey': anon, 'Authorization': 'Bearer ' + anon, 'Prefer': 'count=exact'}
    if any(not re.fullmatch(r'\d+\.\d+', p) for p in args.patch):
        raise ValueError('Unexpected patch identifier')
    out = OUT / 'mayhemstats-api'
    if args.patch:
        out = out / ('filtered-' + '-'.join(args.patch))
    archive = Archive(out)
    results = {}
    for view, order in [('community_totals', None), ('community_patch_spans', 'patch'),
                        ('champion_stats', 'patch,queue_id,champion_id'),
                        ('item_stats', 'patch,queue_id,champion_id,item_id'),
                        ('item_purchase_stats', 'patch,queue_id,champion_id,item_id')]:
        if f'"{view}"' not in bundle:
            raise ValueError('View is not exposed by archived frontend')
        rows, offset, total = [], 0, None
        while True:
            query = {'select': '*', 'limit': args.page_size, 'offset': offset}
            if order:
                query['order'] = order
            if args.patch and view in {'champion_stats', 'item_stats', 'item_purchase_stats'}:
                query.update(patch='in.(' + ','.join(args.patch) + ')', queue_id='eq.2400')
            url = host + '/rest/v1/' + view + '?' + urlencode(query)
            page = json.loads(archive.get(url, headers))
            if not isinstance(page, list):
                raise ValueError('Aggregate response is not a list')
            rows.extend(page)
            content_range = archive.manifest['records'][url].get('content_range', '') or ''
            if '/' in content_range and content_range.split('/')[-1].isdigit():
                total = int(content_range.split('/')[-1])
            print(f'{view}: {len(rows)}/{total} aggregate rows; fields={list(page[0]) if page and offset == 0 else "..."}', flush=True)
            if len(page) < args.page_size or (total is not None and len(rows) >= total) or not args.full:
                break
            offset += args.page_size
            if offset >= 200000:
                raise ValueError('Bounded audit exceeded 200,000 rows; review scope before continuing')
        complete = (total is not None and len(rows) == total) or len(page) < args.page_size
        if complete and total is not None and len(rows) != total:
            raise ValueError('Count differs from archived total')
        results[view] = {'complete': complete, 'total_reported': total, 'rows': rows}
        write(out / (view + '.json'), results[view])
    write(out / 'coverage.json', {view: {'complete': value['complete'], 'rows': len(value['rows']), 'total_reported': value['total_reported']} for view, value in results.items()})

if __name__ == '__main__':
    main()
