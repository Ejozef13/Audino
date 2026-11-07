"""Validation-only experiments. Frozen test interval is recorded, never scored."""
import hashlib
import json
import platform
from pathlib import Path
from .store import instant
from .model import fit
from .evaluate import evaluate


def run_validation(db,config,output):
    required={'dataset_version','data_kind','train_before','validation_end','test_end',
              'factors','iterations','seeds','k','minimum_history'}
    if not isinstance(config,dict) or set(config)!=required:
        raise ValueError('Experiment config must contain exactly the documented fields')
    if config['data_kind'] not in ('fixture','licensed_public','personal') or not isinstance(config['dataset_version'],str) or not config['dataset_version'].strip():
        raise ValueError('Dataset version and kind are required; verify license/provenance before real-data runs')
    train,valid,test=(instant(config[k]) for k in ('train_before','validation_end','test_end'))
    if not train<valid<test: raise ValueError('Frozen boundaries must be chronological')
    if not isinstance(config['factors'],list) or not isinstance(config['seeds'],list):
        raise ValueError('Factors and seeds must be explicit lists')
    if not config['factors'] or not config['seeds'] or len(config['factors'])*len(config['seeds'])>12:
        raise ValueError('Choose 1–12 bounded training runs')
    for value in config['factors']:
        if type(value) is not int or not 1<=value<=64: raise ValueError('Factors must be integers from 1 to 64')
    for value in config['seeds']:
        if type(value) is not int or not 0<=value<2**32: raise ValueError('Invalid random seed')
    for key,maximum in [('iterations',100),('k',50),('minimum_history',10000)]:
        if type(config[key]) is not int or not 1<=config[key]<=maximum: raise ValueError('Invalid '+key)
    if len(set(config['factors']))!=len(config['factors']) or len(set(config['seeds']))!=len(config['seeds']):
        raise ValueError('Duplicate grid entries are not independent runs')
    directory=Path(output)
    directory.mkdir(parents=True,exist_ok=False)
    encoded=json.dumps(config,sort_keys=True,indent=2)
    (directory/'frozen-config.json').write_text(encoded+'\n',encoding='utf-8')
    summary=dict(config_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
                 data_kind=config['data_kind'],dataset_version=config['dataset_version'],
                 test_status='UNRUN: final test interval remains untouched by this runner',
                 environment=dict(python=platform.python_version(),platform=platform.platform(),processor=platform.processor()),
                 runs=[])
    for factors in config['factors']:
        for seed in config['seeds']:
            stem=f'factors-{factors}-seed-{seed}'
            artifact=directory/(stem+'.npz')
            fit(db,train,artifact,factors,config['iterations'],seed,config['data_kind'])
            report=evaluate(db,artifact,train,valid,config['k'],config['minimum_history'])
            report['dataset_version']=config['dataset_version']
            report['evaluation_role']='validation only'
            (directory/(stem+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            summary['runs'].append(dict(factors=factors,seed=seed,artifact=artifact.name,
                                        training_seconds=report['training']['training_seconds'],methods=report['methods']))
    (directory/'validation-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    lines=['# Validation comparison','',
           '**Fixture data: plumbing check only; no quality claim.**' if config['data_kind']=='fixture' else '**Validation data only; verify source license and provenance separately.**',
           '', 'Final test: **UNRUN**.', '',
           '| Factors | Seed | Task / method | Eligible users | Recall@K | NDCG@K | Catalog coverage |',
           '|---:|---:|---|---:|---:|---:|---:|']
    for run in summary['runs']:
        for name,method in run['methods'].items():
            def metric(key):
                value=method['metrics'][key]['mean']
                return 'Unavailable' if value is None else f'{value:.4f}'
            lines.append(f"| {run['factors']} | {run['seed']} | {name} | {method['eligible_users']} | {metric('recall')} | {metric('ndcg')} | {method['catalog_coverage']:.4f} |")
    (directory/'comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dict(directory=str(directory),training_runs=len(summary['runs']),
                data_kind=config['data_kind'],comparison=str(directory/'comparison.md'),test_status=summary['test_status'])
