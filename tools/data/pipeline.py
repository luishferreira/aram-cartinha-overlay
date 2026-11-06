"""Unified local data CLI. Run --help; all commands except fetch are offline."""
import argparse
import json
from pathlib import Path
from mayhem_data.common import ROOT, read
from mayhem_data.pipeline import build, verify_run
from mayhem_data.query import evidence, context, status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/pipeline')
    subs=parser.add_subparsers(dest='command',required=True)
    build_parser=subs.add_parser('build',help='Import preserved evidence, validate and atomically publish SQLite')
    build_parser.add_argument('--input-root',type=Path,default=ROOT,help='Isolated input workspace, default existing research snapshots')
    subs.add_parser('verify',help='Check all raw/output hashes and SQLite integrity')
    subs.add_parser('status',help='Coverage, translations, unknown/stale dates and counts')
    subs.add_parser('changes',help='Show changes and review queue against previous publication')
    item=subs.add_parser('evidence',help='Query source-specific evidence for an entity')
    item.add_argument('entity');item.add_argument('--champion');item.add_argument('--source')
    item.add_argument('--locale',choices=['pt-BR','en-US'],default='pt-BR');item.add_argument('--limit',type=int,default=15)
    ctx=subs.add_parser('context',help='Retrieve contextual candidates and match manually reviewed rules')
    ctx.add_argument('--champion',required=True);ctx.add_argument('--augments',nargs='*',default=[])
    ctx.add_argument('--items',nargs='*',default=[]);ctx.add_argument('--offered',nargs='*',default=[])
    ctx.add_argument('--patches',type=json.loads,default={},help='Source-specific JSON patch map; unknown patches do not validate rules')
    ctx.add_argument('--limit',type=int,default=15)
    bp=subs.add_parser('builds',help='Query full ARAMKit profiles and route options, optionally conditioned on one augment')
    bp.add_argument('--champion',required=True);bp.add_argument('--augment')
    bp.add_argument('--selection',choices=['filtered','unfiltered'],default='filtered')
    bp.add_argument('--limit',type=int,default=10);bp.add_argument('--offset',type=int,default=0)
    fetch=subs.add_parser('fetch',help='Refresh selected public source files in an isolated resumable input workspace')
    fetch.add_argument('--sources',nargs='+',choices=['blitz','opgg','aramkit','arammayhem'],required=True)
    fetch.add_argument('--workspace',type=Path,required=True)
    fetch.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.command=='build':result=build(args.input_root,args.output)
    elif args.command=='fetch':
        from mayhem_data.fetch import fetch_sources
        result=fetch_sources(ROOT,args.workspace,args.sources,args.resume)
    elif args.command=='verify':result=verify_run(args.output,read(args.output/'current.json')['run'])
    elif args.command=='status':result=status(args.output)
    elif args.command=='changes':
        directory=args.output/'runs'/read(args.output/'current.json')['run']
        result={'changes':read(directory/'changes.json'),'review_queue':read(directory/'review-queue.json')}
    elif args.command=='evidence':result=evidence(args.output,args.entity,args.champion,args.locale,args.limit,args.source)
    elif args.command=='builds':
        from mayhem_data.builds import query_builds
        result=query_builds(args.output,args.champion,args.augment,args.selection,args.limit,args.offset)
    else:result=context(args.output,args.champion,args.augments,args.items,args.offered,args.patches,limit=args.limit)
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
