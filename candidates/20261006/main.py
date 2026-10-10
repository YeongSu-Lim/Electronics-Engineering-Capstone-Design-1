"""프레임 시간 → 전체 TTC → 누락 처리 → 타겟 선정 → 단일 경보 → 화면 출력."""
import math
import time

import config
from alert_manager import AlertManager
from target_selector import Target, TargetSelector
from ttc_calculator import TTCCalculator


def process_tracking_data(detections, names, calculator, selector, alerts, timestamp, telemetry=None):
    # telemetry는 한 프레임의 기록만 보관한다. 기본 반환값은 기존과 같다.
    if telemetry is None:
        telemetry = {}
    telemetry.update(observations=[], events=[], alert_emitted=False)
    before_ids = set(calculator.history)
    calculator.expire_tracks(timestamp=timestamp)
    for ident in sorted(before_ids - set(calculator.history)):
        telemetry["events"].append({"event": "ID_EXPIRED", "track_id": ident, "detail": "TTL"})
    observed = set()
    targets = []
    rx1, ry1, rx2, ry2 = config.ROI_BOUNDARY
    ids = detections.tracker_id
    classes = detections.class_id
    confidences = getattr(detections, "confidence", None)

    for i in range(len(detections)):
        ident = ids[i] if ids is not None else None
        cls = classes[i] if classes is not None else None
        cls = int(cls) if cls is not None else None
        confidence = float(confidences[i]) if confidences is not None else None
        raw_box = tuple(float(v) for v in detections.xyxy[i])
        row = {"track_id": int(ident) if ident is not None else None,
               "class_id": cls, "class_name": names.get(cls, "unknown"), "confidence": confidence,
               "eligible": False, "raw_valid": False, "state": "UNASSESSED"}
        telemetry["observations"].append(row)
        if len(raw_box) != 4 or not all(math.isfinite(v) for v in raw_box):
            row["reason"] = "INVALID_BOX"
            if ident is not None:
                calculator.reset(int(ident))
            continue
        x1, y1, x2, y2 = raw_box
        w, h = x2 - x1, y2 - y1
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        in_roi = rx1 <= cx <= rx2 and ry1 <= cy <= ry2
        height_pass = h >= config.MIN_BOX_HEIGHT
        row.update(x1=x1, y1=y1, x2=x2, y2=y2, width_px=w, height_px=h,
                   in_roi=in_roi, height_pass=height_pass)
        if ident is None or int(ident) < 0 or cls is None:
            row["reason"] = "UNTRACKED_OR_NO_CLASS"
            continue
        ident = int(ident)
        if ident in observed:
            row["reason"] = "DUPLICATE_ID"
            continue
        if w <= 0 or h <= 0 or not in_roi or not height_pass:
            row["reason"] = ("INVALID_BOX" if w <= 0 or h <= 0 else
                             "OUTSIDE_ROI" if not in_roi else "TOO_SMALL")
            if ident in calculator.history:
                telemetry["events"].append({"event": "ID_RESET", "track_id": ident, "detail": row["reason"]})
            calculator.reset(ident)
            continue
        observed.add(ident)
        ttc, state = calculator.update_and_get_fsm(ident, w, h, y2, timestamp=timestamp)
        row.update(calculator.last_debug.get(ident, {}))
        row.update(eligible=True, state=state, reason=calculator.last_reason.get(ident, "UNKNOWN"))
        targets.append(Target(ident, names.get(cls, "unknown"), tuple(map(int, raw_box)),
                              ttc, state, row["reason"]))

    for ident in set(calculator.history) - observed:
        if calculator.last_reason.get(ident) != "MISSING":
            telemetry["events"].append({"event": "ID_MISSING", "track_id": ident, "detail": "not observed"})
        calculator.mark_missing(ident)
    alerts.cleanup(calculator.history.keys())
    primary = selector.select(targets, timestamp)
    telemetry["alert_emitted"] = alerts.process(primary, timestamp)
    return targets, primary


class FrameClock:
    """파일 시간과 실제 처리 시간을 분리한다. 같은 프레임에는 같은 값을 사용."""
    def __init__(self, mode, file_time_mode="pts", fps=0):
        if mode not in ("live", "file") or file_time_mode not in ("pts", "fps"):
            raise ValueError("INPUT_MODE/FILE_TIME_MODE 설정을 확인하세요.")
        if mode == "file" and file_time_mode == "fps" and not (math.isfinite(fps) and fps > 0):
            raise ValueError("고정 FPS 시간 모드에는 정상적인 영상 FPS가 필요합니다.")
        self.mode, self.file_time_mode, self.fps = mode, file_time_mode, fps
        self.index = 0
        self.last = None

    def next(self, position_ms=0):
        if self.mode == "live":
            now = time.monotonic()  # 프레임 수신 직후 호출; 실제 촬영 시각과 차이 존재
        elif self.file_time_mode == "fps":
            now = self.index / self.fps  # 고정 FPS 영상에만 사용, 가변 FPS에는 부적합
        else:
            now = position_ms / 1000.0
        if not math.isfinite(now) or (self.last is not None and now <= self.last):
            raise ValueError(
                "프레임 시간이 증가하지 않습니다. 영상 타임스탬프를 확인하세요. "
                "고정 FPS 영상인 경우에만 FILE_TIME_MODE='fps'로 지정할 수 있습니다."
            )
        self.last = now
        self.index += 1
        return now


def process_frame(detections, names, calculator, selector, alerts, ble, timestamp):
    """전체 객체 계산 → MAIN 선정 → 단일 경보 → 같은 MAIN의 BLE → CSV 자료."""
    telemetry = {}
    targets, primary = process_tracking_data(
        detections, names, calculator, selector, alerts, timestamp, telemetry)
    # 서로 다른 객체의 최고 등급/최소 TTC를 조합하지 않는다.
    telemetry['ble'] = ble.update(primary, timestamp)
    return targets, primary, telemetry


def camera_pipeline():
    if config.LIVE_CAMERA_PIPELINE:
        return config.LIVE_CAMERA_PIPELINE
    return (
        'libcamerasrc ! '
        f'video/x-raw, width={config.WINDOW_WIDTH}, height={config.WINDOW_HEIGHT}, '
        'framerate=30/1,format=RGBx ! videoconvert ! '
        'video/x-raw, format=BGR ! appsink drop=true max-buffers=1 sync=false'
    )


def run_collision_warning_system():
    # 로직 테스트에는 장비 패키지가 필요하지 않도록 지연 import.
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    import uuid
    import cv2
    import numpy as np
    from core_detector import DetectionEngine
    from visualizer import Visualizer
    from csv_logger import SessionLogger
    from ble_publisher import BLEPublisher

    if config.INPUT_MODE not in ('live', 'file'):
        raise ValueError("INPUT_MODE는 live 또는 file이어야 합니다.")
    if not math.isfinite(config.VIDEO_FPS) or config.VIDEO_FPS <= 0:
        raise ValueError('VIDEO_FPS는 양의 유한수여야 합니다.')
    calculator = TTCCalculator(config.TTC_HISTORY_FRAMES)
    selector = TargetSelector(config.TARGET_SWITCH_RATIO, config.TARGET_CONFIRM_SECONDS)
    alerts = AlertManager(config.DANGER_ALERT_INTERVAL, config.CAUTION_ALERT_INTERVAL)
    # 파일 재생은 분석용: 계산/CSV는 수행하되 실제 BLE 파일은 건드리지 않는다.
    ble = BLEPublisher(config.BLE_DATA_PATH, config.BLE_PERSIST_SECONDS,
                       config.BLE_ENABLED and config.INPUT_MODE == 'live')
    detector = capture = writer = logger = directory = None
    runtime = {}
    status = 'error'
    frame_index = write_calls = failed_reads = 0

    def save_runtime():
        path = directory / 'runtime.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)

    try:
        renderer = Visualizer()
        detector = DetectionEngine()
        # 팀원 장비 코드의 시작 순서 유지: 더미 추론 후 카메라 개방.
        dummy = np.zeros((config.WINDOW_HEIGHT, config.WINDOW_WIDTH, 3), dtype=np.uint8)
        detector.get_vehicle_results(dummy)
        del dummy
        live = config.INPUT_MODE == 'live'
        source = camera_pipeline() if live else config.VIDEO_PATH
        capture = cv2.VideoCapture(source, cv2.CAP_GSTREAMER if live else cv2.CAP_ANY)
        if not capture.isOpened():
            status = 'capture_open_failed'
            raise RuntimeError(f'영상 입력을 열 수 없습니다: {source}')
        if live:
            print(f'[*] 카메라 웜업: {config.CAMERA_WARMUP_SECONDS:.1f}초')
            time.sleep(config.CAMERA_WARMUP_SECONDS)
        clock = FrameClock(config.INPUT_MODE, config.FILE_TIME_MODE, capture.get(cv2.CAP_PROP_FPS))
        root = Path(config.CSV_LOG_DIR)
        if not root.is_absolute():
            root = Path(__file__).resolve().parent / root
        if config.CSV_ENABLED:
            logger = SessionLogger(root, config, Path(__file__).parent, config.CSV_FLUSH_SECONDS)
            directory = logger.directory
        else:
            directory = root / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid.uuid4().hex[:8])
            directory.mkdir(parents=True, exist_ok=False)
        runtime = {
            'version': 'FULL-TARGET-BLE-CSV-VIDEO-20261006', 'status': 'initializing',
            'source': source, 'input_mode': config.INPUT_MODE,
            'ble_file': str(ble.path.resolve()), 'ble_file_enabled': ble.enabled,
            'ble_persist_seconds': ble.persist_seconds,
            'ble_policy': 'Use selected MAIN state and TTC from the same object; hold output only when no MAIN',
            'video_enabled': config.VIDEO_ENABLED,
            'video_file': 'annotated.mp4' if config.VIDEO_ENABLED else None,
            'playback_fps': config.VIDEO_FPS, 'codec_requested': config.VIDEO_CODEC,
            'video_opened': False, 'video_released': False,
            'frame_mapping': 'On a successful recording: video frame 1 corresponds to CSV frame_index 0',
            'timing': 'Use CSV timestamp_s/source_delta_s, not fixed-FPS playback time',
            'processing_ms_scope': 'Preprocess/inference/TTC/selection/alerts/BLE/drawing; excludes video/CSV writes and capture/display waits',
        }
        save_runtime()
        if config.VIDEO_ENABLED:
            writer = cv2.VideoWriter(str(directory / 'annotated.mp4'),
                cv2.VideoWriter_fourcc(*config.VIDEO_CODEC), config.VIDEO_FPS,
                (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
            if not writer.isOpened():
                status = 'video_open_failed'
                raise RuntimeError('동영상 저장기를 열 수 없습니다. 코덱/경로를 확인하거나 VIDEO_ENABLED=False로 시험하세요.')
            runtime['video_opened'] = True
        runtime['status'] = 'running'
        save_runtime()
        print(f'[*] FULL 통합본 기록 폴더: {directory}')
        print('[*] MAIN 선정 + 단일 경보 + BLE + CSV + 영상 (q / Ctrl+C 종료)')
        first_timestamp = None
        while capture.isOpened():
            success, frame = capture.read()
            if not success:
                failed_reads += 1
                if not live:
                    status = 'file_read_ended'
                    break
                # 카메라 읽기 실패는 성공한 빈 검출 프레임과 구분한다.
                # 수신이 중단된 동안의 BLE 신선도는 송신기 측 감시가 필요하다.
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    status = 'quit_key'
                    break
                time.sleep(0.01)
                continue
            timestamp = clock.next(capture.get(cv2.CAP_PROP_POS_MSEC))
            if first_timestamp is None:
                first_timestamp = timestamp
            start = time.monotonic()
            display = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
            canvas = display.copy()
            detections = detector.get_vehicle_results(display)
            targets, primary, telemetry = process_frame(
                detections, detector.vehicle_names, calculator, selector, alerts, ble, timestamp)
            renderer.draw_roi_zone(canvas)
            for target in targets:
                renderer.draw_target(canvas, target, primary is not None and target.track_id == primary.track_id)
            elapsed_ms = (time.monotonic() - start) * 1000
            renderer.draw_status(canvas, primary, len(calculator.history), elapsed_ms)
            stamp = f'Index:{frame_index} | t={timestamp-first_timestamp:.3f}s'
            cv2.putText(canvas, stamp, (8, config.WINDOW_HEIGHT-12), cv2.FONT_HERSHEY_SIMPLEX,
                        .45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(canvas, stamp, (8, config.WINDOW_HEIGHT-12), cv2.FONT_HERSHEY_SIMPLEX,
                        .45, (255, 255, 255), 1, cv2.LINE_AA)
            if writer is not None:
                writer.write(canvas)
                write_calls += 1  # 호출 완료 수이며 실제 디코딩 프레임 수를 검증한 값은 아님
            if logger is not None:
                basis = 'receive_monotonic' if live else config.FILE_TIME_MODE
                logger.record_frame(frame_index, timestamp, basis, len(detections), targets,
                                    primary, calculator, selector, telemetry, elapsed_ms)
            frame_index += 1
            cv2.imshow('Smart Backpack FULL - MAIN Target', canvas)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                status = 'quit_key'
                break
        else:
            status = 'capture_closed'
    except KeyboardInterrupt:
        status = 'keyboard_interrupt'
        print('\n[*] 종료 요청: 기록 파일을 닫습니다.')
    finally:
        errors = []
        def cleanup(name, operation):
            try:
                operation()
                return True
            except Exception as exc:
                errors.append(f'{name}: {exc}')
                print(f'[!] {name} 종료 확인 필요: {exc}')
                return False
        if writer is not None:
            runtime['video_released'] = cleanup('video', writer.release)
        if capture is not None:
            cleanup('capture', capture.release)
        if detector is not None:
            close = getattr(detector, 'close', None)
            if callable(close):
                cleanup('detector', close)
        if logger is not None:
            cleanup('csv', logger.close)
        cleanup('windows', cv2.destroyAllWindows)
        calculator.reset()
        selector.reset()
        alerts.reset()
        ble.reset()
        # 호환을 위해 종료 시 BLE 파일을 SAFE로 덮어쓰지는 않는다.
        if directory is not None:
            runtime.update(status=status if not errors else status+'_cleanup_error',
                completed_frames=frame_index, video_write_calls_completed=write_calls,
                capture_read_failures=failed_reads, cleanup_errors=list(errors))
            cleanup('runtime', save_runtime)
            print(f"[*] 기록 종료 ({runtime['status']}): {directory}")


if __name__ == '__main__':
    run_collision_warning_system()
