# config.py
# ==========================================================
# [SYSTEM CONFIGURATION]
# ==========================================================

# --- [파일 및 모델 경로] ---
VIDEO_PATH        = 'car_test.mp4'        # 분석할 영상 파일
VEHICLE_MODEL_PT  = 'yolov8n.pt'          # COCO 모델

# --- [탐지 대상 및 임계값] ---
# COCO: 0:사람, 1:자전거, 2:승용차, 3:오토바이, 5:버스, 7:트럭
VEHICLE_CLASSES   = [0, 1, 2, 3, 5, 7]        # 탐지할 차량 및 보행자 클래스 번호
VEHICLE_CONF      = 0.25                  # 차량 탐지 최소 확신도
INFERENCE_SIZE    = 320                   # AI 추론 해상도

# --- [TTC 및 위험 판단] ---
TTC_HISTORY_FRAMES = 5                    # TTC 계산용 프레임 이력
THRESHOLD_DANGER   = 2.0                  # 위험(빨강) 기준 초
THRESHOLD_CAUTION  = 5.0                  # 주의(노랑) 기준 초

# --- [ROI 및 시각화 설정] ---
WINDOW_WIDTH      = 640                   # 화면 가로 크기
WINDOW_HEIGHT     = 360                   # 화면 세로 크기
ROI_BOUNDARY      = (100, 50, 540, 360)   # 관심 영역 설정 (x1, y1, x2, y2)

# --- [필터링 및 색상] ---
COLOR_DANGER    = (0, 0, 255)             # 위험 (빨간색)
COLOR_CAUTION   = (0, 255, 255)           # 주의 (노란색)
COLOR_SAFE      = (0, 255, 0)             # 안전 (초록색)
COLOR_ROI_LINE  = (255, 0, 0)             # ROI 라인 (파란색)

# --- [경고 알림 쿨타임 설정] ---
DANGER_ALERT_INTERVAL = 0.5   # 위험 상태 알림 간격 (초)
CAUTION_ALERT_INTERVAL = 1.5  # 주의 상태 알림 간격 (초)