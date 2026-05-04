import sys
from ultralytics import YOLO
import config

# ==========================================================
# [INITIALIZATION] : 모델을 메모리에 올리는 과정
# ==========================================================

def initialize_models():
    """모델을 로드하고 추론 엔진을 최적화합니다."""
    print(f"[*] AI 모델 최적화 및 로딩 중...")
    try:
        # config.py에 정의된 상수 경로를 사용하여 모델 로드
        vehicle_model = YOLO(config.VEHICLE_MODEL_PT).fuse()
        scooter_model = YOLO(config.SCOOTER_MODEL_PT).fuse()
        return vehicle_model, scooter_model
    except Exception as e:
        print(f"[!] 모델 로드 실패: {e}")
        sys.exit(1)

class DetectionEngine:
    """YOLO 모델 관리 및 추론 수행을 담당하는 클래스"""
    
    def __init__(self):
        # 초기화 시 모델을 로드하여 인스턴스 변수에 저장
        self.vehicle_model, self.scooter_model = initialize_models()

    def get_vehicle_results(self, frame):
        """차량 탐지 모델의 추적 결과를 반환합니다."""
        return self.vehicle_model.track(
            frame, 
            classes=config.VEHICLE_CLASSES, 
            conf=config.VEHICLE_CONF, 
            imgsz=config.INFERENCE_SIZE, 
            persist=True, 
            tracker="bytetrack.yaml", 
            verbose=False
        )

    def get_scooter_results(self, frame):
        """킥보드 탐지 모델의 추적 결과를 반환합니다."""
        return self.scooter_model.track(
            frame, 
            classes=config.SCOOTER_CLASSES, 
            conf=config.SCOOTER_CONF, 
            imgsz=config.INFERENCE_SIZE, 
            persist=True, 
            verbose=False
        )

    @property
    def vehicle_names(self):
        """차량 모델의 클래스 이름 맵을 반환합니다."""
        return self.vehicle_model.names