import { useState, useEffect, useMemo } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { useAudioPlayer, audio as audioApi } from './hooks/useAudioPlayer'
import { useBenchBridge } from './hooks/useBenchBridge'
import SeatRegistration from './components/common/SeatRegistration'
import { colorForIndex } from './components/common/seatColors'
import Lobby from './pages/Lobby'
import Countdown from './pages/Countdown'
import WerewolfGame from './pages/WerewolfGame'
import YachtGame from './pages/YachtGame'

const WEREWOLF_PHASES = new Set([
  'role_registration',
  'night_start', 'night_doppelganger', 'night_werewolf', 'night_minion',
  'night_mason', 'night_seer', 'night_robber', 'night_troublemaker',
  'night_drunk', 'night_insomniac',
  'day_discussion', 'vote_countdown', 'vote', 'result',
])

/** firstPlayerId / direction에 맞게 좌석 순서로 재정렬 */
function orderForTurn(players, firstPlayerId, direction) {
  if (players.length === 0) return []
  const byPos = [...players].sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
  const startIdx = Math.max(0, byPos.findIndex((p) => p.player_id === firstPlayerId))
  const walked = [...byPos.slice(startIdx), ...byPos.slice(0, startIdx)]
  if (direction === 'ccw') {
    return [walked[0], ...walked.slice(1).reverse()]
  }
  return walked
}

export default function App() {
  const [page, setPage] = useState('seat')
  const [gameKey, setGameKey] = useState(0)
  const [isPracticeMode, setIsPracticeMode] = useState(false)
  const [yachtTutorialMode, setYachtTutorialMode] = useState(false)

  // 게임 시작 시점에 픽스되는 정렬된 플레이어 목록.
  // 카운트다운 → 게임 페이지로 넘어가는 동안 이 값 사용.
  const [orderedPlayersAtStart, setOrderedPlayersAtStart] = useState(null)
  const [pendingGame, setPendingGame] = useState(null)  // { gameId, mode, gameType }

  // 시작 플레이어 / 진행 방향 (lobby 입장 전 상태로 유지됨)
  const [firstPlayerId, setFirstPlayerId] = useState(null)
  const [direction, setDirection] = useState('cw')

  const { state, connected, send } = useWebSocket('/ws/tablet', {
    onAudioMessage: audioApi.enqueue,
  })
  useAudioPlayer(send)
  useBenchBridge(send)

  const phase = state?.phase ?? 'player_setup'
  const players = state?.players ?? []
  const registeringId = state?.registering_player_id ?? null
  const seatStep = state?.seat_step ?? 'idle'

  // 등록된 플레이어가 바뀌면 firstPlayerId가 유효한지 확인하고, 없으면 첫 번째 등록 플레이어로
  const registeredPlayers = useMemo(
    () => players.filter((p) => p.playername),
    [players],
  )
  useEffect(() => {
    if (registeredPlayers.length === 0) {
      if (firstPlayerId !== null) setFirstPlayerId(null)
      return
    }
    if (!registeredPlayers.find((p) => p.player_id === firstPlayerId)) {
      const byPos = [...registeredPlayers].sort(
        (a, b) => (a.position ?? 0) - (b.position ?? 0),
      )
      setFirstPlayerId(byPos[0].player_id)
    }
  }, [registeredPlayers, firstPlayerId])

  // 사운드 trigger (좌석 등록 효과음)
  useEffect(() => {
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

  // 좌석 등록 페이지에서 사용할 콜백
  const goLobby = () => setPage('lobby')

  // Lobby에서 게임 카드 선택 → 카운트다운 진입
  const handleSelectGame = (gameId, mode) => {
    // 진행 순서 픽스
    const ordered = orderForTurn(registeredPlayers, firstPlayerId, direction)
    if (ordered.length === 0) return

    // UI용 플레이어 목록 (Countdown 화면 + 게임 페이지로 전달)
    const ui = ordered.map((p, i) => ({
      id: p.player_id,
      player_id: p.player_id,
      playername: p.playername,
      name: p.playername,
      position: p.position,
      color: colorForIndex(i),
      registered: p.registered,
    }))
    setOrderedPlayersAtStart(ui)

    // mode → 백엔드 game_type 매핑
    // 늑대인간 "튜토리얼 모드" = 연습 모드(frontend-only 플래그). game_type은 'werewolf' 그대로.
    let gameType = gameId
    if (gameId === 'yacht' && mode === 'tutorial') gameType = 'yacht_tutorial'
    setPendingGame({ gameId, mode, gameType })
    setIsPracticeMode(gameId === 'werewolf' && mode === 'tutorial')
    setYachtTutorialMode(gameId === 'yacht' && mode === 'tutorial')

    setPage('countdown')
  }

  // Countdown 0초 → 백엔드에 select_game 보내고 게임 페이지로 이동
  const handleCountdownReady = () => {
    if (!pendingGame) return
    send('select_game', { game_type: pendingGame.gameType })
    const target = pendingGame.gameId === 'yacht' ? 'yacht' : 'werewolf'
    setPage(target)
    setPendingGame(null)
  }

  // Countdown 취소 → lobby로 복귀 (백엔드 미통신, frontend state만 롤백)
  const handleCountdownCancel = () => {
    setPendingGame(null)
    setOrderedPlayersAtStart(null)
    setYachtTutorialMode(false)
    setIsPracticeMode(false)
    setPage('lobby')
  }

  if (page === 'seat') {
    return (
      <SeatRegistration
        players={players}
        registeringId={registeringId}
        seatStep={seatStep}
        connected={connected}
        firstPlayerId={firstPlayerId}
        direction={direction}
        onChangeFirst={setFirstPlayerId}
        onChangeDirection={setDirection}
        send={send}
        onStart={goLobby}
      />
    )
  }

  if (page === 'lobby') {
    return (
      <Lobby
        players={players}
        connected={connected}
        onBack={() => setPage('seat')}
        onSelectGame={handleSelectGame}
      />
    )
  }

  if (page === 'countdown' && pendingGame && orderedPlayersAtStart) {
    return (
      <Countdown
        players={orderedPlayersAtStart}
        gameId={pendingGame.gameType}
        mode={pendingGame.mode}
        onCancel={handleCountdownCancel}
        onReady={handleCountdownReady}
      />
    )
  }

  if (page === 'yacht') {
    const playersForGame = orderedPlayersAtStart ?? registeredPlayers
    return (
      <YachtGame
        players={playersForGame}
        tutorialMode={yachtTutorialMode}
        onExit={() => { setOrderedPlayersAtStart(null); setPage('lobby') }}
        onChangePlayers={() => { setOrderedPlayersAtStart(null); setPage('seat') }}
      />
    )
  }

  if (page === 'werewolf') {
    const playersForGame = orderedPlayersAtStart ?? registeredPlayers
    return (
      <WerewolfGame
        key={gameKey}
        players={playersForGame}
        wsState={state}
        send={send}
        isPracticeMode={isPracticeMode}
        onChangePlayers={() => { setOrderedPlayersAtStart(null); setIsPracticeMode(false); setPage('seat') }}
        onChangeGame={() => { setOrderedPlayersAtStart(null); setIsPracticeMode(false); setPage('lobby') }}
        onRestart={() => setGameKey((k) => k + 1)}
      />
    )
  }

  return null
}
