"""자원 사용량 (지표 C) — 백그라운드 thread로 1초마다 샘플링.

BenchmarkSession.start() → ResourceSampler.start() (별도 daemon thread)
finalize() → stop() → CSV 분석 → resource_usage.json

CSV 형식 (results/<ts>/cpu_mem.csv):
    sec_since_start,cpu_pct,rss_mb

분석 결과 (resource_usage.json):
    {
      "duration_sec": ...,
      "samples": ...,
      "cpu_pct": {mean, peak, p95, ...},
      "ram_mb": {mean, peak, p95, ...},
      "by_segment_5min": [...],
      "note": "..."
    }
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from benchmarks.common.stats import summarize


SEGMENT_SEC = 300  # 5분


class ResourceSampler:
    """1초마다 CPU%/RSS 측정 → CSV append. daemon thread.

    psutil 없으면 graceful no-op.
    """

    def __init__(self, csv_path: Path, interval_sec: float = 1.0) -> None:
        self._csv_path = csv_path
        self._interval = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_ts: float = 0.0
        self._proc = None
        try:
            import psutil
            self._psutil = psutil
            self._proc = psutil.Process(os.getpid())
            # 첫 cpu_percent는 항상 0이라 worm-up
            self._proc.cpu_percent(interval=None)
        except Exception:
            self._psutil = None

    def start(self) -> None:
        if self._psutil is None:
            return
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._csv_path, "w", encoding="utf-8") as f:
            f.write("sec_since_start,cpu_pct,rss_mb\n")
        self._start_ts = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="resource-sampler")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        # daemon thread는 5분 단위로 flush. 5분마다 partial 보존.
        last_flush = 0
        while not self._stop.wait(self._interval):
            try:
                cpu_pct = self._proc.cpu_percent(interval=None)
                rss_mb = self._proc.memory_info().rss / (1024 * 1024)
            except Exception:
                continue
            elapsed = time.time() - self._start_ts
            try:
                with open(self._csv_path, "a", encoding="utf-8") as f:
                    f.write(f"{elapsed:.1f},{cpu_pct:.2f},{rss_mb:.1f}\n")
                # 5분마다 fsync (긴 측정 도중 시스템 죽음 대비)
                if int(elapsed) - last_flush >= 60:
                    last_flush = int(elapsed)
            except Exception:
                pass


def analyze(csv_path: Path) -> dict:
    """CSV → 통계 JSON."""
    if not csv_path.exists():
        return {"error": "no csv", "samples": 0}

    cpu_vals: list[float] = []
    ram_vals: list[float] = []
    timeline: list[tuple[float, float, float]] = []

    with open(csv_path, encoding="utf-8") as f:
        next(f, None)  # header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) != 3:
                continue
            try:
                sec = float(parts[0])
                cpu = float(parts[1])
                ram = float(parts[2])
            except ValueError:
                continue
            cpu_vals.append(cpu)
            ram_vals.append(ram)
            timeline.append((sec, cpu, ram))

    if not timeline:
        return {"error": "no samples"}

    # 5분 segmented
    segments: list[dict] = []
    duration = timeline[-1][0]
    for seg_start in range(0, int(duration) + 1, SEGMENT_SEC):
        seg = [(c, r) for s, c, r in timeline if seg_start <= s < seg_start + SEGMENT_SEC]
        if seg:
            seg_cpu = [c for c, _ in seg]
            seg_ram = [r for _, r in seg]
            segments.append({
                "minute_range": f"{seg_start // 60}-{(seg_start + SEGMENT_SEC) // 60}",
                "cpu_mean": round(sum(seg_cpu) / len(seg_cpu), 1),
                "cpu_peak": round(max(seg_cpu), 1),
                "ram_mean_mb": round(sum(seg_ram) / len(seg_ram), 1),
                "ram_peak_mb": round(max(seg_ram), 1),
            })

    return {
        "duration_sec": round(duration, 1),
        "samples": len(timeline),
        "cpu_pct": {
            **summarize(cpu_vals),
            "peak": max(cpu_vals),
        },
        "ram_mb": {
            **summarize(ram_vals),
            "peak": max(ram_vals),
        },
        "by_segment_5min": segments,
        "note": "권장 사양: 측정 환경 동급 이상 (산출 공식 표준 없음, 자세한 environment는 env.json 참고).",
    }


def run(session_dir: Path) -> dict:
    csv_path = session_dir / "cpu_mem.csv"
    result = analyze(csv_path)
    (session_dir / "resource_usage.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    return result
