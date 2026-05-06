import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import SeatRegistration from './components/common/SeatRegistration'
import Lobby from './pages/Lobby'
import WerewolfGame from './pages/WerewolfGame'
import YachtGame from './pages/YachtGame'

export default function App() {
  const [page, setPage] = useState('seat')
  const { state, connected, send } = useWebSocket('/ws/tablet')

  // 사운드 트리거 처리
  useEffect(() => {
    if (state?.sound === 'registered') {
      const audio = new Audio('/sounds/registered.mp3')
      audio.play().catch(() => {})
    }
  }, [state?.sound])

  const players = state?.players ?? []
  // TODO(yacht/werewolf FSM 합류 시): state.phase로 게임 단계별 라우팅 (PLAYER_SETUP/GAME_SELECT/IN_GAME 등)
  // 현재는 page state로 직접 라우팅 중이어서 phase는 미사용. 백엔드 → FSM 통합 후 사용 예정.
  // const phase = state?.phase ?? 'player_setup'
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
  if (page === 'werewolf') return (
    <WerewolfGame
      players={players}
      onLobby={() => setPage('seat')}
      onRestart={() => setPage('lobby')}
    />
  )
  if (page === 'seat') {
    return <SeatRegistration players={players} setPlayers={setPlayers} onStart={() => setPage('lobby')} />
  }
  if (page === 'lobby') {
    return (
      <Lobby
        players={players}
        onSelectYacht={() => setPage('yacht')}
        onSelectWerewolf={() => setPage('werewolf')}
      />
    )
  }
  if (page === 'yacht') return <YachtGame players={players} onExit={() => setPage('lobby')} onChangePlayers={() => setPage('seat')} />
  if (page === 'werewolf') return <WerewolfGame players={players} />
  return null
}
