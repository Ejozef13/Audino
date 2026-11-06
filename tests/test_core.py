import json
import tempfile
import unittest
from pathlib import Path
from music_discovery.store import connect, import_events
from music_discovery.analytics import statistics
from music_discovery.demo import events
from music_discovery.recap import card


class CoreTests(unittest.TestCase):
    def setUp(self): self.db=connect(':memory:')
    def tearDown(self): self.db.close()
    def test_idempotent_preserves_repeated_plays(self):
        row=events()[0]; repeated=dict(row,event_id='different-event')
        self.assertEqual(import_events(self.db,[row,repeated])['inserted'],2)
        self.assertEqual(import_events(self.db,[row,repeated])['inserted'],0)
    def test_conflicts_and_invalid_batches_are_atomic(self):
        row=events()[0]; import_events(self.db,[row])
        with self.assertRaises(ValueError): import_events(self.db,[dict(row,event_id='new'),dict(row,title='conflict')])
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
        for duration in (-1,True,1.5):
            with self.assertRaises(ValueError): import_events(self.db,[dict(row,duration_ms=duration)])
        with self.assertRaises(ValueError): import_events(self.db,[dict(row,timestamp='2026-01-01')])
    def test_offsets_exclusive_boundaries_and_missing_duration(self):
        row=events()[0]
        import_events(self.db,[dict(row,timestamp='2026-01-01T19:00:00-05:00'),
                              dict(row,event_id='next',timestamp='2026-01-03T00:00:00Z',duration_ms=60)])
        stats=statistics(self.db,'demo','2026-01-02T00:00:00Z','2026-01-03T00:00:00Z','America/New_York')
        self.assertEqual(stats['plays'],1)
        self.assertEqual(stats['hours']['19'],1)
        self.assertEqual(stats['missing_duration_events'],1)
        self.assertEqual(stats['reported_duration_ms'],0)
    def test_deterministic_and_xml_safe(self):
        import_events(self.db,[dict(events()[0],artist='<script>&')])
        args=(self.db,'demo','2026-01-01T00:00:00Z','2027-01-01T00:00:00Z')
        self.assertEqual(statistics(*args),statistics(*args))
        svg=card(statistics(*args),True)
        self.assertIn('&lt;script&gt;&amp;',svg)
        self.assertIn('SYNTHETIC DEMO',svg)


class ModelTests(unittest.TestCase):
    def test_leakage_roundtrip_and_eligibility(self):
        from music_discovery.model import fit,load,rank,prepare
        from music_discovery.evaluate import evaluate
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            db=connect(':memory:'); import_events(db,events())
            cutoff='2026-01-15T00:00:00Z'
            before=prepare(db,cutoff)[3].copy()
            import_events(db,[dict(events()[0],event_id='future',timestamp='2026-02-01T00:00:00Z',track_id='future-only',title='Future metadata')])
            np.testing.assert_array_equal(before,prepare(db,cutoff)[3])
            path=Path(directory)/'model.npz'
            fit(db,cutoff,path,factors=4,iterations=2)
            meta,x,y,counts=load(path)
            self.assertNotIn(['synthetic-demo','future-only'],meta['items'])
            self.assertNotIn('Future metadata',meta['titles'])
            self.assertEqual(len(meta['titles']),len(meta['items']))
            seen={tuple(meta['items'][j]) for j in np.flatnonzero(counts[0])}
            recommendations=rank(meta,x,y,counts,meta['users'][0])
            self.assertTrue(all((r['source'],r['track_id']) not in seen for r in recommendations))
            self.assertTrue(all((r['source'],r['track_id']) in seen for r in rank(meta,x,y,counts,meta['users'][0],mode='repeat')))
            unknown=rank(meta,x,y,counts,'unknown')
            self.assertIn('fallback',unknown[0]['method'])
            report=evaluate(db,path,cutoff,'2026-01-29T00:00:00Z',k=3)
            self.assertEqual(len(report['methods']),6)
            self.assertGreater(report['methods']['discovery/als']['eligible_users'],0)
            with self.assertRaises(ValueError): evaluate(db,path,'2026-01-16T00:00:00Z','2026-01-29T00:00:00Z')
            json.dumps(report)
            db.close()
    def test_ranking_metrics_known_example(self):
        from music_discovery.model import fit
        from music_discovery.evaluate import evaluate
        with tempfile.TemporaryDirectory() as directory:
            db=connect(':memory:')
            row=events()[0]
            batch=[dict(row,event_id='a',listener='a',track_id='a',timestamp='2026-01-01T00:00:00Z'),
                   dict(row,event_id='b',listener='b',track_id='b',timestamp='2026-01-01T00:00:00Z'),
                   dict(row,event_id='c',listener='a',track_id='b',timestamp='2026-01-03T00:00:00Z')]
            import_events(db,batch)
            path=Path(directory)/'model.npz'; fit(db,'2026-01-02T00:00:00Z',path,factors=2,iterations=1)
            report=evaluate(db,path,'2026-01-02T00:00:00Z','2026-01-04T00:00:00Z',k=1,minimum=1)
            metric=report['methods']['discovery/popularity']
            self.assertEqual(metric['eligible_users'],1)
            self.assertEqual(metric['metrics']['recall']['mean'],1)
            self.assertEqual(metric['metrics']['ndcg']['mean'],1)
            db.close()


if __name__=='__main__': unittest.main()
