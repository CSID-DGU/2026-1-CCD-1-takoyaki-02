import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import SeatRegistration from './components/common/SeatRegistration'
import Lobby from './pages/Lobby'
import WerewolfGame from './pages/WerewolfGame'
import YachtGame from './pages/YachtGame'

export default function App() {
  const [page, setPage] = useState('seat')
  const { state, connected, send } = useWebSocket('/ws/tablet')

  const players = state?.players ?? []
  const gamePlayers = players.filter(p => p.playername && p.registered)
  const registeringId = state?.registering_player_id ?? null
  const seatStep = state?.seat_step ?? 'idle'

  useEffect(() => {
    if (state?.sound === 'registered') {
      const audio = new Audio('/sounds/registered.mp3')
      audio.play().catch(() => {})
    }
  }, [state?.sound])

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
  if (page === 'lobby') {
    return (
      <Lobby
        players={players}
        send={send}
        onSelectYacht={() => setPage('yacht')}
        onSelectWerewolf={() => setPage('werewolf')}
        onExit={() => setPage('seat')}
      />
    )
  }
  if (page === 'yacht') return <YachtGame players={gamePlayers} onExit={() => setPage('lobby')} onChangePlayers={() => setPage('seat')} />
  if (page === 'werewolf') return (
    <WerewolfGame
      players={gamePlayers}
      wsState={state}
      onLobby={() => setPage('seat')}
      onRestart={() => setPage('lobby')}
    />
  )
  return null
}
