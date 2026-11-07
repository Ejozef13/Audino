import argparse
import json
import getpass
from datetime import datetime, timezone
from pathlib import Path
from .store import connect, load_json
from .analytics import statistics
from .recap import card


def main():
    parser = argparse.ArgumentParser(description='Music Discovery: local offline analytics')
    parser.add_argument('--db', default='private/listens.sqlite')
    commands = parser.add_subparsers(dest='command', required=True)
    ingest=commands.add_parser('import-events'); ingest.add_argument('path')
    check=commands.add_parser('navidrome-check',help='Authenticate and check read-only scrobble history')
    check.add_argument('--url',required=True)
    sync=commands.add_parser('navidrome-sync',help='Import available history with stable source IDs')
    sync.add_argument('--url',required=True)
    sync.add_argument('--server-id',required=True)
    sync.add_argument('--listener',required=True)
    sync.add_argument('--start',required=True)
    sync.add_argument('--end')
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
    train.add_argument('--factors',type=int,default=16)
    train.add_argument('--iterations',type=int,default=10)
    train.add_argument('--seed',type=int,default=42)
    train.add_argument('--data-kind',choices=['unverified','fixture','licensed_public','personal'],default='unverified')
    experiment=commands.add_parser('validate-experiment',help='Freeze config and compare models on validation only')
    experiment.add_argument('--config',required=True)
    experiment.add_argument('--output-directory',required=True)
    ollama=commands.add_parser('ollama-check',help='Check local Ollama and installed model')
    ollama.add_argument('--url',default='http://127.0.0.1:11434')
    ollama.add_argument('--model',default='gpt-oss:20b')
    agent=commands.add_parser('agent',help='Ask local Ollama to use bounded analytics/ranking tools')
    agent.add_argument('--question',required=True)
    agent.add_argument('--listener',required=True)
    agent.add_argument('--start',required=True)
    agent.add_argument('--end')
    agent.add_argument('--timezone',default='UTC')
    agent.add_argument('--artifact')
    agent.add_argument('--mapping')
    agent.add_argument('--demo',action='store_true')
    agent.add_argument('--ollama-url',default='http://127.0.0.1:11434')
    agent.add_argument('--ollama-model',default='gpt-oss:20b')
    ev=commands.add_parser('evaluate'); ev.add_argument('--model',required=True)
    ev.add_argument('--start',required=True); ev.add_argument('--end',required=True)
    ev.add_argument('--output',required=True)
    ev.add_argument('--k',type=int,default=10)
    args=parser.parse_args()
    if args.command=='ollama-check':
        from .agent import Ollama
        print(json.dumps(Ollama(args.url,args.model).check(),indent=2))
        return
    client=None
    if args.command in ('navidrome-check','navidrome-sync'):
        from .navidrome import Client
        client=Client(args.url)
        client.login(input('Navidrome username: '),getpass.getpass('Navidrome password (not saved): '))
        if args.command=='navidrome-check':
            rows=client.history('1970-01-01T00:00:00Z',datetime.now(timezone.utc).isoformat(),size=1)
            print(json.dumps({'authenticated':True,'history_endpoint_accessible':True,
                              'sample_events':len(rows),'note':'An empty result does not establish that history recording is enabled.'},indent=2))
            return
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    db=connect(args.db)
    if args.command=='import-events': result=load_json(db,args.path)
    elif args.command=='navidrome-sync':
        from .navidrome import sync
        result=sync(client,db,args.server_id,args.listener,args.start,args.end or datetime.now(timezone.utc).isoformat())
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
        meta=fit(db,args.cutoff,args.output,args.factors,args.iterations,args.seed,args.data_kind)
        result={'artifact':args.output,'listeners':len(meta['users']),'tracks':len(meta['items']),
                'cutoff':meta['cutoff'],'training_seconds':meta['training_seconds']}
    elif args.command=='validate-experiment':
        from .experiment import run_validation
        with open(args.config,encoding='utf-8') as stream: config=json.load(stream)
        result=run_validation(db,config,args.output_directory)
    elif args.command=='agent':
        from .agent import Ollama,Toolbox,run
        mapping=None
        if args.mapping:
            with open(args.mapping,encoding='utf-8') as stream: mapping=json.load(stream)
            if not isinstance(mapping,list): raise ValueError('Mapping must be a list of explicit identity pairs')
        client=Ollama(args.ollama_url,args.ollama_model)
        client.check()
        toolbox=Toolbox(db,args.listener,args.start,args.end or datetime.now(timezone.utc).isoformat(),
                        args.timezone,args.artifact,mapping,args.demo)
        result=run(client,toolbox,args.question)
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
