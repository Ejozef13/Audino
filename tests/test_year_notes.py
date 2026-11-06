import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from music_discovery.analytics import year_window, statistics
from music_discovery.demo import events
from music_discovery.links import youtube_search
from music_discovery.notes import export_year, MARKER
from music_discovery.store import connect, import_events


class YearAndNotesTests(unittest.TestCase):
    def test_year_is_local_and_current_end_is_now(self):
        now = datetime(2026,1,1,2,tzinfo=timezone.utc)
        start,end = year_window(tz='America/New_York',now=now)
        self.assertEqual(start,'2025-01-01T00:00:00-05:00')
        self.assertEqual(end,'2025-12-31T21:00:00-05:00')
        self.assertEqual(year_window(2024,'America/New_York',now)[1],'2025-01-01T00:00:00-05:00')
        with self.assertRaises(ValueError): year_window(2027,now=now)

    def test_exact_new_year_is_empty_and_future_plays_excluded(self):
        db=connect(':memory:')
        import_events(db,[events()[0]])
        start,end=year_window(now=datetime(2026,1,1,tzinfo=timezone.utc))
        self.assertEqual(statistics(db,'demo',start,end)['plays'],0)
        db.close()

    def test_export_is_repeatable_scoped_and_preserves_other_notes(self):
        db=connect(':memory:'); import_events(db,events())
        now=datetime(2026,2,1,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            personal=Path(directory)/'My notes.md'; personal.write_text('Keep me')
            result=export_year(db,'demo',directory,demo=True,now=now)
            original=result.read_text()
            self.assertIn('SYNTHETIC FIXTURE DEMO',original)
            self.assertIn('**28 play events**',original)
            self.assertIn('63.00 minutes from 21 events',original)
            self.assertEqual(export_year(db,'demo',directory,demo=True,now=now).read_text(),original)
            self.assertNotEqual(export_year(db,'fixture-1',directory,demo=True,now=now),result)
            self.assertEqual(personal.read_text(),'Keep me')
            result.write_text('This is now my own note')
            with self.assertRaises(ValueError): export_year(db,'demo',directory,now=now)
            result.unlink(); result.symlink_to(personal)
            with self.assertRaises(ValueError): export_year(db,'demo',directory,now=now)
            self.assertEqual(personal.read_text(),'Keep me')
        db.close()

    def test_duration_breakdown_and_markdown_untrusted_names(self):
        db=connect(':memory:')
        row=dict(events()[0],artist='[[private]] | <script>',title='A\n# Heading',duration_ms=None)
        import_events(db,[row,dict(row,event_id='second',duration_ms=120000)])
        stats=statistics(db,'demo','2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
        self.assertEqual(stats['tracks'][0]['duration_events'],1)
        self.assertEqual(stats['artist_details'][0]['reported_duration_ms'],120000)
        from music_discovery.notes import render
        note=render(stats)
        self.assertTrue(note.startswith(MARKER))
        self.assertNotIn('[[private]]',note)
        self.assertNotIn('<script>',note)
        db.close()

    def test_youtube_is_encoded_search_not_fake_video(self):
        url=youtube_search('A&B','Song / "Live"')
        self.assertEqual(urlparse(url).netloc,'www.youtube.com')
        self.assertEqual(parse_qs(urlparse(url).query)['search_query'],['A&B Song / "Live" audio'])
        self.assertIsNone(youtube_search('Artist',None))


if __name__=='__main__': unittest.main()
