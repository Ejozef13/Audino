from collections import Counter
from zoneinfo import ZoneInfo
from datetime import datetime
from .store import instant


def statistics(db, listener, start, end, tz='UTC'):
    start, end = instant(start), instant(end)
    if start >= end:
        raise ValueError('start must precede exclusive end')
    zone = ZoneInfo(tz)
    rows = db.execute('SELECT * FROM events WHERE listener=? AND timestamp>=? AND timestamp<? ORDER BY timestamp,source,event_id',
                      (listener, start, end)).fetchall()
    def top(field):
        counts = Counter(r[field] for r in rows if r[field])
        return sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:10]
    tracks = Counter((r['artist'], r['title'], r['source'], r['track_id']) for r in rows)
    hours = Counter(datetime.fromisoformat(r['timestamp']).astimezone(zone).hour for r in rows)
    known = [r['duration_ms'] for r in rows if r['duration_ms'] is not None]
    return dict(start=start, end_exclusive=end, timezone=tz, plays=len(rows),
                artists=top('artist'), albums=top('album'),
                tracks=[{'artist': k[0], 'title': k[1], 'source': k[2], 'track_id': k[3], 'plays': v}
                        for k, v in sorted(tracks.items(), key=lambda x: (-x[1], x[0]))[:10]],
                reported_duration_ms=sum(known), duration_events=len(known),
                missing_duration_events=len(rows)-len(known),
                hours={str(h): hours[h] for h in range(24)},
                observed_first=rows[0]['timestamp'] if rows else None,
                observed_last=rows[-1]['timestamp'] if rows else None)
