import { useState } from 'react'
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

// 밤 행동 순서 (One Night Werewolf 기준)
const NIGHT_ORDER = [
  'doppelganger', 'werewolf', 'minion', 'mason',
  'seer', 'robber', 'troublemaker', 'drunk', 'insomniac',
]

// werewolf_1, mason_2 등 → werewolf, mason 으로 정규화
const normalizeRoleId = (id) => (id ?? '').replace(/_\d+$/, '')

// 선택된 역할 목록에서 야간 순서 큐 생성 (중복 제거, 순서 유지)
const buildNightQueue = (roles) => {
  const present = new Set(roles.map(normalizeRoleId))
  return NIGHT_ORDER.filter(r => present.has(r))
}

export default function WerewolfGame({ players, onLobby, onRestart }) {
  const [phase, setPhase] = useState('role_registration')
  const [selectedRoles, setSelectedRoles] = useState([])
  const [playerIndex, setPlayerIndex] = useState(0)
  const [detectedRoleId, setDetectedRoleId] = useState(null)
  const [nightQueue, setNightQueue] = useState([])
  const [nightQueueIndex, setNightQueueIndex] = useState(0)
  const [votes, setVotes] = useState({})

  if (phase === 'role_registration') {
    return (
      <RoleRegistration
        players={players}
        onStart={(roles) => {
          setSelectedRoles(roles)
          setPlayerIndex(0)
          setPhase('role_reg_show_card')
        }}
      />
    )
  }

  if (phase === 'role_reg_show_card') {
    return (
      <RoleRegShowCard
        player={players[playerIndex]}
        onDetected={(roleId) => {
          setDetectedRoleId(roleId)
          setPhase('role_reg_confirm')
        }}
      />
    )
  }

  if (phase === 'role_reg_confirm') {
    return (
      <RoleRegConfirm
        player={players[playerIndex]}
        detectedRoleId={detectedRoleId ?? selectedRoles[playerIndex]}
        onConfirm={() => {
          const next = playerIndex + 1
          if (next < players.length) {
            setPlayerIndex(next)
            setDetectedRoleId(null)
            setPhase('role_reg_show_card')
          } else {
            setPhase('night_start')
          }
        }}
      />
    )
  }

  if (phase === 'night_start') {
    return (
      <NightStart
        onComplete={() => {
          const queue = buildNightQueue(selectedRoles)
          setNightQueue(queue)
          setNightQueueIndex(0)
          setPhase(queue.length > 0 ? 'night_role_announce' : 'night_end')
        }}
      />
    )
  }

  if (phase === 'night_role_announce') {
    return (
      <NightRoleAnnounce
        roleId={nightQueue[nightQueueIndex]}
        onComplete={() => {
          const next = nightQueueIndex + 1
          if (next < nightQueue.length) {
            setNightQueueIndex(next)
          } else {
            setPhase('night_end')
          }
        }}
      />
    )
  }

  if (phase === 'night_end') {
    return (
      <NightEnd onComplete={() => setPhase('day_discussion')} />
    )
  }

  if (phase === 'day_discussion') {
    return (
      <DayDiscussion
        onVote={() => setPhase('vote')}
        onComplete={() => setPhase('vote')}
      />
    )
  }

  if (phase === 'vote') {
    return (
      <VoteCountdown
        players={players}
        votes={votes}
        onComplete={() => setPhase('vote_result')}
      />
    )
  }

  if (phase === 'vote_result') {
    return (
      <VoteResult
        players={players}
        votes={votes}
        onComplete={() => setPhase('game_end')}
      />
    )
  }

  if (phase === 'game_end') {
    const finalRoles = Object.fromEntries(
      players.map((p, i) => [p.player_id, selectedRoles[i] ?? 'villager_1'])
    )
    return (
      <GameEndWW
        players={players}
        finalRoles={finalRoles}
        winner="village"
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
