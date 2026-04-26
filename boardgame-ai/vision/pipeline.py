"""비전 파이프라인 오케스트레이터.

단일 스레드 동기 루프:
  cv2.VideoCapture → YOLO → ByteTrack → DotCounter → MediaPipe → Gesture
  → SeatMatcher → RollAttributor → FramePerception → FusionEngine → Bridge
"""

from __future__ import annotations

import math
import time
from collections import Counter, deque
from dataclasses import dataclass, field
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

# 한 프레임 사이 손 wrist가 움직일 수 있는 최대 정규화 거리.
# 이 안에 들어오면 직전 프레임의 같은 손으로 간주해 handedness/제스처 이력을 이어 붙인다.
_HAND_TRACK_MAX_DIST = 0.15
# handedness 다수결 버퍼 크기 (5프레임 ≈ 약 0.16초). MediaPipe가 한 프레임 라벨을 뒤집어도 흡수.
_HANDEDNESS_BUF_SIZE = 5


@dataclass
class _HandTrack:
    """프레임 간 손 추적 — handedness/gesture 시간적 안정화용."""

    wrist_xy: tuple[float, float]
    handedness_buf: deque[str] = field(default_factory=lambda: deque(maxlen=_HANDEDNESS_BUF_SIZE))
    prev_gesture: str | None = None


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
        # DiceManager는 pip 측정 시작 임계를 짧게 — 굴림 직후 빠르게 pip 잡히도록.
        # RollAttributor의 stabilization과는 별개 (RollAttributor는 굴림 종료 판정용)
        self._dice_manager = DiceManager(
            motion_threshold=float(DEFAULT_PARAMS["motion_threshold_norm"]),
            stabilization_frames=10,
            history_window=config.dice_history_window,
            pip_buffer_size=config.dice_count_buffer,
        )
        self._seat_matcher = SeatMatcher()
        self._roll_attributor = RollAttributor(
            stabilization_frames=15,  # dice_manager와 동일 — 안정 후 곧바로 비교 가능
            grab_fallback_window_frames=config.grab_fallback_window_frames,
            roll_lift_threshold=config.roll_lift_threshold,
            motion_threshold=float(DEFAULT_PARAMS["motion_threshold_norm"]),
        )
        self._fusion = FusionEngine()
        self._jsonl_logger = JsonlLogger(config.jsonl_log_path)

        # 손 시간적 추적 — handedness 다수결 + 직전 제스처 보관
        # MediaPipe는 매 프레임 인덱스가 안정적이지 않으므로 wrist 좌표 근접도로 매칭
        self._hand_tracks: list[_HandTrack] = []

        # 오버레이용 최근 이벤트 배너
        self._last_event_data: dict | None = None
        self._event_banner_ttl: int = 0  # 남은 표시 프레임 수

        # FSM에서 받은 최신 state_version (이벤트 송신 시 동일 버전 사용 — 계약 정합)
        self._fsm_state_version: int = 0

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

        print(
            f"[pipeline] cap opened={cap.isOpened()}  "
            f"w={cap.get(cv2.CAP_PROP_FRAME_WIDTH):.0f}  "
            f"h={cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f}  "
            f"fps={cap.get(cv2.CAP_PROP_FPS):.0f}"
        )

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    print(
                        "[pipeline] cap.read() returned False — camera disconnected or end of file"
                    )
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

                if self._config.debug_overlay and cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            cap.release()
            if self._config.debug_overlay:
                cv2.destroyAllWindows()
            try:
                self._hand_detector.close()
            finally:
                self._jsonl_logger.close()

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

        # tray 감지 시 dice center가 tray + 패딩 밖이면 무시 (각도 흔들림으로 잡히는 가짜 dice 차단)
        if tray is not None and self._config.tray_mask_padding > 0:
            dice_dets = _filter_dice_inside_tray(
                dice_dets, tray, padding=self._config.tray_mask_padding
            )

        # 2) ByteTrack + DiceManager
        tracked = self._byte_tracker.update(dice_dets, frame_id)
        dice_states = self._dice_manager.update(tracked, frame_bgr, self._dot_counter)
        # track_id 오름차순 정렬 — dice_values 출력 순서를 프레임 간 일관되게 유지
        dice_states.sort(key=lambda d: d.track_id)

        # 3) MediaPipe 손 감지 (RGB 변환)
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        raw_hands = self._hand_detector.detect(frame_rgb)

        # 4) 손 시간적 매칭 → handedness 다수결 + 제스처 분류 + SeatMatcher
        # MediaPipe 손 인덱스는 프레임 간 안정적이지 않으므로 wrist 거리로 매칭한다.
        hands, self._hand_tracks = self._stabilize_hands(raw_hands)

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

        # 6) RollAttributor — finalize된 프레임만 roll_just_confirmed=True.
        # YachtRules가 이 게이트로 ROLL_CONFIRMED/ROLL_UNREADABLE 1회 발화만 허용.
        # actor가 None이어도 finalize 자체는 인정 (FSM ctx.active_player fallback 사용)
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

        # 7) FusionEngine — 송신 시 FSM에서 받은 최신 state_version 사용.
        # 워밍업 동안에는 FusionEngine은 호출(안정화 카운터는 굴려야 함)하되 송신만 skip.
        events = self._fusion.feed(perception)
        if frame_id >= self._config.warmup_frames:
            for event in events:
                self._bridge.send_game_event(event, self._fsm_state_version)
                # ROLL_CONFIRMED 이벤트면 배너 TTL 세팅 (90프레임 ≈ 3초)
                if event.event_type == "ROLL_CONFIRMED":
                    self._last_event_data = event.data if isinstance(event.data, dict) else None
                    self._event_banner_ttl = 90

        # 8) 로깅
        self._jsonl_logger.log(perception)

        # 9) 디버그 오버레이
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
        self._fusion.update_context(ctx)
        self._fsm_state_version = state_version

    # ── 손 안정화 ─────────────────────────────────────────────────────────────

    def _stabilize_hands(self, raw_hands: list[HandDet]) -> tuple[list[HandDet], list[_HandTrack]]:
        """
        wrist 좌표 근접도로 직전 프레임의 손과 매칭한 뒤,
        최근 N프레임 handedness 다수결로 라벨을 안정화한다.

        반환: (안정화된 HandDet 리스트, 갱신된 _HandTrack 리스트)
        """
        prev_tracks = list(self._hand_tracks)
        used_prev: set[int] = set()
        new_tracks: list[_HandTrack] = []
        stabilized: list[HandDet] = []

        for raw in raw_hands:
            best_idx: int | None = None
            best_dist = float("inf")
            for i, prev in enumerate(prev_tracks):
                if i in used_prev:
                    continue
                d = math.hypot(
                    raw.wrist_xy[0] - prev.wrist_xy[0],
                    raw.wrist_xy[1] - prev.wrist_xy[1],
                )
                if d < best_dist:
                    best_dist = d
                    best_idx = i

            if best_idx is not None and best_dist < _HAND_TRACK_MAX_DIST:
                track = prev_tracks[best_idx]
                used_prev.add(best_idx)
            else:
                track = _HandTrack(wrist_xy=raw.wrist_xy)

            track.wrist_xy = raw.wrist_xy
            track.handedness_buf.append(raw.handedness)
            stable_handedness = Counter(track.handedness_buf).most_common(1)[0][0]

            # gesture 분류는 안정화된 handedness로 + 직전 제스처 참고 (release 감지)
            stable_hand = HandDet(
                handedness=stable_handedness,
                wrist_xy=raw.wrist_xy,
                landmarks_21=raw.landmarks_21,
            )
            gesture = self._gesture_clf.classify_with_prev(stable_hand, track.prev_gesture)
            track.prev_gesture = gesture

            player_id = self._seat_matcher.match(stable_hand, self._players)

            stabilized.append(
                HandDet(
                    handedness=stable_handedness,
                    wrist_xy=raw.wrist_xy,
                    landmarks_21=raw.landmarks_21,
                    gesture=gesture,
                    player_id=player_id,
                )
            )
            new_tracks.append(track)

        return stabilized, new_tracks


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


def _filter_dice_inside_tray(dice_dets: list[YoloDet], tray: BBox, padding: float) -> list[YoloDet]:
    """tray bbox + 패딩 밖에 중심이 있는 dice 제거. tray 외부 가짜 detection 차단."""
    pad_x = tray.w * padding
    pad_y = tray.h * padding
    x1, y1 = tray.x1 - pad_x, tray.y1 - pad_y
    x2, y2 = tray.x2 + pad_x, tray.y2 + pad_y
    inside: list[YoloDet] = []
    for d in dice_dets:
        cx, cy = d.bbox.center()
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            inside.append(d)
    return inside
