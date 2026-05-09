"""요트다이스 게임 FSM."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from core.audio import AudioPriority, TTSRequest
from core.constants import AgentRole, MsgType
from core.envelope import WSMessage
from core.events import FusionContext, GameEvent
from core.models import Player
from games.base_fsm import BaseFSM
from games.yacht.scoring import calculate_score
from games.yacht.state import YachtEventType, YachtGameState, YachtInputType, YachtPhase


class YachtFSM(BaseFSM):
    def __init__(
        self,
        players: list[Player | str | dict[str, Any]],
        broadcast: Callable[[WSMessage], Awaitable[None]] | None = None,
    ) -> None:
        self.state = YachtGameState.new(players)
        self._broadcast = broadcast

    def start(self) -> list[WSMessage]:
        self.state.phase = YachtPhase.AWAITING_ROLL.value
        self.state.state_version += 1
        self.state.last_message = f"{self.state.current_player.playername}님, 주사위를 굴려주세요."
        return [
            self._make_state_update(),
            WSMessage.make_fusion_context(self.get_fusion_context(), self.state.state_version),
            self._make_tts(self.state.last_message),
        ]

    def handle_event(self, event: GameEvent) -> list[WSMessage]:
        if event.event_type == YachtEventType.ROLL_CONFIRMED.value:
            return self._handle_roll_confirmed(event)
        if event.event_type == YachtEventType.ROLL_UNREADABLE.value:
            return self._handle_roll_unreadable(event)
        if event.event_type == YachtEventType.DICE_ESCAPED.value:
            return self._warn_and_keep_roll_phase("주사위가 트레이 밖으로 나갔습니다. 다시 굴려주세요.")
        if event.event_type in (
            YachtEventType.RULE_VIOLATION.value,
            YachtEventType.RULE_VIOLATION_LOWER.value,
        ):
            return self._warn_and_keep_roll_phase(
                f"지금은 {self.state.current_player.playername}님 차례입니다.",
                priority=AudioPriority.CRITICAL,
            )
        return []

    def handle_input(
        self,
        input_type: str,
        data: dict,
        player_id: str | None = None,
    ) -> list[WSMessage]:
        if input_type == YachtInputType.DICE_KEEP_SELECTED.value:
            return self._handle_keep_selected(data)
        if input_type == YachtInputType.DICE_REROLL_REQUESTED.value:
            return self._handle_reroll_requested(data)
        if input_type == YachtInputType.SCORE_CATEGORY_SELECTED.value:
            return self._handle_score_category(data, player_id)
        if input_type == YachtInputType.RESOLVE_UNREADABLE_ROLL.value:
            return self._handle_unreadable_resolution(data)
        return []

    def get_fusion_context(self) -> FusionContext:
        phase = YachtPhase(self.state.phase)
        active_player = (
            None if phase == YachtPhase.GAME_END else self.state.current_player.player_id
        )
        expected_events: list[str] = []
        reject_events: list[str] = []

        if phase == YachtPhase.AWAITING_ROLL:
            expected_events = [
                YachtEventType.ROLL_CONFIRMED.value,
                YachtEventType.ROLL_UNREADABLE.value,
                YachtEventType.DICE_ESCAPED.value,
                YachtEventType.RULE_VIOLATION.value,
                YachtEventType.RULE_VIOLATION_LOWER.value,
            ]
        else:
            reject_events = [
                YachtEventType.ROLL_CONFIRMED.value,
                YachtEventType.ROLL_UNREADABLE.value,
                YachtEventType.DICE_ESCAPED.value,
            ]

        return FusionContext(
            fsm_state=phase.value,
            game_type="yacht",
            active_player=active_player,
            allowed_actors=[active_player] if active_player else [],
            expected_events=expected_events,
            reject_events=reject_events,
            valid_targets={"categories": self.state.available_categories},
            zones={},
            anchors={},
            params={},
        )

    def get_state_dict(self) -> dict:
        return self.state.to_dict()

    def _handle_roll_confirmed(self, event: GameEvent) -> list[WSMessage]:
        if self.state.phase != YachtPhase.AWAITING_ROLL.value:
            return []
        if not self._is_current_actor(event.actor_id):
            return self._warn_and_keep_roll_phase(
                f"지금은 {self.state.current_player.playername}님 차례입니다.",
                priority=AudioPriority.CRITICAL,
            )

        dice_values = event.data.get("dice_values", [])
        if len(dice_values) != 5 or any(v is None for v in dice_values):
            unreadable = [i for i, value in enumerate(dice_values) if value is None]
            return self._record_unreadable_roll(dice_values, unreadable)

        self.state.dice_values = [int(v) for v in dice_values]
        self.state.keep_mask = self._normalize_keep_mask(event.data.get("keep_mask"))
        self.state.roll_count += 1
        self.state.unreadable_roll = None
        self.state.phase = (
            YachtPhase.AWAITING_SCORE.value
            if self.state.roll_count >= 3
            else YachtPhase.AWAITING_KEEP.value
        )
        self.state.last_message = self._roll_message()
        self.state.state_version += 1
        return self._state_context_tts(self.state.last_message)

    def _handle_roll_unreadable(self, event: GameEvent) -> list[WSMessage]:
        if self.state.phase != YachtPhase.AWAITING_ROLL.value:
            return []
        if not self._is_current_actor(event.actor_id):
            return []
        dice_values = list(event.data.get("dice_values", []))
        unknown_indices = list(event.data.get("unknown_indices", []))
        return self._record_unreadable_roll(dice_values, unknown_indices)

    def _handle_keep_selected(self, data: dict) -> list[WSMessage]:
        if self.state.phase not in (
            YachtPhase.AWAITING_KEEP.value,
            YachtPhase.AWAITING_SCORE.value,
        ):
            return []
        self.state.keep_mask = self._normalize_keep_mask(data.get("keep_mask"))
        self.state.state_version += 1
        return [self._make_state_update()]

    def _handle_reroll_requested(self, data: dict) -> list[WSMessage]:
        if self.state.phase != YachtPhase.AWAITING_KEEP.value:
            return []
        if self.state.roll_count >= 3:
            return []
        if "keep_mask" in data:
            self.state.keep_mask = self._normalize_keep_mask(data.get("keep_mask"))
        self.state.phase = YachtPhase.AWAITING_ROLL.value
        self.state.state_version += 1
        self.state.last_message = f"{self.state.current_player.playername}님, 다시 굴려주세요."
        return self._state_context_tts(self.state.last_message)

    def _handle_score_category(self, data: dict, player_id: str | None) -> list[WSMessage]:
        if self.state.phase not in (
            YachtPhase.AWAITING_KEEP.value,
            YachtPhase.AWAITING_SCORE.value,
        ):
            return []
        if player_id is not None and player_id != self.state.current_player.player_id:
            return []

        category = data.get("category")
        if not category or category not in self.state.available_categories:
            return [
                WSMessage.make_error(
                    "INVALID_SCORE_CATEGORY",
                    "선택할 수 없는 점수 카테고리입니다.",
                    self.state.state_version,
                )
            ]

        try:
            score = (
                int(data["score"])
                if "score" in data
                else calculate_score(category, self.state.dice_values)
            )
        except (TypeError, ValueError) as exc:
            return [WSMessage.make_error("INVALID_DICE_VALUES", str(exc), self.state.state_version)]

        current_player = self.state.current_player
        current_player.scores[str(category)] = score
        scorer_name = current_player.playername
        self.state.state_version += 1

        if self.state.is_final_round_complete:
            self.state.finish_game()
            self.state.state_version += 1
            self.state.last_message = "게임이 종료되었습니다."
            return [self._make_state_update(), self._make_tts(self.state.last_message)]

        self.state.advance_player()
        self.state.phase = YachtPhase.AWAITING_ROLL.value
        self.state.last_message = (
            f"{scorer_name}님 {score}점입니다. "
            f"{self.state.current_player.playername}님 차례입니다."
        )
        return self._state_context_tts(self.state.last_message)

    def _handle_unreadable_resolution(self, data: dict) -> list[WSMessage]:
        if self.state.phase != YachtPhase.AWAITING_SCORE.value or not self.state.unreadable_roll:
            return []
        dice_values = data.get("dice_values")
        event = GameEvent(
            event_type=YachtEventType.ROLL_CONFIRMED.value,
            actor_id=self.state.current_player.player_id,
            confidence=1.0,
            frame_id=-1,
            data={"dice_values": dice_values, "keep_mask": self.state.keep_mask},
        )
        self.state.phase = YachtPhase.AWAITING_ROLL.value
        return self._handle_roll_confirmed(event)

    def _record_unreadable_roll(
        self, dice_values: list[Any], unknown_indices: list[Any]
    ) -> list[WSMessage]:
        self.state.unreadable_roll = {
            "dice_values": list(dice_values),
            "unknown_indices": [int(i) for i in unknown_indices],
        }
        self.state.phase = YachtPhase.AWAITING_SCORE.value
        self.state.last_message = "읽히지 않은 주사위 값이 있습니다. 화면에서 값을 입력해주세요."
        self.state.state_version += 1
        return self._state_context_tts(self.state.last_message)

    def _warn_and_keep_roll_phase(
        self,
        message: str,
        priority: AudioPriority = AudioPriority.HIGH,
    ) -> list[WSMessage]:
        self.state.last_message = message
        self.state.state_version += 1
        return [self._make_state_update(), self._make_tts(message, priority)]

    def _is_current_actor(self, actor_id: str | None) -> bool:
        return actor_id in (None, self.state.current_player.player_id)

    def _roll_message(self) -> str:
        values = ", ".join(str(v) for v in self.state.dice_values)
        if self.state.phase == YachtPhase.AWAITING_SCORE.value:
            return f"주사위 결과는 {values}입니다. 점수 칸을 선택해주세요."
        return (
            f"주사위 결과는 {values}입니다. "
            "보관할 주사위를 고르거나 점수 칸을 선택해주세요."
        )

    def _normalize_keep_mask(self, keep_mask: Any) -> list[bool]:
        if not isinstance(keep_mask, list) or len(keep_mask) != 5:
            return [False] * 5
        return [bool(v) for v in keep_mask]

    def _state_context_tts(self, text: str) -> list[WSMessage]:
        return [
            self._make_state_update(),
            WSMessage.make_fusion_context(self.get_fusion_context(), self.state.state_version),
            self._make_tts(text),
        ]

    def _make_state_update(self) -> WSMessage:
        return WSMessage(
            msg_type=MsgType.STATE_UPDATE.value,
            payload=self.state.to_dict(),
            state_version=self.state.state_version,
        )

    def _make_tts(
        self,
        text: str,
        priority: AudioPriority = AudioPriority.NORMAL,
    ) -> WSMessage:
        request = TTSRequest(
            text=text,
            priority=priority,
            agent=AgentRole.NARRATOR.value,
            state_version=self.state.state_version,
        )
        return WSMessage.make_tts_play(request, self.state.state_version)
