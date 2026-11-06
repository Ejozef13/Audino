"""Managed Markdown exports. SQLite remains the authoritative event store."""
import os
import hashlib
import tempfile
from pathlib import Path
from .analytics import statistics, year_window

MARKER = '<!-- music-discovery:managed:v1 -->'


def text(value):
    # Names are data, not executable Markdown, wikilinks, HTML, or front matter.
    value = ' '.join(str(value).split())
    for char in ('&', '<', '>', '|', '[', ']', '*', '_', '`', '#', '\\'):
        value = value.replace(char, f'&#{ord(char)};')
    return value


def render(stats, demo=False):
    rows = [MARKER, '# Listening year in progress', '',
            '**SYNTHETIC FIXTURE DEMO — not personal listening history.**' if demo else 'Private listening summary.', '',
            f"Interval: {stats['start']} → {stats['end_exclusive']} (end exclusive).",
            f"Calendar timezone: {stats['timezone']}.", '',
            f"**{stats['plays']} play events** in imported data.",
            f"Reported listening time: {stats['reported_duration_ms']/60000:.2f} minutes from {stats['duration_events']} events; "
            f"{stats['missing_duration_events']} events have no reported duration.",
            'Coverage is imported events only; this is not proof of complete server history.', '',
            '## Top 5 artists', '', '| Artist | Plays | Reported minutes | Events with duration / total |',
            '|---|---:|---:|---:|']
    for artist in stats['artist_details'][:5]:
        rows.append(f"| {text(artist['artist'])} | {artist['plays']} | {artist['reported_duration_ms']/60000:.2f} | {artist['duration_events']}/{artist['plays']} |")
    rows.extend(['', '## Top 5 songs', '', '| Track | Artist | Plays | Reported minutes | Events with duration / total |', '|---|---|---:|---:|---:|'])
    for track in stats['tracks'][:5]:
        rows.append(f"| {text(track['title'])} | {text(track['artist'])} | {track['plays']} | {track['reported_duration_ms']/60000:.2f} | {track['duration_events']}/{track['plays']} |")
    rows.extend(['', '## Interpretation', '',
                 'Ranked by play-event count; ties use deterministic alphabetical ordering.',
                 'Reported time is partial when events lack duration. No runtime-based estimates, skips, or completions are inferred.',
                 'No global percentiles. Plays are implicit preference evidence, not explicit likes.',
                 'This file is generated. Put your own notes in another file; the next export replaces this managed summary.', ''])
    return '\n'.join(rows)


def export_year(db, listener, output_directory, year=None, tz='UTC', demo=False, now=None):
    start, end = year_window(year, tz, now)
    stats = statistics(db, listener, start, end, tz)
    root = Path(output_directory)
    root.mkdir(parents=True, exist_ok=True)
    scope = hashlib.sha256(listener.encode('utf-8')).hexdigest()[:12]
    target = root / f'Listening-{start[:4]}-{scope}.md'
    if target.is_symlink():
        raise ValueError('refusing to replace a symbolic link')
    if target.exists() and not target.read_text(encoding='utf-8').startswith(MARKER+'\n'):
        raise ValueError('refusing to overwrite an unmanaged note')
    descriptor, temporary = tempfile.mkstemp(prefix='.music-discovery-', dir=root)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(render(stats, demo))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return target
