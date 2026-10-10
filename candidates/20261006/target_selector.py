"""전체 객체의 판정 중 이번 프레임에 경보할 주요 타겟 하나를 선정한다."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Target:
    track_id: int
    label: str
    box: tuple
    ttc: float
    state: str
    reason: str = ""


class TargetSelector:
    def __init__(self, switch_ratio=0.20, confirm_seconds=0.30):
        # 최적값이 아닌 조정 시작값. 비율 0.20 = TTC가 20% 이상 짧아야 도전.
        if not 0 <= switch_ratio < 1 or not math.isfinite(confirm_seconds) or confirm_seconds < 0:
            raise ValueError("타겟 전환 설정값을 확인하세요.")
        self.switch_ratio = switch_ratio
        self.confirm_seconds = confirm_seconds
        self.reset()

    def reset(self):
        self.current_id = None
        self.pending_id = None
        self.pending_since = None
        self.last_time = None

    def _choose(self, target):
        self.current_id = target.track_id if target else None
        self.pending_id = None
        self.pending_since = None
        return target

    def select(self, targets, timestamp):
        if not math.isfinite(timestamp):
            raise ValueError("선정 시간은 유한수여야 합니다.")
        if self.last_time is not None and timestamp < self.last_time:
            self.reset()
        self.last_time = timestamp
        levels = {"CAUTION": 1, "DANGER": 2}
        # 현재 프레임에서 관측되고 경보 조건을 만족한 객체만 후보로 사용한다.
        # SAFE/관측 누락/계산 불가 객체를 억지로 주요 타겟으로 만들지 않는다.
        candidates = {
            t.track_id: t for t in targets
            if t.state in levels and math.isfinite(t.ttc) and t.ttc > 0
        }
        if not candidates:
            return self._choose(None)

        # 1순위 위험 등급, 2순위 TTC. 완전 동률은 ID로 결정해 재현성을 확보한다.
        best = min(candidates.values(), key=lambda t: (-levels[t.state], t.ttc, t.track_id))
        current = candidates.get(self.current_id)
        if current is None or levels[best.state] > levels[current.state]:
            # 기존 타겟이 사라지거나 더 높은 위험 등급이 나타나면 즉시 전환한다.
            return self._choose(best)
        if best.track_id == current.track_id:
            return self._choose(current)

        # 같은 등급끼리만 전환 유예를 적용한다. 작은 TTC 차이로 깜빡임을 줄인다.
        if best.ttc >= current.ttc or best.ttc > current.ttc * (1 - self.switch_ratio):
            return self._choose(current)
        if self.pending_id != best.track_id:
            self.pending_id = best.track_id
            self.pending_since = timestamp
        if timestamp - self.pending_since >= self.confirm_seconds:
            return self._choose(best)
        return current
