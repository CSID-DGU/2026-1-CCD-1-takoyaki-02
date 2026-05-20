import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { useAudioPlayer, audio as audioApi } from './hooks/useAudioPlayer'
import { useBenchBridge } from './hooks/useBenchBridge'
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
  const [yachtTutorialMode, setYachtTutorialMode] = useState(false)
  const [gameKey, setGameKey] = useState(0)
  const [isPracticeMode, setIsPracticeMode] = useState(false)
  const { state, connected, send } = useWebSocket('/ws/tablet', {
    onAudioMessage: audioApi.enqueue,
  })
  // App 레벨 싱글톤 audio. send를 넘겨 audio_ack가 backend로 흐르도록.
  useAudioPlayer(send)
  // window._bench.log(...)를 정의하고 250ms 배치로 backend에 전송.
  // backend가 BENCH_TRACE=1 아니면 backend 쪽에서 무시되므로 항상 켜둬도 OK.
  useBenchBridge(send)

  const phase = state?.phase ?? 'player_setup'
  const players = state?.players ?? []
  const registeringId = state?.registering_player_id ?? null
  const seatStep = state?.seat_step ?? 'idle'

  // 사운드 트리거 처리
  useEffect(() => {
    // sound_seq가 바뀔 때마다 재생 (오른손/왼손 각각 트리거됨).
    if (state?.sound === 'registered') {
      const audio = new Audio('/sfx/hand_register.mp3')
      audio.play().catch(() => {})
    }
  }, [state?.sound_seq])

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
  if (page === 'lobby') {
    return (
      <Lobby
        players={players}
        send={send}
        onSelectYacht={() => {
          setYachtTutorialMode(false)
          setPage('yacht')
        }}
        onSelectYachtTutorial={() => {
          setYachtTutorialMode(true)
          setPage('yacht')
        }}
        onSelectWerewolf={() => { setIsPracticeMode(false); setPage('werewolf') }}
        onSelectWerewolfPractice={() => { setIsPracticeMode(true); setPage('werewolf') }}
        onExit={() => setPage('seat')}
      />
    )
  }
  if (page === 'yacht') return (
    <YachtGame
      players={players}
      tutorialMode={yachtTutorialMode}
      onExit={() => setPage('lobby')}
      onChangePlayers={() => setPage('seat')}
    />
  )
  if (page === 'werewolf') return (
    <WerewolfGame
      key={gameKey}
      players={players}
      wsState={state}
      send={send}
      isPracticeMode={isPracticeMode}
      onChangePlayers={() => { setIsPracticeMode(false); setPage('seat') }}
      onChangeGame={() => { setIsPracticeMode(false); setPage('lobby') }}
      onRestart={() => setGameKey(k => k + 1)}
    />
  )
  return null
}
