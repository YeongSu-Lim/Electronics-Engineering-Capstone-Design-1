# main.py
import cv2
import time
from ultralytics import YOLO

from ttc_calculator import TTCCalculator 

def main():
    print("알고리즘 테스트를 시작합니다.")
    
    model = YOLO('yolov8n.pt')
    
    # 불러온 모듈을 사용해 인스턴스 생성
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

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            print("✅ 영상 처리가 완료되었습니다.")
            break

        results = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[1, 2, 3], verbose=False)
        annotated_frame = frame.copy()

        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy() 
            track_ids = results[0].boxes.id.int().cpu().tolist()
            class_ids = results[0].boxes.cls.int().cpu().tolist()

            class_names = {1: "Bicycle", 2: "Car", 3: "Motorcycle"}

            for box, track_id, class_id in zip(boxes, track_ids, class_ids):
                x1, y1, x2, y2 = map(int, box)
                current_h = y2 - y1 
                obj_name = class_names.get(class_id, "Unknown")

                #BBOX가 일정 크기 이상일때만 TTC 알고리즘 가동
                if current_h < 100:
                    ttc, state = float('inf'), "SAFE"

                else:
                    ttc, state = ttc_calc.update_and_get_fsm(track_id, current_h, y2)

                if state == "DANGER":
                    color = (0, 0, 255) 
                    text = f"[{obj_name}] DANGER! TTC:{ttc:.1f}s"
                elif state == "CAUTION":
                    color = (0, 255, 255) 
                    text = f"[{obj_name}] CAUTION TTC:{ttc:.1f}s"
                else:
                    color = (0, 255, 0) 
                    text = f"[{obj_name}] SAFE"

                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)
                cv2.putText(annotated_frame, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                if state == "DANGER":
                    current_t = time.time()
                    if track_id not in last_warning_time or (current_t - last_warning_time[track_id] > 0.5):
                        print(f"🚨 [위험 감지] {obj_name} (ID: {track_id}) | TTC: {ttc:.2f}초")
                        last_warning_time[track_id] = current_t

        out.write(annotated_frame)
        cv2.imshow("BEEP-BEEP Video Test", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release() 
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
