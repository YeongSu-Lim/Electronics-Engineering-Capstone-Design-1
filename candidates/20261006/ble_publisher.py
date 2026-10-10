"""선정된 MAIN의 상태와 TTC를 같은 객체에서 가져와 BLE 공유 파일에 기록."""
import math
from pathlib import Path


class BLEPublisher:
    def __init__(self, path='shared_ble_data.txt', persist_seconds=1.0, enabled=True):
        if not math.isfinite(persist_seconds) or persist_seconds < 0:
            raise ValueError('BLE_PERSIST_SECONDS는 0 이상의 유한수여야 합니다.')
        self.path = Path(path)
        self.persist_seconds = persist_seconds
        self.enabled = enabled
        self.failed = False
        self.reset()

    def reset(self):
        self.last_target = None
        self.last_seen = None
        self.last_time = None

    def update(self, primary, timestamp):
        if not math.isfinite(timestamp):
            raise ValueError('BLE 시간은 유한수여야 합니다.')
        if self.last_time is not None and timestamp < self.last_time:
            self.reset()
        self.last_time = timestamp
        valid = (primary is not None and primary.state in ('CAUTION', 'DANGER')
                 and math.isfinite(primary.ttc) and primary.ttc > 0)
        held = False
        if valid:
            self.last_target, self.last_seen = primary, timestamp
            output = primary
        elif self.last_seen is not None and timestamp - self.last_seen < self.persist_seconds:
            output = self.last_target
            held = True
        else:
            output = None
            self.last_target = self.last_seen = None

        state = output.state if output else 'SAFE'
        ttc = output.ttc if output else 99.9
        payload = f'{state},0.0,0.0,{ttc:.1f}'
        success = None  # 무선 수신 여부가 아니라 파일 쓰기 결과. 비활성화면 빈 값.
        if self.enabled:
            try:
                with self.path.open('w', encoding='utf-8') as handle:
                    handle.write(payload)
                success = True
                self.failed = False
            except OSError as exc:
                success = False
                if not self.failed:
                    print(f'[!] BLE 공유 파일 기록 실패: {exc}')
                self.failed = True
        return {
            'ble_enabled': self.enabled,
            'ble_track_id': output.track_id if output else None,
            'ble_state': state,
            'ble_ttc_s': output.ttc if output else None,
            'ble_held': held,
            'ble_write_ok': success,
        }
