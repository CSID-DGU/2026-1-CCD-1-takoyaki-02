"""한밤의 늑대인간 게임 FSM."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from core.constants import MsgType
from core.envelope import WSMessage
from core.events import FusionContext, GameEvent
from games.base_fsm import BaseFSM
from games.werewolf.judge import judge_winner
from games.werewolf.night_roles import (
    resolve_doppelganger_peek,
    resolve_drunk_swap,
    resolve_insomniac_peek,
    resolve_robber_swap,
    resolve_seer_peek,
    resolve_troublemaker_swap,
)
from games.werewolf.ontology import (
    NIGHT_PHASES,
    PHASE_TO_ROLE,
    WerewolfEventType,
    WerewolfInputType,
    WerewolfPhase,
    WerewolfRole,
    WEREWOLF_TEAM,
)
from games.werewolf.state import WerewolfGameState, WerewolfPlayerState


class WerewolfFSM(BaseFSM):
    def __init__(
        self,
        players: list[WerewolfPlayerState],
        center_cards: list[str],
        broadcast: Callable[[WSMessage], Awaitable[None]],
    ) -> None:
        self.state = WerewolfGameState.new(players, center_cards)
        self._broadcast = broadcast
        self._timer_task: asyncio.Task[None] | None = None
        self._seer_peeks: list[str] = []

    # ── Public API ──────────────────────────────────────────────────────────────

    def start(self) -> list[WSMessage]:
        """게임을 시작한다. NIGHT_START → 첫 야간 페이즈."""
        self.state.state_version += 1
        return [self._make_state_update()] + self._advance_to_next_phase()

    def handle_event(self, event: GameEvent) -> list[WSMessage]:
        etype = event.event_type
        if etype == WerewolfEventType.CARD_PEEK:
            return self._handle_card_peek(event)
        if etype == WerewolfEventType.CARD_SWAP:
            return self._handle_card_swap(event)
        if etype == WerewolfEventType.VOTE_POINT:
            return self._handle_vote_point(event)
        return []

    def handle_input(
        self,
        input_type: str,
        data: dict,
        player_id: str | None = None,
    ) -> list[WSMessage]:
        if input_type == WerewolfInputType.ADD_30_SEC:
            return self._handle_add_30_sec()
        if input_type == WerewolfInputType.START_NOW:
            return self._handle_start_now()
        if input_type == WerewolfInputType.VOTE_PLAYER:
            return self._handle_vote_player(player_id, data)
        return []

    def get_fusion_context(self) -> FusionContext:
        phase = WerewolfPhase(self.state.phase)
        anchors = {
            f"{a.owner_id}_{a.card_index}": a.to_dict()
            for a in self.state.anchors
        }

        if phase == WerewolfPhase.NIGHT_DOPPELGANGER:
            dg_ids = self._players_with_role(WerewolfRole.DOPPELGANGER)
            dg_id = dg_ids[0] if dg_ids else None
            other_players = [
                p.player_id for p in self.state.players if p.player_id != dg_id
            ]
            return FusionContext(
                fsm_state=phase.value,
                game_type="werewolf",
                active_player=dg_id,
                allowed_actors=dg_ids,
                expected_events=[WerewolfEventType.CARD_PEEK],
                reject_events=[WerewolfEventType.CARD_SWAP, WerewolfEventType.VOTE_POINT],
                valid_targets={"player_ids": other_players},
                zones={},
                anchors=anchors,
                params={},
            )

        if phase == WerewolfPhase.NIGHT_SEER:
            seer_ids = self._players_with_role(WerewolfRole.SEER)
            seer_id = seer_ids[0] if seer_ids else None
            other_players = [
                p.player_id for p in self.state.players if p.player_id != seer_id
            ]
            return FusionContext(
                fsm_state=phase.value,
                game_type="werewolf",
                active_player=seer_id,
                allowed_actors=seer_ids,
                expected_events=[WerewolfEventType.CARD_PEEK],
                reject_events=[WerewolfEventType.CARD_SWAP, WerewolfEventType.VOTE_POINT],
                valid_targets={
                    "player_ids": other_players,
                    "center_ids": ["center_0", "center_1", "center_2"],
                },
                zones={},
                anchors=anchors,
                params={},
            )

        if phase == WerewolfPhase.NIGHT_ROBBER:
            robber_ids = self._players_with_role(WerewolfRole.ROBBER)
            robber_id = robber_ids[0] if robber_ids else None
            other_players = [
                p.player_id for p in self.state.players if p.player_id != robber_id
            ]
            return FusionContext(
                fsm_state=phase.value,
                game_type="werewolf",
                active_player=robber_id,
                allowed_actors=robber_ids,
                expected_events=[WerewolfEventType.CARD_SWAP],
                reject_events=[WerewolfEventType.CARD_PEEK, WerewolfEventType.VOTE_POINT],
                valid_targets={"player_ids": other_players},
                zones={},
                anchors=anchors,
                params={},
            )

        if phase == WerewolfPhase.NIGHT_TROUBLEMAKER:
            tm_ids = self._players_with_role(WerewolfRole.TROUBLEMAKER)
            tm_id = tm_ids[0] if tm_ids else None
            other_players = [
                p.player_id for p in self.state.players if p.player_id != tm_id
            ]
            return FusionContext(
                fsm_state=phase.value,
                game_type="werewolf",
                active_player=tm_id,
                allowed_actors=tm_ids,
                expected_events=[WerewolfEventType.CARD_SWAP],
                reject_events=[WerewolfEventType.CARD_PEEK, WerewolfEventType.VOTE_POINT],
                valid_targets={"player_ids": other_players},
                zones={},
                anchors=anchors,
                params={},
            )

        if phase == WerewolfPhase.NIGHT_DRUNK:
            drunk_ids = self._players_with_role(WerewolfRole.DRUNK)
            drunk_id = drunk_ids[0] if drunk_ids else None
            return FusionContext(
                fsm_state=phase.value,
                game_type="werewolf",
                active_player=drunk_id,
                allowed_actors=drunk_ids,
                expected_events=[WerewolfEventType.CARD_SWAP],
                reject_events=[WerewolfEventType.CARD_PEEK, WerewolfEventType.VOTE_POINT],
                valid_targets={"center_ids": ["center_0", "center_1", "center_2"]},
                zones={},
                anchors=anchors,
                params={},
            )

        if phase == WerewolfPhase.NIGHT_INSOMNIAC:
            insomniac_ids = self._players_with_role(WerewolfRole.INSOMNIAC)
            insomniac_id = insomniac_ids[0] if insomniac_ids else None
            return FusionContext(
                fsm_state=phase.value,
                game_type="werewolf",
                active_player=insomniac_id,
                allowed_actors=insomniac_ids,
                expected_events=[WerewolfEventType.CARD_PEEK],
                reject_events=[WerewolfEventType.CARD_SWAP, WerewolfEventType.VOTE_POINT],
                valid_targets={"self_only": True},
                zones={},
                anchors=anchors,
                params={},
            )

        if phase == WerewolfPhase.VOTE:
            return FusionContext(
                fsm_state=phase.value,
                game_type="werewolf",
                active_player=None,
                allowed_actors=list(self.state.player_order),
                expected_events=[WerewolfEventType.VOTE_POINT],
                reject_events=[WerewolfEventType.CARD_PEEK, WerewolfEventType.CARD_SWAP],
                valid_targets={"player_ids": list(self.state.player_order)},
                zones={},
                anchors=anchors,
                params={"pointing_stabilization_frames": 10},
            )

        # 기본: 이벤트 없음 (NIGHT_START, DAY_DISCUSSION, RESULT 등)
        return FusionContext(
            fsm_state=phase.value,
            game_type="werewolf",
            active_player=None,
            allowed_actors=[],
            expected_events=[],
            reject_events=[
                WerewolfEventType.CARD_PEEK,
                WerewolfEventType.CARD_SWAP,
                WerewolfEventType.VOTE_POINT,
            ],
            valid_targets=None,
            zones={},
            anchors=anchors,
            params={},
        )

    def get_state_dict(self) -> dict:
        return self.state.to_dict()

    # ── Internal helpers ────────────────────────────────────────────────────────

    def _players_with_role(self, role: WerewolfRole) -> list[str]:
        """original_role 기준으로 해당 역할의 player_id 목록을 반환한다."""
        return [p.player_id for p in self.state.players if p.original_role == role.value]

    def _make_state_update(self) -> WSMessage:
        return WSMessage(
            msg_type=MsgType.STATE_UPDATE.value,
            payload=self.state.to_dict(),
            state_version=self.state.state_version,
        )

    def _advance_to_next_phase(self) -> list[WSMessage]:
        """현재 페이즈에서 다음 페이즈로 전이한다."""
        current = WerewolfPhase(self.state.phase)

        if current in (WerewolfPhase.NIGHT_START, *NIGHT_PHASES):
            search_from = (
                -1
                if current == WerewolfPhase.NIGHT_START
                else NIGHT_PHASES.index(current)
            )
            for next_phase in NIGHT_PHASES[search_from + 1:]:
                if self._players_with_role(PHASE_TO_ROLE[next_phase]):
                    return self._enter_phase(next_phase)
            return self._enter_phase(WerewolfPhase.DAY_DISCUSSION)

        if current == WerewolfPhase.DAY_DISCUSSION:
            return self._enter_phase(WerewolfPhase.VOTE_COUNTDOWN)

        if current == WerewolfPhase.VOTE_COUNTDOWN:
            return self._enter_phase(WerewolfPhase.VOTE)

        if current == WerewolfPhase.VOTE:
            self.state.winner = judge_winner(self.state)
            return self._enter_phase(WerewolfPhase.RESULT)

        return []

    def _enter_phase(self, phase: WerewolfPhase) -> list[WSMessage]:
        """페이즈 진입: state 업데이트 + FusionContext 발송."""
        self.state.phase = phase.value
        self.state.state_version += 1
        msgs: list[WSMessage] = [self._make_state_update()]

        if phase == WerewolfPhase.NIGHT_WEREWOLF:
            # 늑대인간들은 original_role로 서로를 인식 → 카드 행동 불필요, 즉시 전이
            return msgs + self._advance_to_next_phase()

        if phase == WerewolfPhase.NIGHT_MINION:
            # 하수인은 늑대인간 목록 확인만 → 즉시 전이
            return msgs + self._advance_to_next_phase()

        if phase == WerewolfPhase.NIGHT_MASON:
            # 두 메이슨이 서로를 확인만 → 즉시 전이
            return msgs + self._advance_to_next_phase()

        if phase == WerewolfPhase.NIGHT_SEER:
            self._seer_peeks = []

        elif phase == WerewolfPhase.DAY_DISCUSSION:
            self._timer_task = asyncio.create_task(self._run_timer())

        elif phase == WerewolfPhase.VOTE_COUNTDOWN:
            # 시각적 카운트다운은 UI 담당; FSM은 즉시 VOTE로 전이
            return msgs + self._advance_to_next_phase()

        elif phase == WerewolfPhase.RESULT:
            return msgs  # 종료 상태; FusionContext 불필요

        msgs.append(
            WSMessage.make_fusion_context(
                self.get_fusion_context(),
                state_version=self.state.state_version,
            )
        )
        return msgs

    # ── Event handlers ──────────────────────────────────────────────────────────

    def _handle_card_peek(self, event: GameEvent) -> list[WSMessage]:
        phase = WerewolfPhase(self.state.phase)
        actor_id = event.actor_id
        data = event.data
        card_owner_id: str | None = data.get("card_owner_id")
        card_index = int(data.get("card_index", 0))

        if phase == WerewolfPhase.NIGHT_DOPPELGANGER:
            if actor_id not in self._players_with_role(WerewolfRole.DOPPELGANGER):
                return []
            # 도플갱어는 다른 플레이어 카드만 확인 가능 (센터 카드 불가)
            if not card_owner_id or card_owner_id.startswith("center_"):
                return []
            resolve_doppelganger_peek(self.state, actor_id, card_owner_id)
            self.state.state_version += 1
            return [self._make_state_update()] + self._advance_to_next_phase()

        if phase == WerewolfPhase.NIGHT_SEER:
            if actor_id not in self._players_with_role(WerewolfRole.SEER):
                return []
            target_id = f"center_{card_index}" if card_owner_id is None else card_owner_id
            resolve_seer_peek(self.state, actor_id, target_id, card_index)
            self._seer_peeks.append(target_id)

            # 플레이어 카드 1장 또는 센터 카드 2장 → 완료
            done = not target_id.startswith("center_") or len(self._seer_peeks) >= 2
            self.state.state_version += 1
            msgs = [self._make_state_update()]
            if done:
                return msgs + self._advance_to_next_phase()
            msgs.append(
                WSMessage.make_fusion_context(
                    self.get_fusion_context(),
                    state_version=self.state.state_version,
                )
            )
            return msgs

        if phase == WerewolfPhase.NIGHT_INSOMNIAC:
            if actor_id not in self._players_with_role(WerewolfRole.INSOMNIAC):
                return []
            if card_owner_id != actor_id:
                return []
            resolve_insomniac_peek(self.state, actor_id)
            self.state.state_version += 1
            return [self._make_state_update()] + self._advance_to_next_phase()

        return []

    def _handle_card_swap(self, event: GameEvent) -> list[WSMessage]:
        phase = WerewolfPhase(self.state.phase)
        actor_id = event.actor_id
        from_id: str = event.data.get("from_id", "")
        to_id: str = event.data.get("to_id", "")

        if phase == WerewolfPhase.NIGHT_ROBBER:
            if actor_id not in self._players_with_role(WerewolfRole.ROBBER):
                return []
            target_id = to_id if from_id == actor_id else from_id
            resolve_robber_swap(self.state, actor_id, target_id)
            self.state.state_version += 1
            return [self._make_state_update()] + self._advance_to_next_phase()

        if phase == WerewolfPhase.NIGHT_TROUBLEMAKER:
            if actor_id not in self._players_with_role(WerewolfRole.TROUBLEMAKER):
                return []
            resolve_troublemaker_swap(self.state, actor_id, from_id, to_id)
            self.state.state_version += 1
            return [self._make_state_update()] + self._advance_to_next_phase()

        if phase == WerewolfPhase.NIGHT_DRUNK:
            if actor_id not in self._players_with_role(WerewolfRole.DRUNK):
                return []
            center_id = to_id if from_id == actor_id else from_id
            resolve_drunk_swap(self.state, actor_id, center_id)
            self.state.state_version += 1
            return [self._make_state_update()] + self._advance_to_next_phase()

        return []

    def _handle_vote_point(self, event: GameEvent) -> list[WSMessage]:
        if WerewolfPhase(self.state.phase) != WerewolfPhase.VOTE:
            return []
        actor_id = event.actor_id
        target_id = event.data.get("target_id")
        if not actor_id or not target_id:
            return []
        return self._record_vote(actor_id, target_id)

    def _record_vote(self, voter_id: str, target_id: str) -> list[WSMessage]:
        try:
            voter = self.state.get_player(voter_id)
            self.state.get_player(target_id)  # target 존재 검증
        except KeyError:
            return []
        voter.voted_for = target_id
        self.state.state_version += 1
        msgs = [self._make_state_update()]
        if all(p.voted_for is not None for p in self.state.players):
            self.state.winner = judge_winner(self.state)
            msgs += self._advance_to_next_phase()
        return msgs

    # ── Input handlers ──────────────────────────────────────────────────────────

    def _handle_add_30_sec(self) -> list[WSMessage]:
        if WerewolfPhase(self.state.phase) != WerewolfPhase.DAY_DISCUSSION:
            return []
        self.state.timer_remaining += 30
        self.state.state_version += 1
        return [self._make_state_update()]

    def _handle_start_now(self) -> list[WSMessage]:
        if WerewolfPhase(self.state.phase) != WerewolfPhase.DAY_DISCUSSION:
            return []
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None
        return self._advance_to_next_phase()

    def _handle_vote_player(self, player_id: str | None, data: dict) -> list[WSMessage]:
        if WerewolfPhase(self.state.phase) != WerewolfPhase.VOTE:
            return []
        if not player_id:
            return []
        target_id = data.get("target_id")
        if not target_id:
            return []
        return self._record_vote(player_id, target_id)

    # ── Timer ───────────────────────────────────────────────────────────────────

    async def _run_timer(self) -> None:
        """DAY_DISCUSSION 1초 타이머. 만료 시 VOTE_COUNTDOWN으로 전이."""
        try:
            while self.state.timer_remaining > 0:
                await asyncio.sleep(1)
                if WerewolfPhase(self.state.phase) != WerewolfPhase.DAY_DISCUSSION:
                    return
                self.state.timer_remaining -= 1
                self.state.state_version += 1
                await self._broadcast(self._make_state_update())

            if WerewolfPhase(self.state.phase) == WerewolfPhase.DAY_DISCUSSION:
                for msg in self._advance_to_next_phase():
                    await self._broadcast(msg)
        except asyncio.CancelledError:
            pass
