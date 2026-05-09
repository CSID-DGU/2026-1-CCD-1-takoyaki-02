import { useEffect, useMemo, useState } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'

const CATEGORY_LABELS = [
  ['ones', 'Aces'],
  ['twos', 'Twos'],
  ['threes', 'Threes'],
  ['fours', 'Fours'],
  ['fives', 'Fives'],
  ['sixes', 'Sixes'],
  ['bonus', '상단 보너스'],
  ['full_house', 'Full House'],
  ['four_of_a_kind', '4 of a Kind'],
  ['small_straight', 'S. Straight'],
  ['large_straight', 'L. Straight'],
  ['yacht', 'Yacht'],
  ['choice', 'Choice'],
]

const UPPER = ['ones', 'twos', 'threes', 'fours', 'fives', 'sixes']
const DISPLAY_CATEGORIES = CATEGORY_LABELS.filter(([key]) => key !== 'bonus').map(([key]) => key)

const s = {
  page: {
    minHeight: '100vh',
    background: '#f4f4f4',
    color: '#111',
    fontFamily: 'Arial, "Segoe UI", sans-serif',
    padding: 24,
    boxSizing: 'border-box',
  },
  shell: {
    width: 'min(1120px, calc(100vw - 48px))',
    minHeight: 600,
    margin: '0 auto',
    background: '#fff',
    border: '2px solid #555',
    display: 'grid',
    gridTemplateColumns: '1.05fr 0.95fr',
  },
  header: {
    gridColumn: '1 / -1',
    height: 66,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 28px',
    boxSizing: 'border-box',
  },
  title: { fontSize: 21, fontWeight: 600 },
  headerActions: { display: 'flex', gap: 12 },
  button: {
    border: 'none',
    background: '#dedede',
    color: '#111',
    padding: '9px 17px',
    fontSize: 18,
    fontWeight: 600,
    cursor: 'pointer',
  },
  buttonSmall: {
    border: 'none',
    background: '#e6e6e6',
    color: '#111',
    padding: '8px 13px',
    fontSize: 17,
    cursor: 'pointer',
  },
  main: { padding: '10px 28px 28px', boxSizing: 'border-box' },
  turnRow: { display: 'flex', alignItems: 'center', gap: 28, marginBottom: 42 },
  turnBadge: { background: '#d8d8d8', padding: '10px 18px', fontSize: 18 },
  roundText: { fontSize: 18, fontWeight: 600 },
  clips: { display: 'flex', gap: 7, alignItems: 'center', marginBottom: 22 },
  clip: active => ({
    width: 18,
    height: 18,
    borderRadius: '50%',
    background: active ? '#15bd42' : '#d9d9d9',
    boxShadow: active ? 'inset 0 -2px 4px rgba(0,0,0,0.2)' : 'inset 0 2px 4px rgba(0,0,0,0.12)',
  }),
  diceTray: {
    width: 365,
    minHeight: 106,
    background: '#d7d7d7',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 18,
    marginBottom: 16,
  },
  die: kept => ({
    width: 44,
    height: 44,
    border: 'none',
    background: kept ? '#18bf68' : '#bfbfbf',
    fontSize: 21,
    fontWeight: 700,
    cursor: 'pointer',
  }),
  hint: { marginTop: 54, fontSize: 18, lineHeight: 1.35 },
  scoreWrap: { padding: '10px 28px 28px 0', boxSizing: 'border-box' },
  scoreboard: { borderCollapse: 'collapse', width: '100%', fontSize: 15 },
  th: { background: '#f2f1e9', textAlign: 'left', padding: '10px 12px', fontWeight: 700 },
  tdName: { padding: '9px 12px', borderBottom: '1px solid #e4e4e4', fontWeight: 700 },
  tdScore: { padding: '9px 12px', borderBottom: '1px solid #e4e4e4', textAlign: 'right' },
  scoreRow: clickable => ({
    background: clickable ? '#dff0ff' : '#fff',
    cursor: clickable ? 'pointer' : 'default',
  }),
  bonusRow: { background: '#eef8e5', color: '#477232', fontWeight: 700 },
  totalRow: { fontWeight: 800 },
  footerLine: { minHeight: 24, color: '#777', fontSize: 14, marginTop: 12 },
  modalShade: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.08)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  leaderboard: {
    width: 'min(920px, calc(100vw - 64px))',
    background: '#fff',
    border: '2px solid #555',
  },
  leaderboardHeader: {
    height: 72,
    background: '#d9d9d9',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 22,
    position: 'relative',
  },
  close: {
    position: 'absolute',
    right: 22,
    top: 16,
    color: 'red',
    fontSize: 28,
    border: 0,
    background: 'transparent',
    cursor: 'pointer',
  },
  endShell: {
    width: 'min(920px, calc(100vw - 48px))',
    minHeight: 560,
    margin: '0 auto',
    background: '#fff',
    border: '2px solid #555',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  endPanel: { width: 430 },
  winner: { fontSize: 36, fontWeight: 800, textAlign: 'center', marginBottom: 44 },
  finalScoreTitle: { fontSize: 22, marginBottom: 20 },
  rankRow: {
    display: 'flex',
    justifyContent: 'space-between',
    background: '#d9d9d9',
    padding: '15px 22px',
    marginBottom: 14,
    fontSize: 22,
  },
  endActions: { display: 'flex', gap: 16, justifyContent: 'center', marginTop: 26 },
}

export default function YachtGame({ players, onExit, onChangePlayers }) {
  const { state, connected, messages, send } = useWebSocket('/ws/yacht')
  const [leaderboardOpen, setLeaderboardOpen] = useState(false)

  useEffect(() => {
    if (!connected) return
    send('START_YACHT', { players: normalizePlayers(players) })
  }, [connected])

  const currentPlayer = useMemo(
    () => state?.players?.find(p => p.player_id === state.current_player_id),
    [state],
  )
  const round = (currentPlayer?.scores ? Object.keys(currentPlayer.scores).length : 0) + 1
  const ranked = useMemo(
    () => [...(state?.players || [])].sort((a, b) => b.total - a.total),
    [state],
  )

  if (!state) {
    return (
      <div style={s.page}>
        <div style={s.shell}>
          <div style={s.header}>
            <div style={s.title}>요트다이스</div>
            <div>{connected ? '게임 준비 중' : '서버 연결 중'}</div>
          </div>
        </div>
      </div>
    )
  }

  if (state.phase === 'GAME_END') {
    const winner = ranked[0]
    return (
      <div style={s.page}>
        <div style={s.endShell}>
          <div style={s.endPanel}>
            <div style={s.winner}>{winner?.playername || '플레이어'} 님 승리!</div>
            <div style={s.finalScoreTitle}>최종 점수</div>
            {ranked.map(player => (
              <div key={player.player_id} style={s.rankRow}>
                <strong>{player.playername}</strong>
                <span>{player.total}</span>
              </div>
            ))}
            <div style={s.endActions}>
              <button style={s.buttonSmall} onClick={onChangePlayers}>플레이어 변경</button>
              <button style={s.buttonSmall} onClick={onExit}>게임 변경</button>
              <button style={s.buttonSmall} onClick={() => send('RESTART')}>게임 재시작</button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={s.page}>
      <div style={{ color: '#b8b8b8', width: 'min(1120px, calc(100vw - 48px))', margin: '0 auto 8px' }}>
        {state.phase === 'AWAITING_ROLL' ? 'AWAITING_ROLL' : 'SCORE_RECORDED'}
      </div>
      <div style={s.shell}>
        <header style={s.header}>
          <div style={s.title}>요트다이스</div>
          <div style={s.headerActions}>
            <button style={s.button} onClick={() => send('RESTART')}>되돌리기</button>
            <button style={s.button} onClick={onExit}>나가기</button>
          </div>
        </header>

        <main style={s.main}>
          <div style={s.turnRow}>
            <div style={s.turnBadge}>{currentPlayer?.playername || '-'} 님 차례</div>
            <div style={s.roundText}>라운드 {round} / 12</div>
          </div>

          <div style={s.clips}>
            <span>굴림</span>
            {[0, 1, 2].map(i => <span key={i} style={s.clip(i < state.roll_count)} />)}
          </div>

          <div style={s.diceTray}>
            {(state.dice_values?.length ? state.dice_values : ['-', '-', '-', '-', '-']).map((value, index) => (
              <button
                key={index}
                style={s.die(Boolean(state.keep_mask?.[index]))}
                onClick={() => toggleKeep(index, state, send)}
                disabled={!state.dice_values?.length}
                title="보관"
              >
                {value}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <button style={s.buttonSmall} onClick={() => setLeaderboardOpen(true)}>리더보드 보기</button>
            {state.phase === 'AWAITING_ROLL' && (
              <button style={s.buttonSmall} onClick={() => send('ROLL_DICE')}>굴리기</button>
            )}
            {state.phase === 'AWAITING_KEEP' && (
              <button
                style={s.buttonSmall}
                onClick={() => send('DICE_REROLL_REQUESTED', { keep_mask: state.keep_mask })}
              >
                다시 굴리기
              </button>
            )}
          </div>

          <div style={s.hint}>
            {state.phase === 'AWAITING_ROLL'
              ? '미사용 족보: 검은 글씨 → 이미 사용했거나 불가능: 회색'
              : '가능한 족보: 파란색 배경 → 클릭하면 점수 기록'}
          </div>
        </main>

        <aside style={s.scoreWrap}>
          <ScoreTable state={state} currentOnly onScore={(category) => scoreCategory(category, state, send)} />
          <div style={s.footerLine}>
            {messages.find(m => m.msg_type === 'tts_play')?.payload?.text || state.last_message}
          </div>
        </aside>
      </div>

      {leaderboardOpen && (
        <div style={s.modalShade}>
          <div style={s.leaderboard}>
            <div style={s.leaderboardHeader}>
              리더보드
              <button style={s.close} onClick={() => setLeaderboardOpen(false)}>x</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${state.players.length}, 1fr)` }}>
              {state.players.map(player => (
                <div key={player.player_id}>
                  <ScoreTable state={{ ...state, players: [player], current_player_id: player.player_id }} compact />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreTable({ state, currentOnly = false, compact = false, onScore }) {
  const players = currentOnly
    ? state.players.filter(player => player.player_id === state.current_player_id)
    : state.players
  const player = players[0]

  return (
    <table style={s.scoreboard}>
      <thead>
        <tr><th colSpan="2" style={s.th}>점수판 · {player?.playername || '-'}</th></tr>
      </thead>
      <tbody>
        {CATEGORY_LABELS.map(([key, label]) => {
          if (key === 'bonus') {
            const subtotal = upperSubtotal(player?.scores || {})
            return (
              <tr key={key} style={s.bonusRow}>
                <td style={s.tdName}>{label}</td>
                <td style={s.tdScore}>{Math.min(subtotal, 63)} / 63</td>
              </tr>
            )
          }

          const score = player?.scores?.[key]
          const available = state.available_categories?.includes(key)
          const canScore =
            !compact &&
            player?.player_id === state.current_player_id &&
            available &&
            state.dice_values?.length

          return (
            <tr key={key} style={s.scoreRow(canScore)} onClick={canScore ? () => onScore(key) : undefined}>
              <td style={{ ...s.tdName, color: score == null && !available ? '#aaa' : '#111' }}>{label}</td>
              <td style={{ ...s.tdScore, color: score == null ? '#999' : '#111' }}>
                {score ?? predictedScore(key, state)}
              </td>
            </tr>
          )
        })}
        <tr style={s.totalRow}>
          <td style={s.tdName}>합계</td>
          <td style={s.tdScore}>{player?.total ?? 0}</td>
        </tr>
      </tbody>
    </table>
  )
}

function normalizePlayers(players) {
  if (!players?.length) {
    return [
      { player_id: 'p1', playername: '형승' },
      { player_id: 'p2', playername: '병진' },
      { player_id: 'p3', playername: '성민' },
    ]
  }
  return players.map((player, index) => ({
    player_id: String(player.player_id || player.id || `p${index + 1}`),
    playername: String(player.playername || player.name || `플레이어 ${index + 1}`),
  }))
}

function toggleKeep(index, state, send) {
  if (!state.dice_values?.length || state.phase === 'AWAITING_SCORE') return
  const keep = [...state.keep_mask]
  keep[index] = !keep[index]
  send('DICE_KEEP_SELECTED', { keep_mask: keep })
}

function scoreCategory(category, state, send) {
  if (!DISPLAY_CATEGORIES.includes(category)) return
  send('SCORE_CATEGORY_SELECTED', { category }, state.current_player_id)
}

function upperSubtotal(scores) {
  return UPPER.reduce((sum, key) => sum + Number(scores[key] || 0), 0)
}

function predictedScore(category, state) {
  if (!state.available_categories?.includes(category)) return '—'
  if (!state.dice_values?.length) return '—'
  return previewScore(category, state.dice_values)
}

function previewScore(category, dice) {
  const counts = dice.reduce((acc, value) => ({ ...acc, [value]: (acc[value] || 0) + 1 }), {})
  const sum = dice.reduce((acc, value) => acc + Number(value), 0)
  const unique = new Set(dice)
  const upperFace = {
    ones: 1,
    twos: 2,
    threes: 3,
    fours: 4,
    fives: 5,
    sixes: 6,
  }[category]
  if (upperFace) return dice.filter(value => value === upperFace).reduce((acc, value) => acc + value, 0)
  if (category === 'choice') return sum
  if (category === 'four_of_a_kind') return Object.values(counts).some(count => count >= 4) ? sum : 0
  if (category === 'full_house') {
    return JSON.stringify(Object.values(counts).sort()) === JSON.stringify([2, 3]) ? sum : 0
  }
  if (category === 'small_straight') {
    return [[1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6]].some(line =>
      line.every(value => unique.has(value)),
    )
      ? 15
      : 0
  }
  if (category === 'large_straight') return unique.size === 5 && (!unique.has(1) || !unique.has(6)) ? 30 : 0
  if (category === 'yacht') return Object.values(counts).some(count => count === 5) ? 50 : 0
  return '—'
}
