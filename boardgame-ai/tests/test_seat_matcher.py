"""seat_matcher 단위 테스트 — arm 방향 기반 매칭."""

import math

import pytest

from core.models import ArmAnchor, Player, SeatZone
from vision.attribution.seat_matcher import (
    MARGIN_THRESHOLD,
    match_player_by_arm,
    players_with_both_hands_tracked,
)


def _mk_player(pid, body_xy, right_wrist, right_angle, left_wrist, left_angle):
    sz = SeatZone(
        right_arm=ArmAnchor("Right", right_wrist, right_angle),
        left_arm=ArmAnchor("Left", left_wrist, left_angle),
        body_xy=body_xy,
        posture="stretched",
    )
    return Player(pid, f"name_{pid}", sz)


@pytest.fixture
def four_players():
    """4명의 플레이어가 사방에 앉음."""
    p_top = _mk_player("p_top", (0.5, -0.3), (0.55, 0.1), -math.pi / 2, (0.45, 0.1), -math.pi / 2)
    p_bot = _mk_player("p_bot", (0.5, 1.3), (0.45, 0.9), math.pi / 2, (0.55, 0.9), math.pi / 2)
    p_lft = _mk_player("p_lft", (-0.3, 0.5), (0.1, 0.45), math.pi, (0.1, 0.55), math.pi)
    p_rgt = _mk_player("p_rgt", (1.3, 0.5), (0.9, 0.55), 0.0, (0.9, 0.45), 0.0)
    return [p_top, p_bot, p_lft, p_rgt]


def test_match_top_player(four_players):
    pid, _, _ = match_player_by_arm("Right", (0.55, 0.15), -math.pi / 2 + 0.05, four_players)
    assert pid == "p_top"


def test_match_left_player(four_players):
    pid, _, _ = match_player_by_arm("Left", (0.1, 0.55), math.pi - 0.05, four_players)
    assert pid == "p_lft"


def test_match_excluded(four_players):
    """정답을 excluded에 넣으면 다른 사람이 폴백."""
    pid, _, _ = match_player_by_arm(
        "Right", (0.55, 0.15), -math.pi / 2, four_players, excluded_player_ids={"p_top"}
    )
    assert pid != "p_top"
    assert pid in {"p_bot", "p_lft", "p_rgt"}


def test_match_no_registered_returns_none():
    """등록자 없으면 None, margin은 inf."""
    pid, _, margin = match_player_by_arm("Right", (0.5, 0.5), 0.0, [])
    assert pid is None
    assert margin == float("inf")


def test_match_only_other_handedness(four_players):
    """모든 등록자가 같은 handedness anchor를 갖고 있으므로 항상 매칭."""
    pid, _, _ = match_player_by_arm("Left", (0.5, 0.5), 0.0, four_players)
    assert pid is not None  # 풀이 비지 않으면 항상 best 반환


# ── margin (best vs 2nd-best 점수 차) ────────────────────────────────────────


def test_margin_clear_best_is_large(four_players):
    """정답 좌석에 정확히 일치하면 margin이 충분히 큼."""
    _, _, margin = match_player_by_arm("Right", (0.55, 0.1), -math.pi / 2, four_players)
    # 정답(p_top)과 2등(p_bot/p_lft/p_rgt) 차이가 명확해야 한다.
    assert margin >= MARGIN_THRESHOLD


def test_margin_single_candidate_is_inf(four_players):
    """후보가 1명뿐(나머지 모두 excluded)이면 margin은 inf."""
    _, _, margin = match_player_by_arm(
        "Right",
        (0.55, 0.1),
        -math.pi / 2,
        four_players,
        excluded_player_ids={"p_bot", "p_lft", "p_rgt"},
    )
    assert margin == float("inf")


def test_margin_ambiguous_between_neighbors_is_small():
    """옆자리 두 사람의 anchor가 거의 같으면 margin이 작다 (Hold 트리거 케이스)."""
    # 거의 같은 위치/각도의 두 옆자리 플레이어 — 의도적 모호 시나리오.
    p_a = _mk_player("p_a", (0.5, -0.3), (0.50, 0.10), -math.pi / 2, (0.40, 0.10), -math.pi / 2)
    p_b = _mk_player("p_b", (0.52, -0.3), (0.52, 0.10), -math.pi / 2, (0.42, 0.10), -math.pi / 2)
    _, _, margin = match_player_by_arm("Right", (0.51, 0.12), -math.pi / 2, [p_a, p_b])
    # 두 옆자리가 거의 같으니 margin이 임계 미만이어야 한다.
    assert margin < MARGIN_THRESHOLD


# ── players_with_both_hands_tracked ──────────────────────────────────────────


class _FakeTrack:
    def __init__(self, hd, pid):
        self._hd = hd
        self._pid = pid

    @property
    def confirmed_handedness(self):
        return self._hd

    @property
    def confirmed_player_id(self):
        return self._pid


def test_both_hands_tracked():
    tracks = [
        _FakeTrack("Right", "p_top"),
        _FakeTrack("Left", "p_top"),
        _FakeTrack("Right", "p_bot"),
    ]
    assert players_with_both_hands_tracked(tracks) == {"p_top"}


def test_no_both_hands_tracked():
    tracks = [_FakeTrack("Right", "p_top"), _FakeTrack("Right", "p_bot")]
    assert players_with_both_hands_tracked(tracks) == set()


def test_ignore_unknown_pid():
    tracks = [_FakeTrack("Right", None), _FakeTrack("Left", None)]
    assert players_with_both_hands_tracked(tracks) == set()
