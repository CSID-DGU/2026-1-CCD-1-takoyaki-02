"""HandTrack player_id 접근자 단위 테스트.

confirmed_player_id는 초기 오매칭 굳음 방지를 위해 "2표+마진" 게이트를 건다.
best_effort_player_id는 그 게이트 미달이어도 한 번이라도 매칭됐으면 최빈값을
돌려, 옆사람의 짧은 굴림 트랙도 actor로 잡혀 차례 위반이 감지되게 한다.
"""

from __future__ import annotations

from vision.tracking.hand_tracker import HandTrack


def _track() -> HandTrack:
    return HandTrack(track_id=1, wrist_xy=(0.5, 0.5), arm_angle=0.0)


def test_confirmed_requires_votes_and_margin() -> None:
    t = _track()
    t.player_id_buf.append("p_2")  # 1표 — 마진 게이트 미달
    assert t.confirmed_player_id is None


def test_best_effort_resolves_with_single_vote() -> None:
    """1표만 있어도 best_effort는 그 값을 돌린다 (None 방지)."""
    t = _track()
    t.player_id_buf.append("p_2")
    assert t.best_effort_player_id == "p_2"


def test_best_effort_none_when_never_matched() -> None:
    """매칭 이력이 전혀 없으면(빈 버퍼/전부 None) best_effort도 None."""
    t = _track()
    assert t.best_effort_player_id is None
    t.player_id_buf.append(None)
    assert t.best_effort_player_id is None


def test_best_effort_picks_plurality() -> None:
    t = _track()
    for pid in ["p_2", "p_2", "p_3", None]:
        t.player_id_buf.append(pid)
    assert t.best_effort_player_id == "p_2"


def test_pipeline_assignment_prefers_confirmed_then_best_effort() -> None:
    """파이프라인 할당 규칙: confirmed 우선, 미달이면 best_effort 폴백."""
    t = _track()
    t.player_id_buf.append("p_2")  # confirmed=None, best_effort=p_2
    assigned = t.confirmed_player_id or t.best_effort_player_id
    assert assigned == "p_2"

    # 2표+마진 충족 시 confirmed가 그대로 쓰임.
    t.player_id_buf.append("p_2")
    assert t.confirmed_player_id == "p_2"
