"""Fusion Engine: FramePerception + FusionContext → GameEvent 리스트.

3조건 필터:
  1. event_type in expected_events AND not in reject_events
  2. 물리적 변화 감지 (motion 또는 제스처 변화)
  3. N프레임 안정화 (stabilization_frames 동안 동일 판정 유지)

안정화 카운터는 event_type별로 관리.
"""

from __future__ import annotations

from collections import defaultdict

from core.constants import DEFAULT_PARAMS, CommonEventType, CommonPhase
from core.events import FusionContext, GameEvent
from vision.fusion.yacht_rules import YachtRules
from vision.schemas import FramePerception, HandDet


class FusionEngine:
    def __init__(self) -> None:
        self._context: FusionContext = FusionContext(
            fsm_state=CommonPhase.PLAYER_SETUP,
            game_type=None,
            active_player=None,
            allowed_actors=[],
            expected_events=[],
        )
        self._yacht_rules = YachtRules()
        # event_type → 연속 안정화 프레임 카운터
        self._stab_counters: dict[str, int] = defaultdict(int)
        # event_type → 직전 프레임 후보 데이터 (안정화 중 동일 데이터 유지 확인)
        self._stab_candidates: dict[str, object] = {}

    # ── 외부 인터페이스 ────────────────────────────────────────────────────────

    def update_context(self, context: FusionContext) -> None:
        """FSM에서 들어오는 FusionContext 갱신. 상태 전이 시 카운터 리셋."""
        if context.fsm_state != self._context.fsm_state:
            self._stab_counters.clear()
            self._stab_candidates.clear()
        self._context = context

    def feed(self, perception: FramePerception) -> list[GameEvent]:
        """FramePerception을 소비해 통과한 GameEvent 리스트 반환."""
        ctx = self._context
        params = {**DEFAULT_PARAMS, **ctx.params}
        stab_frames = int(
            params.get("stabilization_frames", DEFAULT_PARAMS["stabilization_frames"])
        )
        gesture_stab = int(
            params.get(
                "gesture_stabilization_frames", DEFAULT_PARAMS["gesture_stabilization_frames"]
            )
        )
        conf_threshold = float(
            params.get("confidence_threshold", DEFAULT_PARAMS["confidence_threshold"])
        )

        candidates: list[tuple[str, object, float]] = []  # (event_type, data_key, confidence)

        # ── SEAT_REGISTER_RIGHT / LEFT ────────────────────────────────────────
        if ctx.fsm_state in (CommonPhase.SEAT_REGISTER_RIGHT, CommonPhase.SEAT_REGISTER_LEFT):
            for hand in perception.hands:
                evt, data, conf = self._build_seat_hand_candidate(ctx, hand)
                if evt:
                    candidates.append((evt, data, conf))

        # ── 요트 전용 ─────────────────────────────────────────────────────────
        if ctx.game_type == "yacht":
            yacht_candidates = self._yacht_rules.build_candidates(ctx, perception)
            candidates.extend(yacht_candidates)

        # ── 3조건 필터 → GameEvent 생성 ───────────────────────────────────────
        events: list[GameEvent] = []
        for event_type, data_key, conf in candidates:
            # 조건 1: expected_events 매칭
            if not ctx.expects(event_type):
                self._stab_counters[event_type] = 0
                continue

            # 조건 2: 물리적 변화 (데이터 키가 달라지면 카운터 리셋)
            # dict 타입이면 _key 필드로 비교, 그 외 직접 비교
            stab_key = data_key.get("_key") if isinstance(data_key, dict) else data_key
            prev = self._stab_candidates.get(event_type)
            if prev != stab_key:
                self._stab_counters[event_type] = 0
                self._stab_candidates[event_type] = stab_key

            # 조건 3: N프레임 안정화
            required = (
                gesture_stab
                if "seat_hand" in event_type or "gesture" in event_type
                else stab_frames
            )
            self._stab_counters[event_type] += 1
            if self._stab_counters[event_type] < required:
                continue

            if conf < conf_threshold:
                continue

            # 통과 → GameEvent 생성
            event_data = data_key if isinstance(data_key, dict) else {}
            actor_id = event_data.get("actor_id") or ctx.active_player

            # allowed_actors 검증 (비어있으면 개발 모드 → 스킵)
            if ctx.allowed_actors and actor_id and actor_id not in ctx.allowed_actors:
                events.append(
                    GameEvent(
                        event_type=CommonEventType.RULE_VIOLATION,
                        actor_id=actor_id,
                        confidence=1.0,
                        frame_id=perception.frame_id,
                        data={
                            "violation_type": "WRONG_TURN",
                            "detail": f"{actor_id} not in allowed_actors",
                        },
                    )
                )
                self._stab_counters[event_type] = 0
                continue

            events.append(
                GameEvent(
                    event_type=event_type,
                    actor_id=actor_id,
                    confidence=conf,
                    frame_id=perception.frame_id,
                    data={k: v for k, v in event_data.items() if k not in ("actor_id", "_key")},
                )
            )
            # 발화 후 카운터 리셋 (중복 발화 방지)
            self._stab_counters[event_type] = 0

        return events

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _build_seat_hand_candidate(
        self,
        ctx: FusionContext,
        hand: HandDet,
    ) -> tuple[str | None, dict, float]:
        """SEAT_REGISTER_RIGHT/LEFT 단계에서 seat_hand_registered 후보 생성."""
        if ctx.fsm_state == CommonPhase.SEAT_REGISTER_RIGHT:
            expected_hand = "Right"
            expected_gesture = "v_sign"
        else:
            expected_hand = "Left"
            expected_gesture = "ok_sign"

        if hand.handedness != expected_hand:
            return None, {}, 0.0
        if hand.gesture != expected_gesture:
            return None, {}, 0.0

        # data_key: wrist를 0.01 단위로 양자화해 안정화 판정 (dict로 통일)
        # active_player를 _key에 포함 → context 전환 시 카운터 리셋
        data_key = {
            "hand": hand.handedness,
            "wrist": list(hand.wrist_xy),
            "gesture": expected_gesture,
            "actor_id": ctx.active_player,
            "_key": (
                hand.handedness,
                round(hand.wrist_xy[0], 2),
                round(hand.wrist_xy[1], 2),
                hand.gesture,
                ctx.active_player,
            ),
        }
        return CommonEventType.SEAT_HAND_REGISTERED, data_key, 0.9
