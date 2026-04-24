# ttc_calculator.py
import time
from collections import deque

class TTCCalculator:
    def __init__(self, history_frames=5):
        self.history = {} 
        self.ttc_history = {} 
        self.history_frames = history_frames

    def update_and_get_fsm(self, track_id, current_h, current_y2):
        current_time = time.time()

        if track_id not in self.history:
            self.history[track_id] = deque(maxlen=self.history_frames)
            self.ttc_history[track_id] = deque(maxlen=self.history_frames)

        self.history[track_id].append((current_time, current_h, current_y2))

        if len(self.history[track_id]) < 2:
            return float('inf'), "SAFE"

        old_time, old_h, old_y2 = self.history[track_id][0]
        
        delta_h = current_h - old_h
        delta_y2 = current_y2 - old_y2 
        delta_t = current_time - old_time

        if delta_t <= 0: 
            delta_t = 0.001

        if delta_h <= 0 or delta_y2 <= 0:
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

        if smoothed_ttc <= 2.0:
            state = "DANGER"
        elif smoothed_ttc <= 5.0:
            state = "CAUTION"
        else:
            state = "SAFE"

        return smoothed_ttc, state
