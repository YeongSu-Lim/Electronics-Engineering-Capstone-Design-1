# AI 기반 스마트 백팩 후방 안전 보조 시스템

후방 카메라 영상에서 보행자와 차량을 탐지·추적하고, 객체 크기의 변화로 **TTC(Time-To-Collision, 충돌 예상 시간)** 를 추정하는 전자공학 종합설계 프로젝트입니다. Hailo NPU 추론, ByteTrack 기반 추적, 접근 판단, 화면 표시를 모듈별로 구성했습니다.

## 주요 기능

- YOLOv8n HEF 모델과 Hailo 하드웨어 가속을 이용한 객체 탐지
- 사람, 자전거, 승용차, 오토바이, 버스, 트럭 추적
- 관심 영역(ROI)과 객체 높이 조건을 이용한 분석 대상 선별
- 바운딩박스 면적의 제곱근을 이용한 TTC 계산
- 최근 유효 TTC의 이동평균과 위험 조건의 연속 충족 여부를 이용한 경보 안정화
- 안전·주의·위험 상태의 색상 표시 및 객체별 콘솔 경고

## 처리 흐름

1. GStreamer 카메라 입력을 읽고 640 × 360으로 축소합니다.
2. 추론 입력을 640 × 640으로 변환해 Hailo에서 객체를 탐지합니다.
3. Supervision의 ByteTrack으로 객체 ID를 유지합니다.
4. 중심점이 ROI 내부에 있고 높이가 90px 이상인 객체를 분석합니다.
5. 객체별 TTC와 위험 상태를 계산하고 결과를 화면에 표시합니다.

### TTC 계산과 필터링

객체의 대표 크기를 `s = sqrt(width × height)`로 정의합니다. 현재 크기와 이력의 가장 오래된 크기를 비교하여 다음과 같이 계산합니다.

```text
expansion_rate = (s_current - s_old) / (t_current - t_old)
TTC = s_current / expansion_rate
```

대표 크기가 증가하면서 박스 하단 좌표도 아래로 이동한 경우에만 유효한 TTC를 계산합니다. 이력 구간에서 대표 크기가 20%를 초과해 증가하면 이상치로 처리합니다. 최근 이력 중 유한한 TTC 값만 평균에 포함합니다.

| 상태 | 판정 조건 |
| --- | --- |
| DANGER | 평활화 TTC ≤ 2초 조건이 같은 객체의 연속 3회 업데이트에서 충족 |
| CAUTION | TTC ≤ 5초이거나, 위험 조건의 연속 횟수가 아직 3회 미만 |
| SAFE | 위 조건에 해당하지 않음 |

연속 횟수는 필터를 통과해 TTC 계산에 들어온 업데이트 기준입니다. 영상의 모든 프레임에 대해 연속성을 검사하는 구조는 아닙니다. TTC는 영상상의 크기 변화로 추정하는 값이며 실제 거리·속도의 직접 측정값은 아닙니다.

## 파일 구성

| 파일 | 역할 |
| --- | --- |
| [main.py](main.py) | 카메라 입력, ROI·크기 필터, 모듈 연결, 화면 출력 |
| [config.py](config.py) | 모델·카메라 경로, 탐지 클래스, 임계값, 화면 설정 |
| [core_detector.py](core_detector.py) | Hailo 추론 및 ByteTrack 추적 |
| [ttc_calculator.py](ttc_calculator.py) | 크기 이력, TTC 평활화, 위험 상태 판정 |
| [visualizer.py](visualizer.py) | 객체 표시, ROI 표시, 콘솔 경고 간격 관리 |
| [yolov8n.hef](yolov8n.hef) | Hailo용으로 컴파일된 객체 탐지 모델 |

## 실행 환경

- Python 3, NumPy, Supervision, OpenCV
- 포함된 HEF 모델과 호환되는 Hailo NPU 및 HailoRT Python 패키지(`hailo_platform`)
- GStreamer 및 `libcamerasrc` 카메라 입력을 지원하는 Linux 환경
- **GStreamer 지원이 활성화된 OpenCV**와 GUI 표시 환경

의존성 버전 고정 파일은 현재 포함되어 있지 않습니다. Supervision의 `ByteTrack` 생성자 옵션과 HailoRT API가 코드와 호환되는지 확인해야 합니다.

## 설치 및 실행

1. 저장소를 내려받고 해당 폴더에서 터미널을 엽니다.
2. 대상 장치에 맞는 Hailo 드라이버·HailoRT와 카메라 환경을 준비합니다. 기존 안내의 `sudo apt install hailo-all`은 해당 패키지를 제공하는 OS 저장소에서만 적용할 수 있습니다.
3. 시스템에 설치된 HailoRT와 OpenCV를 사용할 수 있도록 가상환경을 구성합니다.

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install numpy supervision
```

4. 다음 명령으로 가져오기와 OpenCV의 GStreamer 지원을 확인합니다.

```bash
python -c "import cv2, numpy, supervision, hailo_platform; print(cv2.getBuildInformation())"
```

출력의 `GStreamer` 항목이 `YES`여야 합니다. 일반 `opencv-python` 패키지 설치만으로 이 조건이 충족된다고 가정하지 마세요.

5. `config.py`의 카메라 파이프라인과 모델 경로를 확인한 뒤 실행합니다.

```bash
python main.py
```

화면에서 **q**를 누르면 종료됩니다.

## 기본 설정

| 항목 | 기본값 |
| --- | --- |
| 카메라 요청 해상도 / 프레임률 | 1536 × 864 / 60fps |
| 화면 해상도 | 640 × 360 |
| 추론 입력 크기 | 640 × 640 |
| 탐지 신뢰도 하한 | 0.25 |
| TTC 이력 길이 | 5회 |
| ROI | (100, 50) ~ (540, 360) |
| 위험 / 주의 경고 간격 | 객체별 0.5초 / 1.5초 |

카메라의 요청 프레임률은 실제 추론 처리 속도를 의미하지 않습니다. 영상 파일로 테스트할 때도 현재 코드가 `cv2.CAP_GSTREAMER`를 명시하므로 파일 입력을 지원하는 파이프라인 또는 캡처 코드 조정이 필요합니다. TTC 시간은 영상 타임스탬프가 아닌 실제 처리 시각을 사용합니다.

## 실행 전 확인 사항

- 모델 출력은 행마다 `ymin, xmin, ymax, xmax, score, class_id`가 제공되는 형태를 가정합니다. HEF의 실제 출력 형식이 다르면 `core_detector.py` 후처리를 맞춰야 합니다.
- 경고는 현재 **화면 표시와 콘솔 출력**으로 구현되어 있습니다.
- [연계 Android 앱](https://github.com/YeongSu-Lim/Electronics-Engineering-Capstone-Design-1---Application-Development)은 HTTP 서버를 요구하지만, 이 저장소에는 `/data`·`/video` 서버가 포함되어 있지 않습니다.
- 정량 성능 평가 데이터와 자동 테스트는 현재 저장소에 포함되어 있지 않습니다.
