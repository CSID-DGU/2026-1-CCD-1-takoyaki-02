"""BenchmarkSession — 측정 전 과정의 single point of orchestration.

라이프사이클:
1. server.py lifespan에서 BENCH_TRACE=1 감지 → BenchmarkSession.start()
2. 새 results/<timestamp>/ 디렉토리 생성
3. bench logger를 그 디렉토리로 라우팅
4. (TODO) 백그라운드 thread로 psutil 자원 샘플링
5. 게임 종료 이벤트 감지 → finalize() 호출 → summary.md 생성
   (현재는 server shutdown 시점에 finalize. 게임 단위 finalize는 후속.)
6. server shutdown 시 stop() → 모든 핸들러 정리

스레드 모델: asyncio 단일 루프. resource 샘플링 thread는 별도 background thread.
"""

from __future__ import annotations

import logging
import platform
import time
from datetime import datetime
from pathlib import Path

from benchmarks.common.trace_setup import (
    is_bench,
    setup_bench_logger,
    teardown_bench_logger,
)

logger = logging.getLogger(__name__)

# 측정 결과 저장 루트 (.gitignore 됨).
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"


class BenchmarkSession:
    """측정 1회 분량의 컨테이너. server.py에서 1개만 활성."""

    def __init__(self) -> None:
        self._started = False
        self._session_dir: Path | None = None
        self._start_ts: float = 0.0

    def start(self) -> Path | None:
        """BENCH_TRACE=1이면 새 세션 시작. results/<ts>/ 경로 반환.

        idempotent — 이미 시작됐으면 같은 경로 반환.
        """
        if self._started:
            return self._session_dir
        if not is_bench():
            return None

        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        self._session_dir = _RESULTS_ROOT / ts
        self._session_dir.mkdir(parents=True, exist_ok=True)

        setup_bench_logger(self._session_dir)

        self._start_ts = time.time()
        self._started = True

        # 환경 정보 자동 캡처 → env.json
        self._write_env_json()

        logger.info("BenchmarkSession started: %s", self._session_dir)
        return self._session_dir

    def stop(self) -> None:
        """server shutdown 시 호출. finalize 호출 + logger 정리."""
        if not self._started:
            return
        try:
            self.finalize()
        finally:
            teardown_bench_logger()
            duration = time.time() - self._start_ts
            logger.info(
                "BenchmarkSession stopped (duration=%.1fs, dir=%s)",
                duration, self._session_dir,
            )
            self._started = False
            self._session_dir = None

    def finalize(self) -> None:
        """게임 종료 또는 shutdown 시 자동 호출. 분석 모듈 실행 + summary.md 생성.

        현재는 placeholder. 분석 모듈 추가하면 여기서 호출.
        """
        if self._session_dir is None:
            return
        # TODO: trace_collector, channel_latency, ui_latency, fps_analysis, cache_hit_rate,
        # ws_recovery, resource_usage 분석 모듈 in-process 호출 후 summary.md 생성.
        # 일단 placeholder로 finalized 마커만 작성.
        marker = self._session_dir / "finalized.txt"
        marker.write_text(
            f"finalized_at={datetime.now().isoformat()}\n"
            f"duration_sec={time.time() - self._start_ts:.1f}\n"
        )

    def session_dir(self) -> Path | None:
        return self._session_dir

    def _write_env_json(self) -> None:
        """장비/OS/CPU 정보 자동 캡처."""
        import json

        if self._session_dir is None:
            return

        env: dict = {
            "started_at": datetime.now().isoformat(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "platform_release": platform.release(),
            "python": platform.python_version(),
            "cpu_model": _get_cpu_model(),
            "cpu_cores_logical": _safe_cpu_count(logical=True),
            "cpu_cores_physical": _safe_cpu_count(logical=False),
            "cpu_freq_max_mhz": _get_cpu_freq_max(),
            "ram_gb": _get_ram_gb(),
            "yolo_device": None,  # TTSEngine처럼 추후 capture
            "gpu_info": _get_gpu_info(),
        }
        (self._session_dir / "env.json").write_text(
            json.dumps(env, indent=2, ensure_ascii=False)
        )


# ── 환경 정보 헬퍼 (psutil 없으면 graceful fallback) ──────────────────────────


def _safe_cpu_count(logical: bool = True) -> int | None:
    try:
        import psutil

        return psutil.cpu_count(logical=logical)
    except Exception:
        import os

        return os.cpu_count() if logical else None


def _get_cpu_model() -> str:
    """OS별 CPU 모델명. 실패 시 platform.processor() fallback."""
    try:
        if platform.system() == "Darwin":
            import subprocess

            return subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True, timeout=2,
            ).strip()
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        elif platform.system() == "Windows":
            return platform.processor()
    except Exception:
        pass
    return platform.processor() or "unknown"


def _get_cpu_freq_max() -> float | None:
    try:
        import psutil

        freq = psutil.cpu_freq()
        if freq and freq.max:
            return float(freq.max)
    except Exception:
        pass
    return None


def _get_ram_gb() -> float | None:
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        return None


def _get_gpu_info() -> str | None:
    """best-effort. NVIDIA면 nvidia-smi, 그 외는 None."""
    try:
        import subprocess

        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            text=True, timeout=2, stderr=subprocess.DEVNULL,
        ).strip()
        return out if out else None
    except Exception:
        return None
