# 영상 처리 아키텍처

[README로 이동](../README.md) · [버전 구분](versions.md)

## 모듈과 인터페이스

| 모듈 | 입력 → 출력 | 현재 구현 |
| --- | --- | --- |
| [config.py](../config.py) | 상수 → 각 모듈 설정 | 카메라 파이프라인, HEF 경로, 클래스, 임계값 |
| [main.py](../main.py) | 카메라 프레임 → 처리·화면 루프 | ROI/높이 필터, TTC 호출, q 종료 |
| [core_detector.py](../core_detector.py) | BGR 프레임 → Supervision Detections | Hailo 추론, xyxy·confidence·class_id·tracker_id |
| [ttc_calculator.py](../ttc_calculator.py) | ID·폭·높이·하단 y → TTC·상태 | 객체별 이력, 평활화, 위험 횟수 |
| [visualizer.py](../visualizer.py) | 박스·ID·클래스·상태 → 화면·콘솔 | 색상 표시, 객체별 경고 간격 |
| [yolov8n.hef](../yolov8n.hef) | 컴파일된 모델 | 실제 모델 메타데이터·출력 호환성은 장치 확인 필요 |

## 좌표와 필터

1. 입력 프레임을 640×360으로 축소하고, 별도의 640×640 입력으로 리사이즈하여 추론합니다.
2. 후처리는 정규화 박스 좌표를 화면 좌표로 환산합니다. 현재 전처리는 letterbox가 아닌 직접 리사이즈입니다.
3. 클래스 0/1/2/3/5/7과 신뢰도 0.25 이상을 남깁니다.
4. 추적 ID가 있고 박스 중심이 ROI `(100, 50)~(540, 360)` 안이며 높이 90px 이상일 때 TTC를 갱신합니다.

ROI·높이 조건은 원거리·관심 밖 객체의 TTC 연산을 줄이지만 ROI에 들어오는 전 과정을 관측하지 못할 수 있습니다. **ROI는 추론 이후 필터**이므로 NPU가 ROI만 추론해 계산량을 줄인 구조로 표현하지 않습니다.

## 실행 주기와 자원

카메라 요청은 1536×864/60fps이며 실제 탐지 FPS·종단 지연 측정값은 아닙니다. 추론·후처리·TTC·표시를 한 루프에서 순차 처리합니다. `frame_delay`는 계산하지만 실제 대기에는 `cv2.waitKey(1)`을 사용합니다.

객체별 두 deque는 최대 5개 항목으로 제한하지만 ID 사전 전체를 정리하는 경로는 현재 main에 없습니다. 장시간 실행에서 사라진 ID가 축적될 수 있습니다. 빈 검출에서는 ByteTrack 업데이트 전에 반환하므로 빈 프레임 처리도 재검토 대상입니다.

## 장치 전체와 저장소의 경계

현재 경고 출력은 화면과 콘솔입니다. 부저·진동·BLE·HTTP 서버는 현재 main에 구현되어 있지 않습니다. [Android 앱 저장소](https://github.com/YeongSu-Lim/Electronics-Engineering-Capstone-Design-1---Application-Development)는 `/data`·`/video` HTTP 서버를 요구하지만 이 저장소에는 해당 서버가 없습니다.

Raspberry Pi 5 기반 장치 구성은 프로젝트 설명에 따른 개발 대상입니다. 소스만으로 카메라 모델·Hailo 모델·장착 위치·전원 사양을 확정하지 않습니다. 실제 장치 사진·배선·모델 정보를 공개 가능한 범위에서 추가해야 합니다.
