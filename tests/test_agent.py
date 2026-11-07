import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from music_discovery.agent import Ollama, Toolbox, run
from music_discovery.demo import events
from music_discovery.model import fit,load,rank_profile
from music_discovery.store import connect,import_events


class ScriptedOllama:
    model='fixture-mock-not-a-real-LLM'
    def __init__(self,responses): self.responses=iter(responses); self.messages=[]
    def chat(self,messages,tools):
        self.messages.append(list(messages))
        return {'message':next(self.responses)}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(':memory:'); import_events(self.db,events())
        self.tools=Toolbox(self.db,'demo','2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')
    def tearDown(self): self.db.close()

    def test_roundtrip_tools_have_deterministic_evidence(self):
        client=ScriptedOllama([
            {'role':'assistant','content':'','tool_calls':[{'function':{'name':'listening_summary','arguments':{}}}]},
            {'role':'assistant','content':'The tool reports 28 events.'}])
        result=run(client,self.tools,'Summarize my listening')
        self.assertEqual(result['evidence'][0]['result']['plays'],28)
        self.assertEqual(client.messages[1][-1]['role'],'tool')
        self.assertEqual(result['status'],'completed')

    def test_model_cannot_change_listener_execute_sql_or_write_files(self):
        for name,args in [('run_shell',{'command':'anything'}),('listening_summary',{'listener':'other'}),
                          ('recommend_tracks',{'sql':'SELECT 1'}),('recommend_tracks',{'k':True})]:
            with self.assertRaises(ValueError): self.tools.dispatch(name,args)
        result=self.tools.dispatch('recommend_tracks',{})
        self.assertEqual(result['status'],'not_ready')

    def test_no_tools_used_is_explicit_and_loop_budget_stops(self):
        result=run(ScriptedOllama([{'role':'assistant','content':'Unsupported claim'}]),self.tools,'Question')
        self.assertEqual(result['status'],'no_tools_used')
        repeated={'role':'assistant','content':'','tool_calls':[{'function':{'name':'listening_summary','arguments':{}}}]}
        with self.assertRaises(ValueError): run(ScriptedOllama([repeated]*4),self.tools,'Question',max_rounds=2)

    def test_fixture_catalog_refused_for_personal_use(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.npz'; fit(self.db,'2026-01-15T00:00:00Z',path,factors=4,iterations=2,data_kind='fixture')
            self.tools.artifact=path
            self.assertEqual(self.tools.dispatch('recommend_tracks',{})['status'],'not_ready')
            self.tools.demo=True
            result=self.tools.dispatch('recommend_tracks',{})
            self.assertTrue(result['personalized'])
            self.assertEqual(result['matched_events'],28)
            self.assertTrue(all(r['youtube_search'].startswith('https://www.youtube.com/results?') for r in result['recommendations']))

    def test_explicit_mapping_and_unmatched_cold_start(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.npz'; fit(self.db,'2026-01-15T00:00:00Z',path,factors=4,iterations=2,data_kind='fixture')
            import_events(self.db,[dict(events()[0],source='navidrome:fixture-server',event_id='local',listener='local-person',track_id='local-track')])
            tools=Toolbox(self.db,'local-person',self.tools.start,self.tools.end,artifact=path,demo=True)
            result=tools.dispatch('recommend_tracks',{})
            self.assertFalse(result['personalized']); self.assertEqual(result['unmatched_events'],1)
            self.assertIn('fallback',result['recommendations'][0]['method'])
            tools.mapping=[dict(source='navidrome:fixture-server',track_id='local-track',model_source='synthetic-demo',model_track_id='fictional-track-0')]
            result=tools.dispatch('recommend_tracks',{})
            self.assertTrue(result['personalized']); self.assertEqual(result['matched_events'],1)
            self.assertTrue(all(r['track_id']!='fictional-track-0' for r in result['recommendations']))

    def test_fold_in_known_item_is_repeat_only_and_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.npz'; fit(self.db,'2026-01-15T00:00:00Z',path,factors=4,iterations=2)
            meta,x,y,counts=load(path); profile=np.zeros(len(meta['items'])); profile[0]=3
            recs=rank_profile(meta,y,counts,profile,mode='repeat')
            self.assertEqual(len(recs),1)
            self.assertEqual(recs[0]['track_id'],meta['items'][0][1])
            self.assertEqual(recs,rank_profile(meta,y,counts,profile,mode='repeat'))
            with self.assertRaises(ValueError): rank_profile(meta,y,counts,profile*np.nan)

    def test_corrupt_model_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.npz'; fit(self.db,'2026-01-15T00:00:00Z',path,factors=4,iterations=2)
            meta,x,y,counts=load(path)
            x[0,0]=np.nan
            np.savez(path,x=x,y=y,counts=counts,metadata=json.dumps(meta))
            with self.assertRaises(ValueError): load(path)

    def test_ollama_stays_local_and_cloud_tags_refused(self):
        for url in ('https://example.com','http://192.168.1.1:11434','http://user:pass@localhost:11434','http://localhost:11434/path'):
            with self.assertRaises(ValueError): Ollama(url)
        with self.assertRaises(ValueError): Ollama(model='gpt-oss:20b-cloud')
        self.assertEqual(Ollama().model,'gpt-oss:20b')


if __name__=='__main__': unittest.main()
