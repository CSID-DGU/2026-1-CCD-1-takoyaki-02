"""요트 다이스 비전 파이프라인.

CameraManager가 공급하는 frame_queue에서 프레임을 소비해 처리한다.
"""

from __future__ import annotations

import queue
import time
from typing import Any

import cv2

from bridge.interface import Bridge
from core.constants import DEFAULT_PARAMS
from core.events import FusionContext
from core.models import Player
from vision.attribution.roll_attributor import RollAttributor
from vision.attribution.seat_matcher import (
    match_player_by_arm,
    players_with_both_hands_tracked,
)
from vision.yacht.config import VisionConfig
from vision.debug.jsonl_logger import JsonlLogger
from vision.debug.overlay import draw_overlay
from vision.detectors.dot_counter import DotCounter
from vision.detectors.gesture_classifier import GestureClassifier
from vision.detectors.hand_detector import HandDetector
from vision.detectors.yolo_detector import YoloDetector
from vision.fusion.engine import FusionEngine
from vision.geometry.arm_vector import compute_arm_angle
from vision.schemas import BBox, HandDet, YoloDet
from vision.yacht.schemas import YachtFramePerception
from vision.tracking.byte_tracker import ByteTracker
from vision.tracking.dice_manager import DiceManager
from vision.tracking.hand_tracker import HandTracker


class VisionPipeline:
    def __init__(
        self,
        config: VisionConfig,
        bridge: Bridge,
        players: list[Player],
    ) -> None:
        self._config = config
        self._bridge = bridge
        self._players = players
        self._running = False
        self._active = True  # False이면 프레임 처리 스킵 (큐 소진만)
        self._frame_id = 0

        self._yolo = YoloDetector(
            weights_path=config.weights_path,
            conf=config.yolo_conf,
            iou=config.yolo_iou,
            imgsz=config.yolo_imgsz,
        )
        self._hand_detector = HandDetector(
            max_num_hands=config.mp_max_num_hands,
            min_detection_confidence=config.mp_min_detection_confidence,
            min_tracking_confidence=config.mp_min_tracking_confidence,
        )
        self._gesture_clf = GestureClassifier()
        self._hand_tracker = HandTracker()
        self._prev_gestures: dict[int, str | None] = {}
        self._byte_tracker = ByteTracker()
        self._dot_counter = DotCounter()
        self._dice_manager = DiceManager(
            motion_threshold=float(DEFAULT_PARAMS["motion_threshold_norm"]),
            stabilization_frames=10,
            history_window=config.dice_history_window,
            pip_buffer_size=config.dice_count_buffer,
        )
        self._roll_attributor = RollAttributor(
            stabilization_frames=15,
            grab_fallback_window_frames=config.grab_fallback_window_frames,
            roll_lift_threshold=config.roll_lift_threshold,
            motion_threshold=float(DEFAULT_PARAMS["motion_threshold_norm"]),
        )
        self._fusion = FusionEngine()
        self._jsonl_logger = JsonlLogger(config.jsonl_log_path)

        self._last_event_data: dict | None = None
        self._event_banner_ttl: int = 0
        self._fsm_state_version: int = 0
        self._has_context: bool = False

        self._bridge.on_fusion_context(self._on_fusion_context, game_type="yacht")

    def start(self, frame_queue: "queue.Queue[Any]") -> None:
        """CameraManager가 공급하는 frame_queue에서 프레임을 소비해 처리 (블로킹)."""
        self._running = True
        skip_counter = 0
        print("[yacht_pipeline] 시작")

        try:
            while self._running:
                try:
                    frame = frame_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if not self._active:
                    continue  # 비활성 상태: 큐 소진만, ML 처리 스킵

                if self._config.frame_skip > 0:
                    skip_counter += 1
                    if skip_counter <= self._config.frame_skip:
                        continue
                    skip_counter = 0

                ts = time.time()
                self._process_one(frame, self._frame_id, ts)
                self._frame_id += 1

                if self._config.debug_overlay and cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            if self._config.debug_overlay:
                cv2.destroyAllWindows()
            try:
                self._hand_detector.close()
            finally:
                self._jsonl_logger.close()

    def stop(self) -> None:
        self._running = False

    def set_active(self, enabled: bool) -> None:
        self._active = enabled

    def update_players(self, players: list[Player]) -> None:
        self._players = players

    def _process_one(self, frame_bgr: Any, frame_id: int, ts: float) -> None:
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
            frame_id=frame_id,
            ts=ts,
            image_hw=(h, w),
            tray=tray,
            tray_inner=tray_inner,
            roll_tray=roll_tray,
            dice=dice_states,
            hands=hands,
        )

        roll_actor = self._roll_attributor.update(perception)
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

        if frame_id % 30 == 0 and self._has_context:
            hand_info = [(h.handedness, h.player_id, h.gesture) for h in hands]
            dice_info = [(d.track_id, d.pip_count, d.stable_frames) for d in dice_states]
            print(
                f"[yacht f{frame_id}] "
                f"tray={'O' if tray else 'X'}  "
                f"dice={dice_info}  "
                f"hands={hand_info}"
            )

        events = self._fusion.feed(perception)
        if frame_id >= self._config.warmup_frames:
            for event in events:
                self._bridge.send_game_event(event, self._fsm_state_version)
                if event.event_type == "ROLL_CONFIRMED":
                    self._last_event_data = event.data if isinstance(event.data, dict) else None
                    self._event_banner_ttl = 90

        self._jsonl_logger.log(perception)

        if self._config.debug_overlay:
            warmup_remaining = max(0, self._config.warmup_frames - frame_id)
            vis = draw_overlay(
                frame_bgr.copy(),
                perception,
                recent_event=self._last_event_data,
                event_ttl_frames=self._event_banner_ttl,
                warmup_remaining=warmup_remaining,
            )
            if self._event_banner_ttl > 0:
                self._event_banner_ttl -= 1
            cv2.imshow("VisionPipeline", vis)

    def _on_fusion_context(self, ctx: FusionContext, state_version: int) -> None:
        self._has_context = True
        self._fusion.update_context(ctx)
        self._fsm_state_version = state_version

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
                pid, _score = match_player_by_arm(
                    handedness=stable_handedness,
                    entry_wrist_xy=track.entry_wrist_xy,
                    entry_arm_angle=track.entry_arm_angle,
                    players=self._players,
                    excluded_player_ids=excluded,
                )
                track.player_id_buf.append(pid)
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


def _split_dets(
    dets: list[YoloDet],
) -> tuple[BBox | None, BBox | None, BBox | None, list[YoloDet]]:
    tray = tray_inner = roll_tray = None
    dice_dets: list[YoloDet] = []
    for d in dets:
        if d.cls_name == "tray":
            tray = d.bbox
        elif d.cls_name == "tray_inner":
            tray_inner = d.bbox
        elif d.cls_name == "roll_tray":
            roll_tray = d.bbox
        elif d.cls_name == "dice":
            dice_dets.append(d)
    return tray, tray_inner, roll_tray, dice_dets


def _filter_dice_inside_tray(
    dice_dets: list[YoloDet], tray: BBox, padding: float
) -> list[YoloDet]:
    pad_x = tray.w * padding
    pad_y = tray.h * padding
    x1, y1 = tray.x1 - pad_x, tray.y1 - pad_y
    x2, y2 = tray.x2 + pad_x, tray.y2 + pad_y
    return [d for d in dice_dets if x1 <= d.bbox.cx <= x2 and y1 <= d.bbox.cy <= y2]
