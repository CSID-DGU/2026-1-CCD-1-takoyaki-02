"""비전 파이프라인 오케스트레이터.

단일 스레드 동기 루프:
  cv2.VideoCapture → YOLO → ByteTrack → DotCounter → MediaPipe → Gesture
  → SeatMatcher → RollAttributor → FramePerception → FusionEngine → Bridge
"""

from __future__ import annotations

import time
from typing import Any

import cv2

from bridge.interface import Bridge
from core.constants import DEFAULT_PARAMS
from core.events import FusionContext
from core.models import Player
from vision.attribution.roll_attributor import RollAttributor
from vision.attribution.seat_matcher import SeatMatcher
from vision.config import VisionConfig
from vision.debug.jsonl_logger import JsonlLogger
from vision.debug.overlay import draw_overlay
from vision.detectors.dot_counter import DotCounter
from vision.detectors.gesture_classifier import GestureClassifier
from vision.detectors.hand_detector import HandDetector
from vision.detectors.yolo_detector import YoloDetector
from vision.fusion.engine import FusionEngine
from vision.schemas import BBox, FramePerception, HandDet, YoloDet
from vision.tracking.byte_tracker import ByteTracker
from vision.tracking.dice_manager import DiceManager


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
        self._frame_id = 0

        # 컴포넌트 초기화
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
        self._byte_tracker = ByteTracker()
        self._dot_counter = DotCounter()
        self._dice_manager = DiceManager(
            motion_threshold=float(DEFAULT_PARAMS["motion_threshold_norm"]),
            stabilization_frames=int(DEFAULT_PARAMS["stabilization_frames"]),
            history_window=config.dice_history_window,
            pip_buffer_size=config.dice_count_buffer,
        )
        self._seat_matcher = SeatMatcher()
        self._roll_attributor = RollAttributor(
            roll_lift_threshold=config.roll_lift_threshold,
            grab_fallback_window_frames=config.grab_fallback_window_frames,
            stabilization_frames=int(DEFAULT_PARAMS["stabilization_frames"]),
            motion_threshold=float(DEFAULT_PARAMS["motion_threshold_norm"]),
        )
        self._fusion = FusionEngine()
        self._jsonl_logger = JsonlLogger(config.jsonl_log_path)

        # 직전 제스처 (release 감지용)
        self._prev_gestures: dict[int, str] = {}  # hand index → gesture

        # 오버레이용 최근 이벤트 배너
        self._last_event_data: dict | None = None
        self._event_banner_ttl: int = 0  # 남은 표시 프레임 수

        # Bridge에서 FusionContext 수신 핸들러 등록
        self._bridge.on_fusion_context(self._on_fusion_context)

    # ── 공개 인터페이스 ────────────────────────────────────────────────────────

    def start(self) -> None:
        """캡처 루프 시작 (블로킹)."""
        cap = cv2.VideoCapture(self._config.source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.resolution[1])
        cap.set(cv2.CAP_PROP_FPS, self._config.target_fps)

        self._running = True
        skip_counter = 0

        print(f"[pipeline] cap opened={cap.isOpened()}  "
              f"w={cap.get(cv2.CAP_PROP_FRAME_WIDTH):.0f}  "
              f"h={cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f}  "
              f"fps={cap.get(cv2.CAP_PROP_FPS):.0f}")

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    print("[pipeline] cap.read() returned False — camera disconnected or end of file")
                    break

                # frame_skip: 0=모든 프레임, N=N프레임 건너뜀
                if self._config.frame_skip > 0:
                    skip_counter += 1
                    if skip_counter <= self._config.frame_skip:
                        continue
                    skip_counter = 0

                ts = time.time()
                self._process_one(frame, self._frame_id, ts)
                self._frame_id += 1

                if self._config.debug_overlay:
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
        finally:
            cap.release()
            if self._config.debug_overlay:
                cv2.destroyAllWindows()
            self._hand_detector.close()

    def stop(self) -> None:
        self._running = False

    def update_players(self, players: list[Player]) -> None:
        self._players = players

    # ── 내부 처리 ──────────────────────────────────────────────────────────────

    def _process_one(self, frame_bgr: Any, frame_id: int, ts: float) -> None:
        h, w = frame_bgr.shape[:2]

        # 1) YOLO 감지
        yolo_dets = self._yolo.detect(frame_bgr)
        tray, tray_inner, roll_tray, dice_dets = _split_dets(yolo_dets)

        # 2) ByteTrack + DiceManager
        tracked = self._byte_tracker.update(dice_dets, frame_id)
        dice_states = self._dice_manager.update(tracked, frame_bgr, self._dot_counter)

        # 3) MediaPipe 손 감지 (RGB 변환)
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        raw_hands = self._hand_detector.detect(frame_rgb)

        # 4) 제스처 분류 + SeatMatcher
        hands: list[HandDet] = []
        for i, hand in enumerate(raw_hands):
            prev_g = self._prev_gestures.get(i)
            gesture = self._gesture_clf.classify_with_prev(hand, prev_g)
            self._prev_gestures[i] = gesture

            player_id = self._seat_matcher.match(hand, self._players)
            hands.append(HandDet(
                handedness=hand.handedness,
                wrist_xy=hand.wrist_xy,
                landmarks_21=hand.landmarks_21,
                gesture=gesture,
                player_id=player_id,
            ))

        # 사라진 손 이력 정리
        for k in list(self._prev_gestures.keys()):
            if k >= len(raw_hands):
                del self._prev_gestures[k]

        # 5) 임시 perception 조립 (RollAttributor 입력용)
        perception = FramePerception(
            frame_id=frame_id,
            ts=ts,
            image_hw=(h, w),
            tray=tray,
            tray_inner=tray_inner,
            roll_tray=roll_tray,
            dice=dice_states,
            hands=hands,
        )

        # 6) RollAttributor
        roll_actor = self._roll_attributor.update(perception)
        if roll_actor is not None:
            perception.roll_actor_id = roll_actor
        perception.phase_hints = {
            "dice_all_stable": perception.dice_all_stable(
                int(DEFAULT_PARAMS["stabilization_frames"])
            ),
            "dice_count": len(dice_states),
            "roll_state": self._roll_attributor.state.name,
        }

        # 7) FusionEngine
        events = self._fusion.feed(perception)
        for event in events:
            self._bridge.send_game_event(event, 0)
            # dice_rolled 이벤트면 배너 TTL 세팅 (90프레임 ≈ 3초)
            if event.event_type == "dice_rolled":
                self._last_event_data = event.data if isinstance(event.data, dict) else None
                self._event_banner_ttl = 90

        # 8) 로깅
        self._jsonl_logger.log(perception)

        # 9) 디버그 오버레이
        if self._config.debug_overlay:
            vis = draw_overlay(
                frame_bgr.copy(), perception,
                recent_event=self._last_event_data,
                event_ttl_frames=self._event_banner_ttl,
            )
            if self._event_banner_ttl > 0:
                self._event_banner_ttl -= 1
            cv2.imshow("VisionPipeline", vis)

    def _on_fusion_context(self, ctx: FusionContext, state_version: int) -> None:
        self._fusion.update_context(ctx)


def _split_dets(
    dets: list[YoloDet],
) -> tuple[BBox | None, BBox | None, BBox | None, list[YoloDet]]:
    """YoloDet 리스트를 tray/tray_inner/roll_tray/dice로 분리."""
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
