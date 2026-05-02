import { useState, useEffect, useRef } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import SeatRegistration from './components/common/SeatRegistration'
import Lobby from './pages/Lobby'
import WerewolfGame from './pages/WerewolfGame'

export default function App() {
  const [page, setPage] = useState('seat')
  const { state, connected, send } = useWebSocket('/ws/tablet')
  const soundRef = useRef(null)

  // 사운드 트리거 처리
  useEffect(() => {
    if (state?.sound === 'registered') {
      const audio = new Audio('/sounds/registered.mp3')
      audio.play().catch(() => {})
    }
  }, [state?.sound])

  const players = state?.players ?? []
  const phase = state?.phase ?? 'player_setup'
  const registeringId = state?.registering_player_id ?? null
  const seatStep = state?.seat_step ?? 'idle'

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
  if (page === 'lobby') return <Lobby players={players} onSelectWerewolf={() => setPage('werewolf')} />
  if (page === 'werewolf') return <WerewolfGame players={players} />
  return null
}
