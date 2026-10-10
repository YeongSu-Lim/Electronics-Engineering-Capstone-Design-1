"""그리기와 경보를 분리한다. 선정된 한 객체만 이 모듈에 전달한다."""
import math


class AlertManager:
    def __init__(self, danger_interval=0.5, caution_interval=1.5, emit=print):
        self.intervals = {"DANGER": danger_interval, "CAUTION": caution_interval}
        if any(not math.isfinite(v) or v <= 0 for v in self.intervals.values()):
            raise ValueError("경보 간격은 양의 유한수여야 합니다.")
        self.emit = emit
        self.reset()

    def reset(self):
        self.last_alert = {}  # (객체 ID, 경보 등급) -> 마지막 알림 시각
        self.last_emit_time = None
        self.last_emit_state = None

    def cleanup(self, retained_ids):
        # TTC 이력이 만료된 ID의 알림 기록도 함께 삭제한다.
        retained_ids = set(retained_ids)
        for key in list(self.last_alert):
            if key[0] not in retained_ids:
                del self.last_alert[key]

    def process(self, target, timestamp):
        if target is None:
            return False
        if target.state not in self.intervals or not math.isfinite(target.ttc):
            return False
        if self.last_emit_time is not None and timestamp < self.last_emit_time:
            self.reset()
        key = (target.track_id, target.state)
        interval = self.intervals[target.state]
        if timestamp - self.last_alert.get(key, -math.inf) < interval:
            return False

        # 타겟 ID만 바뀌어 알림이 연속 출력되는 현상도 제한한다.
        # 단, 마지막 출력이 주의였고 지금 위험이면 즉시 위험 알림을 허용한다.
        escalation = target.state == "DANGER" and self.last_emit_state != "DANGER"
        if (not escalation and self.last_emit_time is not None
                and timestamp - self.last_emit_time < interval):
            return False
        self.emit(
            f"[{target.state}] MAIN ID:{target.track_id} {target.label} "
            f"TTC:{target.ttc:.2f}s"
        )
        self.last_alert[key] = timestamp
        self.last_emit_time = timestamp
        self.last_emit_state = target.state
        return True
