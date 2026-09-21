# visualizer.py
import cv2
import time
import config

class Visualizer:

    def __init__(self):
        self.last_danger_time = {}
        self.last_caution_time = {}

    def draw_roi_zone(self, canvas):

        roi_x1, roi_y1, roi_x2, roi_y2 = config.ROI_BOUNDARY
        cv2.rectangle(canvas, (roi_x1, roi_y1), (roi_x2, roi_y2), config.COLOR_ROI_LINE, 1)
        cv2.putText(canvas, "ROI ZONE", (roi_x1, roi_y1 - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, config.COLOR_ROI_LINE, 1)

    def draw_object(self, canvas, box, track_id, final_label, risk_state, ttc_value):

        x1, y1, x2, y2 = box
        
        # 1. 상태별 색상 결정
        if risk_state == "DANGER":
            current_color = config.COLOR_DANGER
        elif risk_state == "CAUTION":
            current_color = config.COLOR_CAUTION
        else:
            current_color = config.COLOR_SAFE

        # 2. 알림 프로세스 호출 (DANGER 또는 CAUTION 상태일 때만 수행)
        if risk_state in ("DANGER", "CAUTION"):
            self._process_alerts(track_id, final_label, risk_state, ttc_value)

        # 3. 객체 박스 렌더링
        caption = f"{track_id} {final_label}"
        cv2.rectangle(canvas, (x1, y1), (x2, y2), current_color, 2)
        
        # 4. 라벨 배경 및 텍스트 출력
        (text_w, text_h), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(canvas, (x1, y1 - 25), (x1 + text_w, y1), current_color, -1)
        cv2.putText(canvas, caption, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    def _process_alerts(self, track_id, final_label, risk_state, ttc_value):
        
        now = time.time()

        if risk_state == "DANGER":
            if track_id not in self.last_danger_time or (now - self.last_danger_time[track_id] > config.DANGER_ALERT_INTERVAL):
                print(f"🔴 [위험] {final_label}(ID:{track_id}) 충돌 임박! TTC: {ttc_value:.2f}s")
                self.last_danger_time[track_id] = now

        elif risk_state == "CAUTION":
            if track_id not in self.last_caution_time or (now - self.last_caution_time[track_id] > config.CAUTION_ALERT_INTERVAL):
                print(f"🟡 [주의] {final_label}(ID:{track_id}) 접근 중. TTC: {ttc_value:.2f}s")
                self.last_caution_time[track_id] = now
