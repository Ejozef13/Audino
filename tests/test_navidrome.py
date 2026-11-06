import unittest
import io
from unittest.mock import Mock
from music_discovery.navidrome import Client, convert, sync
from music_discovery.store import connect


class FakeClient:
    user='fixture-user-id'
    def __init__(self, rows): self.rows=rows
    def history(self, start, end, page=0, size=100):
        return self.rows[page*size:(page+1)*size]
    def request(self, path, payload=None):
        return dict(id='song-1',title='Fixture title',artist='Fixture artist',album='Fixture album',duration=240)


class NavidromeTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(':memory:')
        self.start='2026-01-01T00:00:00Z'; self.end='2026-01-02T00:00:00Z'
        self.row=dict(id=1,mediaFileId='song-1',submissionTime=1767225600)
    def tearDown(self): self.db.close()

    def test_idempotence_repeated_plays_and_runtime_not_listening_duration(self):
        client=FakeClient([self.row,dict(self.row,id=2)])
        first=sync(client,self.db,'fixture-server','fixture-listener',self.start,self.end,page_size=1)
        self.assertEqual(first['inserted'],2)
        self.assertEqual(sync(client,self.db,'fixture-server','fixture-listener',self.start,self.end)['inserted'],0)
        rows=self.db.execute('SELECT * FROM events').fetchall()
        self.assertTrue(all(row['duration_ms'] is None for row in rows))
        self.assertEqual(rows[0]['source'],'navidrome:fixture-server')
        self.assertNotEqual(rows[0]['event_id'],rows[1]['event_id'])

    def test_exclusive_end(self):
        result=sync(FakeClient([self.row,dict(self.row,id=2,submissionTime=1767312000)]),
                    self.db,'fixture-server','fixture-listener',self.start,self.end)
        self.assertEqual(result['inserted'],1)

    def test_bounded_import_is_atomic(self):
        with self.assertRaises(ValueError):
            sync(FakeClient([self.row]),self.db,'fixture-server','fixture-listener',self.start,self.end,max_pages=1,page_size=1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
        with self.assertRaises(ValueError):
            sync(FakeClient([self.row,dict(self.row,id=2,mediaFileId='wrong-song')]),self.db,'fixture-server','fixture-listener',self.start,self.end)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],0)

    def test_overlapping_pages_and_source_ids_validated(self):
        with self.assertRaises(ValueError):
            sync(FakeClient([self.row,self.row]),self.db,'fixture-server','fixture-listener',self.start,self.end,page_size=1)
        with self.assertRaises(ValueError):
            convert(dict(self.row,id=None),{},'server','user','listener')

    def test_credentials_in_url_and_unsupported_scheme_refused(self):
        for url in ('file:///etc/passwd','https://name:password@example.com','https://example.com?token=secret'):
            with self.assertRaises(ValueError): Client(url)

    def test_native_authentication_and_history_request_contract(self):
        client=Client('http://fixture.invalid:4533')
        client.opener=Mock()
        client.opener.open.side_effect=[io.BytesIO(b'{"id":"fixture-user","token":"fixture-token"}'),
                                       io.BytesIO(b'[]')]
        client.login('fixture-name','fixture-password')
        self.assertEqual(client.history(self.start,self.end,size=1),[])
        login_request=client.opener.open.call_args_list[0].args[0]
        self.assertEqual(login_request.get_method(),'POST')
        self.assertTrue(login_request.full_url.endswith('/auth/login'))
        history_request=client.opener.open.call_args_list[1].args[0]
        self.assertEqual(history_request.get_method(),'GET')
        self.assertEqual(history_request.get_header('X-nd-authorization'),'Bearer fixture-token')
        self.assertIn('/api/scrobble?',history_request.full_url)
        self.assertNotIn('password',client.__dict__)


if __name__=='__main__': unittest.main()
