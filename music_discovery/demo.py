"""Generate unmistakably fictional data for smoke tests, never ML evidence."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def events():
    result=[]
    for u in range(6):
        for day in range(28):
            track=(day+u*3)%18
            result.append(dict(source='synthetic-demo',event_id=f'{u}-{day}',
                listener='demo' if u==0 else f'fixture-{u}',
                timestamp=(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(days=day,hours=u)).isoformat(),
                track_id=f'fictional-track-{track}',artist=f'Fictional Artist {track//3+1}',
                title=f'Fictional Song {track+1}',album=f'Fictional Album {track//6+1}',
                duration_ms=180000 if day%4 else None))
    return result


if __name__=='__main__':
    Path('private').mkdir(exist_ok=True)
    with open('private/demo-events.json','x',encoding='utf-8') as f:
        json.dump(events(),f,indent=2)
