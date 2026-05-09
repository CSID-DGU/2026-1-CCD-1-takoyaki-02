import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import SeatRegistration from './components/common/SeatRegistration'
import Lobby from './pages/Lobby'
import WerewolfGame from './pages/WerewolfGame'
import YachtGame from './pages/YachtGame'

const WEREWOLF_PHASES = new Set([
  'role_registration',
  'night_start', 'night_doppelganger', 'night_werewolf', 'night_minion',
  'night_mason', 'night_seer', 'night_robber', 'night_troublemaker',
  'night_drunk', 'night_insomniac',
  'day_discussion', 'vote_countdown', 'vote', 'result',
])

export default function App() {
  const [page, setPage] = useState('seat')
  const { state, connected, send } = useWebSocket('/ws/tablet')

  const phase = state?.phase ?? 'player_setup'
  const players = state?.players ?? []
  const registeringId = state?.registering_player_id ?? null
  const seatStep = state?.seat_step ?? 'idle'

  // 사운드 트리거 처리
  useEffect(() => {
    if (state?.sound === 'registered') {
      const audio = new Audio('/sounds/registered.mp3')
      audio.play().catch(() => {})
    }
  }, [state?.sound])

  // 백엔드 phase가 늑대인간 게임 단계로 진입하면 page 동기화
  useEffect(() => {
    if (WEREWOLF_PHASES.has(phase) && page !== 'werewolf') {
      setPage('werewolf')
    }
  }, [phase, page])

  if (page === 'seat') {
    return (
      <SeatRegistration
        players={players}
        registeringId={registeringId}
        seatStep={seatStep}
        connected={connected}
        send={send}
        onStart={() => setPage('lobby')}
      />
    )
  }
  if (page === 'lobby') return <Lobby players={players} send={send} onSelectYacht={() => setPage('yacht')} onSelectWerewolf={() => setPage('werewolf')} />
  if (page === 'yacht') return <YachtGame players={players} onExit={() => setPage('lobby')} onChangePlayers={() => setPage('seat')} />
  if (page === 'werewolf') return (
    <WerewolfGame
      players={players}
      wsState={state}
      send={send}
      onLobby={() => setPage('seat')}
      onRestart={() => setPage('lobby')}
    />
  )
  return null
}
