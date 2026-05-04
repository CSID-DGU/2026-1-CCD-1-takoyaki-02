"""Fusion Engine: FramePerception + FusionContext → GameEvent 리스트.

3조건 필터:
  1. event_type in expected_events AND not in reject_events
  2. 물리적 변화 감지 (motion 또는 제스처 변화)
  3. N프레임 안정화 (stabilization_frames 동안 동일 판정 유지)

안정화 카운터는 event_type별로 관리.
"""

from __future__ import annotations

import threading
from collections import defaultdict

from core.constants import DEFAULT_PARAMS, CommonEventType, CommonPhase
from core.events import FusionContext, GameEvent
from core.models import ArmAnchor, SeatZone
from vision.fusion.yacht_rules import YachtRules
from vision.geometry.arm_vector import compute_arm_angle, estimate_body_xy
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
        # WerewolfVisionPipeline 이 register_werewolf_rules() 로 주입
        self._werewolf_rules: object | None = None
        # event_type → 연속 안정화 프레임 카운터
        self._stab_counters: dict[str, int] = defaultdict(int)
        # event_type → 직전 프레임 후보 데이터 (안정화 중 동일 데이터 유지 확인)
        self._stab_candidates: dict[str, object] = {}
        # SEAT_REGISTER 순차 등록 상태: 오른손 V사인 확인 후 왼손 OK사인 대기
        # actor_id → (wrist_xy, arm_angle)
        self._seat_right_confirmed: dict[str, tuple[tuple[float, float], float]] = {}
        # 중간 이벤트 SEAT_RIGHT_REGISTERED 1회 발화 가드
        self._seat_right_event_emitted: set[str] = set()
        # update_context()는 백엔드(FastAPI/WS) 스레드에서, feed()는 비전 캡처 스레드에서
        # 호출될 수 있어 내부 상태 보호용 lock 필요. RLock으로 동일 스레드 재진입 허용.
        self._lock = threading.RLock()

    # ── 외부 인터페이스 ────────────────────────────────────────────────────────

    def update_context(self, context: FusionContext) -> None:
        """FSM에서 들어오는 FusionContext 갱신. 상태 전이 시 카운터 리셋."""
        with self._lock:
            if context.fsm_state != self._context.fsm_state:
                self._stab_counters.clear()
                self._stab_candidates.clear()
                self._seat_right_confirmed.clear()
                self._seat_right_event_emitted.clear()
            self._context = context

    def register_werewolf_rules(self, rules: object) -> None:
        """WerewolfVisionPipeline 에서 WerewolfRules 인스턴스를 주입한다."""
        with self._lock:
            self._werewolf_rules = rules

    def feed(self, perception: FramePerception) -> list[GameEvent]:
        """FramePerception을 소비해 통과한 GameEvent 리스트 반환."""
        with self._lock:
            return self._feed_locked(perception)

    def _feed_locked(self, perception: FramePerception) -> list[GameEvent]:
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

        # ── SEAT_REGISTER (오른손 V사인 → 왼손 OK사인 순차) ─────────────────
        if ctx.fsm_state == CommonPhase.SEAT_REGISTER:
            # 중간 이벤트: 오른손 V사인만 보이면 1회 발화
            evt_r, data_r, conf_r = self._build_seat_right_registered_candidate(ctx, perception)
            if evt_r:
                candidates.append((evt_r, data_r, conf_r))
            # 완료 이벤트: 양손 모두 캡처되면 발화
            evt, data, conf = self._build_seat_registered_candidate(ctx, perception)
            if evt:
                candidates.append((evt, data, conf))

        # ── SEAT_REGISTER_RIGHT / LEFT (하위 호환) ────────────────────────────
        elif ctx.fsm_state in (CommonPhase.SEAT_REGISTER_RIGHT, CommonPhase.SEAT_REGISTER_LEFT):
            for hand in perception.hands:
                evt, data, conf = self._build_seat_hand_candidate(ctx, hand)
                if evt:
                    candidates.append((evt, data, conf))

        # ── 요트 전용 ─────────────────────────────────────────────────────────
        if ctx.game_type == "yacht":
            yacht_candidates = self._yacht_rules.build_candidates(ctx, perception)
            candidates.extend(yacht_candidates)

        # ── 늑대인간 전용 ─────────────────────────────────────────────────────
        if ctx.game_type == "werewolf" and self._werewolf_rules is not None:
            candidates.extend(self._werewolf_rules.build_candidates(ctx, perception))

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

            # 조건 3: N프레임 안정화.
            # ROLL_CONFIRMED/ROLL_UNREADABLE/DICE_ESCAPED는 yacht_rules가 자체적으로
            # 1회성 게이트(roll_just_confirmed / _reported_escaped)를 적용하므로 즉시 발화.
            if event_type in ("ROLL_CONFIRMED", "ROLL_UNREADABLE", "DICE_ESCAPED"):
                required = 1
            elif (
                event_type
                in (
                    CommonEventType.SEAT_REGISTERED,
                    CommonEventType.SEAT_RIGHT_REGISTERED,
                )
                or "seat_hand" in event_type
                or "gesture" in event_type
            ):
                required = gesture_stab
            else:
                required = stab_frames
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
            # 중간 이벤트 1회 발화 가드
            if event_type == CommonEventType.SEAT_RIGHT_REGISTERED and actor_id:
                self._seat_right_event_emitted.add(actor_id)
            # 발화 후 카운터 리셋 (중복 발화 방지)
            self._stab_counters[event_type] = 0

        return events

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _build_seat_registered_candidate(
        self,
        ctx: FusionContext,
        perception: FramePerception,
    ) -> tuple[str | None, dict, float]:
        """SEAT_REGISTER phase: 오른손 V사인 확인 후 왼손 OK사인 순차 인식.

        Step 1: 오른손 V사인 감지 → _seat_right_confirmed에 (wrist, arm_angle) 저장
        Step 2: 왼손 OK사인 감지 → seat_registered 후보 반환
        두 손이 동시에 보일 필요 없음. arm_angle은 21 landmark에서 직접 계산.
        """
        actor = ctx.active_player or ""

        right_hand: HandDet | None = None
        left_hand: HandDet | None = None
        for hand in perception.hands:
            if hand.gesture == "v_sign" and hand.handedness == "Right":
                right_hand = hand
            elif hand.gesture == "ok_sign" and hand.handedness == "Left":
                left_hand = hand

        # Step 1: 오른손 V사인 → 기억
        if right_hand is not None:
            r_angle = (
                right_hand.arm_angle
                if right_hand.arm_angle is not None
                else compute_arm_angle(right_hand.landmarks_21)
            )
            self._seat_right_confirmed[actor] = (right_hand.wrist_xy, r_angle)

        # Step 2: 왼손 OK사인 + 오른손 이미 확인됨 → 발화
        if left_hand is not None and actor in self._seat_right_confirmed:
            right_wrist, right_angle = self._seat_right_confirmed[actor]
            left_wrist = left_hand.wrist_xy
            left_angle = (
                left_hand.arm_angle
                if left_hand.arm_angle is not None
                else compute_arm_angle(left_hand.landmarks_21)
            )

            right_anchor = ArmAnchor(
                handedness="Right",
                wrist_xy=right_wrist,
                arm_angle=right_angle,
            )
            left_anchor = ArmAnchor(
                handedness="Left",
                wrist_xy=left_wrist,
                arm_angle=left_angle,
            )
            body_xy, posture = estimate_body_xy(right_wrist, right_angle, left_wrist, left_angle)
            seat_zone = SeatZone(
                right_arm=right_anchor,
                left_arm=left_anchor,
                body_xy=body_xy,
                posture=posture,
            )

            data_key = {
                "seat_zone": seat_zone.to_dict(),
                "actor_id": actor,
                "_key": (
                    round(left_wrist[0], 1),
                    round(left_wrist[1], 1),
                    actor,
                ),
            }
            return CommonEventType.SEAT_REGISTERED, data_key, 0.9

        return None, {}, 0.0

    def _build_seat_right_registered_candidate(
        self,
        ctx: FusionContext,
        perception: FramePerception,
    ) -> tuple[str | None, dict, float]:
        """SEAT_REGISTER phase 중간 이벤트: 오른손 V사인 1회만 발화.

        한 actor당 1회만 발화하도록 _seat_right_event_emitted로 가드.
        """
        actor = ctx.active_player or ""
        if actor in self._seat_right_event_emitted:
            return None, {}, 0.0

        for hand in perception.hands:
            if hand.gesture == "v_sign" and hand.handedness == "Right":
                data_key = {
                    "actor_id": actor,
                    "hand": "Right",
                    "_key": ("right", actor),
                }
                return CommonEventType.SEAT_RIGHT_REGISTERED, data_key, 0.9
        return None, {}, 0.0

    def _build_seat_hand_candidate(
        self,
        ctx: FusionContext,
        hand: HandDet,
    ) -> tuple[str | None, dict, float]:
        """SEAT_REGISTER_RIGHT/LEFT 단계에서 seat_hand_registered 후보 생성 (하위 호환)."""
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
