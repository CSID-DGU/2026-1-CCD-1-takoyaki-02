"""데모 3 — 상황 판단: 차례가 아닌 플레이어의 주사위 굴림 = 규칙 위반.

실제 요트 비전 파이프라인(YOLO+ByteTrack+RollAttributor+Fusion)을 그대로 돌린다.
FSM 대신 데모가 FusionContext(현재 차례 = active_player)를 주입하고, 차례가
아닌 플레이어가 굴리면 FusionEngine 이 rule_violation 을 발화 → 빨간 배너로 표시.

선행: `python -m demos.register` 로 2명 이상 등록 (예: Player1, Player2).

실행 (boardgame-ai 디렉터리에서):
  python -m demos.demo3_violation --active p_1
  python -m demos.demo3_violation --active p_1 --mirror --record /tmp/demo3.mp4
"""

from __future__ import annotations

import sys

import cv2
import numpy as np

from bridge.local_bridge import LocalBridge
from core.constants import DEFAULT_PARAMS
from core.events import FusionContext
from demos import common
from vision.debug.overlay import draw_overlay
from vision.yacht.config import VisionConfig
from vision.yacht.pipeline import (
    VisionPipeline,
    _filter_dice_inside_tray,
    _split_dets,
)
from vision.yacht.schemas import YachtFramePerception


class DemoYachtPipeline(VisionPipeline):
    """요트 파이프라인 + 규칙위반 배너. 프레임을 직접 받아 주석 프레임 반환."""

    def __init__(self, config, bridge, players) -> None:
        super().__init__(config, bridge, players)
        self._active = True
        self.violation_ttl = 0
        self.violation_actor = ""

    def set_turn(self, ctx: FusionContext) -> None:
        self._fusion.update_context(ctx)
        self._active_player = ctx.active_player
        self._has_context = True

    def step(self, frame_bgr: np.ndarray, frame_id: int, ts: float):
        """_process_one 을 데모용으로 복제 — 렌더된 프레임과 이벤트 반환."""
        h, w = frame_bgr.shape[:2]

        yolo_dets = self._yolo.detect(frame_bgr)
        tray, tray_inner, roll_tray, dice_dets = _split_dets(yolo_dets)
        if tray is not None and self._config.tray_mask_padding > 0:
            dice_dets = _filter_dice_inside_tray(
                dice_dets, tray, padding=self._config.tray_mask_padding
            )

        tracked = self._byte_tracker.update(dice_dets, frame_id)
        dice_states = self._dice_manager.update(tracked, frame_bgr, self._dot_counter)
        dice_states.sort(key=lambda d: d.track_id)

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        raw_hands = self._hand_detector.detect(frame_rgb)
        hands = self._stabilize_hands(raw_hands)

        perception = YachtFramePerception(
            frame_id=frame_id, ts=ts, image_hw=(h, w),
            tray=tray, tray_inner=tray_inner, roll_tray=roll_tray,
            dice=dice_states, hands=hands,
        )
        roll_actor = self._roll_attributor.update(perception, active_player=self._active_player)
        if roll_actor is not None:
            perception.roll_actor_id = roll_actor
        if self._roll_attributor.just_finalized:
            perception.roll_just_confirmed = True
        perception.phase_hints = {
            "dice_all_stable": perception.dice_all_stable(
                int(DEFAULT_PARAMS["stabilization_frames"])
            ),
            "dice_count": len(dice_states),
            "roll_state": self._roll_attributor.state.name,
        }

        events = []
        if frame_id >= self._config.warmup_frames:
            events = self._fusion.feed(perception)

        vis = draw_overlay(frame_bgr.copy(), perception)
        return vis, events


def main() -> None:
    parser = common.base_arg_parser("규칙 위반 (차례 아닌 굴림) 시각화")
    parser.add_argument("--weights", default="weights/yacht_v4.pt")
    parser.add_argument("--active", default="p_1", help="현재 차례 플레이어 id")
    args = parser.parse_args()

    players = common.load_players(args.players)
    if len(players) < 2:
        print("[demo3] 2명 이상 등록 필요. 먼저: python -m demos.register")
        sys.exit(1)
    name_by_pid = {p.player_id: (p.playername or p.player_id) for p in players}
    if args.active not in name_by_pid:
        print(f"[demo3] --active {args.active} 가 등록 목록에 없음: {list(name_by_pid)}")
        sys.exit(1)

    config = VisionConfig(weights_path=args.weights, warmup_frames=30)
    bridge = LocalBridge()
    pipe = DemoYachtPipeline(config, bridge, players)
    pipe.set_turn(FusionContext(
        fsm_state="AWAITING_ROLL",
        game_type="yacht",
        active_player=args.active,
        allowed_actors=[args.active],
        expected_events=["ROLL_CONFIRMED", "ROLL_UNREADABLE", "DICE_ESCAPED"],
    ))

    text_r = common.TextRenderer()
    demo = common.Demo("Demo3 - Rule Violation", args)
    active_name = name_by_pid[args.active]

    def process(frame: np.ndarray, frame_id: int, ts: float) -> np.ndarray:
        vis, events = pipe.step(frame, frame_id, ts)
        h, w = vis.shape[:2]

        for evt in events:
            if evt.event_type == "rule_violation":
                pipe.violation_ttl = 110
                pipe.violation_actor = name_by_pid.get(evt.actor_id, evt.actor_id or "?")
            elif evt.event_type == "ROLL_CONFIRMED":
                # 정상 굴림(현재 차례)도 잠깐 표시
                pipe.violation_ttl = max(pipe.violation_ttl, 0)

        # 현재 차례 헤더
        cv2.rectangle(vis, (0, 0), (w, 44), (0, 0, 0), -1)
        text_r.text(vis, (12, 6), f"현재 차례: {active_name}", color=common.GREEN, size=28)

        if pipe.violation_ttl > 0:
            pipe.violation_ttl -= 1
            overlay = vis.copy()
            cv2.rectangle(overlay, (0, h // 2 - 70), (w, h // 2 + 70), (0, 0, 60), -1)
            cv2.addWeighted(overlay, 0.55, vis, 0.45, 0, vis)
            text_r.text(vis, (40, h // 2 - 56),
                        "⚠ 규칙 위반!", color=(80, 80, 255), size=52)
            text_r.text(vis, (40, h // 2 + 6),
                        f"{pipe.violation_actor} 님은 지금 차례가 아닙니다",
                        color=common.WHITE, size=34)
        return vis

    try:
        demo.run(process)
    finally:
        pipe._hand_detector.close()


if __name__ == "__main__":
    main()
