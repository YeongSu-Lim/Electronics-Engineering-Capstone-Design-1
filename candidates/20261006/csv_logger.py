"""측정값을 실시간 CSV로 기록한다. 실제 정답 라벨은 자동으로 만들지 않는다."""
import csv
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import time
import uuid


FRAME_FIELDS = ["session_id", "frame_index", "timestamp_s", "time_basis", "source_delta_s",
    "tracked_count", "eligible_count", "retained_ids", "primary_id", "primary_state",
    "primary_ttc_s", "pending_id", "pending_since_s", "alert_emitted", "processing_ms",
    "ble_enabled", "ble_track_id", "ble_state", "ble_ttc_s", "ble_held", "ble_write_ok"]
OBS_FIELDS = ["session_id", "frame_index", "timestamp_s", "track_id", "class_id", "class_name",
    "confidence", "x1", "y1", "x2", "y2", "width_px", "height_px", "in_roi", "height_pass",
    "eligible", "reason", "size_px", "window_dt_s", "delta_size_px", "recent_delta_size_px",
    "delta_y2_px", "growth_ratio", "expansion_px_s", "candidate_ttc_s", "recent_expansion_pass",
    "growth_pass", "bottom_motion_pass", "window_expansion_pass", "raw_valid", "raw_ttc_s",
    "smoothed_ttc_s", "danger_streak", "state", "selected"]
EVENT_FIELDS = ["session_id", "frame_index", "timestamp_s", "event", "track_id", "other_id", "detail"]
LABEL_FIELDS = ["session_id", "clip_id", "event_id", "entity_id", "track_id", "start_s", "end_s",
    "approach_label", "risk_label", "reference_time_s", "reference_type", "notes"]


def clean(value):
    # inf/NaN을 0으로 기록하지 않는다. 빈칸으로 두고 유효성/사유와 함께 읽는다.
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else ""
    return value


class SessionLogger:
    def __init__(self, root="logs", config_module=None, source_dir=None,
                 flush_seconds=1.0, dataset_kind="REAL_UNLABELED"):
        if not math.isfinite(flush_seconds) or flush_seconds <= 0:
            raise ValueError("flush_seconds는 양의 유한수여야 합니다.")
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
        self.directory = Path(root) / self.session_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.handles, self.writers = {}, {}
        self.flush_seconds = flush_seconds
        self.last_flush = time.monotonic()
        self.previous_timestamp = None
        self.previous_primary = None
        try:
            for name, fields in [("frames", FRAME_FIELDS), ("observations", OBS_FIELDS), ("events", EVENT_FIELDS)]:
                h = (self.directory / (name + ".csv")).open("w", newline="", encoding="utf-8-sig")
                self.handles[name] = h
                self.writers[name] = csv.DictWriter(h, fieldnames=fields, extrasaction="ignore")
                self.writers[name].writeheader()
            with (self.directory / "annotations_template.csv").open("w", newline="", encoding="utf-8-sig") as h:
                csv.writer(h).writerow(LABEL_FIELDS)
            cfg = {k: v for k, v in vars(config_module).items() if k.isupper()} if config_module else {}
            versions = {}
            for package in ("numpy", "supervision", "opencv-python", "opencv-python-headless", "hailort"):
                try:
                    versions[package] = metadata.version(package)
                except metadata.PackageNotFoundError:
                    versions[package] = "not_reported"
            hashes = {}
            if source_dir:
                for path in sorted(Path(source_dir).glob("*.py")):
                    hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            info = {"session_id": self.session_id, "schema_version": 2, "dataset_kind": dataset_kind,
                "created_utc": datetime.now(timezone.utc).isoformat(), "config": cfg,
                "python": platform.python_version(), "platform": platform.platform(),
                "package_versions": versions, "source_sha256": hashes,
                "notes": ["상태는 알고리즘 출력이며 정답이 아님", "빈 수치는 무효 또는 미계산",
                    "processing_ms는 추론/판단/그리기/BLE 파일 쓰기 구간이며 영상/CSV 쓰기/캡처/화면대기 제외",
                    "ble_held=1은 과거 MAIN의 출력 유지. 현재 primary와 다를 수 있음. ble_write_ok는 무선 수신 확인 아님",
                    "observations는 검출기/추적기 출력 이후이며 confidence/class prefilter 탈락은 미포함",
                    "입력 영상 및 HEF 바이트는 복사/해시하지 않음: 실험 파일을 별도 보관"]}
            (self.directory / "metadata.json").write_text(json.dumps(info, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except Exception:
            self.close()
            raise

    def _write(self, name, row):
        self.writers[name].writerow({k: clean(v) for k, v in row.items()})

    def record_frame(self, frame_index, timestamp, time_basis, detections_count, targets,
                     primary, calculator, selector, telemetry, processing_ms):
        base = {"session_id": self.session_id, "frame_index": frame_index, "timestamp_s": timestamp}
        primary_id = primary.track_id if primary else None
        self._write("frames", {**base, "time_basis": time_basis,
            "source_delta_s": None if self.previous_timestamp is None else timestamp - self.previous_timestamp,
            "tracked_count": detections_count, "eligible_count": len(targets), "retained_ids": len(calculator.history),
            "primary_id": primary_id, "primary_state": primary.state if primary else "NONE",
            "primary_ttc_s": primary.ttc if primary else None, "pending_id": selector.pending_id,
            "pending_since_s": selector.pending_since, "alert_emitted": telemetry["alert_emitted"],
            "processing_ms": processing_ms,
            **{k: telemetry.get('ble', {}).get(k) for k in FRAME_FIELDS if k.startswith('ble_')}})
        for observation in telemetry["observations"]:
            self._write("observations", {**base, **observation,
                "selected": primary_id is not None and observation.get("eligible", False) and observation.get("track_id") == primary_id})
        events = list(telemetry["events"])
        if primary_id != self.previous_primary:
            events.append({"event": "PRIMARY_CHANGED", "track_id": primary_id,
                           "other_id": self.previous_primary, "detail": "current frame selection"})
        if telemetry["alert_emitted"]:
            events.append({"event": "ALERT_EMITTED", "track_id": primary_id,
                           "detail": primary.state})
        for event in events:
            self._write("events", {**base, **event})
        self.previous_primary = primary_id
        self.previous_timestamp = timestamp
        if time.monotonic() - self.last_flush >= self.flush_seconds:
            for h in self.handles.values():
                h.flush()
            self.last_flush = time.monotonic()

    def close(self):
        for h in self.handles.values():
            if not h.closed:
                h.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
