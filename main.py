# 가상환경 활성화 : .\venv\Scripts\activate

import cv2
import config
from core_detector import DetectionEngine
from visualizer import Visualizer
from ttc_calculator import TTCCalculator

def run_collision_warning_system():
    """메인 탐지 및 충돌 경고 시스템을 실행합니다."""
    
    # 1. 초기화 및 객체 생성
    screen_total_area = config.WINDOW_WIDTH * config.WINDOW_HEIGHT
    
    detector = DetectionEngine()
    renderer = Visualizer()
    ttc_calculator = TTCCalculator(history_frames=config.TTC_HISTORY_FRAMES)
    
    video_capture = cv2.VideoCapture(config.VIDEO_PATH)
    if not video_capture.isOpened():
        print(f"[!] 영상을 열 수 없습니다: {config.VIDEO_PATH}")
        return

    # 상태 관리 변수
    frame_count = 0
    vehicle_results = None
    scooter_results = None
    
    fps = video_capture.get(cv2.CAP_PROP_FPS)
    frame_delay = int(1000 / fps) if fps > 0 else 33
    
    # ROI 좌표 분해
    roi_x1, roi_y1, roi_x2, roi_y2 = config.ROI_BOUNDARY

    print(f"[*] 모니터링 시작... (종료: 'q' 키)")

    while video_capture.isOpened():
        success, frame = video_capture.read()
        if not success:
            break

        frame_count += 1

        # [단계 1] 프레임 전처리
        display_frame = cv2.resize(frame, (config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        canvas = display_frame.copy()

        # [단계 2] ROI 시각화 가이드 출력
        renderer.draw_roi_zone(canvas)

        # [단계 3] AI 추론 (ByteTrack 연속성 유지를 위해 매 프레임 실행)
        vehicle_results = detector.get_vehicle_results(display_frame)
        scooter_results = detector.get_scooter_results(display_frame)

        # [단계 4] 내부 처리 함수
        def process_tracking_data(results, label_name=""):
            if not results or results[0].boxes.id is None:
                return
            
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            class_ids = results[0].boxes.cls.int().cpu().tolist()

            for box, track_id, cls_id in zip(boxes, track_ids, class_ids):
                x1, y1, x2, y2 = map(int, box)
                center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
                
                #2차 필터: ROI 내부 여부 확인
                if roi_x1 <= center_x <= roi_x2 and roi_y1 <= center_y <= roi_y2:
                    
                    # 킥보드 전용 필터
                    if label_name == "Scooter":
                        object_area = (x2 - x1) * (y2 - y1)
                        if object_area > (screen_total_area * config.MAX_SCOOTER_SCREEN_RATIO):
                            continue

                    # 1차 필터: 거리/크기 필터
                    current_box_height = y2 - y1
                    if current_box_height < 90:
                        continue
                    
                    # 3차 필터 (수학적 알고리즘): TTC 및 위험 상태 판정
                    ttc_value, risk_state = ttc_calculator.update_and_get_fsm(track_id, current_box_height, y2)
                    
                    # 최종 라벨 결정 
                    final_label = label_name if label_name else detector.vehicle_names[cls_id]
                    
                    # 시각화 클래스에 렌더링 위임 
                    renderer.draw_object(canvas, (x1, y1, x2, y2), track_id, final_label, risk_state, ttc_value)

        # [단계 5] 추적 결과 적용
        process_tracking_data(vehicle_results)
        process_tracking_data(scooter_results, label_name="Scooter")

        # [단계 6] 최종 화면 출력
        cv2.imshow("Collision Prevention System", canvas)
        if cv2.waitKey(frame_delay) & 0xFF == ord('q'): 
            break 

    video_capture.release()
    cv2.destroyAllWindows()
    print("[*] 시스템이 정상적으로 종료되었습니다.")

if __name__ == "__main__":
    run_collision_warning_system()
