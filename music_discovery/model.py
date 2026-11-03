"""Small reference implicit ALS implementation; NumPy is loaded only for ML."""
import json
import time
import numpy as np
from .store import instant


def prepare(db, cutoff):
    rows = db.execute('SELECT listener,source,track_id,artist FROM events WHERE timestamp<? ORDER BY listener,source,track_id',
                      (instant(cutoff),)).fetchall()
    users = sorted({r['listener'] for r in rows})
    items = sorted({(r['source'], r['track_id']) for r in rows})
    ui, ii = {u:i for i,u in enumerate(users)}, {t:i for i,t in enumerate(items)}
    if len(users) * len(items) > 2_000_000:
        raise ValueError('reference dense implementation limited to 2 million user/item cells')
    counts = np.zeros((len(users), len(items)))
    artists = [''] * len(items)
    for r in rows:
        j = ii[(r['source'], r['track_id'])]
        counts[ui[r['listener']], j] += 1
        artists[j] = r['artist']
    return users, items, artists, counts


def fit(db, cutoff, output, factors=16, iterations=10, seed=42):
    users, items, artists, counts = prepare(db, cutoff)
    if len(users) < 2 or len(items) < 2:
        raise ValueError('collaborative training requires multiple listeners and tracks')
    if factors < 1 or iterations < 1:
        raise ValueError('positive factors and iterations required')
    rng = np.random.default_rng(seed)
    x, y = rng.normal(0,.01,(len(users), factors)), rng.normal(0,.01,(len(items), factors))
    confidence = 1 + 10 * np.log1p(counts)
    preference = (counts > 0).astype(float)
    started = time.perf_counter()
    def update(other, conf, pref):
        gram = other.T @ other + .1 * np.eye(factors)
        return np.array([np.linalg.solve(gram + other.T @ ((c-1)[:,None]*other),
                                        other.T @ (c*p)) for c,p in zip(conf,pref)])
    for _ in range(iterations):
        x = update(y, confidence, preference)
        y = update(x, confidence.T, preference.T)
    meta = dict(users=users, items=items, artists=artists, cutoff=instant(cutoff),
                seed=seed, factors=factors, iterations=iterations, alpha=10, regularization=.1,
                training_seconds=time.perf_counter()-started, numpy=np.__version__)
    np.savez_compressed(output, x=x, y=y, counts=counts, metadata=json.dumps(meta))
    return meta


def load(path):
    with np.load(path, allow_pickle=False) as data:
        return json.loads(str(data['metadata'])), data['x'].copy(), data['y'].copy(), data['counts'].copy()


def scores(meta, x, y, counts, user, method):
    if user not in meta['users']:
        return counts.sum(axis=0), 'popularity fallback: unknown listener'
    i = meta['users'].index(user)
    if method == 'als':
        return x[i] @ y.T, 'implicit ALS: latent factor dot product'
    if method == 'artist':
        weights = {}
        for a, count in zip(meta['artists'], counts[i]):
            weights[a] = weights.get(a, 0) + count
        return np.array([weights[a] for a in meta['artists']]), 'artist affinity: training play counts'
    if method != 'popularity':
        raise ValueError('unknown method')
    return counts.sum(axis=0), 'popularity baseline: training play counts'


def rank(meta, x, y, counts, user, method='als', mode='discovery', k=10):
    if mode not in ('discovery', 'repeat') or k < 1:
        raise ValueError('invalid ranking mode or k')
    values, label = scores(meta,x,y,counts,user,method)
    seen = counts[meta['users'].index(user)] > 0 if user in meta['users'] else np.zeros(len(values),dtype=bool)
    eligible = ~seen if mode == 'discovery' else seen
    order = sorted(np.flatnonzero(eligible), key=lambda j:(-float(values[j]),meta['items'][j]))[:k]
    return [dict(source=meta['items'][j][0], track_id=meta['items'][j][1], artist=meta['artists'][j],
                 score=float(values[j]), method=label, availability='unverified catalog suggestion') for j in order]
