import { useState, useEffect, useRef } from 'react'
import RoleRegistration from '../components/werewolf/RoleRegistration'
import RoleRegShowCard from '../components/werewolf/RoleRegShowCard'
import RoleRegConfirm from '../components/werewolf/RoleRegConfirm'
import NightStart from '../components/werewolf/NightStart'
import NightRoleAnnounce from '../components/werewolf/NightRoleAnnounce'
import NightEnd from '../components/werewolf/NightEnd'
import DayDiscussion from '../components/werewolf/DayDiscussion'
import VoteCountdown from '../components/werewolf/VoteCountdown'
import VoteResult from '../components/werewolf/VoteResult'
import GameEndWW from '../components/werewolf/GameEndWW'

// 수동으로 start_now를 보내야 하는 야간 페이즈 (카메라 감지가 없는 패시브 페이즈)
const PASSIVE_NIGHT_PHASES = new Set(['night_werewolf', 'night_minion', 'night_mason'])

export default function WerewolfGame({ state, send, players, onLobby, onRestart }) {
  const phase = state?.phase
  const roleReg = state?.role_reg
  const werewolf = state?.werewolf

  // 야간 → 낮 전환 감지용: NightEnd 화면을 1회 보여주기 위한 로컬 상태
  const prevPhaseRef = useRef(phase)
  const [showNightEnd, setShowNightEnd] = useState(false)
  // result 페이즈 내 단계: 'vote_result' → 'game_end'
  const [resultStage, setResultStage] = useState('vote_result')

  useEffect(() => {
    const prev = prevPhaseRef.current
    prevPhaseRef.current = phase
    // 야간 페이즈에서 낮 토론으로 전환될 때 NightEnd 화면 표시
    if (prev?.startsWith('night_') && phase === 'day_discussion') {
      setShowNightEnd(true)
    }
    // result 페이즈 재진입 시 vote_result부터 다시
    if (phase === 'result' && prev !== 'result') {
      setResultStage('vote_result')
    }
  }, [phase])

  // ── 역할 선택 UI (백엔드 game_select 페이즈 또는 초기 진입) ─────────────────
  if (!phase || phase === 'game_select') {
    return (
      <RoleRegistration
        players={players}
        onStart={(roles) => {
          const playerOrder = players.map(p => p.player_id)
          send('start_role_registration', { selected_roles: roles, player_order: playerOrder })
        }}
      />
    )
  }

  // ── 카메라 역할 인식 단계 ────────────────────────────────────────────────────
  if (phase === 'role_registration') {
    const currentPlayer = players.find(p => p.player_id === roleReg?.player_id) ?? players[0]

    if (!roleReg || roleReg.detected_role === null) {
      // 카메라가 카드를 감지할 때까지 대기
      return <RoleRegShowCard player={currentPlayer} />
    }

    // 카드 감지됨 → 플레이어 확인 대기
    return (
      <RoleRegConfirm
        player={currentPlayer}
        detectedRoleId={roleReg.detected_role}
        onConfirm={() => send('confirm_role', { player_id: roleReg.player_id })}
      />
    )
  }

  // ── 야간 시작 ──────────────────────────────────────────────────────────────
  if (phase === 'night_start') {
    return <NightStart onComplete={() => send('start_now', {})} />
  }

  // ── 야간 각 역할 페이즈 ────────────────────────────────────────────────────
  if (phase?.startsWith('night_')) {
    const roleId = phase.replace('night_', '')
    return (
      <NightRoleAnnounce
        roleId={roleId}
        onComplete={() => {
          // 패시브 페이즈는 start_now로 수동 전환, 액티브 페이즈는 카메라 이벤트로 자동 전환
          if (PASSIVE_NIGHT_PHASES.has(phase)) {
            send('start_now', {})
          }
        }}
      />
    )
  }

  // ── 야간 종료 전환 화면 ────────────────────────────────────────────────────
  if (showNightEnd) {
    return <NightEnd onComplete={() => setShowNightEnd(false)} />
  }

  // ── 낮 토론 ────────────────────────────────────────────────────────────────
  if (phase === 'day_discussion') {
    return (
      <DayDiscussion
        initialTime={werewolf?.timer_remaining ?? 300}
        onVote={() => send('start_now', {})}
        onComplete={() => send('start_now', {})}
        onAddTime={() => send('add_30_sec', {})}
      />
    )
  }

  // ── 투표 단계 ──────────────────────────────────────────────────────────────
  if (phase === 'vote_countdown' || phase === 'vote') {
    const votes = Object.fromEntries(
      (werewolf?.players ?? [])
        .filter(p => p.voted_for != null)
        .map(p => [p.player_id, p.voted_for])
    )
    return (
      <VoteCountdown
        players={players}
        votes={votes}
        onComplete={() => {}}
      />
    )
  }

  // ── 결과 ────────────────────────────────────────────────────────────────────
  if (phase === 'result') {
    const votes = Object.fromEntries(
      (werewolf?.players ?? [])
        .filter(p => p.voted_for != null)
        .map(p => [p.player_id, p.voted_for])
    )
    if (resultStage === 'vote_result') {
      return (
        <VoteResult
          players={players}
          votes={votes}
          onComplete={() => setResultStage('game_end')}
        />
      )
    }
    const finalRoles = Object.fromEntries(
      (werewolf?.players ?? []).map(p => [p.player_id, p.current_role])
    )
    return (
      <GameEndWW
        players={players}
        finalRoles={finalRoles}
        winner={werewolf?.winner ?? 'village'}
        onLobby={onLobby}
        onRestart={onRestart}
      />
    )
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0d1520',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#eee',
      fontFamily: "'Segoe UI', sans-serif",
    }}>
      게임 준비 중...
    </div>
  )
}
