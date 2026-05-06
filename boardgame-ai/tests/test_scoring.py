import pytest

from games.yacht.scoring import calculate_score, total_score


def test_upper_and_choice_scores():
    dice = [1, 1, 3, 5, 6]
    assert calculate_score("ones", dice) == 2
    assert calculate_score("threes", dice) == 3
    assert calculate_score("choice", dice) == 16


def test_pattern_scores():
    assert calculate_score("four_of_a_kind", [6, 6, 6, 6, 2]) == 26
    assert calculate_score("full_house", [2, 2, 3, 3, 3]) == 13
    assert calculate_score("small_straight", [1, 2, 3, 4, 6]) == 15
    assert calculate_score("large_straight", [2, 3, 4, 5, 6]) == 30
    assert calculate_score("yacht", [4, 4, 4, 4, 4]) == 50


def test_zero_scores_for_unmatched_patterns():
    assert calculate_score("four_of_a_kind", [1, 1, 1, 2, 3]) == 0
    assert calculate_score("full_house", [2, 2, 2, 2, 3]) == 0
    assert calculate_score("large_straight", [1, 2, 3, 4, 4]) == 0


def test_total_score_includes_upper_bonus():
    scores = {
        "ones": 3,
        "twos": 6,
        "threes": 9,
        "fours": 12,
        "fives": 15,
        "sixes": 18,
    }
    assert total_score(scores) == 98


def test_invalid_dice_rejected():
    with pytest.raises(ValueError):
        calculate_score("choice", [1, 2, 3, 4, None])
