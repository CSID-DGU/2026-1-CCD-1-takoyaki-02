import { useState } from 'react'
import SeatRegistration from './components/common/SeatRegistration'
import Lobby from './pages/Lobby'
import WerewolfGame from './pages/WerewolfGame'

export default function App() {
  const [page, setPage] = useState('seat')
  const [players, setPlayers] = useState([])

  if (page === 'seat') return <SeatRegistration players={players} setPlayers={setPlayers} onStart={() => setPage('lobby')} />
  if (page === 'lobby') return <Lobby players={players} onSelectWerewolf={() => setPage('werewolf')} />
  if (page === 'werewolf') return <WerewolfGame players={players} />
  return null
}
