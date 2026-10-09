# 실행 환경과 재현 절차

[README로 이동](../README.md)

## 현재 코드에서 요구하는 환경

| 항목 | 필요 조건 / 현재 확인 상태 |
| --- | --- |
| 장치 | 프로젝트 대상 Raspberry Pi 5 및 포함 HEF와 호환되는 Hailo NPU |
| OS·카메라 | Linux, GStreamer, `libcamerasrc`를 통한 카메라 입력 |
| Python | Python 3. 정확한 사용 버전·패키지 잠금 파일 없음 |
| 추론 | 장치 드라이버와 호환되는 HailoRT Python의 `hailo_platform` |
| 영상·추적 | GStreamer 지원 OpenCV, NumPy, Supervision |
| 표시 | `cv2.imshow()`를 사용할 GUI 환경 |
| 모델 | 저장소 루트의 `yolov8n.hef`; 실제 입출력 형식 확인 필요 |

실제로 동작했던 OS 이미지·Hailo 모델·드라이버·HailoRT·OpenCV·Supervision 버전을 확보한 뒤 고정해야 합니다. 확인하지 않은 버전을 임의로 requirements에 고정하지 않습니다.

## 준비 및 실행

1. 대상 보드에 맞는 카메라·Hailo 드라이버와 런타임을 준비합니다. 배포판별 패키지 제공 여부가 달라 단일 시스템 설치 명령을 보장하지 않습니다.
2. 저장소 루트에서 시스템 HailoRT·OpenCV를 사용할 환경을 구성합니다. 아래 명령은 환경 구성 예시이며 장치 재현 시험을 마친 설치 조합이 아닙니다.

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install numpy supervision
python -c "import cv2, numpy, supervision, hailo_platform; print(cv2.getBuildInformation())"
```

3. OpenCV 빌드 정보의 GStreamer 지원과 카메라 파이프라인을 확인합니다. 일반 OpenCV wheel 설치만으로 해당 지원을 가정하지 않습니다.
4. `config.py`에서 HEF 경로·카메라 파이프라인·ROI를 실제 장치에 맞게 확인합니다. `core_detector.py`의 ByteTrack 생성자 옵션과 HEF 입출력 형태가 설치 버전에 맞아야 합니다.
5. 소스의 현재 작업 디렉터리에서 실행합니다.

```bash
python main.py
```

화면에서 `q`를 누르면 종료합니다. 실패한 영상 열기·모델 초기화·패키지 호환성은 별도 원인 확인이 필요합니다. 이 문서 작업에서 장치 실행 성공을 검증하지 않았습니다.

## 영상 파일과 후속 업데이트 주의점

현재 코드가 `cv2.CAP_GSTREAMER`를 명시하므로 `VIDEO_PATH`를 단순 파일명으로 바꾸는 것만으로 녹화 영상 재현을 보장하지 않습니다. 영상 입력 파이프라인과 프레임 시간 처리까지 맞춰야 합니다. 현재 TTC는 처리 시각을 사용하므로 영상 재생 속도가 바뀌면 계산 결과도 달라질 수 있습니다.

후속 ZIP은 여러 파일·설정이 함께 바뀐 별도 통합본입니다. 일부 파일만 현재 main에 덮어쓰지 않으며, 기능 적용은 별도 PR과 검증 범위로 관리합니다. [차이 보기](versions.md)
