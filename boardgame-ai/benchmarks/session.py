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
        self._resource_sampler = None

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

        # 자원 사용량 1초 샘플링 시작 (psutil 없으면 no-op)
        from benchmarks.resource_usage import ResourceSampler
        self._resource_sampler = ResourceSampler(self._session_dir / "cpu_mem.csv")
        self._resource_sampler.start()

        logger.info("BenchmarkSession started: %s", self._session_dir)
        return self._session_dir

    def stop(self) -> None:
        """server shutdown 시 호출. finalize 호출 + logger 정리."""
        if not self._started:
            return
        # 자원 샘플러 먼저 정지 → CSV flush 보장
        if self._resource_sampler is not None:
            self._resource_sampler.stop()
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
        """게임 종료 또는 shutdown 시 자동 호출. 분석 모듈 실행 + summary.md 생성."""
        if self._session_dir is None:
            return

        # 분석 모듈은 lazy import로 — finalize 시점에만 로드.
        from benchmarks import (
            cache_hit_rate,
            channel_latency,
            completion_rate,
            fps_analysis,
            recognition_rate,
            resource_usage,
            trace_collector,
            ui_latency,
            undo_rate,
            ws_recovery,
        )

        log_path = self._session_dir / "raw" / "app.log"
        results: dict = {}

        # 1. raw/app.log → traces.jsonl (사후 분석용 보존)
        if log_path.exists():
            try:
                count = trace_collector.collect(
                    log_path, self._session_dir / "traces.jsonl"
                )
                results["trace_events"] = count
            except Exception as e:
                logger.exception("trace_collector failed")
                results["trace_events"] = f"error: {e}"

        # 2. 분석 모듈 in-process 호출
        for name, mod in [
            ("channel_latency", channel_latency),
            ("ui_latency", ui_latency),
            ("fps_analysis", fps_analysis),
            ("cache_hit_rate", cache_hit_rate),
            ("ws_recovery", ws_recovery),
            ("undo_rate", undo_rate),
            ("recognition_rate", recognition_rate),
            ("completion_rate", completion_rate),
            ("resource_usage", resource_usage),
        ]:
            try:
                results[name] = mod.run(self._session_dir)
            except Exception as e:
                logger.exception("%s analysis failed", name)
                results[name] = {"error": str(e)}

        # 3. summary.md 생성 + 콘솔 출력
        summary = self._render_summary(results)
        (self._session_dir / "summary.md").write_text(summary, encoding="utf-8")
        # 콘솔에도 (uvicorn stdout에 보이도록)
        print("\n" + "=" * 60)
        print("BenchmarkSession finalized")
        print("=" * 60)
        print(summary)

        # 마커
        (self._session_dir / "finalized.txt").write_text(
            f"finalized_at={datetime.now().isoformat()}\n"
            f"duration_sec={time.time() - self._start_ts:.1f}\n"
        )

    def _render_summary(self, results: dict) -> str:
        """간이 한 페이지 마크다운 요약."""
        lines: list[str] = []
        lines.append(f"# 측정 결과 — {self._session_dir.name if self._session_dir else '?'}")
        lines.append("")
        lines.append(f"- 측정 시간: {time.time() - self._start_ts:.1f} sec")
        lines.append(f"- 총 trace 이벤트: {results.get('trace_events', '?')}")
        lines.append("")

        # 채널별 응답 시간
        cl = results.get("channel_latency", {})
        if isinstance(cl, dict) and "by_channel" in cl:
            lines.append("## ① 음성 채널별 응답 시간 (enqueue → broadcast)")
            lines.append("")
            lines.append("> 큐 직렬화 대기 포함 — 앞선 오디오 재생이 끝나야 다음 항목이")
            lines.append("> broadcast되므로 cached 항목도 큐가 밀리면 latency가 커진다.")
            lines.append("> 순수 합성/조회 비용은 synth_ms(JSON) 참고.")
            lines.append("")
            lines.append("| 채널 | count | p50 (ms) | p95 (ms) | p99 (ms) |")
            lines.append("|---|---:|---:|---:|---:|")
            for ch, data in cl["by_channel"].items():
                s = data.get("enqueue_to_broadcast_ms", {})
                if s.get("count"):
                    lines.append(
                        f"| {ch} | {data['count']} | "
                        f"{s['p50']:.1f} | {s['p95']:.1f} | {s['p99']:.1f} |"
                    )
            lines.append("")

        # UI 화면 갱신
        ui = results.get("ui_latency", {})
        if isinstance(ui, dict) and "paint_interval_ms" in ui:
            lines.append("## ② UI 화면 갱신 (paint 간격)")
            s = ui["paint_interval_ms"]
            lines.append(f"- paint 횟수: {ui.get('paint_count', 0)}")
            if s.get("count"):
                lines.append(f"- 간격 p50: {s['p50']:.1f} ms / p95: {s['p95']:.1f} ms")
            lines.append("")

        # FPS
        fps = results.get("fps_analysis", {})
        if isinstance(fps, dict) and "fps_summary" in fps:
            lines.append("## ③ 비전 처리 FPS")
            s = fps["fps_summary"]
            lines.append(
                f"- 목표 {fps.get('target_fps')} fps / 실제 평균 {s['mean']:.1f} fps "
                f"(p5 {s.get('p5', 0):.0f}, min {s.get('min', 0):.0f}, "
                f"drop {fps.get('drop_rate', 0)*100:.1f}%)"
            )
            for seg in fps.get("by_segment", []):
                lines.append(
                    f"  - {seg['minute_range']} min: 평균 {seg['mean_fps']:.1f} fps "
                    f"(min {seg['min_fps']})"
                )
            lines.append("")

        # 캐시 적중률
        cache = results.get("cache_hit_rate", {})
        if isinstance(cache, dict) and "hit_rate" in cache:
            lines.append("## ④ TTS 캐시 적중률")
            lines.append(
                f"- 전체 {cache['hits']}/{cache['total']} = {cache['hit_rate']*100:.1f}%"
            )
            for layer, d in cache.get("by_layer", {}).items():
                tot = d["hits"] + d["misses"]
                if tot:
                    lines.append(
                        f"  - {layer}: {d['hits']}/{tot} ({100*d['hits']/tot:.1f}%)"
                    )
            lines.append(
                f"- API 합성 절감: 약 {cache.get('estimated_api_time_saved_sec', 0)} sec"
            )
            lines.append("")

        # 라운드 정확도 (undo proxy)
        ur = results.get("undo_rate", {})
        if isinstance(ur, dict) and ur.get("rolls", 0) > 0:
            lines.append("## ⑤ 실전 라운드 정확도 (되돌리기 proxy)")
            lines.append(
                f"- {ur['rolls']} 굴림 중 인식실패 {ur.get('recognition_failures', ur['undos'])} "
                f"(되돌리기 {ur['undos']} + 눈수정 {ur.get('manual_corrections', 0)}) "
                f"= 정확도 추정 {ur['estimated_accuracy']*100:.1f}%"
            )
            lines.append("")

        # 웨어울프 비전 인식 정확도
        rr = results.get("recognition_rate", {})
        if isinstance(rr, dict) and ("role_overall" in rr or "vote" in rr):
            ro = rr.get("role_overall", {})
            vt = rr.get("vote", {})
            reg = rr.get("role_registration", {})
            rev = rr.get("role_reveal", {})
            has_role = ro.get("total", 0) > 0
            has_vote = vt.get("vision_casts", 0) > 0
            if has_role or has_vote:
                lines.append("## ⑤-2 웨어울프 비전 인식 정확도")
                if has_role:
                    lines.append(
                        f"- 역할 인식 전체 {ro['matched']}/{ro['total']} "
                        f"= {ro['accuracy']*100:.1f}%"
                    )
                    if reg.get("total"):
                        lines.append(
                            f"  - 등록: {reg['matched']}/{reg['total']} "
                            f"({reg['accuracy']*100:.1f}%)"
                        )
                    if rev.get("total"):
                        lines.append(
                            f"  - 최종공개: {rev['matched']}/{rev['total']} "
                            f"({rev['accuracy']*100:.1f}%)"
                        )
                if has_vote:
                    acc = vt.get("estimated_accuracy")
                    acc_str = f"{acc*100:.1f}%" if acc is not None else "?"
                    lines.append(
                        f"- 투표 인식: {vt['vision_casts']} 투표 중 "
                        f"수동정정 {vt['manual_corrections']} = 정확도 추정 {acc_str}"
                    )
                lines.append("")

        # 게임 진행 성공률
        cr = results.get("completion_rate", {})
        if isinstance(cr, dict) and "overall" in cr:
            ov = cr["overall"]
            if ov.get("started", 0) > 0:
                lines.append("## ⑥ 게임 진행 성공률 (무개입 완주)")
                lines.append(
                    f"- 전체 {ov['completed']}/{ov['started']} = "
                    f"{ov['completion_rate']*100:.1f}%"
                )
                for gt, d in cr.get("by_type", {}).items():
                    if d["started"]:
                        lines.append(
                            f"  - {gt}: {d['completed']}/{d['started']} "
                            f"({d['completion_rate']*100:.1f}%, abandoned {d['abandoned']})"
                        )
                lines.append("")

        # WS 끊김 복구
        ws = results.get("ws_recovery", {})
        if isinstance(ws, dict) and ws.get("total_disconnects", 0) > 0:
            lines.append("## ⑦ WebSocket 끊김 복구")
            lines.append(
                f"- 총 끊김 {ws['total_disconnects']} / 자동 복구 {ws['auto_recoveries']} "
                f"({ws['recovery_rate']*100:.1f}%)"
            )
            rt = ws.get("recovery_time_ms", {})
            if rt.get("count"):
                lines.append(
                    f"- 복구 시간 p50 {rt['p50']:.0f} ms / p95 {rt['p95']:.0f} ms"
                )
            lines.append("")

        # 자원 사용량
        ru = results.get("resource_usage", {})
        if isinstance(ru, dict) and ru.get("samples", 0) > 0:
            lines.append("## ⑧ 자원 사용량")
            cpu = ru["cpu_pct"]
            ram = ru["ram_mb"]
            lines.append(
                f"- CPU 평균 {cpu['mean']:.1f}% / peak {cpu['peak']:.1f}% / p95 {cpu['p95']:.1f}%"
            )
            lines.append(
                f"- RAM 평균 {ram['mean']:.0f} MB / peak {ram['peak']:.0f} MB"
            )
            lines.append(f"- 측정 시간 {ru['duration_sec']:.0f}s ({ru['samples']} 샘플)")
            for seg in ru.get("by_segment_5min", []):
                lines.append(
                    f"  - {seg['minute_range']} min: "
                    f"CPU {seg['cpu_mean']:.0f}% (peak {seg['cpu_peak']:.0f}) / "
                    f"RAM {seg['ram_peak_mb']:.0f} MB"
                )
            lines.append("")

        sd_name = self._session_dir.name if self._session_dir else "?"
        lines.append(f"_상세 JSON: `{sd_name}/*.json`_")
        lines.append("_환경: env.json 참고 (CPU/RAM/OS 등)_")
        return "\n".join(lines)

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
