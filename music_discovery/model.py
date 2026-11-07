"""Small reference implicit ALS implementation; NumPy is loaded only for ML."""
import json
import time
import hashlib
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


def fit(db, cutoff, output, factors=16, iterations=10, seed=42, data_kind='unverified'):
    users, items, artists, counts = prepare(db, cutoff)
    if len(users) < 2 or len(items) < 2:
        raise ValueError('collaborative training requires multiple listeners and tracks')
    if not 1 <= factors <= 64 or not 1 <= iterations <= 100:
        raise ValueError('reference implementation allows 1–64 factors and 1–100 iterations')
    if data_kind not in ('unverified','fixture','licensed_public','personal'):
        raise ValueError('invalid training data kind')
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
    fingerprint=hashlib.sha256()
    for row in db.execute('SELECT * FROM events WHERE timestamp<? ORDER BY source,event_id', (instant(cutoff),)):
        fingerprint.update((json.dumps(tuple(row),ensure_ascii=False)+'\n').encode())
    meta = dict(users=users, items=items, artists=artists, cutoff=instant(cutoff),data_kind=data_kind,
                training_fingerprint=fingerprint.hexdigest(),
                seed=seed, factors=factors, iterations=iterations, alpha=10, regularization=.1,
                training_seconds=time.perf_counter()-started, numpy=np.__version__)
    titles = {}
    for row in db.execute('SELECT source,track_id,title FROM events WHERE timestamp<? ORDER BY timestamp,event_id', (instant(cutoff),)):
        titles[(row['source'],row['track_id'])] = row['title']
    meta['titles'] = [titles[tuple(item)] for item in items]
    np.savez_compressed(output, x=x, y=y, counts=counts, metadata=json.dumps(meta))
    return meta


def load(path):
    with np.load(path, allow_pickle=False) as data:
        meta=json.loads(str(data['metadata']))
        x,y,counts=data['x'].copy(),data['y'].copy(),data['counts'].copy()
    if (x.ndim!=2 or y.ndim!=2 or counts.ndim!=2 or x.shape[1]!=y.shape[1]
            or x.shape[0]!=len(meta['users']) or y.shape[0]!=len(meta['items'])
            or counts.shape!=(len(meta['users']),len(meta['items']))
            or len(meta['artists'])!=len(meta['items']) or ('titles' in meta and len(meta['titles'])!=len(meta['items']))):
        raise ValueError('Model artifact shapes and metadata disagree')
    if not all(np.isfinite(array).all() for array in (x,y,counts)) or (counts<0).any():
        raise ValueError('Model artifact contains invalid factors or counts')
    if len(set(meta['users']))!=len(meta['users']) or len({tuple(item) for item in meta['items']})!=len(meta['items']):
        raise ValueError('Model artifact contains duplicate identities')
    return meta,x,y,counts


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
                 title=meta.get('titles', [None]*len(meta['items']))[j],
                 score=float(values[j]), method=label, availability='unverified catalog suggestion') for j in order]


def rank_profile(meta, y, counts, profile, method='als', mode='discovery', k=10):
    """Fit a listener vector with frozen item factors; only explicitly matched IDs."""
    profile=np.asarray(profile,dtype=float)
    if profile.shape!=(len(meta['items']),) or not np.isfinite(profile).all() or (profile<0).any():
        raise ValueError('invalid matched listening profile')
    if method not in ('als','artist','popularity') or mode not in ('discovery','repeat') or not 1<=k<=50:
        raise ValueError('invalid ranking arguments')
    seen=profile>0
    label='popularity baseline: training play counts'
    values=counts.sum(axis=0)
    if profile.sum()==0:
        label='popularity fallback: no matched listening history'
    elif method=='als':
        confidence=1+meta.get('alpha',10)*np.log1p(profile)
        gram=y.T@y + y.T@((confidence-1)[:,None]*y) + meta.get('regularization',.1)*np.eye(y.shape[1])
        vector=np.linalg.solve(gram,y.T@(confidence*seen))
        values=vector@y.T
        label='implicit ALS: fitted listener vector against frozen trained item factors'
    elif method=='artist':
        weights={}
        for artist,n in zip(meta['artists'],profile): weights[artist]=weights.get(artist,0)+n
        values=np.array([weights[a] for a in meta['artists']])
        label='artist affinity: matched profile play counts'
    eligible=~seen if mode=='discovery' else seen
    order=sorted(np.flatnonzero(eligible),key=lambda j:(-float(values[j]),meta['items'][j]))[:k]
    return [dict(source=meta['items'][j][0],track_id=meta['items'][j][1],artist=meta['artists'][j],
                 title=meta.get('titles',[None]*len(meta['items']))[j],score=float(values[j]),method=label,
                 availability='catalog suggestion; local library availability unverified') for j in order]
