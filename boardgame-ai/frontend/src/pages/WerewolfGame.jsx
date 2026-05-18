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
import PhaseTransition from '../components/werewolf/PhaseTransition'

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

const NIGHT_PHASES = new Set(['night_start', ...Object.keys(NIGHT_PHASE_ROLES)])

function getTransitionType(from, to) {
  if (!from || !to) return null
  if (NIGHT_PHASES.has(from) && NIGHT_PHASES.has(to)) return 'eye_close'
  if (NIGHT_PHASES.has(from) && to === 'day_discussion')  return 'dawn'
  if (from === 'day_discussion'  && to === 'vote')        return 'red_vignette'
  if (from === 'vote'            && to === 'result')      return 'flash_fade'
  return 'fade'
}

// wsState: /ws/tablet 상태 (gesture_confirmed 등 로비 이벤트용)
export default function WerewolfGame({ players, onChangePlayers, onChangeGame, onRestart, wsState }) {
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

  // 트랜지션 상태
  const [transitioning, setTransitioning] = useState(false)
  const [transitionType, setTransitionType] = useState('fade')
  const [transitionKey, setTransitionKey] = useState(0)
  const [displayedPhase, setDisplayedPhase] = useState(null)
  const prevPhaseRef = useRef(null)

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

  // phase가 바뀌면 트랜지션 시작
  useEffect(() => {
    if (!phase || phase === 'role_registration') return
    const from = prevPhaseRef.current
    const to = phase
    prevPhaseRef.current = to

    const type = getTransitionType(from, to)
    if (!type) {
      setDisplayedPhase(to)
      return
    }
    if (from) setDisplayedPhase(from)
    setTransitionType(type)
    setTransitionKey(k => k + 1)
    setTransitioning(true)
  }, [phase])

  // ── 게임 FSM 단계 렌더링 ──────────────────────────────────────────────
  const renderGamePhase = (ph) => {
    if (!ph) return <div style={loadingStyle}>게임 진행 중...</div>

    if (NIGHT_PHASE_ROLES[ph]) {
      return (
        <NightRoleAnnounce
          roleId={NIGHT_PHASE_ROLES[ph]}
          onComplete={() => send('start_now', {})}
        />
      )
    }

    if (ph === 'night_start') {
      return <NightStart onComplete={() => send('start_now', {})} />
    }

    if (ph === 'day_discussion') {
      return (
        <DayDiscussion
          timeLeft={wwState.timer_remaining}
          onAddTime={() => send('add_30_sec', {})}
          onVote={() => send('start_now', {})}
        />
      )
    }

    if (ph === 'vote') {
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
          send={send}
        />
      )
    }

    if (ph === 'result') {
      const finalRoles = Object.fromEntries(
        (wwState.players ?? []).map(p => [p.player_id, p.current_role])
      )
      const resetAndCall = (cb) => { send('reset_game', {}); cb() }
      return (
        <GameEndWW
          players={players}
          finalRoles={finalRoles}
          winner={wwState.winner ?? 'village'}
          onChangePlayers={() => resetAndCall(onChangePlayers)}
          onChangeGame={() => resetAndCall(onChangeGame)}
          onRestart={() => resetAndCall(onRestart)}
        />
      )
    }

    return <div style={loadingStyle}>게임 진행 중...</div>
  }

  // ── 게임 진행 중 (트랜지션 포함) ──────────────────────────────────────

  if (phase && phase !== 'role_registration') {
    return (
      <>
        {renderGamePhase(displayedPhase)}
        {transitioning && (
          <PhaseTransition
            key={transitionKey}
            type={transitionType}
            onMidpoint={() => setDisplayedPhase(phase)}
            onDone={() => setTransitioning(false)}
          />
        )}
      </>
    )
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

    return <div style={loadingStyle}>역할 등록 준비 중...</div>
  }

  // ── 초기: 역할 선택 ────────────────────────────────────────────────────

  return (
    <RoleRegistration
      players={players}
      onExit={onChangeGame}
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
