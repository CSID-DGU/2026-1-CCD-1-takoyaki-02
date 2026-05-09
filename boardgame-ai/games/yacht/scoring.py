"""요트다이스 점수 계산."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum


class YachtCategory(StrEnum):
    ONES = "ones"
    TWOS = "twos"
    THREES = "threes"
    FOURS = "fours"
    FIVES = "fives"
    SIXES = "sixes"
    CHOICE = "choice"
    FOUR_OF_A_KIND = "four_of_a_kind"
    FULL_HOUSE = "full_house"
    SMALL_STRAIGHT = "small_straight"
    LARGE_STRAIGHT = "large_straight"
    YACHT = "yacht"


UPPER_CATEGORIES: tuple[YachtCategory, ...] = (
    YachtCategory.ONES,
    YachtCategory.TWOS,
    YachtCategory.THREES,
    YachtCategory.FOURS,
    YachtCategory.FIVES,
    YachtCategory.SIXES,
)

ALL_CATEGORIES: tuple[YachtCategory, ...] = (
    *UPPER_CATEGORIES,
    YachtCategory.CHOICE,
    YachtCategory.FOUR_OF_A_KIND,
    YachtCategory.FULL_HOUSE,
    YachtCategory.SMALL_STRAIGHT,
    YachtCategory.LARGE_STRAIGHT,
    YachtCategory.YACHT,
)

UPPER_BONUS_THRESHOLD = 63
UPPER_BONUS_SCORE = 35


def normalize_dice(dice_values: list[int | None] | tuple[int | None, ...]) -> list[int]:
    """5개의 확정 주사위 값을 검증하고 int 리스트로 반환한다."""
    values = list(dice_values)
    if len(values) != 5:
        raise ValueError("요트다이스 점수 계산에는 주사위 5개가 필요합니다.")
    if any(v is None for v in values):
        raise ValueError("읽히지 않은 주사위 값이 있어 점수를 계산할 수 없습니다.")
    dice = [int(v) for v in values if v is not None]
    if any(v < 1 or v > 6 for v in dice):
        raise ValueError("주사위 값은 1부터 6 사이여야 합니다.")
    return dice


def calculate_score(category: str, dice_values: list[int | None] | tuple[int | None, ...]) -> int:
    """카테고리 하나에 대한 점수를 계산한다."""
    dice = normalize_dice(dice_values)
    cat = YachtCategory(category)
    counts = Counter(dice)

    if cat in UPPER_CATEGORIES:
        face = UPPER_CATEGORIES.index(cat) + 1
        return sum(v for v in dice if v == face)
    if cat == YachtCategory.CHOICE:
        return sum(dice)
    if cat == YachtCategory.FOUR_OF_A_KIND:
        return sum(dice) if max(counts.values()) >= 4 else 0
    if cat == YachtCategory.FULL_HOUSE:
        return sum(dice) if sorted(counts.values()) == [2, 3] else 0
    if cat == YachtCategory.SMALL_STRAIGHT:
        unique = set(dice)
        straights = ({1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6})
        return 15 if any(straight <= unique for straight in straights) else 0
    if cat == YachtCategory.LARGE_STRAIGHT:
        return 30 if set(dice) in ({1, 2, 3, 4, 5}, {2, 3, 4, 5, 6}) else 0
    if cat == YachtCategory.YACHT:
        return 50 if len(counts) == 1 else 0

    raise ValueError(f"지원하지 않는 점수 카테고리입니다: {category}")


def upper_subtotal(scores: dict[str, int]) -> int:
    return sum(scores.get(cat.value, 0) for cat in UPPER_CATEGORIES)


def total_score(scores: dict[str, int]) -> int:
    bonus = UPPER_BONUS_SCORE if upper_subtotal(scores) >= UPPER_BONUS_THRESHOLD else 0
    return sum(scores.values()) + bonus
