"""면적 기반 TTC 계산과 연속 관측에 따른 경보 판정.

기존 main.py의 4개 인자 호출과 (TTC, 상태) 반환 형식을 유지한다.
SAFE는 기존 화면과의 호환을 위한 '현재 경보 조건 미충족' 값이다.
관측 부족/무효도 SAFE로 반환하므로 실제 안전이 확인됐다는 뜻은 아니다.
유효한 박스로 등록된 ID의 세부 사유는 last_reason.get(track_id)로 확인한다.
잘못된 박스 입력은 해당 ID를 삭제하므로 사유도 함께 사라진다.
"""

import math
import time
from collections import deque

import config


class TTCCalculator:
    def __init__(self, history_frames=5):
        if not isinstance(history_frames, int) or history_frames < 2:
            raise ValueError("history_frames는 2 이상의 정수여야 합니다.")

        self.history_frames = history_frames
        self.history = {}
        self.ttc_history = {}
        self.danger_streak = {}
        self.last_reason = {}
        self.last_debug = {}  # CSV용 최근 계산 지표. ID 만료 때 함께 삭제.

        # 기존 config.py에 항목이 없어도 기본값으로 동작한다.
        # 0.5초는 검증된 최적값이 아닌 시작값: 실측 처리 간격에 맞춰 조정한다.
        self.max_gap = float(getattr(config, "TTC_MAX_GAP_SECONDS", 0.5))
        self.required_streak = int(getattr(config, "TTC_DANGER_STREAK", 3))
        self.max_growth = float(getattr(config, "TTC_MAX_GROWTH_RATIO", 0.20))
        self.danger_threshold = float(config.THRESHOLD_DANGER)
        self.caution_threshold = float(config.THRESHOLD_CAUTION)
        if not (math.isfinite(self.max_gap) and self.max_gap > 0):
            raise ValueError("TTC_MAX_GAP_SECONDS는 양의 유한수여야 합니다.")
        if self.required_streak < 1:
            raise ValueError("TTC_DANGER_STREAK는 1 이상이어야 합니다.")
        if not (math.isfinite(self.max_growth) and self.max_growth > 0):
            raise ValueError("TTC_MAX_GROWTH_RATIO는 양의 유한수여야 합니다.")
        if not (0 < self.danger_threshold <= self.caution_threshold < math.inf):
            raise ValueError("0 < 위험 임계값 <= 주의 임계값이어야 합니다.")

        self._clock_mode = None

    def reset(self, track_id=None):
        """객체 삭제 시 해당 ID 초기화. 새 영상 시작 시 reset()으로 전체 초기화."""
        stores = (self.history, self.ttc_history, self.danger_streak, self.last_reason, self.last_debug)
        for store in stores:
            if track_id is None:
                store.clear()
            else:
                store.pop(track_id, None)
        if track_id is None:
            self._clock_mode = None

    def _clear_evidence(self, track_id, reason):
        # [핵심 수정] 무효 TTC를 평균에서 제외하는 것만으로는 부족하다.
        # 과거의 낮은 TTC가 남으면 접근이 멈춰도 위험 횟수가 증가한다.
        # 현재 접근 근거가 끊기면 평균 이력과 연속 위험 횟수를 함께 비운다.
        self.ttc_history[track_id].clear()
        self.danger_streak[track_id] = 0
        self.last_reason[track_id] = reason
        if track_id in self.last_debug:
            self.last_debug[track_id].update(reason=reason, raw_valid=False, danger_streak=0)
        return math.inf, "SAFE"

    def mark_missing(self, track_id):
        """현재 프레임에 관측되지 않은 ID의 연속 근거를 끊는다.

        마지막 관측 시각과 크기 이력은 변경하지 않아 expire_tracks가
        원래 관측 시각을 기준으로 삭제한다. 관측 누락은 안전 확인이 아니다.
        """
        if track_id in self.history:
            self._clear_evidence(track_id, "MISSING")

    def expire_tracks(self, timestamp=None):
        """오래 관측되지 않은 ID 삭제. 반환값은 이번 호출에서 사용할 시간.

        update에서 자동 호출한다. 검출이 전혀 없는 동안에도 정리하려면
        main의 프레임 루프에서 같은 시간 기준으로 직접 호출할 수 있다.
        """
        mode = "monotonic" if timestamp is None else "external"
        now = time.monotonic() if timestamp is None else float(timestamp)
        if not math.isfinite(now):
            raise ValueError("timestamp는 초 단위의 유한수여야 합니다.")
        if self._clock_mode is not None and self._clock_mode != mode:
            raise ValueError("시간 기준을 바꾸기 전에 reset()을 호출하세요.")
        self._clock_mode = mode

        for track_id in list(self.history):
            last_time = self.history[track_id][-1][0]
            # 영상 되감기처럼 시간이 역행하면 미래 시점의 이력도 폐기한다.
            if now < last_time or now - last_time > self.max_gap:
                self.reset(track_id)
        return now

    def update_and_get_fsm(
        self, track_id, current_w, current_h, current_y2, timestamp=None
    ):
        """기존 호출에 timestamp(초)만 선택적으로 추가했다.

        실시간 기존 호출: timestamp 생략 시 time.monotonic() 사용.
        녹화 영상 비교: 프레임의 영상 시간을 timestamp로 반드시 전달.
        같은 프레임의 객체에는 같은 시간을 사용하고 시간 기준을 섞지 않는다.
        생략 시 시스템 시각 변경의 영향은 피하지만 캡처 지연은 보정하지 못한다.
        """
        now = self.expire_tracks(timestamp)

        # 잘못된 박스는 sqrt/TTC 연산 전에 차단하고 이전 이력도 폐기한다.
        if not all(math.isfinite(v) for v in (current_w, current_h, current_y2)):
            self.reset(track_id)
            return math.inf, "SAFE"
        if current_w <= 0 or current_h <= 0:
            self.reset(track_id)
            return math.inf, "SAFE"

        # 기존 대표 크기 유지: s = sqrt(폭 * 높이).
        current_dim = math.sqrt(current_w) * math.sqrt(current_h)
        if not math.isfinite(current_dim):
            self.reset(track_id)
            return math.inf, "SAFE"

        if track_id not in self.history:
            self.history[track_id] = deque(maxlen=self.history_frames)
            self.ttc_history[track_id] = deque(maxlen=self.history_frames)
            self.danger_streak[track_id] = 0

        # 프레임마다 새 진단값으로 덮어써 이전 값이 CSV에 섞이지 않게 한다.
        self.last_debug[track_id] = {"size_px": current_dim, "raw_valid": False}

        history = self.history[track_id]
        previous = history[-1] if history else None
        sample = (now, current_dim, current_y2)

        # 같은 시각을 다시 처리해 연속 횟수가 올라가는 것을 방지한다.
        # 기존처럼 delta_t를 임의의 0.001초로 바꾸어 TTC를 만들지 않는다.
        if previous is not None and now <= previous[0]:
            history.clear()
            history.append(sample)
            return self._clear_evidence(track_id, "NON_INCREASING_TIME")

        history.append(sample)
        if len(history) < 2:
            return self._clear_evidence(track_id, "WARMUP")

        old_time, old_dim, old_y2 = history[0]
        delta_t = now - old_time
        delta_dim = current_dim - old_dim
        delta_y2 = current_y2 - old_y2

        # 필터 적용 전 후보 TTC까지 기록한다. 후보값은 유효 판정값과 구분한다.
        # 필터가 접근을 얼마나 제외했는지 살펴보기 위한 관측값이며 경보에 쓰지 않는다.
        candidate_ttc = current_dim * delta_t / delta_dim if delta_dim > 0 else None
        self.last_debug[track_id].update(
            window_dt_s=delta_t, delta_size_px=delta_dim,
            recent_delta_size_px=current_dim - previous[1],
            delta_y2_px=delta_y2, growth_ratio=delta_dim / old_dim,
            expansion_px_s=delta_dim / delta_t,
            candidate_ttc_s=candidate_ttc,
            recent_expansion_pass=current_dim > previous[1],
            growth_pass=delta_dim / old_dim <= self.max_growth,
            bottom_motion_pass=delta_y2 > 0,
            window_expansion_pass=delta_dim > 0,
        )

        # [추가] 최근 크기가 줄거나 정체됐다면 위험 진입 근거를 끊는다.
        # 오래된 프레임 대비 크기가 커도 '지금도 커지는가'를 별도로 확인한다.
        # 작은 박스 흔들림에도 초기화될 수 있으므로 실제 영상에서 누락을 검증한다.
        if current_dim <= previous[1]:
            return self._clear_evidence(track_id, "NO_RECENT_EXPANSION")

        # 기존 20% 증가 필터와 하단 좌표 조건은 비교를 위해 유지한다.
        # 20%는 면적 자체가 아닌 sqrt(면적)의 증가율이며, 이력 구간 기준이다.
        # 실제 빠른 접근도 걸러질 수 있으므로 노이즈라고 확정하는 근거는 아니다.
        if delta_dim / old_dim > self.max_growth:
            return self._clear_evidence(track_id, "GROWTH_FILTER")
        if delta_dim <= 0 or delta_y2 <= 0:
            return self._clear_evidence(track_id, "APPROACH_GATE_FAILED")

        # 기존 식 유지: TTC = s / (ds/dt).
        # 박스 팽창 기반 추정값이며, 충돌 경로까지 판정하는 값은 아니다.
        raw_ttc = current_dim / (delta_dim / delta_t)
        if not math.isfinite(raw_ttc) or raw_ttc <= 0:
            return self._clear_evidence(track_id, "INVALID_TTC")

        # 현재 접근 관측이 유효한 경우에만 TTC 평균에 새 값을 넣는다.
        self.ttc_history[track_id].append(raw_ttc)
        smoothed_ttc = sum(self.ttc_history[track_id]) / len(self.ttc_history[track_id])
        self.last_debug[track_id].update(raw_valid=True, raw_ttc_s=raw_ttc, smoothed_ttc_s=smoothed_ttc)

        # [핵심 수정] 평균뿐 아니라 현재 raw TTC도 위험 기준을 만족해야 한다.
        # 현재 raw TTC가 기준을 벗어나면 과거 평균이 낮아도 연속 횟수는 끊긴다.
        if raw_ttc <= self.danger_threshold and smoothed_ttc <= self.danger_threshold:
            self.danger_streak[track_id] += 1
            self.last_debug[track_id]["danger_streak"] = self.danger_streak[track_id]
            if self.danger_streak[track_id] >= self.required_streak:
                self.last_reason[track_id] = "DANGER_CONFIRMED"
                return smoothed_ttc, "DANGER"
            self.last_reason[track_id] = "DANGER_PENDING"
            return smoothed_ttc, "CAUTION"

        self.danger_streak[track_id] = 0
        self.last_debug[track_id]["danger_streak"] = 0
        if raw_ttc <= self.caution_threshold and smoothed_ttc <= self.caution_threshold:
            self.last_reason[track_id] = "CAUTION"
            return smoothed_ttc, "CAUTION"

        self.last_reason[track_id] = "ABOVE_THRESHOLD"
        return smoothed_ttc, "SAFE"
