
# ==========================================================
# [SYSTEM CONFIGURATION]
# ==========================================================

# --- [파일 및 모델 경로] ---
VIDEO_PATH        = 'test.mp4'        # 분석할 영상 파일
VEHICLE_MODEL_PT  = 'yolov8n.pt'          # COCO 모델 (차량용)
SCOOTER_MODEL_PT  = 'PM-Tracker.pt'       # 커스텀 모델 (킥보드용)

# --- [탐지 대상 및 임계값] ---
# COCO: 1:자전거, 2:승용차, 3:오토바이, 5:버스, 7:트럭
VEHICLE_CLASSES   = [1, 2, 3, 5, 7]        # 탐지할 차량 클래스 번호
SCOOTER_CLASSES   = [0]                   # 탐지할 킥보드 클래스 번호

VEHICLE_CONF      = 0.25                  # 차량 탐지 최소 확신도
SCOOTER_CONF      = 0.30                  # 킥보드 탐지 최소 확신도
INFERENCE_SIZE    = 320                   # AI 추론 해상도
DETECTION_STRIDE  = 1                     # 추론 주기

# --- [TTC 및 위험 판단] ---
TTC_HISTORY_FRAMES = 5                    # TTC 계산용 프레임 이력
THRESHOLD_DANGER   = 2.0                  # 위험(빨강) 기준 초
THRESHOLD_CAUTION  = 5.0                  # 주의(노랑) 기준 초
LOG_INTERVAL_SEC   = 0.5                  # 터미널 로그 출력 간격 (초)

# --- [ROI 및 시각화 설정] ---
WINDOW_WIDTH      = 640                   # 화면 가로 크기
WINDOW_HEIGHT     = 360                   # 화면 세로 크기
# ROI (x1, y1, x2, y2)
ROI_BOUNDARY      = (100, 50, 540, 360)   # 관심 영역 설정

# --- [필터링 및 색상] ---
MAX_SCOOTER_SCREEN_RATIO = 0.3            # 오탐지 방지용 면적 비율
COLOR_DANGER    = (0, 0, 255)             # 위험 (빨간색)
COLOR_CAUTION   = (0, 255, 255)           # 주의 (노란색)
COLOR_SAFE      = (0, 255, 0)             # 안전 (초록색)
COLOR_ROI_LINE  = (255, 0, 0)             # ROI 라인 (파란색)

# --- [경고 알림 쿨타임 설정] ---
DANGER_ALERT_INTERVAL = 0.5   # 위험 상태 알림 간격 (초)
CAUTION_ALERT_INTERVAL = 1.5  # 주의 상태 알림 간격 (초)
