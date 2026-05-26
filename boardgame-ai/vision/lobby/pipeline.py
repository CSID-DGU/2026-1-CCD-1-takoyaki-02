"""로비 전용 비전 파이프라인.

자리 등록(seat registration) 단계에서만 동작.
주사위·카드 감지 없이 손 감지 + 제스처 분류만 수행한다.

game_type=None 인 FusionContext 만 수신하므로 요트/웨어울프 파이프라인과 이벤트가 중복되지 않는다.
"""

from __future__ import annotations

import queue
import time
from typing import Any

import cv2

from bridge.interface import Bridge
from core.events import FusionContext
from core.models import Player
from vision.attribution.seat_matcher import (
    MARGIN_THRESHOLD,
    match_player_by_arm,
    players_with_both_hands_tracked,
)
from vision.debug.jsonl_logger import JsonlLogger
from vision.detectors.gesture_classifier import GestureClassifier
from vision.detectors.hand_detector import HandDetector
from vision.fusion.engine import FusionEngine
from vision.geometry.arm_vector import compute_arm_angle
from vision.schemas import FramePerception, HandDet
from vision.tracking.hand_tracker import MAX_MATCH_ATTEMPTS, HandTracker


class LobbyVisionPipeline:
    """로비(자리 등록) 전용 비전 파이프라인.

    손 감지 + 제스처 분류만 수행. game_type=None FusionContext 만 처리.
    """

    def __init__(
        self,
        bridge: Bridge,
        players: list[Player],
        max_num_hands: int = 8,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        warmup_frames: int = 30,
    ) -> None:
        self._bridge = bridge
        self._players = players
        self._warmup_frames = warmup_frames
        self._running = False
        self._active = True  # 로비가 기본 활성 파이프라인
        self._frame_id = 0
        self._fsm_state_version: int = 0
        self._debug_snapshot: dict[str, Any] = {
            "frame_id": None,
            "active": self._active,
            "hands": [],
            "events": [],
            "context": None,
        }

        self._hand_detector = HandDetector(
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._gesture_clf = GestureClassifier()
        self._hand_tracker = HandTracker()
        self._prev_gestures: dict[int, str | None] = {}

        self._fusion = FusionEngine()
        self._jsonl_logger = JsonlLogger(None)

        # game_type=None 인 FusionContext 만 수신
        self._bridge.on_fusion_context(self._on_fusion_context, game_type=None)

    # ── 공개 인터페이스 ────────────────────────────────────────────────────────

    def start(self, frame_queue: "queue.Queue[Any]") -> None:
        """CameraManager가 공급하는 frame_queue에서 프레임을 소비해 처리 (블로킹)."""
        self._running = True
        print("[lobby_pipeline] 시작")

        try:
            while self._running:
                try:
                    frame = frame_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if not self._active:
                    continue  # 비활성 상태: 큐 소진만, ML 처리 스킵

                ts = time.time()
                self._process_one(frame, self._frame_id, ts)
                self._frame_id += 1
        finally:
            self._hand_detector.close()
            self._jsonl_logger.close()

    def stop(self) -> None:
        self._running = False

    def set_active(self, enabled: bool) -> None:
        self._active = enabled

    def update_players(self, players: list[Player]) -> None:
        self._players = players

    def debug_snapshot(self) -> dict[str, Any]:
        return dict(self._debug_snapshot)

    # ── 내부 처리 ──────────────────────────────────────────────────────────────

    def _process_one(self, frame_bgr: Any, frame_id: int, ts: float) -> None:
        h, w = frame_bgr.shape[:2]

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        raw_hands = self._hand_detector.detect(frame_rgb)
        hands = self._stabilize_hands(raw_hands)

        if frame_id % 30 == 0:
            hand_info = [(h.handedness, h.player_id, h.gesture) for h in hands]
            print(f"[lobby f{frame_id}] hands={hand_info}")

        perception = FramePerception(
            frame_id=frame_id,
            ts=ts,
            image_hw=(h, w),
            hands=hands,
        )

        events = self._fusion.feed(perception)
        self._debug_snapshot = {
            "frame_id": frame_id,
            "active": self._active,
            "hands": [
                {
                    "handedness": hand.handedness,
                    "gesture": hand.gesture,
                    "player_id": hand.player_id,
                    "wrist_xy": list(hand.wrist_xy),
                }
                for hand in hands
            ],
            "events": [event.to_dict() for event in events],
            "context": self._fusion._context.to_dict(),
        }
        if frame_id >= self._warmup_frames:
            for event in events:
                self._bridge.send_game_event(event, self._fsm_state_version)

    def _on_fusion_context(self, ctx: FusionContext, state_version: int) -> None:
        self._fusion.update_context(ctx)
        self._fsm_state_version = state_version

    # ── 손 안정화 ──────────────────────────────────────────────────────────────

    def _stabilize_hands(self, raw_hands: list[HandDet]) -> list[HandDet]:
        detections: list[tuple[tuple[float, float], float]] = []
        for h in raw_hands:
            angle = compute_arm_angle(h.landmarks_21)
            detections.append((h.wrist_xy, angle))

        tracks = self._hand_tracker.update(detections)
        excluded = players_with_both_hands_tracked(self._hand_tracker.active_tracks())

        stabilized: list[HandDet] = []
        for raw, track in zip(raw_hands, tracks, strict=True):
            track.handedness_buf.append(raw.handedness)
            stable_handedness = track.confirmed_handedness or raw.handedness

            if track.pending_match and track.frames_since_entry >= 3 and self._players:
                pid, _score, margin = match_player_by_arm(
                    handedness=stable_handedness,
                    entry_wrist_xy=track.entry_wrist_xy,
                    entry_arm_angle=track.entry_arm_angle,
                    players=self._players,
                    excluded_player_ids=excluded,
                )
                # margin 충분 → 즉시 확정. 부족하면 Hold(여러 프레임 voting 누적),
                # MAX_MATCH_ATTEMPTS 도달 시 best로 강제 확정(타임아웃).
                track.player_id_buf.append(pid)
                track.match_attempts += 1
                if margin >= MARGIN_THRESHOLD or track.match_attempts >= MAX_MATCH_ATTEMPTS:
                    track.pending_match = False

            player_id = track.confirmed_player_id
            prev_gesture = self._prev_gestures.get(track.track_id)
            stable_hand = HandDet(
                handedness=stable_handedness,
                wrist_xy=raw.wrist_xy,
                landmarks_21=raw.landmarks_21,
            )
            gesture = self._gesture_clf.classify_with_prev(stable_hand, prev_gesture)
            self._prev_gestures[track.track_id] = gesture

            stabilized.append(
                HandDet(
                    handedness=stable_handedness,
                    wrist_xy=raw.wrist_xy,
                    landmarks_21=raw.landmarks_21,
                    gesture=gesture,
                    player_id=player_id,
                    arm_angle=track.arm_angle,
                )
            )

        live_ids = {t.track_id for t in self._hand_tracker.active_tracks()}
        stale = [tid for tid in self._prev_gestures if tid not in live_ids]
        for tid in stale:
            del self._prev_gestures[tid]

        return stabilized
