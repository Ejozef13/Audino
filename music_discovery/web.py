"""Loopback-only development UI. Never deploy this stdlib server publicly."""
import json
import os
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from .store import connect
from .analytics import statistics, year_window
from .links import youtube_search
from .recap import card


def serve(path, port, demo=False, artifact=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass  # query strings may contain private identifiers
        def send(self,code,body,kind='text/html; charset=utf-8'):
            data=body.encode()
            self.send_response(code)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            route=urlparse(self.path)
            if route.path not in ('/','/stats.json','/recap.svg'):
                return self.send(404,'Not found')
            query=parse_qs(route.query)
            get=lambda k,d:query.get(k,[d])[0]
            listener=get('listener',os.environ.get('MUSIC_DISCOVERY_LISTENER','demo' if demo else 'local'))
            tz=get('timezone',os.environ.get('MUSIC_DISCOVERY_TIMEZONE','UTC'))
            try:
                default_start,default_end=year_window(tz=tz)
            except (ValueError,KeyError):
                return self.send(400,'Invalid calendar timezone')
            start=get('start',default_start)
            end=get('end',default_end)
            method=get('method','als')
            db=connect(path)
            try:
                stats=statistics(db,listener,start,end,tz)
                if route.path=='/stats.json': return self.send(200,json.dumps(stats),'application/json')
                if route.path=='/recap.svg': return self.send(200,card(stats,demo),'image/svg+xml')
                e=lambda s:escape(str(s),quote=True)
                fields=''.join(f'<label>{k}<input name="{k}" value="{e(v)}" required></label>' for k,v in [('listener',listener),('start',start),('end',end),('timezone',tz)])
                artists=''.join(f'<li>{e(a["artist"])} <strong>{a["plays"]} plays</strong> · {a["reported_duration_ms"]/60000:.1f} reported minutes ({a["duration_events"]}/{a["plays"]} events have duration)</li>' for a in stats['artist_details'][:5]) or '<li>No events in this interval.</li>'
                tracks=''.join(f'<li>{e(t["title"])} — {e(t["artist"])} <strong>{t["plays"]} plays</strong> · {t["reported_duration_ms"]/60000:.1f} reported minutes ({t["duration_events"]}/{t["plays"]} events have duration)</li>' for t in stats['tracks'][:5])
                albums=''.join(f'<li>{e(a)} <strong>{n}</strong></li>' for a,n in stats['albums'])
                hours=''.join(f'<li>{h}:00 · {n} events</li>' for h,n in stats['hours'].items() if n)
                recs='<p>Model pending. No recommendations have been invented.</p>'
                if artifact:
                    from .model import load,rank
                    meta,x,y,counts=load(artifact)
                    suggestions=rank(meta,x,y,counts,listener,method=method)
                    feedback={r['track_id']:r['action'] for r in db.execute('SELECT track_id,action FROM feedback WHERE listener=?',(listener,))}
                    recs='<p>External catalog suggestions · library availability unverified</p><ul>'
                    for r in suggestions:
                        key=json.dumps([r['source'],r['track_id']],separators=(',',':'))
                        if feedback.get(key)=='dismiss': continue
                        link=youtube_search(r['artist'],r.get('title'))
                        search=f'<a href="{e(link)}" target="_blank" rel="noopener noreferrer">Search YouTube (unverified match)</a>' if link else '<small>Retrain this older artifact to include titles for YouTube search.</small>'
                        recs+=f'<li>{e(r["artist"])} · {e(r.get("title") or r["track_id"])}<small>{e(r["method"])} · score {r["score"]:.3f}</small>{search}<form method="post" action="/feedback"><input type="hidden" name="listener" value="{e(listener)}"><input type="hidden" name="track_id" value="{e(key)}"><button name="action" value="save">Save</button><button name="action" value="dismiss">Dismiss</button></form></li>'
                    recs+='</ul>'
                body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Music Discovery</title>
                <style>body{{font:17px system-ui;background:#10192b;color:#f5f2e9;max-width:1000px;margin:50px auto;padding:24px}}h1{{font-size:52px}}h2{{color:#edb871}}label,small{{display:block;margin:12px 0}}input,button{{padding:10px;border-radius:6px;border:1px solid #72809b}}input{{display:block;width:90%}}button{{background:#edb871;color:#10192b;cursor:pointer}}section{{background:#1c2942;padding:24px;border-radius:16px;margin:24px 0}}li{{padding:10px}}strong{{color:#edb871}}a{{color:#edb871}}</style>
                <p>{'SYNTHETIC DEMO · NOT YOUR LISTENING HISTORY' if demo else 'LOCAL IMPORTS · PRIVATE BY DEFAULT'}</p><h1>Music Discovery</h1><p>Your listening, in focus.</p>
                <details><summary>Choose listener and interval</summary><form>{fields}<button>Update dashboard</button></form></details>
                <section><h2>{stats['plays']} play events</h2><p>{e(start)} → {e(end)} (end exclusive)</p><p>Reported listening duration: {stats['reported_duration_ms']/60000:.1f} minutes across {stats['duration_events']} events; {stats['missing_duration_events']} events lack duration.</p><p>Coverage is imported events only. No skip or completion inference.</p></section>
                <section><h2>Top 5 artists</h2><ol>{artists}</ol><h2>Top 5 tracks</h2><ol>{tracks}</ol><h2>Top albums</h2><ol>{albums}</ol><details><summary>Listening hours ({e(tz)})</summary><ul>{hours}</ul></details></section>
                <section><h2>Discovery and baseline comparison</h2><p>Real-data comparison pending. Fixture results validate plumbing only.</p><form>{fields}<label>Method<select name="method"><option value="als">Implicit ALS</option><option value="popularity">Popularity baseline</option><option value="artist">Artist affinity baseline</option></select></label><button>Compare method</button></form>{recs}</section><form action="/recap.svg">{fields}<button>Export recap SVG</button></form><p>Recaps contain personal listening metadata. Review before sharing.</p></html>'''
                self.send(200,body)
            except (ValueError,KeyError) as exc: self.send(400,escape(str(exc)))
            finally: db.close()
        def do_POST(self):
            if self.path!='/feedback': return self.send(404,'Not found')
            # Browser forms from a different origin are refused; no permissive CORS.
            if self.headers.get('Origin') not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                return self.send(403,'Local origin required')
            length=int(self.headers.get('Content-Length','0'))
            if length<1 or length>4096: return self.send(400,'Invalid body size')
            query=parse_qs(self.rfile.read(length).decode())
            try:
                listener,track,action=(query[k][0] for k in ('listener','track_id','action'))
                if action not in ('save','dismiss'): raise ValueError('invalid action')
                db=connect(path)
                with db: db.execute('INSERT OR REPLACE INTO feedback VALUES (?,?,?,?)',(listener,track,action,datetime.now(timezone.utc).isoformat()))
                db.close(); self.send(200,'Saved locally. <a href="/">Dashboard</a>')
            except (KeyError,ValueError): self.send(400,'Invalid feedback')
    server=HTTPServer(('127.0.0.1',port),Handler)
    print(f'Listening on loopback port {port}',flush=True)
    server.serve_forever()
