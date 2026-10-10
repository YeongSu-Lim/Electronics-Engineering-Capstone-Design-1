"""하드웨어 없이 MAIN / BLE / CSV 및 시작·종료 연결을 검증한다."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import config
import main
from alert_manager import AlertManager
from ble_publisher import BLEPublisher
from csv_logger import SessionLogger
from target_selector import Target, TargetSelector
from test_logic import Detections
from ttc_calculator import TTCCalculator


class IntegrationTests(unittest.TestCase):
    def test_primary_ble_csv_consistent_and_hold_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            calc,selector=TTCCalculator(),TargetSelector()
            messages=[]
            alerts=AlertManager(emit=messages.append)
            ble=BLEPublisher(Path(tmp)/'ble.txt')
            logger=SessionLogger(tmp,config,Path(__file__).resolve().parents[1],dataset_kind='SYNTHETIC_TEST')
            for i,size in enumerate([100,105,110,115]):
                rows=[(1,(150,100,150+size,100+size))]
                if i>=2:
                    s=100 if i==2 else 115
                    rows.append((2,(300,100,300+s,100+s)))
                det=Detections(rows)
                targets,primary,telemetry=main.process_frame(det,{2:'car'},calc,selector,alerts,ble,i*.05)
                logger.record_frame(i,i*.05,'synthetic',len(det),targets,primary,calc,selector,telemetry,1)
            # ID2 has a lower TTC, but is only CAUTION (pending danger); MAIN must be ID1 DANGER.
            self.assertEqual(primary.track_id,1)
            self.assertEqual(primary.state,'DANGER')
            self.assertLess(next(t.ttc for t in targets if t.track_id==2),primary.ttc)
            self.assertEqual(telemetry['ble']['ble_track_id'],1)
            self.assertAlmostEqual(telemetry['ble']['ble_ttc_s'],primary.ttc)
            self.assertEqual((Path(tmp)/'ble.txt').read_text(),f'DANGER,0.0,0.0,{primary.ttc:.1f}')
            for index,t in enumerate([.3,.8,1.2],4):
                targets,primary,telemetry=main.process_frame(Detections([]),{2:'car'},calc,selector,alerts,ble,t)
                logger.record_frame(index,t,'synthetic',0,targets,primary,calc,selector,telemetry,1)
                self.assertIsNone(primary)
                if t==.3:
                    self.assertEqual(calc.danger_streak[1],0)
                    self.assertTrue(telemetry['ble']['ble_held'])
                if t==.8:
                    self.assertFalse(calc.history)
                    self.assertFalse(alerts.last_alert)
                    self.assertTrue(telemetry['ble']['ble_held'])
            self.assertEqual(telemetry['ble']['ble_state'],'SAFE')
            logger.close()
            with (logger.directory/'frames.csv').open(encoding='utf-8-sig') as f:
                frames=list(csv.DictReader(f))
            self.assertEqual(frames[3]['primary_id'],frames[3]['ble_track_id'])
            self.assertEqual(frames[3]['primary_ttc_s'],frames[3]['ble_ttc_s'])
            self.assertEqual(frames[4]['primary_state'],'NONE')
            self.assertEqual(frames[4]['ble_state'],'DANGER')
            self.assertEqual(frames[4]['ble_held'],'1')
            with (logger.directory/'observations.csv').open(encoding='utf-8-sig') as f:
                selected=[r for r in csv.DictReader(f) if r['frame_index']=='3' and r['selected']=='1']
            self.assertEqual([r['track_id'] for r in selected],['1'])

    def test_switch_uses_new_selected_object_without_old_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=BLEPublisher(Path(tmp)/'ble.txt')
            first=Target(1,'car',(0,0,10,10),1.2,'DANGER')
            second=Target(2,'car',(0,0,10,10),3.0,'CAUTION')
            b.update(first,0)
            output=b.update(second,.1)
            self.assertEqual(output['ble_track_id'],2)
            self.assertEqual(output['ble_state'],'CAUTION')
            self.assertFalse(output['ble_held'])

    def test_disabled_ble_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ble.txt';path.write_text('existing')
            b=BLEPublisher(path,enabled=False)
            self.assertIsNone(b.update(None,0)['ble_write_ok'])
            self.assertEqual(path.read_text(),'existing')

    def test_ble_write_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=BLEPublisher(Path(tmp)/'missing'/'ble.txt')
            self.assertFalse(b.update(None,0)['ble_write_ok'])

    def test_ble_clock_rewind_clears_held_output(self):
        b=BLEPublisher(enabled=False)
        b.update(Target(1,'car',(),1,'DANGER'),10)
        self.assertEqual(b.update(None,1)['ble_state'],'SAFE')


class LifecycleTests(unittest.TestCase):
    def run_case(self,mode):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[];frames=[];stamps=[];rendered=[]
            class Image:
                def copy(self):return self
            class Detector:
                vehicle_names={2:'car'}
                def get_vehicle_results(self,frame):
                    calls.append('infer')
                    return Detections([])
                def close(self):calls.append('detector_close')
            class Renderer:
                def draw_roi_zone(self,*a):pass
                def draw_target(self,canvas,target,selected):rendered.append((target,selected))
                def draw_status(self,*a):pass
            class Capture:
                count=0
                def isOpened(self):return mode!='capture_failure'
                def get(self,prop):return 30 if prop==1 else max(0,self.count-1)*100
                def read(self):
                    self.count+=1
                    if self.count<=2:return True,Image()
                    if mode=='interrupt':raise KeyboardInterrupt()
                    if mode=='processing_error':raise RuntimeError('read failed')
                    return False,None
                def release(self):calls.append('capture_close')
            cap=Capture()
            class Writer:
                def __init__(self,path,codec,fps,size):
                    calls.append(('video_open',path));Path(path).write_bytes(b'MOCK_ONLY')
                def isOpened(self):return mode!='video_open_failure'
                def write(self,frame):
                    if mode=='video_write_failure':raise OSError('video write failed')
                    frames.append(frame)
                def release(self):
                    calls.append('video_close')
                    if mode=='video_close_failure':raise OSError('video release failed')
            def open_capture(source,backend):
                self.assertEqual(calls,['infer'])
                if mode=='file':self.assertEqual(source,'fake.mp4')
                else:self.assertIn('max-buffers=1',source)
                return cap
            def sleep(seconds):
                if mode=='warmup_interrupt':raise KeyboardInterrupt()
            def wait(delay):
                return ord('q') if cap.count==2 and mode not in ('file','interrupt','processing_error') else -1
            fake_cv=types.SimpleNamespace(VideoCapture=open_capture,VideoWriter=Writer,
                CAP_GSTREAMER=0,CAP_ANY=2,CAP_PROP_FPS=1,CAP_PROP_POS_MSEC=3,
                VideoWriter_fourcc=lambda *a:'mp4v',resize=lambda frame,sz:frame,
                FONT_HERSHEY_SIMPLEX=0,LINE_AA=0,putText=lambda frame,s,*a:stamps.append(s),
                imshow=lambda *a:None,waitKey=wait,destroyAllWindows=lambda:calls.append('windows_close'))
            modules={'cv2':fake_cv,'core_detector':types.SimpleNamespace(DetectionEngine=Detector),
                     'visualizer':types.SimpleNamespace(Visualizer=Renderer),
                     'numpy':types.SimpleNamespace(zeros=lambda *a,**kw:Image(),uint8=0)}
            overrides=dict(CSV_LOG_DIR=tmp,INPUT_MODE='file' if mode=='file' else 'live',VIDEO_PATH='fake.mp4',
                BLE_DATA_PATH=str(Path(tmp)/'ble.txt'),VIDEO_ENABLED=mode!='video_disabled',
                CSV_ENABLED=mode!='csv_disabled')
            with patch.dict(sys.modules,modules),patch.multiple(config,**overrides),patch.object(main.time,'sleep',side_effect=sleep):
                if mode in ('capture_failure','video_open_failure','video_write_failure','processing_error'):
                    with self.assertRaises((OSError,RuntimeError)):
                        main.run_collision_warning_system()
                else:main.run_collision_warning_system()
            self.assertIn('capture_close',calls)
            self.assertIn('detector_close',calls)
            self.assertIn('windows_close',calls)
            dirs=[p for p in Path(tmp).iterdir() if p.is_dir()]
            if not dirs:
                self.assertIn(mode,('capture_failure','warmup_interrupt'))
                return
            runtime=json.loads((dirs[0]/'runtime.json').read_text())
            if mode in ('normal','video_disabled','csv_disabled','video_close_failure','interrupt','processing_error','file'):
                self.assertEqual(runtime['completed_frames'],2)
                self.assertEqual(runtime['video_write_calls_completed'],0 if mode=='video_disabled' else 2)
                self.assertTrue(stamps[0].startswith('Index:0'))
                self.assertTrue(stamps[2].startswith('Index:1'))
                if mode!='csv_disabled':
                    with (dirs[0]/'frames.csv').open(encoding='utf-8-sig') as f:
                        rows=list(csv.DictReader(f))
                    self.assertEqual([r['frame_index'] for r in rows],['0','1'])
            if mode=='file':
                self.assertFalse((Path(tmp)/'ble.txt').exists())
                self.assertEqual(rows[0]['time_basis'],'pts')
                self.assertEqual(runtime['status'],'file_read_ended')
            if mode=='video_open_failure':self.assertEqual(runtime['status'],'video_open_failed')
            if mode=='video_close_failure':self.assertEqual(runtime['status'],'quit_key_cleanup_error')
            if mode=='interrupt':self.assertEqual(runtime['status'],'keyboard_interrupt')

for _mode in ('normal','file','video_disabled','csv_disabled','video_open_failure','video_write_failure',
              'video_close_failure','capture_failure','warmup_interrupt','interrupt','processing_error'):
    def test(self,mode=_mode):self.run_case(mode)
    setattr(LifecycleTests,'test_'+_mode,test)

if __name__=='__main__':unittest.main(verbosity=2)
