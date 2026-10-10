# config.py
# ==========================================================
# [SYSTEM CONFIGURATION]
# ==========================================================

# --- [파일 및 모델 경로] ---
VIDEO_PATH = 'walk_test.mp4'  # INPUT_MODE='file'일 때만 사용하는 파일 경로
# live는 팀원 파이프라인을 WINDOW_WIDTH/HEIGHT로 구성한다.
# 장비 고유 파이프라인이 필요하면 아래 None을 해당 문자열로 교체한다.
LIVE_CAMERA_PIPELINE = None
VEHICLE_MODEL_HEF  = 'yolov8n.hef'        # (.pt 대용) 컴파일된 Hailo 전용 모델 파일 경로

# --- [탐지 대상 및 임계값] ---
# COCO: 0:사람, 1:자전거, 2:승용차, 3:오토바이, 5:버스, 7:트럭
VEHICLE_CLASSES   = [0, 1, 2, 3, 5, 7]    # 탐지할 차량 및 보행자 클래스 번호
VEHICLE_CONF      = 0.25                  # 차량 탐지 최소 확신도
INFERENCE_SIZE    = 640                   # AI 추론 해상도

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

# --- [입력 시간 기준] ---
INPUT_MODE = "live"  # 실시간 카메라: live / 녹화 영상: file
FILE_TIME_MODE = "pts"  # 파일의 CAP_PROP_POS_MSEC 사용
# pts가 제대로 제공되지 않는 '고정 FPS 영상'에만 fps 사용.
# 파일 테스트 시 INPUT_MODE='file'과 VIDEO_PATH='walk_test.mp4'를 함께 변경.

# --- [TTC 이력 관리: 실측 영상으로 조정할 시작값] ---
TTC_MAX_GAP_SECONDS = 0.5  # 마지막 유효 박스 관측부터 이 시간이 지나면 ID 삭제
TTC_DANGER_STREAK = 3  # 아직 프레임 횟수 기준; 시간 기반 위험 FSM은 후속 작업
TTC_MAX_GROWTH_RATIO = 0.20  # 기존 sqrt(면적) 증가 필터 유지
MIN_BOX_HEIGHT = 90  # 기존 90px 조건을 설정 파일로 이동

# --- [동일 위험 등급 내 주요 타겟 교체] ---
TARGET_SWITCH_RATIO = 0.20  # 도전 객체 TTC가 기존보다 20% 이상 짧음
TARGET_CONFIRM_SECONDS = 0.30  # 위 조건이 관측 프레임에서 0.3초 지속
# DANGER가 CAUTION보다 우선하며, 등급 상승/기존 타겟 누락에는 유예를 적용하지 않음.

# --- [CSV 계측: 실행마다 별도 로그 폴더 생성] ---
CSV_ENABLED = True
CSV_LOG_DIR = "logs"
CSV_FLUSH_SECONDS = 1.0  # 실행 시간 기준 주기적 flush; 정상 종료 시 close
# 디스크 기록은 계속 증가한다. 장시간 시험 전 여유 공간과 기록 시간을 확인한다.

# --- [팀원 카메라 / BLE / 영상 기능 통합] ---
CAMERA_WARMUP_SECONDS = 3.0
BLE_ENABLED = True  # 파일 재생 모드에서는 파일 쓰기를 자동으로 비활성화
BLE_DATA_PATH = 'shared_ble_data.txt'  # 기존대로 터미널 작업 폴더 기준
BLE_PERSIST_SECONDS = 1.0  # MAIN이 없을 때 마지막 출력만 유지. 타겟 자체를 유지하지 않음
VIDEO_ENABLED = True
VIDEO_FPS = 30.0  # 파일 재생 FPS; 실제 처리 간격은 CSV의 timestamp_s로 확인
VIDEO_CODEC = 'mp4v'
