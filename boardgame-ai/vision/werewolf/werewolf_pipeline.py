"""한밤의 늑대인간 전용 비전 파이프라인.

VisionPipeline(요트) 과 독립적으로 동작. 공통 컴포넌트(HandDetector,
GestureClassifier, HandTracker, FusionEngine)는 재사용하고,
요트 전용 컴포넌트(DiceManager, DotCounter, RollAttributor)는 포함하지 않는다.

처리 흐름:
  cv2.VideoCapture
    → WerewolfCardDetector (YOLO, 모델 없으면 fallback)
    → CardTracker (ByteTrack + 역할/플레이어 매핑)
    → HandDetector + GestureClassifier + HandTracker
    → FramePerception 조립 (hands 필드만 채움)
    → FusionEngine (WerewolfRules 주입됨)
    → Bridge.send_game_event()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2

from bridge.interface import Bridge
from core.events import FusionContext
from core.models import Player
from vision.attribution.seat_matcher import (
    match_player_by_arm,
    players_with_both_hands_tracked,
)
from vision.debug.jsonl_logger import JsonlLogger
from vision.detectors.gesture_classifier import GestureClassifier
from vision.detectors.hand_detector import HandDetector
from vision.fusion.engine import FusionEngine
from vision.fusion.werewolf_rules import WerewolfRules
from vision.geometry.arm_vector import compute_arm_angle
from vision.schemas import FramePerception, HandDet
from vision.tracking.hand_tracker import HandTracker
from vision.werewolf.card_detector import WerewolfCardDetector
from vision.werewolf.card_tracker import CardTracker


@dataclass
class WerewolfVisionConfig:
    """WerewolfVisionPipeline 하드웨어·IO 설정."""

    # 카메라 / 소스
    source: int | str = 0
    resolution: tuple[int, int] = (1920, 1080)
    target_fps: int = 30
    frame_skip: int = 0

    # YOLO 카드 감지 모델
    # 학습 완료 후 이 경로에 .pt 파일을 두면 자동 로드
    card_weights_path: str | Path = "vision/weights/werewolf_cards.pt"
    yolo_conf: float = 0.50
    yolo_iou: float = 0.45
    yolo_imgsz: int = 640

    # MediaPipe Hand
    mp_max_num_hands: int = 8
    mp_min_detection_confidence: float = 0.5
    mp_min_tracking_confidence: float = 0.5

    # 카드-플레이어 근접 매칭 임계 (정규화 거리)
    card_player_match_threshold: float = 0.25

    # 시작 시 워밍업 프레임 (이 기간은 GameEvent 송신 skip)
    warmup_frames: int = 60

    # 디버그·로깅
    debug_overlay: bool = False
    jsonl_log_path: Path | None = None

    def __post_init__(self) -> None:
        self.card_weights_path = Path(self.card_weights_path)
        if self.jsonl_log_path is not None:
            self.jsonl_log_path = Path(self.jsonl_log_path)


class WerewolfVisionPipeline:
    """한밤의 늑대인간 비전 파이프라인.

    VisionPipeline(요트 전용) 과 완전히 독립된 클래스.
    공통 컴포넌트만 재사용하고 요트 전용 로직은 포함하지 않는다.
    """

    def __init__(
        self,
        config: WerewolfVisionConfig,
        bridge: Bridge,
        players: list[Player],
    ) -> None:
        self._config = config
        self._bridge = bridge
        self._players = players
        self._running = False
        self._frame_id = 0

        # 카드 파이프라인 (늑대인간 전용)
        self._card_detector = WerewolfCardDetector(
            model_path=str(config.card_weights_path),
            conf=config.yolo_conf,
            iou=config.yolo_iou,
            imgsz=config.yolo_imgsz,
        )
        self._card_tracker = CardTracker(
            player_match_threshold=config.card_player_match_threshold,
        )

        # 손 파이프라인 (기존 컴포넌트 재사용)
        self._hand_detector = HandDetector(
            max_num_hands=config.mp_max_num_hands,
            min_detection_confidence=config.mp_min_detection_confidence,
            min_tracking_confidence=config.mp_min_tracking_confidence,
        )
        self._gesture_clf = GestureClassifier()
        self._hand_tracker = HandTracker()
        # track_id → 직전 제스처 (release 감지용)
        self._prev_gestures: dict[int, str | None] = {}

        # Fusion (WerewolfRules 주입)
        self._fusion = FusionEngine()
        self._werewolf_rules = WerewolfRules(self._card_tracker)
        self._fusion.register_werewolf_rules(self._werewolf_rules)

        # 상태
        self._fsm_state_version: int = 0
        self._jsonl_logger = JsonlLogger(config.jsonl_log_path)

        # FSM → FusionContext 수신 핸들러 등록
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
            f"[werewolf_pipeline] cap opened={cap.isOpened()}  "
            f"card_model={'loaded' if self._card_detector.is_loaded else 'NOT LOADED (fallback)'}  "
            f"w={cap.get(cv2.CAP_PROP_FRAME_WIDTH):.0f}  "
            f"h={cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f}  "
            f"fps={cap.get(cv2.CAP_PROP_FPS):.0f}"
        )

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    print("[werewolf_pipeline] cap.read() False — 카메라 연결 끊김 또는 파일 끝")
                    break

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
        """백엔드에서 플레이어 목록이 갱신될 때 호출."""
        self._players = players

    # ── 내부 처리 ──────────────────────────────────────────────────────────────

    def _process_one(self, frame_bgr: Any, frame_id: int, ts: float) -> None:
        h, w = frame_bgr.shape[:2]

        # 1) 카드 감지 + 추적 (CardTracker 내부 상태 갱신)
        card_dets = self._card_detector.detect(frame_bgr)
        self._card_tracker.update(card_dets, self._players, frame_id)

        # 2) 손 감지 (RGB 변환 후 MediaPipe)
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        raw_hands = self._hand_detector.detect(frame_rgb)

        # 3) 손 시간적 안정화 + player_id 배정
        hands = self._stabilize_hands(raw_hands)

        # 4) FramePerception 조립
        #    dice/tray 필드는 기본값(None/[]) 그대로 — 요트 전용 필드
        perception = FramePerception(
            frame_id=frame_id,
            ts=ts,
            image_hw=(h, w),
            hands=hands,
        )

        # 5) FusionEngine → GameEvent 생성
        #    WerewolfRules 는 내부에서 self._card_tracker 를 직접 참조
        events = self._fusion.feed(perception)
        if frame_id >= self._config.warmup_frames:
            for event in events:
                self._bridge.send_game_event(event, self._fsm_state_version)

        # 6) JSONL 로깅
        self._jsonl_logger.log(perception)

    def _on_fusion_context(self, ctx: FusionContext, state_version: int) -> None:
        self._fusion.update_context(ctx)
        self._fsm_state_version = state_version

    # ── 손 안정화 (VisionPipeline._stabilize_hands 와 동일 로직) ──────────────

    def _stabilize_hands(self, raw_hands: list[HandDet]) -> list[HandDet]:
        """HandTracker 로 frame-to-frame track 을 유지하고 player_id 를 안정화한다."""
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
