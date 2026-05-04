import cv2
import time
import config

class Visualizer:
    """화면 렌더링 및 시각적/물리적 피드백을 담당하는 클래스"""

    def __init__(self):
        # 💡 [수정] DANGER와 CAUTION의 쿨타임을 개별적으로 관리하도록 분리
        self.last_danger_time = {}
        self.last_caution_time = {}

    def draw_roi_zone(self, canvas):
        """설정된 ROI 영역과 가이드라인을 화면에 그립니다."""
        roi_x1, roi_y1, roi_x2, roi_y2 = config.ROI_BOUNDARY
        
        # ROI 사각형 그리기
        cv2.rectangle(canvas, (roi_x1, roi_y1), (roi_x2, roi_y2), config.COLOR_ROI_LINE, 1)
        
        # ROI 라벨 텍스트
        cv2.putText(canvas, "ROI ZONE", (roi_x1, roi_y1 - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, config.COLOR_ROI_LINE, 1)

    def draw_object(self, canvas, box, track_id, final_label, risk_state, ttc_value):
        """객체의 박스, ID, 라벨 및 위험 상태별 색상을 화면에 표시합니다."""
        x1, y1, x2, y2 = box
        
        # 1. 상태별 색상 결정 및 터미널 로그/알림 출력
        if risk_state == "DANGER":
            current_color = config.COLOR_DANGER
            self._process_alerts(track_id, final_label, risk_state, ttc_value) # 💡 알림 함수 호출
        elif risk_state == "CAUTION":
            current_color = config.COLOR_CAUTION
            self._process_alerts(track_id, final_label, risk_state, ttc_value) # 💡 알림 함수 호출
        else:
            current_color = config.COLOR_SAFE

        # 2. 객체 박스 렌더링
        caption = f"{track_id} {final_label}"
        cv2.rectangle(canvas, (x1, y1), (x2, y2), current_color, 2)
        
        # 3. 라벨 배경 (텍스트 가독성용)
        (text_w, text_h), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(canvas, (x1, y1 - 25), (x1 + text_w, y1), current_color, -1)
        
        # 4. 라벨 텍스트 (흰색)
        cv2.putText(canvas, caption, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    def _process_alerts(self, track_id, final_label, risk_state, ttc_value):
        """위험/주의 상태에 맞춰 쿨타임을 계산하고 경고 로그 및 제어 신호를 출력합니다."""
        now = time.time()

        if risk_state == "DANGER":
            if track_id not in self.last_danger_time or (now - self.last_danger_time[track_id] > config.DANGER_ALERT_INTERVAL):
                print(f"🔴 [위험] {final_label}(ID:{track_id}) 충돌 임박! TTC: {ttc_value:.2f}s")
                self.last_danger_time[track_id] = now

        elif risk_state == "CAUTION":
            if track_id not in self.last_caution_time or (now - self.last_caution_time[track_id] > config.CAUTION_ALERT_INTERVAL):
                print(f"🟡 [주의] {final_label}(ID:{track_id}) 접근 중. TTC: {ttc_value:.2f}s")
                self.last_caution_time[track_id] = now
