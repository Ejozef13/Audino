import hashlib
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone


def instant(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timestamps must include a UTC offset')
    return dt.astimezone(timezone.utc).isoformat()


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript('''
    CREATE TABLE IF NOT EXISTS events (
      source TEXT, event_id TEXT, listener TEXT NOT NULL, timestamp TEXT NOT NULL,
      track_id TEXT NOT NULL, artist TEXT NOT NULL, title TEXT NOT NULL,
      album TEXT, duration_ms INTEGER, identity_hint TEXT NOT NULL,
      PRIMARY KEY(source, event_id));
    CREATE TABLE IF NOT EXISTS feedback (
      listener TEXT, track_id TEXT, action TEXT CHECK(action IN ('save','dismiss')),
      timestamp TEXT, PRIMARY KEY(listener,track_id));
    ''')
    return db


def import_events(db, records):
    """Validate entire batch before inserting. Explicit IDs preserve repeated plays."""
    rows = []
    seen = {}
    for r in records:
        for key in ('source', 'event_id', 'listener', 'timestamp', 'track_id', 'artist', 'title'):
            if not isinstance(r.get(key), str) or not r[key].strip():
                raise ValueError(f'{key} must be a nonempty string')
        duration = r.get('duration_ms')
        if duration is not None and (type(duration) is not int or duration < 0):
            raise ValueError('duration_ms must be nonnegative integer or null')
        if r.get('album') is not None and not isinstance(r['album'], str):
            raise ValueError('album must be a string or null')
        row = (r['source'], r['event_id'], r['listener'], instant(r['timestamp']),
               r['track_id'], r['artist'], r['title'], r.get('album'), duration,
               normalized(r['artist']) + ' / ' + normalized(r['title']))
        key = row[:2]
        previous = db.execute('SELECT * FROM events WHERE source=? AND event_id=?', key).fetchone()
        if (previous and tuple(previous) != row) or (key in seen and seen[key] != row):
            raise ValueError('conflicting source event ID; import rolled back')
        seen[key] = row
        rows.append(row)
    before = db.total_changes
    with db:
        db.executemany('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
    return {'inserted': db.total_changes - before, 'provided': len(rows)}


def load_json(db, path):
    with open(path, encoding='utf-8') as f:
        records = json.load(f)
    if not isinstance(records, list):
        raise ValueError('expected a JSON array of internal-format events')
    return import_events(db, records)
