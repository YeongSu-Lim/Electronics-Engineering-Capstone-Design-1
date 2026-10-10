"""라벨 없이 계산 가능한 관측 통계만 요약한다. 정확도/오탐률은 만들지 않는다.

사용: python summarize_logs.py logs/세션폴더
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import statistics


def summarize(directory):
    directory = Path(directory)
    with (directory / "frames.csv").open(encoding="utf-8-sig", newline="") as f:
        frames = list(csv.DictReader(f))
    with (directory / "observations.csv").open(encoding="utf-8-sig", newline="") as f:
        reasons = Counter(r["reason"] for r in csv.DictReader(f))
    with (directory / "events.csv").open(encoding="utf-8-sig", newline="") as f:
        events = Counter(r["event"] for r in csv.DictReader(f))
    samples = [float(r["processing_ms"]) for r in frames if r["processing_ms"]]
    intervals = [float(r["source_delta_s"]) for r in frames if r["source_delta_s"]]
    result = {
        "frame_count": len(frames),
        "recorded_duration_s": float(frames[-1]["timestamp_s"]) - float(frames[0]["timestamp_s"]) if len(frames) > 1 else 0,
        "empty_tracked_frames": sum(int(r["tracked_count"]) == 0 for r in frames),
        "maximum_retained_ids": max((int(r["retained_ids"]) for r in frames), default=0),
        "mean_processing_ms_excluding_csv": statistics.mean(samples) if samples else None,
        "median_source_interval_s": statistics.median(intervals) if intervals else None,
        "observation_reason_counts": dict(reasons), "event_counts": dict(events),
        "warning": "정답 라벨 없음: 정확도/정밀도/재현율/오경보율/TTC 오차는 산출하지 않음. PRIMARY_CHANGED는 NONE 전환도 포함."
    }
    (directory / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session_directory")
    print(json.dumps(summarize(parser.parse_args().session_directory), ensure_ascii=False, indent=2))
