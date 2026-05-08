import { useState } from 'react'
import RoleRegistration from '../components/werewolf/RoleRegistration'
import RoleRegShowCard from '../components/werewolf/RoleRegShowCard'
import RoleRegConfirm from '../components/werewolf/RoleRegConfirm'
import NightStart from '../components/werewolf/NightStart'
import NightRoleAnnounce from '../components/werewolf/NightRoleAnnounce'
import DayDiscussion from '../components/werewolf/DayDiscussion'
import VoteCountdown from '../components/werewolf/VoteCountdown'
import VoteResult from '../components/werewolf/VoteResult'
import GameEndWW from '../components/werewolf/GameEndWW'

// 백엔드 night phase → roleId 매핑
const NIGHT_PHASE_ROLES = {
  night_doppelganger: 'doppelganger',
  night_werewolf: 'werewolf',
  night_minion: 'minion',
  night_mason: 'mason',
  night_seer: 'seer',
  night_robber: 'robber',
  night_troublemaker: 'troublemaker',
  night_drunk: 'drunk',
  night_insomniac: 'insomniac',
}

// werewolf_1, mason_2 등 → werewolf, mason 으로 정규화
const normalizeRoleId = (id) => (id ?? '').replace(/_\d+$/, '')

const loadingStyle = {
  minHeight: '100vh',
  background: '#0d1520',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: '#eee',
  fontFamily: "'Segoe UI', sans-serif",
}

export default function WerewolfGame({ players, onLobby, onRestart, wsState, send }) {
  const [localPhase, setLocalPhase] = useState('role_registration')
  const [selectedRoles, setSelectedRoles] = useState([])
  const [playerIndex, setPlayerIndex] = useState(0)
  const [detectedRoleId, setDetectedRoleId] = useState(null)
  const [gameSent, setGameSent] = useState(false)
  // vote_result 전환 화면 표시용
  const [showVoteResult, setShowVoteResult] = useState(false)

  const gameState = wsState?.game_state
  const backendPhase = gameState?.phase

  // ── 백엔드 game_state가 도착하면 FSM 기반으로 렌더링 ──────────────────

  if (gameState) {
    // 야간 역할 안내
    if (NIGHT_PHASE_ROLES[backendPhase]) {
      return (
        <NightRoleAnnounce
          roleId={NIGHT_PHASE_ROLES[backendPhase]}
          onComplete={() => {}}
        />
      )
    }

    if (backendPhase === 'night_start') {
      return <NightStart onComplete={() => {}} />
    }

    if (backendPhase === 'day_discussion') {
      return (
        <DayDiscussion
          timeLeft={gameState.timer_remaining}
          onAddTime={() => send('add_30_sec', {})}
          onVote={() => send('start_now', {})}
        />
      )
    }

    if (backendPhase === 'vote') {
      const votes = Object.fromEntries(
        (gameState.players ?? [])
          .filter(p => p.voted_for != null)
          .map(p => [p.player_id, p.voted_for])
      )
      if (showVoteResult) {
        return (
          <VoteResult
            players={players}
            votes={votes}
            onComplete={() => setShowVoteResult(false)}
          />
        )
      }
      return (
        <VoteCountdown
          players={players}
          votes={votes}
          onComplete={() => setShowVoteResult(true)}
        />
      )
    }

    if (backendPhase === 'result') {
      const finalRoles = Object.fromEntries(
        (gameState.players ?? []).map(p => [p.player_id, p.current_role])
      )
      const handleEnd = (cb) => {
        send('reset_game', {})
        cb()
      }
      return (
        <GameEndWW
          players={players}
          finalRoles={finalRoles}
          winner={gameState.winner ?? 'village'}
          onLobby={() => handleEnd(onLobby)}
          onRestart={() => handleEnd(onRestart)}
        />
      )
    }

    return <div style={loadingStyle}>게임 진행 중...</div>
  }

  // ── 게임 시작 요청 후 백엔드 응답 대기 중 ────────────────────────────

  if (gameSent) {
    return <div style={loadingStyle}>게임 준비 중...</div>
  }

  // ── 프리게임: 역할 등록 (로컬 단계) ─────────────────────────────────

  if (localPhase === 'role_registration') {
    return (
      <RoleRegistration
        players={players}
        onStart={(roles) => {
          setSelectedRoles(roles)
          setPlayerIndex(0)
          setLocalPhase('role_reg_show_card')
        }}
      />
    )
  }

  if (localPhase === 'role_reg_show_card') {
    return (
      <RoleRegShowCard
        player={players[playerIndex]}
        onDetected={(roleId) => {
          setDetectedRoleId(roleId)
          setLocalPhase('role_reg_confirm')
        }}
      />
    )
  }

  if (localPhase === 'role_reg_confirm') {
    return (
      <RoleRegConfirm
        player={players[playerIndex]}
        detectedRoleId={detectedRoleId ?? selectedRoles[playerIndex]}
        onConfirm={() => {
          const next = playerIndex + 1
          if (next < players.length) {
            setPlayerIndex(next)
            setDetectedRoleId(null)
            setLocalPhase('role_reg_show_card')
          } else {
            // 모든 플레이어 확인 완료 → 백엔드로 게임 시작 요청
            const playerRoles = players.map((p, i) => ({
              player_id: p.player_id,
              role: normalizeRoleId(selectedRoles[i] ?? 'villager_1'),
            }))
            const centerRoles = selectedRoles.slice(players.length).map(normalizeRoleId)
            send('start_werewolf_game', { player_roles: playerRoles, center_roles: centerRoles })
            setGameSent(true)
          }
        }}
      />
    )
  }

  return <div style={loadingStyle}>게임 준비 중...</div>
}
