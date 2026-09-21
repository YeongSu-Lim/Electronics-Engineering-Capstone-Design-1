# 🎒 AI 기반 스마트 백팩 안전 보조 시스템

이 저장소는 후방 카메라를 통해 다가오는 위험 요소(자동차, 오토바이, 킥보드 등)를 실시간으로 감지하고 **TTC(충돌 예상 시간)** 를 분석하여 위험을 알리는 **AI 객체 탐지 모듈**을 담고 있습니다.

---

## 📢 업데이트 사항 (26.06.05)
> bytetracker에서 supervision으로 변경, 그리고 다운로드 오류 방지를 위해 yolov8n.hef를 미리 넣어놨습니다.

---

## 0) 하드웨어 연결 및 확인, 카메라 테스트

## 1) 파일 다운로드 (Project_mid) 후 해당 폴더 경로로 터미널 열기

## 2) 업데이트
sudo apt update
sudo apt install hailo-all

## 3) 가상환경 만들기
python -m venv venv --system-site-packages
source venv/bin/activate
(venv)라는 글자 뜨는지 확인

## 4) 라이브러리 설치
pip install numpy supervision opencv-python
pip install /usr/lib/python3/dist-packages/hailo_platform-*.whl

## 5) 실행확인 (종료; q키)
python main.py

 
* 주의사항: 오류방지를 위해 기존에 실패했던 폴더를 다시 쓰지 말고, 새 파일에서 새 가상환경 세팅 후 진행해주세요
* 오류시에 어떤 부분을 진행 중에 어떤 오류가 떴는지 상세하게 알려주세요