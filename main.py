import cv2
import time
from ultralytics import YOLO

# 💡 TTCCalculator 모듈 불러오기 (ttc_calculator.py 파일이 같은 폴더에 있어야 함)
from ttc_calculator import TTCCalculator 

def main():
    print("🚀 BEEP-BEEP: 최종 알고리즘(거리 1차 + ROI 2차 필터) 테스트를 시작합니다.")
    print("💡 사용법: 실행 중 'r' 키를 누르면 영상이 멈춥니다. 마우스로 ROI 영역을 드래그하고 스페이스바/엔터를 누르세요.")

    
    model = YOLO('yolov8n.pt')
    ttc_calc = TTCCalculator(history_frames=5)
    
    video_path = "test_drive.mp4" 
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"❌ 에러: '{video_path}' 파일을 찾을 수 없습니다.")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter('output_demo.mp4', fourcc, fps, (frame_width, frame_height))

    last_warning_time = {}

    # 초기 ROI 설정 (처음엔 전체 화면으로 설정)
    roi = (0, 0, frame_width, frame_height)


    win_name = "BEEP-BEEP Video Test"
    cv2.namedWindow(win_name)

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            print("✅ 영상 처리가 완료되었습니다.")
            break

        results = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[1, 2, 3, 5, 7], verbose=False)
        annotated_frame = frame.copy()

        # 설정된 ROI 영역을 화면에 파란색 사각형으로 표시
        cv2.rectangle(annotated_frame, (int(roi[0]), int(roi[1])), 
                      (int(roi[0]+roi[2]), int(roi[1]+roi[3])), (255, 0, 0), 2)

        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy() 
            track_ids = results[0].boxes.id.int().cpu().tolist()
            class_ids = results[0].boxes.cls.int().cpu().tolist()

            class_names = {1: "Bicycle", 2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck"}

            for box, track_id, class_id in zip(boxes, track_ids, class_ids):
                x1, y1, x2, y2 = map(int, box)
                current_h = y2 - y1 
                obj_name = class_names.get(class_id, "Unknown")

                # ️ 1차 필터 : 거리/크기 필터
                if current_h < 100:
                    ttc, state = float('inf'), "SAFE"
                
                else:

                    #2차 필터 : 객체 중앙점이 ROI 내부에 있는지 확인
                    
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    rx, ry, rw, rh = roi
                    
                    if rx < cx < rx + rw and ry < cy < ry + rh:
                        # 두 필터를 모두 통과해야만 진짜 TTC 연산 수행
                        ttc, state = ttc_calc.update_and_get_fsm(track_id, current_h, y2)
                    else:
                        # ROI 밖의 객체는 크기가 커도 무시
                        ttc, state = float('inf'), "SAFE"

                # 상태별 색상 지정
                if state == "DANGER":
                    color = (0, 0, 255) 
                    text = f"[{obj_name}] DANGER! TTC:{ttc:.1f}s"
                elif state == "CAUTION":
                    color = (0, 255, 255) 
                    text = f"[{obj_name}] CAUTION TTC:{ttc:.1f}s"
                else:
                    color = (0, 255, 0) 
                    text = f"[{obj_name}] SAFE"

                # 화면에 Bounding Box와 텍스트 출력
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)
                cv2.putText(annotated_frame, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                if state == "DANGER":
                    current_t = time.time()
                    if track_id not in last_warning_time or (current_t - last_warning_time[track_id] > 0.5):
                        print(f"🚨 [위험 감지] {obj_name} (ID: {track_id}) | TTC: {ttc:.2f}초")
                        last_warning_time[track_id] = current_t

        out.write(annotated_frame)
        cv2.imshow(win_name, annotated_frame)

        #키보드 입력 처리
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("테스트를 종료합니다.")
            break
        elif key == ord('r'):
            # 'r' 누르면 영상이 일시정지되며 ROI를 그릴 수 있는 십자선 생성
            print("⏸️ ROI 재설정 모드: 마우스로 영역을 드래그하고 스페이스바 또는 엔터를 누르세요.")
            new_roi = cv2.selectROI(win_name, frame, False)
            if new_roi[2] > 20 and new_roi[3] > 20: # 박스를 너무 작게 그리지 않은 경우만 적용
                roi = new_roi
                print(f"✅ 새로운 ROI 적용 완료: {roi}")

    cap.release()
    out.release() 
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
