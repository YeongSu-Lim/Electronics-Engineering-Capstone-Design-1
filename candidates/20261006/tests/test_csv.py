import csv
import json
from pathlib import Path
import tempfile
import unittest

import config
from alert_manager import AlertManager
from csv_logger import SessionLogger
from main import process_tracking_data
from summarize_logs import summarize
from target_selector import TargetSelector
from test_logic import Detections
from ttc_calculator import TTCCalculator


class CSVTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.calc = TTCCalculator()
        self.selector = TargetSelector()
        self.alerts = AlertManager(emit=lambda text: None)
        self.logger = SessionLogger(self.tmp.name, config, Path(__file__).resolve().parents[1], dataset_kind="SYNTHETIC_TEST")
        self.directory = self.logger.directory

    def tearDown(self):
        self.logger.close()
        self.tmp.cleanup()

    def frame(self, index, t, rows=()):
        telemetry = {}
        det = Detections(rows)
        targets, primary = process_tracking_data(det, {2:"car"}, self.calc, self.selector, self.alerts, t, telemetry)
        self.logger.record_frame(index,t,"synthetic",len(det),targets,primary,self.calc,self.selector,telemetry,1.0)
        return telemetry

    def rows(self, name):
        self.logger.close()
        with (self.directory / (name + '.csv')).open(encoding='utf-8-sig',newline='') as f:
            return list(csv.DictReader(f))

    def test_empty_frame_and_expiry_are_logged(self):
        self.frame(0,0,[(1,(150,100,250,200))]); self.frame(1,.6)
        frames = self.rows('frames')
        self.assertEqual(len(frames),2)
        self.assertEqual(frames[-1]['tracked_count'],'0')
        self.assertEqual(frames[-1]['retained_ids'],'0')
        self.assertIn('ID_EXPIRED',[r['event'] for r in self.rows('events')])
        self.assertFalse(self.calc.last_debug)

    def test_filter_rejected_observations_not_silenced(self):
        self.frame(0,0,[(1,(0,50,100,150)),(2,(150,100,200,150))])
        self.assertEqual({r['reason'] for r in self.rows('observations')},{'OUTSIDE_ROI','TOO_SMALL'})

    def test_prefilter_candidate_recorded_but_invalid(self):
        self.frame(0,0,[(1,(150,100,250,200))])
        self.frame(1,.1,[(1,(150,100,280,230))])
        row=self.rows('observations')[-1]
        self.assertEqual(row['reason'],'GROWTH_FILTER')
        self.assertEqual(row['raw_valid'],'0')
        self.assertGreater(float(row['candidate_ttc_s']),0)
        self.assertEqual(row['raw_ttc_s'],'')

    def test_alerts_selection_and_settings_snapshot(self):
        for i,s in enumerate([100,105,110,115]):
            self.frame(i,i*.05,[(1,(150,100,150+s,100+s))])
        frames=self.rows('frames')
        self.assertEqual(frames[-1]['primary_state'],'DANGER')
        self.assertEqual(sum(int(r['alert_emitted']) for r in frames),2)
        meta=json.loads((self.directory/'metadata.json').read_text())
        self.assertEqual(meta['dataset_kind'],'SYNTHETIC_TEST')
        self.assertEqual(meta['config']['THRESHOLD_DANGER'],2)
        self.assertIn('main.py',meta['source_sha256'])
        summary=summarize(self.directory)
        self.assertEqual(summary['frame_count'],4)
        self.assertNotIn('accuracy',summary)


if __name__ == '__main__':
    unittest.main()
