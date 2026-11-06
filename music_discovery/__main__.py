import argparse
import json
from pathlib import Path
from .store import connect, load_json
from .analytics import statistics
from .recap import card


def main():
    parser = argparse.ArgumentParser(description='Music Discovery: local offline analytics')
    parser.add_argument('--db', default='private/listens.sqlite')
    commands = parser.add_subparsers(dest='command', required=True)
    ingest=commands.add_parser('import-events'); ingest.add_argument('path')
    export=commands.add_parser('export-year',help='Export a managed Obsidian-compatible Markdown summary')
    export.add_argument('--listener',required=True)
    export.add_argument('--output-directory',required=True)
    export.add_argument('--year',type=int)
    export.add_argument('--timezone',default='UTC')
    export.add_argument('--demo',action='store_true')
    for name in ('stats','recap'):
        command=commands.add_parser(name)
        command.add_argument('--listener',required=True)
        command.add_argument('--start',required=True); command.add_argument('--end',required=True)
        command.add_argument('--timezone',default='UTC')
        if name=='recap':
            command.add_argument('--output',required=True); command.add_argument('--demo',action='store_true')
    serve=commands.add_parser('serve'); serve.add_argument('--port',type=int,default=8765)
    serve.add_argument('--demo',action='store_true'); serve.add_argument('--model')
    train=commands.add_parser('train'); train.add_argument('--cutoff',required=True)
    train.add_argument('--output',required=True)
    ev=commands.add_parser('evaluate'); ev.add_argument('--model',required=True)
    ev.add_argument('--start',required=True); ev.add_argument('--end',required=True)
    ev.add_argument('--output',required=True)
    ev.add_argument('--k',type=int,default=10)
    args=parser.parse_args()
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    db=connect(args.db)
    if args.command=='import-events': result=load_json(db,args.path)
    elif args.command=='export-year':
        from .notes import export_year
        result={'exported':str(export_year(db,args.listener,args.output_directory,args.year,args.timezone,args.demo))}
    elif args.command in ('stats','recap'):
        result=statistics(db,args.listener,args.start,args.end,args.timezone)
        if args.command=='recap':
            with open(args.output,'x',encoding='utf-8') as f: f.write(card(result,args.demo))
            result={'exported':args.output}
    elif args.command=='train':
        from .model import fit
        if Path(args.output).exists(): raise ValueError('refusing to overwrite model')
        meta=fit(db,args.cutoff,args.output)
        result={'artifact':args.output,'listeners':len(meta['users']),'tracks':len(meta['items']),
                'cutoff':meta['cutoff'],'training_seconds':meta['training_seconds']}
    elif args.command=='evaluate':
        from .evaluate import evaluate
        result=evaluate(db,args.model,args.start,args.end,args.k)
        with open(args.output,'x',encoding='utf-8') as f: json.dump(result,f,indent=2)
        result={'report':args.output,'methods':list(result['methods'])}
    else:
        db.close()
        from .web import serve
        serve(args.db,args.port,args.demo,args.model)
        return
    db.close()
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
