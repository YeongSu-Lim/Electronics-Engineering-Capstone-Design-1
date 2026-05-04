import config
import time
from collections import deque

class TTCCalculator:
    def __init__(self, history_frames=5):
        self.history = {} 
        self.ttc_history = {} 
        self.history_frames = history_frames
        self.danger_streak = {} 

    def update_and_get_fsm(self, track_id, current_h, current_y2):
        current_time = time.time()

        if track_id not in self.history:
            self.history[track_id] = deque(maxlen=self.history_frames)
            self.ttc_history[track_id] = deque(maxlen=self.history_frames)
            self.danger_streak[track_id] = 0 #스트릭 초기화

        self.history[track_id].append((current_time, current_h, current_y2))

        if len(self.history[track_id]) < 2:
            return float('inf'), "SAFE"

        old_time, old_h, old_y2 = self.history[track_id][0]
        
        delta_h = current_h - old_h
        delta_y2 = current_y2 - old_y2 
        delta_t = current_time - old_time

        if delta_t <= 0: 
            delta_t = 0.001
            
        # 팽창 이상치 제거 (가려짐 풀림 방어)
        # 한 프레임 만에 크기가 20% 이상 커지면 돌진이 아니라 노이즈로 간주
        if old_h > 0 and (delta_h / old_h) > 0.20:
            raw_ttc = float('inf')
        elif delta_h <= 0 or delta_y2 <= 0:
            raw_ttc = float('inf')
        else:
            expansion_rate = delta_h / delta_t
            raw_ttc = current_h / expansion_rate

        self.ttc_history[track_id].append(raw_ttc)
        valid_ttcs = [t for t in self.ttc_history[track_id] if t != float('inf')]
        
        if not valid_ttcs:
            smoothed_ttc = float('inf')
        else:
            smoothed_ttc = sum(valid_ttcs) / len(valid_ttcs)

        # 시간적 지속성 검증
        if smoothed_ttc <= config.THRESHOLD_DANGER:
            self.danger_streak[track_id] += 1
            
            # 최소 3프레임 연속으로 DANGER 수치여야만 진짜 DANGER 판정
            if self.danger_streak[track_id] >= 3:
                state = "DANGER"
            else:
                state = "CAUTION" # 아직 유예 기간이므로 CAUTION 출력
                
        elif smoothed_ttc <= config.THRESHOLD_CAUTION:
            self.danger_streak[track_id] = 0 # 위험에서 벗어나면 스트릭 초기화
            state = "CAUTION"
            
        else:
            self.danger_streak[track_id] = 0
            state = "SAFE"

        return smoothed_ttc, state
