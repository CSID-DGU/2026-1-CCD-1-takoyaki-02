import { useEffect, useRef, useState } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { audio as audioApi, useAudioPlayer } from '../hooks/useAudioPlayer'
import RoleRegistration from '../components/werewolf/RoleRegistration'
import RoleRegShowCard from '../components/werewolf/RoleRegShowCard'
import RoleRegConfirm from '../components/werewolf/RoleRegConfirm'
import NightStart from '../components/werewolf/NightStart'
import NightRoleAnnounce from '../components/werewolf/NightRoleAnnounce'
import DayDiscussion from '../components/werewolf/DayDiscussion'
import VoteCountdown from '../components/werewolf/VoteCountdown'
import VoteResult from '../components/werewolf/VoteResult'
import GameEndWW from '../components/werewolf/GameEndWW'

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

// wsState: /ws/tablet 상태 (gesture_confirmed 등 로비 이벤트용)
export default function WerewolfGame({ players, onLobby, onRestart, wsState }) {
  const { state: wwState, send } = useWebSocket('/ws/werewolf', {
    onAudioMessage: audioApi.enqueue,
  })
  // /ws/werewolf 채널로도 audio_ack가 흐르도록 등록.
  useAudioPlayer(send)
  const [showVoteResult, setShowVoteResult] = useState(false)

  // 역할 감지 상태: 백엔드 role_reg.detected_role 변화 추적
  const [detectedRoleId, setDetectedRoleId] = useState(null)
  const prevDetectedRef = useRef(null)
  const prevPlayerRef = useRef(null)

  const phase = wwState?.phase
  const roleReg = wwState?.role_reg

  useEffect(() => {
    // 플레이어가 바뀌면 이전 감지 초기화
    if (roleReg?.player_id !== prevPlayerRef.current) {
      prevPlayerRef.current = roleReg?.player_id ?? null
      prevDetectedRef.current = null
      setDetectedRoleId(null)
    }
    // 새 역할 감지 시 상태 업데이트
    const detected = roleReg?.detected_role
    if (detected && detected !== prevDetectedRef.current) {
      prevDetectedRef.current = detected
      setDetectedRoleId(detected)
    }
  }, [roleReg?.player_id, roleReg?.detected_role])

  // ── 게임 FSM 단계 ──────────────────────────────────────────────────────

  if (phase && phase !== 'role_registration') {
    if (NIGHT_PHASE_ROLES[phase]) {
      return (
        <NightRoleAnnounce
          roleId={NIGHT_PHASE_ROLES[phase]}
          onComplete={() => send('start_now', {})}
        />
      )
    }

    if (phase === 'night_start') {
      return <NightStart onComplete={() => send('start_now', {})} />
    }

    if (phase === 'day_discussion') {
      return (
        <DayDiscussion
          timeLeft={wwState.timer_remaining}
          onAddTime={() => send('add_30_sec', {})}
          onVote={() => send('start_now', {})}
        />
      )
    }

    if (phase === 'vote') {
      const votes = Object.fromEntries(
        (wwState.players ?? [])
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

    if (phase === 'result') {
      const finalRoles = Object.fromEntries(
        (wwState.players ?? []).map(p => [p.player_id, p.current_role])
      )
      const handleEnd = (cb) => {
        send('RESTART', {})
        cb()
      }
      return (
        <GameEndWW
          players={players}
          finalRoles={finalRoles}
          winner={wwState.winner ?? 'village'}
          onLobby={() => handleEnd(onLobby)}
          onRestart={() => handleEnd(onRestart)}
        />
      )
    }

    return <div style={loadingStyle}>게임 진행 중...</div>
  }

  // ── 역할 등록 단계 ─────────────────────────────────────────────────────

  if (phase === 'role_registration') {
    const currentPlayer = players.find(p => p.player_id === roleReg?.player_id)

    // 역할 감지됨 → 확인 화면
    if (detectedRoleId && currentPlayer) {
      return (
        <RoleRegConfirm
          player={currentPlayer}
          detectedRoleId={detectedRoleId}
          wsState={wsState}
          onConfirm={(selectedRole) => {
            send('CONFIRM_ROLE', { role: selectedRole?.id ?? detectedRoleId }, currentPlayer.player_id)
          }}
        />
      )
    }

    // 카드 스캔 화면
    if (currentPlayer) {
      return (
        <RoleRegShowCard
          player={currentPlayer}
          onBack={() => {
            send('RESTART', {})
            onRestart()
          }}
          onExit={onRestart}
          onDetected={(roleId) => setDetectedRoleId(roleId)}
        />
      )
    }
  }

  // ── 초기: 역할 선택 ────────────────────────────────────────────────────

  return (
    <RoleRegistration
      players={players}
      onExit={onRestart}
      onStart={(roles) => {
        const playerOrder = players.map(p => p.player_id)
        send('START_ROLE_REGISTRATION', {
          selected_roles: roles.map(normalizeRoleId),
          player_order: playerOrder,
        })
      }}
    />
  )
}
