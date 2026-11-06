"""Read-only history adapter verified against Navidrome v0.64.2 source.

Native API is version-specific. Passwords/tokens are never persisted or logged.
Only authentication POST plus history/song GET requests are issued.
"""
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .store import instant, import_events


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Server redirected the request; use its final base URL directly')


class Client:
    def __init__(self, url):
        parsed=urlsplit(url)
        if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('Use an HTTP(S) base URL without credentials, query, or fragment')
        self.url=url.rstrip('/')
        self.token=None
        self.user=None
        self.opener=build_opener(NoRedirect())

    def request(self, path, payload=None):
        headers={'Accept':'application/json'}
        if self.token: headers['X-ND-Authorization']='Bearer '+self.token
        body=None if payload is None else json.dumps(payload).encode()
        if body is not None: headers['Content-Type']='application/json'
        request=Request(self.url+path,data=body,headers=headers)
        try:
            with self.opener.open(request,timeout=20) as response:
                data=response.read(4_000_001)
            if len(data)>4_000_000: raise ValueError('API response exceeded the 4 MB limit')
            return json.loads(data)
        except HTTPError as error:
            raise ValueError(f'Navidrome returned HTTP {error.code}; check login, URL, and API access') from None
        except (URLError,TimeoutError):
            raise ValueError('Cannot reach Navidrome; check the URL and local network connection') from None
        except (UnicodeError,json.JSONDecodeError):
            raise ValueError('Navidrome did not return valid JSON') from None

    def login(self, username, password):
        result=self.request('/auth/login',{'username':username,'password':password})
        if not isinstance(result,dict) or not isinstance(result.get('token'),str) or not result['token']:
            raise ValueError('Unexpected authentication response')
        if not isinstance(result.get('id'),str) or not result['id']:
            raise ValueError('Authentication response has no user ID')
        self.token=result['token']; self.user=result['id']

    def history(self, start, end, page=0, size=100):
        # Server bounds are inclusive; conversion applies the exclusive end locally.
        params=urlencode({'_start':page*size,'_end':(page+1)*size,
                          '_sort':'submission_time','_order':'ASC',
                          'from':int(datetime.fromisoformat(instant(start)).timestamp()),
                          'to':int(datetime.fromisoformat(instant(end)).timestamp())})
        result=self.request('/api/scrobble?'+params)
        if result is None: return []
        if not isinstance(result,list) or len(result)>size:
            raise ValueError('Unexpected history response or unsupported pagination')
        return result


def convert(row, song, server_id, user_id, listener):
    if type(row.get('id')) is not int or row['id']<1:
        raise ValueError('Scrobble is missing a stable positive integer ID')
    if not isinstance(row.get('mediaFileId'),str) or not row['mediaFileId']:
        raise ValueError('Scrobble is missing its media ID')
    if type(row.get('submissionTime')) is not int:
        raise ValueError('Scrobble is missing its epoch-seconds timestamp')
    if not isinstance(song,dict) or song.get('id')!=row['mediaFileId']:
        raise ValueError('Song metadata does not match the scrobble media ID')
    for key in ('title','artist'):
        if not isinstance(song.get(key),str) or not song[key].strip():
            raise ValueError('Song metadata is missing a title or artist; no import was committed')
    return dict(source='navidrome:'+server_id,event_id=user_id+':'+str(row['id']),
                listener=listener,timestamp=datetime.fromtimestamp(row['submissionTime'],timezone.utc).isoformat(),
                track_id=row['mediaFileId'],title=song['title'],artist=song['artist'],
                album=song.get('album'),duration_ms=None)


def sync(client, db, server_id, listener, start, end, max_pages=100, page_size=100):
    start,end=instant(start),instant(end)
    if start>=end: raise ValueError('Start must precede end')
    if not server_id.strip() or not listener.strip(): raise ValueError('Server ID and listener must be nonempty')
    if not 1<=max_pages<=1000 or not 1<=page_size<=100:
        raise ValueError('Invalid import page bounds')
    songs={}; events=[]; seen=set()
    for page in range(max_pages):
        rows=client.history(start,end,page,page_size)
        for row in rows:
            if not isinstance(row,dict): raise ValueError('Unexpected history row')
            if type(row.get('submissionTime')) is not int: raise ValueError('Invalid event timestamp')
            timestamp=datetime.fromtimestamp(row['submissionTime'],timezone.utc).isoformat()
            if not start<=timestamp<end: continue
            media=row.get('mediaFileId')
            if not isinstance(media,str) or not media: raise ValueError('Missing media ID')
            if media not in songs: songs[media]=client.request('/api/song/'+quote(media,safe=''))
            record=convert(row,songs[media],server_id,client.user,listener)
            if record['event_id'] in seen:
                raise ValueError('History pages overlap; retry with a fixed historical interval')
            seen.add(record['event_id']); events.append(record)
        if len(rows)<page_size:
            result=import_events(db,events)
            return dict(result,tracks=len(songs),missing_duration_events=len(events),
                        start=start,end_exclusive=end,
                        coverage='Available per-user scrobble history only; not exact listening duration')
    raise ValueError('Import reached the page limit; use a shorter date interval. No events committed')
