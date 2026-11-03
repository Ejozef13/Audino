"""Frozen-window, full training-catalog ranking. Does not tune on test."""
import math
import platform
import time
import numpy as np
from .model import load, rank
from .store import instant


def evaluate(db, artifact, start, end, k=10, minimum=5):
    meta,x,y,counts = load(artifact)
    start,end = instant(start),instant(end)
    if start != meta['cutoff'] or end <= start:
        raise ValueError('evaluation start must equal frozen training cutoff and precede end')
    catalog = {tuple(t) for t in meta['items']}
    future = db.execute('SELECT listener,source,track_id FROM events WHERE timestamp>=? AND timestamp<?', (start,end)).fetchall()
    truth = {}
    for row in future:
        truth.setdefault(row['listener'],set()).add((row['source'],row['track_id']))
    report = dict(protocol='full training catalog; no sampled negatives; discovery excludes training-seen tracks; repeat includes only training-seen tracks',
                  training=meta, start=start,end_exclusive=end,k=k,minimum_training_events=minimum,
                  hardware=platform.platform()+' / '+platform.machine(), methods={})
    pop = counts.sum(axis=0)
    probabilities = (pop+1)/(pop.sum()+len(pop))
    for mode in ('discovery','repeat'):
        for method in ('popularity','artist','als'):
            metrics=[]; covered=set(); artists=set(); excluded=0; examples=[]
            started=time.perf_counter()
            for i,user in enumerate(meta['users']):
                if counts[i].sum() < minimum:
                    continue
                seen = {tuple(meta['items'][j]) for j in np.flatnonzero(counts[i])}
                eligible = catalog-seen if mode=='discovery' else seen
                actual = truth.get(user,set())
                excluded += len(actual-eligible)
                relevant = actual & eligible
                if not relevant:
                    continue
                recs = rank(meta,x,y,counts,user,method,mode,k)
                keys = [(r['source'],r['track_id']) for r in recs]
                hits = [int(t in relevant) for t in keys]
                recall=sum(hits)/len(relevant)
                dcg=sum(h/math.log2(j+2) for j,h in enumerate(hits))
                ideal=sum(1/math.log2(j+2) for j in range(min(k,len(relevant))))
                artist_list=[r['artist'] for r in recs]
                pairs=len(recs)*(len(recs)-1)/2
                diversity=sum(a!=b for j,a in enumerate(artist_list) for b in artist_list[j+1:])/pairs if pairs else 0
                novelty=float(np.mean([-math.log2(probabilities[meta['items'].index(list(t))]) for t in keys])) if keys else 0
                metrics.append([recall,dcg/ideal,diversity,novelty])
                covered.update(keys); artists.update(artist_list)
                if not sum(hits) and len(examples)<3:
                    examples.append({'training_events':int(counts[i].sum()),'eligible_targets':len(relevant),'hits':0})
            array=np.array(metrics)
            summary={}
            for j,name in enumerate(('recall','ndcg','artist_pair_diversity','novelty_bits')):
                summary[name]={'mean':float(array[:,j].mean()) if len(array) else None,
                               'user_standard_error':float(array[:,j].std(ddof=1)/math.sqrt(len(array))) if len(array)>1 else None}
            report['methods'][mode+'/'+method]=dict(metrics=summary,eligible_users=len(metrics),
                catalog_coverage=len(covered)/len(catalog),artist_coverage=len(artists)/len(set(meta['artists'])),
                excluded_target_occurrences=excluded,failure_examples=examples,inference_seconds=time.perf_counter()-started)
    report['cold_start']=dict(unknown_evaluation_users=len(set(truth)-set(meta['users'])),
                              unknown_target_tracks=len({t for ts in truth.values() for t in ts}-catalog),
                              policy='unknown users use labeled popularity fallback; absent tracks cannot be ranked')
    return report
