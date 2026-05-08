"""한밤의 늑대인간 게임 전용 Phase·역할·이벤트·입력 타입."""

from __future__ import annotations

from enum import StrEnum


class WerewolfRole(StrEnum):
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    SEER = "seer"                  # 예언자
    ROBBER = "robber"              # 도둑
    TROUBLEMAKER = "troublemaker"  # 말썽꾼
    DRUNK = "drunk"                # 술꾼
    INSOMNIAC = "insomniac"        # 불면증환자
    HUNTER = "hunter"              # 사냥꾼
    TANNER = "tanner"              # 무두장이
    DOPPELGANGER = "doppelganger"  # 도플갱어
    MINION = "minion"              # 하수인
    MASON = "mason"                # 프리메이슨


# 늑대 팀에 속하는 역할 집합
WEREWOLF_TEAM: frozenset[str] = frozenset({WerewolfRole.WEREWOLF.value})

# 밤에 행동 순서가 있는 역할 (스펙 §4 야간 순서)
NIGHT_ORDER: list[str] = [
    WerewolfRole.DOPPELGANGER.value,
    WerewolfRole.WEREWOLF.value,
    WerewolfRole.MINION.value,
    WerewolfRole.MASON.value,
    WerewolfRole.SEER.value,
    WerewolfRole.ROBBER.value,
    WerewolfRole.TROUBLEMAKER.value,
    WerewolfRole.DRUNK.value,
    WerewolfRole.INSOMNIAC.value,
]


class WerewolfPhase(StrEnum):
    NIGHT_START = "night_start"
    NIGHT_DOPPELGANGER = "night_doppelganger"
    NIGHT_WEREWOLF = "night_werewolf"
    NIGHT_MINION = "night_minion"
    NIGHT_MASON = "night_mason"
    NIGHT_SEER = "night_seer"
    NIGHT_ROBBER = "night_robber"
    NIGHT_TROUBLEMAKER = "night_troublemaker"
    NIGHT_DRUNK = "night_drunk"
    NIGHT_INSOMNIAC = "night_insomniac"
    DAY_DISCUSSION = "day_discussion"    # 300초 타이머
    VOTE_COUNTDOWN = "vote_countdown"
    VOTE = "vote"
    RESULT = "result"


class WerewolfEventType(StrEnum):
    """비전팀이 발생시키는 늑대인간 전용 이벤트.

    data 스키마:
        CARD_PEEK:  {"card_owner_id": str|None, "card_index": int}
        CARD_SWAP:  {"from_id": str, "to_id": str}
        VOTE_POINT: {"target_id": str}
    """

    CARD_PEEK = "werewolf_card_peek"    # 카드 들여다보기 감지
    CARD_SWAP = "werewolf_card_swap"    # 카드 교환 제스처 감지
    VOTE_POINT = "werewolf_vote_point"  # 투표 포인팅 감지


class WerewolfInputType(StrEnum):
    """UI → FSM 늑대인간 전용 입력.

    data 스키마:
        VOTE_PLAYER: {"target_id": str}
    """

    ADD_30_SEC = "add_30_sec"
    START_NOW = "start_now"
    VOTE_PLAYER = "werewolf_vote_player"


# 야간 페이즈 순서 (NIGHT_ORDER 역할 문자열과 대응)
NIGHT_PHASES: list[WerewolfPhase] = [
    WerewolfPhase.NIGHT_DOPPELGANGER,
    WerewolfPhase.NIGHT_WEREWOLF,
    WerewolfPhase.NIGHT_MINION,
    WerewolfPhase.NIGHT_MASON,
    WerewolfPhase.NIGHT_SEER,
    WerewolfPhase.NIGHT_ROBBER,
    WerewolfPhase.NIGHT_TROUBLEMAKER,
    WerewolfPhase.NIGHT_DRUNK,
    WerewolfPhase.NIGHT_INSOMNIAC,
]

# 야간 페이즈 → 해당 역할 매핑
PHASE_TO_ROLE: dict[WerewolfPhase, WerewolfRole] = {
    WerewolfPhase.NIGHT_DOPPELGANGER: WerewolfRole.DOPPELGANGER,
    WerewolfPhase.NIGHT_WEREWOLF: WerewolfRole.WEREWOLF,
    WerewolfPhase.NIGHT_MINION: WerewolfRole.MINION,
    WerewolfPhase.NIGHT_MASON: WerewolfRole.MASON,
    WerewolfPhase.NIGHT_SEER: WerewolfRole.SEER,
    WerewolfPhase.NIGHT_ROBBER: WerewolfRole.ROBBER,
    WerewolfPhase.NIGHT_TROUBLEMAKER: WerewolfRole.TROUBLEMAKER,
    WerewolfPhase.NIGHT_DRUNK: WerewolfRole.DRUNK,
    WerewolfPhase.NIGHT_INSOMNIAC: WerewolfRole.INSOMNIAC,
}
