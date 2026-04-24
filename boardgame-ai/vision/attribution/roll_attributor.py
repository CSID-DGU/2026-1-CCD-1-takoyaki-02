"""굴린 플레이어 결정 (RollAttributor).

상태머신: IDLE → GRAB_SEEN → ROLL_TRAY_LIFTED → RELEASE_SEEN → DICE_MOVING → DICE_STABLE

핵심 설계 원칙:
- GRAB_SEEN 시점에 SeatMatcher로 candidate_actor_id 저장
- DICE_STABLE 도달 시 roll_actor_id 확정
- Fallback: grab/release 인식 실패 시 최근 K프레임 동안
  roll_tray에 가장 오래 겹쳤던 hand의 player_id
- "남 차례에 트레이 건네주기" 방어: GRAB_SEEN→DICE_STABLE 사이클을
  한 번만 완결, 중간에 다른 사람이 잠깐 트레이 잡아도 actor 유지
"""

from __future__ import annotations

from collections import Counter, deque
from enum import Enum, auto

from vision.schemas import BBox, FramePerception, HandDet


class RollState(Enum):
    IDLE = auto()
    GRAB_SEEN = auto()
    ROLL_TRAY_LIFTED = auto()
    RELEASE_SEEN = auto()
    DICE_MOVING = auto()
    DICE_STABLE = auto()


class RollAttributor:
    """
    Parameters
    ----------
    roll_lift_threshold         : roll_tray 중심 이동 속도 임계값 (정규화)
    grab_fallback_window_frames : fallback용 최근 K프레임
    stabilization_frames        : dice stable 확정 프레임 수
    motion_threshold            : dice motion_score 임계값
    """

    def __init__(
        self,
        roll_lift_threshold: float = 0.01,
        grab_fallback_window_frames: int = 60,
        stabilization_frames: int = 30,
        motion_threshold: float = 0.002,
    ) -> None:
        self._lift_threshold = roll_lift_threshold
        self._fallback_window = grab_fallback_window_frames
        self._stab_frames = stabilization_frames
        self._motion_threshold = motion_threshold

        self._state = RollState.IDLE
        self._candidate_actor: str | None = None
        self._confirmed_actor: str | None = None

        # roll_tray 이전 중심 (lift 감지용)
        self._prev_roll_tray_center: tuple[float, float] | None = None

        # fallback: deque[(player_id | None)]
        self._fallback_buf: deque[str | None] = deque(maxlen=grab_fallback_window_frames)

        # 직전 프레임 roll_tray bbox (lift 계산용)
        self._prev_roll_tray: BBox | None = None

        # IDLE fallback 쿨다운: 한번 finalize 후 최소 N프레임 대기 (무한루프 방지)
        self._idle_cooldown: int = 0
        self._idle_cooldown_frames: int = stabilization_frames * 2

    # ── public ───────────────────────────────────────────────────────────────

    def update(self, perception: FramePerception) -> str | None:
        """
        매 프레임 호출. roll_actor_id 확정 시 반환, 아직이면 None.
        DICE_STABLE에 도달하면 actor를 반환하고 상태를 IDLE로 리셋.
        """
        roll_tray = perception.roll_tray

        # fallback 버퍼 갱신 (roll_tray 근처 손 player_id)
        nearest = self._nearest_player_to_roll_tray(perception)
        self._fallback_buf.append(nearest)

        # roll_tray lift 계산
        lift_speed = self._compute_lift_speed(roll_tray)
        self._prev_roll_tray = roll_tray

        actor: str | None = None

        if self._state == RollState.IDLE:
            if self._idle_cooldown > 0:
                self._idle_cooldown -= 1
            # roll_tray가 충분히 움직이면 grab 없이도 ROLL_TRAY_LIFTED로 바로 전이
            elif lift_speed > self._lift_threshold and roll_tray is not None:
                self._state = RollState.ROLL_TRAY_LIFTED
            # fallback: grab 인식 없이 dice가 바로 stable이면 fallback으로 확정
            # 단, 쿨다운 중에는 재발화 금지 (정적 화면에서 무한루프 방지)
            elif self._all_dice_stable(perception) and perception.dice:
                actor = self._finalize(perception)
            else:
                actor = self._handle_idle(perception, roll_tray)

        elif self._state == RollState.GRAB_SEEN:
            actor = self._handle_grab_seen(perception, roll_tray, lift_speed)

        elif self._state == RollState.ROLL_TRAY_LIFTED:
            actor = self._handle_lifted(perception, roll_tray)

        elif self._state == RollState.RELEASE_SEEN:
            actor = self._handle_release_seen(perception)

        elif self._state == RollState.DICE_MOVING:
            actor = self._handle_dice_moving(perception)

        elif self._state == RollState.DICE_STABLE:
            # 이미 이전 프레임에서 확정됐으면 즉시 리셋
            actor = self._confirmed_actor
            self._reset()

        return actor

    @property
    def state(self) -> RollState:
        return self._state

    # ── state handlers ────────────────────────────────────────────────────────

    def _handle_idle(
        self, perception: FramePerception, roll_tray: BBox | None
    ) -> str | None:
        grab_hand = self._find_grab_on_roll_tray(perception, roll_tray)
        if grab_hand is not None:
            self._candidate_actor = grab_hand.player_id
            self._state = RollState.GRAB_SEEN
        return None

    def _handle_grab_seen(
        self,
        perception: FramePerception,
        roll_tray: BBox | None,
        lift_speed: float,
    ) -> str | None:
        # grab 유지 확인
        grab_hand = self._find_grab_on_roll_tray(perception, roll_tray)

        if lift_speed > self._lift_threshold and grab_hand is not None:
            # candidate 재확인 (grab 유지 중인 손)
            if grab_hand.player_id is not None:
                self._candidate_actor = grab_hand.player_id
            self._state = RollState.ROLL_TRAY_LIFTED
        elif grab_hand is None:
            # grab 없어짐 → release로 간주
            self._state = RollState.RELEASE_SEEN
        return None

    def _handle_lifted(
        self, perception: FramePerception, roll_tray: BBox | None
    ) -> str | None:
        # release 감지: grab→non-grab 전환
        release_hand = self._find_release_near_tray(perception, roll_tray)
        if release_hand is not None:
            if release_hand.player_id is not None:
                self._candidate_actor = release_hand.player_id
            self._state = RollState.RELEASE_SEEN
        return None

    def _handle_release_seen(self, perception: FramePerception) -> str | None:
        # dice가 움직이기 시작하면 DICE_MOVING
        if self._any_dice_moving(perception):
            self._state = RollState.DICE_MOVING
        elif not self._any_dice_moving(perception) and self._all_dice_stable(perception):
            # 조용히 놓은 경우 (별 움직임 없이 바로 stable)
            return self._finalize(perception)
        return None

    def _handle_dice_moving(self, perception: FramePerception) -> str | None:
        if self._all_dice_stable(perception):
            return self._finalize(perception)
        return None

    # ── helpers ───────────────────────────────────────────────────────────────

    def _finalize(self, perception: FramePerception) -> str | None:
        # candidate 없으면 fallback
        actor = self._candidate_actor or self._fallback_actor()
        self._confirmed_actor = actor
        self._state = RollState.DICE_STABLE
        return actor

    def _reset(self) -> None:
        self._state = RollState.IDLE
        self._candidate_actor = None
        self._confirmed_actor = None
        self._prev_roll_tray = None
        self._idle_cooldown = self._idle_cooldown_frames

    def _compute_lift_speed(self, roll_tray: BBox | None) -> float:
        if roll_tray is None or self._prev_roll_tray is None:
            return 0.0
        px, py = self._prev_roll_tray.center()
        cx, cy = roll_tray.center()
        return ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5

    def _find_grab_on_roll_tray(
        self, perception: FramePerception, roll_tray: BBox | None
    ) -> HandDet | None:
        """roll_tray 위에서 grab 제스처인 손 반환."""
        if roll_tray is None:
            return None
        for hand in perception.hands:
            if hand.gesture == "grab":
                wx, wy = hand.wrist_xy
                if roll_tray.contains_point(wx, wy):
                    return hand
        return None

    def _find_release_near_tray(
        self, perception: FramePerception, roll_tray: BBox | None
    ) -> HandDet | None:
        """release 제스처이면서 tray_inner 또는 roll_tray 근처인 손."""
        target = perception.tray_inner or roll_tray
        if target is None:
            return None
        for hand in perception.hands:
            if hand.gesture == "release":
                wx, wy = hand.wrist_xy
                # 약간 확장된 영역 허용 (bbox 패딩 10%)
                pad = 0.1
                if (
                    target.x1 - pad <= wx <= target.x2 + pad
                    and target.y1 - pad <= wy <= target.y2 + pad
                ):
                    return hand
        return None

    def _any_dice_moving(self, perception: FramePerception) -> bool:
        # motion_score 기준 + 최소 2개 이상이 움직여야 굴림으로 판정
        # (손에 가려졌다 복귀할 때 일시적 1개 흔들림은 무시)
        moving = [d for d in perception.dice if d.motion_score > self._motion_threshold]
        return len(moving) >= max(1, len(perception.dice) // 2)

    def _all_dice_stable(self, perception: FramePerception) -> bool:
        return perception.dice_all_stable(self._stab_frames)

    def _nearest_player_to_roll_tray(
        self, perception: FramePerception
    ) -> str | None:
        if perception.roll_tray is None:
            return None
        cx, cy = perception.roll_tray.center()
        best_pid: str | None = None
        best_dist = float("inf")
        for hand in perception.hands:
            if hand.player_id is None:
                continue
            wx, wy = hand.wrist_xy
            d = ((wx - cx) ** 2 + (wy - cy) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_pid = hand.player_id
        return best_pid

    def _fallback_actor(self) -> str | None:
        """최근 K프레임에서 roll_tray에 가장 오래 있었던 player_id."""
        counts = Counter(pid for pid in self._fallback_buf if pid is not None)
        if not counts:
            return None
        return counts.most_common(1)[0][0]
