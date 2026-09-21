# 가상환경 활성화 : .\venv\Scripts\activate
import cv2
import config
from core_detector import DetectionEngine
from visualizer import Visualizer
from ttc_calculator import TTCCalculator

def process_tracking_data(results, detector, ttc_calculator, renderer, canvas):
    """트래킹 데이터를 기반으로 ROI 필터링 및 TTC 계산, 시각화를 처리합니다."""
    if not results or results[0].boxes.id is None:
        return
    
    roi_x1, roi_y1, roi_x2, roi_y2 = config.ROI_BOUNDARY
    boxes = results[0].boxes.xyxy.cpu().numpy()
    track_ids = results[0].boxes.id.int().cpu().tolist()
    class_ids = results[0].boxes.cls.int().cpu().tolist()

    for box, track_id, cls_id in zip(boxes, track_ids, class_ids):
        x1, y1, x2, y2 = map(int, box)
        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
        
        # 2차 필터: ROI 내부 여부 확인
        if roi_x1 <= center_x <= roi_x2 and roi_y1 <= center_y <= roi_y2:
            
            # 1차 필터: 거리/크기 필터 (최소 높이 검증)
            current_box_height = y2 - y1
            
            # 3차 필터: TTC 및 위험 상태 판정
            ttc_value, risk_state = ttc_calculator.update_and_get_fsm(track_id, current_box_height, y2)
            
            # 최종 라벨 결정 및 렌더링 위임
            final_label = detector.vehicle_names[cls_id]
            renderer.draw_object(canvas, (x1, y1, x2, y2), track_id, final_label, risk_state, ttc_value)


def run_collision_warning_system():
    """메인 탐지 및 충돌 경고 시스템을 실행합니다."""
    
    detector = DetectionEngine()
    renderer = Visualizer()
    ttc_calculator = TTCCalculator(history_frames=config.TTC_HISTORY_FRAMES)
    
    video_capture = cv2.VideoCapture(config.VIDEO_PATH)
    if not video_capture.isOpened():
        print(f"[!] 영상을 열 수 없습니다: {config.VIDEO_PATH}")
        return

    fps = video_capture.get(cv2.CAP_PROP_FPS)
    frame_delay = int(1000 / fps) if fps > 0 else 33

    print(f"[*] 모니터링 시작... (종료: 'q' 키)")

    while video_capture.isOpened():
        success, frame = video_capture.read()
        if not success:
            break

        # [단계 1] 프레임 전처리
        display_frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        canvas = display_frame.copy()

        # [단계 2] ROI 시각화 가이드 출력
        renderer.draw_roi_zone(canvas)

        # [단계 3] AI 추론 (ByteTrack 연속성 유지를 위해 매 프레임 실행)
        vehicle_results = detector.get_vehicle_results(display_frame)

        # [단계 4] 트래킹 데이터 처리 및 시각화
        process_tracking_data(vehicle_results, detector, ttc_calculator, renderer, canvas)

        # [단계 5] 최종 화면 출력
        cv2.imshow("Collision Prevention System", canvas)
        if cv2.waitKey(frame_delay) & 0xFF == ord('q'): 
            break 

    video_capture.release()
    cv2.destroyAllWindows()
    print("[*] 시스템이 정상적으로 종료되었습니다.")

if __name__ == "__main__":
    run_collision_warning_system()