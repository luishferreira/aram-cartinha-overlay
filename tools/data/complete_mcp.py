"""Audit and promote the full MCP collection without deleting older snapshots."""
import argparse
import json
from pathlib import Path
from mayhem_data.completion import audit,promote


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['audit','promote'])
    parser.add_argument('--workspace',type=Path,required=True)
    args=parser.parse_args()
    result=promote(args.workspace) if args.command=='promote' else audit(args.workspace)
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
