import numpy as np
import cv2
import config
from hailo_platform import VDevice, HEF, ConfigureParams, InferVStreams
import supervision as sv

# ==========================================================
# [HAILO DETECTOR ENGINE]
# ==========================================================
class DetectionEngine:
    
    def __init__(self):
        print("[*] [하드웨어] Hailo NPU 하드웨어 가속기 초기화 및 모델 로딩 중...")
        self.target = VDevice()
        self.hef = HEF(config.VEHICLE_MODEL_HEF)

        from hailo_platform import HailoStreamInterface, InputVStreamParams, OutputVStreamParams

        self.configure_params = ConfigureParams.create_from_hef(hef=self.hef, interface=HailoStreamInterface.PCIe)
        self.network_group = self.target.configure(self.hef, self.configure_params)[0]
        
        self.active_context = self.network_group.activate(self.network_group.create_params())
        self.active_context.__enter__()
        
        input_vstreams_params = InputVStreamParams.make(self.network_group)
        output_vstreams_params = OutputVStreamParams.make(self.network_group)
        self.pipeline_context = InferVStreams(self.network_group, input_vstreams_params, output_vstreams_params)
        self.infer_pipeline = self.pipeline_context.__enter__()
        
        self.tracker = sv.ByteTrack(
            track_activation_threshold=config.VEHICLE_CONF,
            minimum_matching_iou=0.8,
            minimum_consecutive_frames=1 # 즉각적인 추적을 위해 1로 설정
        )
        self._class_names = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}

    def get_vehicle_results(self, frame):
        
        h_img, w_img = frame.shape[:2]
        
        # 1. 모델 입력 크기(640x640)에 맞게 프레임 리사이즈 및 전처리
        input_size = config.INFERENCE_SIZE
        resized_frame = cv2.resize(frame, (input_size, input_size))
        input_data = {self.hef.get_input_vstream_infos()[0].name: np.expand_dims(resized_frame, axis=0)}

        # 2. 추론 파이프라인 실행
        raw_outputs = self.infer_pipeline.infer(input_data)
        
        # 3. 후처리 및 데이터 파싱
        xyxy_list, conf_list, class_id_list = [], [], []
        output_name = self.hef.get_output_vstream_infos()[0].name
        raw_vstream_data = raw_outputs[output_name][0]

        # 객체 파싱 루프
        for pred in raw_vstream_data:
            ymin, xmin, ymax, xmax, score, class_id = pred[:6]
            if score < config.VEHICLE_CONF or int(class_id) not in config.VEHICLE_CLASSES:
                continue
            
            # 메인 루프 해상도에 맞게 픽셀 좌표 복원
            x1, y1 = int(xmin * w_img), int(ymin * h_img)
            x2, y2 = int(xmax * w_img), int(ymax * h_img)
            
            xyxy_list.append([x1, y1, x2, y2])
            conf_list.append(score)
            class_id_list.append(int(class_id))

        # 프레임 내에 객체가 없으면 빈 Detections 반환
        if len(xyxy_list) == 0:
            return sv.Detections.empty()

        # 4. Supervision Detections 포맷팅
        detections = sv.Detections(
            xyxy=np.array(xyxy_list),
            confidence=np.array(conf_list),
            class_id=np.array(class_id_list).astype(int)
        )

        # 5. Tracker 업데이트 수행
        tracked_detections = self.tracker.update_with_detections(detections)
        
        return tracked_detections

    @property
    def vehicle_names(self):
        return self._class_names

    def __del__(self):
        try:
            if hasattr(self, 'pipeline_context'):
                self.pipeline_context.__exit__(None, None, None)
            if hasattr(self, 'active_context'):
                self.active_context.__exit__(None, None, None)
            print("[*] Hailo NPU 자원이 정상적으로 안전 해제되었습니다.")
        except Exception:
            pass