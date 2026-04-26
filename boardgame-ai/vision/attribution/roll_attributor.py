"""굴린 플레이어 결정 (RollAttributor) — 손 점유 기반.

상태머신:
  WAITING
   │  손(wrist 또는 21 landmark 중 하나)이 tray bbox 안에 들어옴 → HAND_IN_TRAY
   │  진입 시점에 snapshot 저장 (tray_inner 밖 dice만, 즉 굴림 대상)
   ↓
  HAND_IN_TRAY (점유 중)
   │  매 프레임 nearest player_id 누적
   │  종료 조건: 모든 손이 tray 밖 + dice 5개 모두 인식 + 모두 stable + 변화 점수 ≥ 임계
   │    → ROLL_CONFIRMED 발화 → WAITING
   │  손 빠졌는데 변화 없음 → 그냥 WAITING (손만 댄 케이스, 발화 없음)
   ↓
  WAITING

킵존 인지:
  - snapshot에 들어가는 건 tray_inner 밖 dice (= 다시 굴리는 dice)
  - 비교도 tray_inner 밖 dice만
  - ROLL_CONFIRMED data에는 전체 dice_values 포함, keep_mask에 tray_inner 안 dice = True
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from enum import Enum, auto

from vision.schemas import BBox, DiceState, FramePerception, HandDet


class RollState(Enum):
    WAITING = auto()
    HAND_IN_TRAY = auto()


@dataclass
class _DiceSnapshot:
    """점유 시작 시점의 굴림 대상 dice 스냅샷."""

    items: dict[int, tuple[tuple[float, float], int | None]]
    # track_id → (center, pip_count)


class RollAttributor:
    """
    Parameters
    ----------
    stabilization_frames    : dice 안정 판정 임계 (이 만큼 stable_frames 도달해야 안정)
    grab_fallback_window_frames : nearest player_id 누적 윈도우
    expected_dice_count     : 굴림 후 모두 보여야 할 dice 총 개수 (요트 5개)
    change_score_threshold  : snapshot 대비 변화 비율 임계 (이상이면 굴림으로 인정)
    center_shift_ratio      : center 이동을 "변화"로 판정하는 박스 변길이 대비 비율
    tray_pad                : 손이 tray 진입했다고 볼 패딩 (정규화)
    """

    def __init__(
        self,
        stabilization_frames: int = 30,
        grab_fallback_window_frames: int = 60,
        expected_dice_count: int = 5,
        change_score_threshold: float = 0.4,
        center_shift_ratio: float = 0.2,
        tray_pad: float = 0.02,
        enter_debounce_frames: int = 3,
        exit_debounce_frames: int = 3,
        # 호환용 — 더 이상 사용하지 않지만 기존 호출자 깨지지 않도록 유지
        roll_lift_threshold: float = 0.02,
        motion_threshold: float = 0.002,
    ) -> None:
        self._stab_frames = stabilization_frames
        self._fallback_window = grab_fallback_window_frames
        self._expected_dice = expected_dice_count
        self._change_threshold = change_score_threshold
        self._center_shift_ratio = center_shift_ratio
        self._tray_pad = tray_pad
        self._enter_debounce = enter_debounce_frames
        self._exit_debounce = exit_debounce_frames
        # 미사용 (인터페이스 호환만 유지)
        _ = roll_lift_threshold
        _ = motion_threshold

        self._state = RollState.WAITING
        self._candidate_actor: str | None = None
        self._snapshot: _DiceSnapshot | None = None
        # WAITING 동안 마지막으로 확보한 안정 snapshot. 손이 dice를 가린 후의 흐트러진
        # 좌표가 아니라, 손 들어가기 직전 진짜 안정 상태를 비교 기준으로 사용한다.
        self._last_stable_snapshot: _DiceSnapshot | None = None
        # 직전 update()에서 굴림이 finalize됐는지 (actor가 None이어도 True 가능).
        # pipeline이 perception.roll_just_confirmed 게이트 세팅에 사용.
        self._just_finalized: bool = False

        # 디바운스 카운터: 손 안에 있는 연속 프레임, 밖에 있는 연속 프레임
        self._in_streak: int = 0
        self._out_streak: int = 0

        # nearest player 누적 — fallback actor 산정용
        self._fallback_buf: deque[str | None] = deque(maxlen=grab_fallback_window_frames)

    # ── public ───────────────────────────────────────────────────────────────

    def update(self, perception: FramePerception) -> str | None:
        """매 프레임 호출. ROLL_CONFIRMED 발화 시 actor 반환, 아니면 None."""
        self._just_finalized = False  # 매 프레임 리셋 — 발화 분기에서만 True

        # nearest player_id 누적 (tray 또는 roll_tray 근처)
        nearest = self._nearest_player_to_tray(perception)
        self._fallback_buf.append(nearest)

        # 디바운스 카운터 갱신
        if self._is_any_hand_in_tray(perception):
            self._in_streak += 1
            self._out_streak = 0
        else:
            self._out_streak += 1
            self._in_streak = 0

        if self._state == RollState.WAITING:
            return self._step_waiting(perception)
        # HAND_IN_TRAY
        return self._step_hand_in_tray(perception)

    @property
    def state(self) -> RollState:
        return self._state

    @property
    def just_finalized(self) -> bool:
        """직전 update()에서 굴림이 finalize 됐는지. actor가 None이어도 True 가능."""
        return self._just_finalized

    # ── 상태별 step ───────────────────────────────────────────────────────────

    def _step_waiting(self, perception: FramePerception) -> str | None:
        if perception.tray is None:
            return None
        # 손이 안 잡힌 동안에는 마지막 stable snapshot 갱신.
        # 굴림 대상 dice 모두 stable이면 그 시점을 비교 기준으로 들고 있는다.
        if self._out_streak > 0:
            target = self._dice_outside_keep(perception)
            if target and all(d.stable_frames >= self._stab_frames for d in target):
                if self._last_stable_snapshot is None or len(target) != len(
                    self._last_stable_snapshot.items
                ):
                    print(
                        f"[roll] last_stable_snapshot 갱신 "
                        f"size={len(target)} kept={self._n_kept(perception)}"
                    )
                self._last_stable_snapshot = _take_snapshot(target)
        # 진입 디바운스 — 연속 N프레임 안에 있어야 진짜 진입으로 인정
        if self._in_streak >= self._enter_debounce:
            self._enter_hand_in_tray(perception)
        return None

    def _step_hand_in_tray(self, perception: FramePerception) -> str | None:
        # 점유 중에는 candidate_actor 강화 (들고 있는 동안 가장 가까운 player)
        nearest = self._nearest_player_to_tray(perception)
        if nearest is not None:
            self._candidate_actor = nearest

        # 진출 디바운스 — 연속 N프레임 밖이어야 진짜 빠진 걸로 인정
        if self._out_streak < self._exit_debounce:
            return None

        # 손이 빠짐 — 굴림 종료 조건 체크
        target_dice = self._dice_outside_keep(perception)
        n_kept = self._n_kept(perception)
        need = self._expected_dice - n_kept
        # 1) 모든 굴림 대상 dice가 보여야 함 (개수 일치)
        if len(target_dice) < need:
            print(
                f"[roll] hand_out: dice 부족 — got={len(target_dice)} need={need} "
                f"kept={n_kept} (state 유지)"
            )
            return None
        # 2) 모두 stable
        unstable = [
            (d.track_id, d.stable_frames)
            for d in target_dice
            if d.stable_frames < self._stab_frames
        ]
        if unstable:
            print(f"[roll] hand_out: dice 불안정 — {unstable} (state 유지)")
            return None
        # 3) snapshot 대비 변화 점수
        if self._snapshot is None:
            print("[roll] hand_out: snapshot 없음 → WAITING 복귀 (발화 없음)")
            self._reset_to_waiting()
            return None
        score = _compute_change_score(self._snapshot, target_dice, self._center_shift_ratio)
        print(
            f"[roll] hand_out: score={score:.2f} threshold={self._change_threshold:.2f} "
            f"snap_size={len(self._snapshot.items)} cur_size={len(target_dice)}"
        )
        if score >= self._change_threshold:
            actor = self._candidate_actor or self._fallback_actor()
            self._just_finalized = True
            print(f"[roll] ROLL_CONFIRMED actor={actor}")
            self._reset_to_waiting()
            return actor
        # 변화 없음 — 손만 댄 케이스
        print("[roll] 변화 부족 → WAITING (손만 댐)")
        self._reset_to_waiting()
        return None

    def _enter_hand_in_tray(self, perception: FramePerception) -> None:
        self._state = RollState.HAND_IN_TRAY
        # 손이 들어온 직후의 흐트러진 dice 좌표 대신,
        # 손 들어가기 직전 마지막 stable snapshot을 비교 기준으로 사용.
        if self._last_stable_snapshot is not None:
            self._snapshot = self._last_stable_snapshot
        else:
            target = self._dice_outside_keep(perception)
            self._snapshot = _take_snapshot(target)
        # 점유 시점 nearest를 candidate로 우선 채택
        nearest = self._nearest_player_to_tray(perception)
        if nearest is not None:
            self._candidate_actor = nearest
        n_kept = self._n_kept(perception)
        n_outside = len(self._dice_outside_keep(perception))
        print(
            f"[roll] WAITING → HAND_IN_TRAY "
            f"snap_size={len(self._snapshot.items) if self._snapshot else 0} "
            f"dice_total={len(perception.dice)} kept={n_kept} outside={n_outside} "
            f"tray_inner={'Y' if perception.tray_inner else 'N'} "
            f"actor={self._candidate_actor}"
        )

    def _reset_to_waiting(self) -> None:
        self._state = RollState.WAITING
        self._snapshot = None
        self._candidate_actor = None

    # ── 헬퍼 ─────────────────────────────────────────────────────────────────

    def _is_any_hand_in_tray(self, perception: FramePerception) -> bool:
        """어떤 손의 wrist 또는 손가락 끝(5개) 중 하나라도 tray 패딩 영역 안에 있는가.

        21 landmark 전부 검사하면 손이 멀리 있어도 한 점이 안에 떨어져 false positive.
        wrist + 5개 fingertip만 본다.
        """
        tray = perception.tray
        if tray is None or not perception.hands:
            return False
        x1, y1 = tray.x1 - self._tray_pad, tray.y1 - self._tray_pad
        x2, y2 = tray.x2 + self._tray_pad, tray.y2 + self._tray_pad
        # MediaPipe fingertip 인덱스: thumb=4, index=8, middle=12, ring=16, pinky=20
        fingertip_indices = (4, 8, 12, 16, 20)
        for hand in perception.hands:
            wx, wy = hand.wrist_xy
            if x1 <= wx <= x2 and y1 <= wy <= y2:
                return True
            for idx in fingertip_indices:
                if idx >= len(hand.landmarks_21):
                    continue
                lx, ly = hand.landmarks_21[idx]
                if x1 <= lx <= x2 and y1 <= ly <= y2:
                    return True
        return False

    def _dice_outside_keep(self, perception: FramePerception) -> list[DiceState]:
        """굴림 대상 dice — 현재는 tray_inner를 무시하고 모든 dice를 굴림 대상으로 본다.

        tray_inner가 사실상 tray 전체를 덮어 dice가 모두 kept로 분류되던 문제를 회피.
        킵존 ROI는 추후 게임 약속(예: tray 우측 N%)으로 별도 정의 예정.
        """
        return list(perception.dice)

    def _n_kept(self, perception: FramePerception) -> int:
        return 0

    def _nearest_player_to_tray(self, perception: FramePerception) -> str | None:
        """tray 또는 roll_tray 중심에 가장 가까운 player_id 보유 손."""
        ref = perception.tray or perception.roll_tray
        if ref is None:
            return None
        cx, cy = ref.center()
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
        counts = Counter(pid for pid in self._fallback_buf if pid is not None)
        if not counts:
            return None
        return counts.most_common(1)[0][0]


# ── 모듈 헬퍼 ────────────────────────────────────────────────────────────────


def _take_snapshot(dice: list[DiceState]) -> _DiceSnapshot:
    return _DiceSnapshot(items={d.track_id: (d.center, d.pip_count) for d in dice})


def _compute_change_score(
    snapshot: _DiceSnapshot,
    current: list[DiceState],
    center_shift_ratio: float,
) -> float:
    """snapshot 대비 변화한 dice 비율 (0.0~1.0).

    각 dice가 다음 중 하나라도 만족하면 changed:
      - track_id가 snapshot에 없음 (가림 후 새 ID 부여 = 큰 이동)
      - center 이동 > min_size * center_shift_ratio
      - pip_count 바뀜
    snapshot의 dice 개수와 현재 개수가 다르면 점수 1.0 (확실히 변함).
    """
    if not current:
        return 0.0
    # snapshot이 비어있으면 (점유 시작 시 dice 미감지) 어떤 변화든 인정
    if not snapshot.items:
        return 1.0
    if len(snapshot.items) != len(current):
        return 1.0

    changed = 0
    for d in current:
        prev = snapshot.items.get(d.track_id)
        if prev is None:
            changed += 1
            continue
        prev_center, prev_pip = prev
        size = min(d.bbox.w, d.bbox.h)
        threshold = size * center_shift_ratio
        dx = d.center[0] - prev_center[0]
        dy = d.center[1] - prev_center[1]
        moved = (dx * dx + dy * dy) ** 0.5 > threshold
        # pip 변화 — 둘 다 값이 있고 다르거나, None에서 값이 새로 잡힌 경우
        pip_changed = False
        if d.pip_count is not None and prev_pip is not None:
            pip_changed = d.pip_count != prev_pip
        elif d.pip_count is not None and prev_pip is None:
            # 점유 시점엔 pip 못 잡았다가 굴림 후 새로 잡힌 케이스
            pip_changed = True
        if moved or pip_changed:
            changed += 1
    return changed / len(current)


# ── 미사용 export 호환 (기존 import 깨지지 않도록) ────────────────────────────
__all__ = ["BBox", "HandDet", "RollAttributor", "RollState"]
