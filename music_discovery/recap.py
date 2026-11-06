from html import escape
from .presentation import play_events


def card(stats, demo=False):
    label = 'SYNTHETIC DEMO · ' if demo else ''
    lines = [(64, 80, 22, label + 'MUSIC DISCOVERY'),
             (64, 160, 48, 'Your listening, in focus'),
             (64, 210, 17, stats['start'][:10] + ' → ' + stats['end_exclusive'][:10] + ' (end exclusive)'),
             (64, 305, 70, play_events(stats['plays'])),
             (64, 350, 18, f"Duration reported for {stats['duration_events']}/{stats['plays']} events"),
             (64, 405, 26, 'TOP ARTISTS')]
    for i, (artist, count) in enumerate(stats['artists'][:5]):
        lines.append((64, 455+i*46, 24, f'{i+1}. {artist[:48]} · {count}'))
    lines.append((64, 730, 26, 'TOP TRACKS'))
    for i, track in enumerate(stats['tracks'][:3]):
        lines.append((64, 780+i*45, 21, f"{track['title'][:38]} — {track['artist'][:25]} · {track['plays']}"))
    lines.extend([(64, 970, 16, 'Coverage: imported events only. No global comparisons.'),
                  (64, 1000, 16, 'Review names and listening history before sharing.')])
    text = ''.join(f'<text x="{x}" y="{y}" font-size="{size}" fill="#f8f4e8">{escape(s)}</text>' for x,y,size,s in lines)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080">'
            '<defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="#17243f"/>'
            '<stop offset="1" stop-color="#452745"/></linearGradient></defs>'
            '<rect width="1080" height="1080" fill="url(#g)"/>'
            '<circle cx="960" cy="200" r="220" fill="#e2a35a" opacity=".12"/>'
            '<g font-family="sans-serif">'+text+'</g></svg>')
