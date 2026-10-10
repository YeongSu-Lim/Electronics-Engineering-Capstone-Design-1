"""화면 출력만 담당한다. 경보는 main -> AlertManager에서 한 번만 수행한다."""
import math
import cv2
import config


class Visualizer:
    # 기존 객체별 알림 딕셔너리는 AlertManager로 이동했다.
    # 따라서 이 모듈에는 프레임을 넘어 누적되는 객체 메모리가 없다.
    def draw_roi_zone(self, canvas):
        x1, y1, x2, y2 = config.ROI_BOUNDARY
        cv2.rectangle(canvas, (x1, y1), (x2, y2), config.COLOR_ROI_LINE, 1)
        cv2.putText(canvas, "ROI", (x1, max(12, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, config.COLOR_ROI_LINE, 1)

    def draw_target(self, canvas, target, is_primary=False):
        if target.state == "DANGER":
            color = config.COLOR_DANGER
        elif target.state == "CAUTION":
            color = config.COLOR_CAUTION
        elif target.reason == "ABOVE_THRESHOLD":
            color = config.COLOR_SAFE
        else:
            # 관측 부족/계산 불가를 '안전 확정'처럼 초록색으로 보이지 않는다.
            color = (160, 160, 160)
        x1, y1, x2, y2 = target.box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 3 if is_primary else 1)
        value = f"{target.ttc:.2f}s" if math.isfinite(target.ttc) else "--"
        state = target.state if math.isfinite(target.ttc) else "UNCONFIRMED"
        caption = f"{'MAIN ' if is_primary else ''}{target.track_id} {target.label} {state} {value}"
        cv2.putText(canvas, caption, (max(0, x1), max(14, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1)

    def draw_status(self, canvas, primary, retained_count, processing_ms):
        # 처리 시간은 read 이후이며 종단 간 지연은 아니다.
        selected = str(primary.track_id) if primary else "NONE"
        text = f"MAIN: {selected} | retained IDs: {retained_count} | process: {processing_ms:.1f}ms"
        cv2.putText(canvas, text, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
