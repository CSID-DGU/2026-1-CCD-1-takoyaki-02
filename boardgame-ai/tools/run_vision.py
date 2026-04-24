"""비전 파이프라인 실행 CLI.

Usage:
    python -m tools.run_vision --source 0 --weights weights/yacht_best.pt --debug
    python -m tools.run_vision --source /tmp/session.mp4 --weights weights/yacht_best.pt --jsonl-log /tmp/out.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bridge.local_bridge import LocalBridge
from core.events import FusionContext
from vision.config import VisionConfig
from vision.pipeline import VisionPipeline


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BoardGame AI 비전 파이프라인 실행")
    p.add_argument("--source", default="0",
                   help="카메라 인덱스(정수) 또는 mp4 경로")
    p.add_argument("--weights", default="weights/yacht_best.pt",
                   help="YOLO 가중치 경로")
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--iou", type=float, default=0.5)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--debug", action="store_true",
                   help="cv2.imshow 디버그 오버레이 표시")
    p.add_argument("--jsonl-log", default=None,
                   help="JSONL 로그 저장 경로")
    p.add_argument("--frame-skip", type=int, default=0,
                   help="건너뛸 프레임 수 (0=모든 프레임)")
    p.add_argument("--mode", default="AWAITING_ROLL",
                   choices=["AWAITING_ROLL", "seat_register_right", "seat_register_left"],
                   help="테스트용 FSM 상태 (기본: AWAITING_ROLL)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    # source: 숫자면 카메라 인덱스, 아니면 파일 경로
    source: int | str
    try:
        source = int(args.source)
    except ValueError:
        source = args.source

    config = VisionConfig(
        source=source,
        weights_path=Path(args.weights),
        yolo_conf=args.conf,
        yolo_iou=args.iou,
        yolo_imgsz=args.imgsz,
        debug_overlay=args.debug,
        jsonl_log_path=Path(args.jsonl_log) if args.jsonl_log else None,
        frame_skip=args.frame_skip,
    )

    # 더미 FSM 핸들러: 이벤트를 콘솔에 출력
    bridge = LocalBridge()
    bridge.on_game_event(lambda evt, ver: print(f"[EVENT] {evt.to_dict()}"))

    pipeline = VisionPipeline(config=config, bridge=bridge, players=[])

    # 테스트용 FusionContext 주입 — 실제 FSM 없이 이벤트 발화 확인
    _MODE_CONTEXTS = {
        "AWAITING_ROLL": FusionContext(
            fsm_state="AWAITING_ROLL",
            game_type="yacht",
            active_player="p_1",
            allowed_actors=["p_1", "p_2", "p_3", "p_4"],
            expected_events=["ROLL_CONFIRMED"],
        ),
        "seat_register_right": FusionContext(
            fsm_state="seat_register_right",
            game_type="yacht",
            active_player="p_1",
            allowed_actors=["p_1"],
            expected_events=["seat_hand_registered"],
        ),
        "seat_register_left": FusionContext(
            fsm_state="seat_register_left",
            game_type="yacht",
            active_player="p_1",
            allowed_actors=["p_1"],
            expected_events=["seat_hand_registered"],
        ),
    }
    pipeline._fusion.update_context(_MODE_CONTEXTS[args.mode])
    print(f"[run_vision] FusionContext mode={args.mode}")

    print(f"[run_vision] source={source}  weights={args.weights}  debug={args.debug}")
    print("Press 'q' to quit (debug mode) or Ctrl+C")
    try:
        pipeline.start()
    except KeyboardInterrupt:
        pipeline.stop()
        print("\n[run_vision] stopped.")


if __name__ == "__main__":
    main()
