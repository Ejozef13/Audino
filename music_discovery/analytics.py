from collections import Counter
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from .store import instant


def year_window(year=None, tz='UTC', now=None):
    """Calendar boundaries in the listener's timezone; current year stops at now."""
    zone = ZoneInfo(tz)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    local = now.astimezone(zone)
    year = local.year if year is None else year
    if not 1 <= year < 9999 or year > local.year:
        raise ValueError('year must be a current or past calendar year')
    start = datetime(year, 1, 1, tzinfo=zone)
    end = min(datetime(year + 1, 1, 1, tzinfo=zone), local)
    return start.isoformat(), end.isoformat()


def statistics(db, listener, start, end, tz='UTC'):
    start, end = instant(start), instant(end)
    if start > end:
        raise ValueError('start must not follow exclusive end')
    zone = ZoneInfo(tz)
    rows = db.execute('SELECT * FROM events WHERE listener=? AND timestamp>=? AND timestamp<? ORDER BY timestamp,source,event_id',
                      (listener, start, end)).fetchall()
    def top(field):
        counts = Counter(r[field] for r in rows if r[field])
        return sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:10]
    tracks = Counter((r['artist'], r['title'], r['source'], r['track_id']) for r in rows)
    hours = Counter(datetime.fromisoformat(r['timestamp']).astimezone(zone).hour for r in rows)
    known = [r['duration_ms'] for r in rows if r['duration_ms'] is not None]
    def duration_summary(selected):
        values = [r['duration_ms'] for r in selected if r['duration_ms'] is not None]
        return dict(reported_duration_ms=sum(values), duration_events=len(values),
                    missing_duration_events=len(selected)-len(values))
    return dict(start=start, end_exclusive=end, timezone=tz, plays=len(rows),
                artists=top('artist'), albums=top('album'),
                artist_details=[dict(artist=a, plays=n, **duration_summary([r for r in rows if r['artist']==a]))
                                for a,n in top('artist')],
                tracks=[{'artist': k[0], 'title': k[1], 'source': k[2], 'track_id': k[3], 'plays': v}
                        | duration_summary([r for r in rows if (r['artist'],r['title'],r['source'],r['track_id'])==k])
                        for k, v in sorted(tracks.items(), key=lambda x: (-x[1], x[0]))[:10]],
                reported_duration_ms=sum(known), duration_events=len(known),
                missing_duration_events=len(rows)-len(known),
                hours={str(h): hours[h] for h in range(24)},
                observed_first=rows[0]['timestamp'] if rows else None,
                observed_last=rows[-1]['timestamp'] if rows else None)
