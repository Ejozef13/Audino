import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from music_discovery.store import connect,import_events
from music_discovery.demo import events
from music_discovery.experiment import run_validation


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(':memory:'); import_events(self.db,events())
        self.config=dict(dataset_version='fixture-v1',data_kind='fixture',train_before='2026-01-15T00:00:00Z',
                         validation_end='2026-01-22T00:00:00Z',test_end='2026-01-29T00:00:00Z',
                         factors=[4],iterations=2,seeds=[42],k=3,minimum_history=5)
    def tearDown(self): self.db.close()

    def test_frozen_config_baselines_and_test_unrun(self):
        from music_discovery.evaluate import evaluate
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'validation'
            with patch('music_discovery.experiment.evaluate',wraps=evaluate) as measured:
                result=run_validation(self.db,self.config,output)
            self.assertEqual(result['training_runs'],1)
            self.assertEqual(measured.call_count,1)
            self.assertEqual(measured.call_args.args[3],'2026-01-22T00:00:00+00:00')
            self.assertEqual(json.loads((output/'frozen-config.json').read_text()),self.config)
            report=json.loads((output/'validation-summary.json').read_text())
            self.assertEqual(len(report['runs'][0]['methods']),6)
            self.assertIn('UNRUN',report['test_status'])
            self.assertIn('popularity',(output/'comparison.md').read_text())
            with self.assertRaises(FileExistsError): run_validation(self.db,self.config,output)

    def test_invalid_boundaries_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'invalid'
            with self.assertRaises(ValueError): run_validation(self.db,dict(self.config,test_end='2026-01-01T00:00:00Z'),output)
            self.assertFalse(output.exists())


if __name__=='__main__': unittest.main()
