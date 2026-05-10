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
    background: '#f6f7f4',
    color: '#171917',
    fontFamily: '"Segoe UI", Arial, sans-serif',
    padding: 28,
    boxSizing: 'border-box',
  },
  shell: {
    width: 'min(1120px, calc(100vw - 48px))',
    minHeight: 600,
    margin: '0 auto',
    background: 'rgba(255,255,255,0.96)',
    border: '1px solid #dfe3dc',
    borderRadius: 10,
    boxShadow: '0 18px 42px rgba(31,35,29,0.08)',
    display: 'grid',
    gridTemplateColumns: '1.05fr 0.95fr',
    overflow: 'hidden',
  },
  header: {
    gridColumn: '1 / -1',
    height: 72,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 28px',
    boxSizing: 'border-box',
    borderBottom: '1px solid #edf0ea',
  },
  title: { fontSize: 22, fontWeight: 750, letterSpacing: 0 },
  headerActions: { display: 'flex', gap: 12 },
  button: {
    border: '1px solid #d6dbd3',
    borderRadius: 8,
    background: '#f7f8f5',
    color: '#1c211a',
    padding: '9px 16px',
    fontSize: 16,
    fontWeight: 700,
    cursor: 'pointer',
  },
  buttonDisabled: {
    opacity: 0.45,
    cursor: 'not-allowed',
  },
  buttonSmall: {
    border: '1px solid #d6dbd3',
    borderRadius: 8,
    background: '#f7f8f5',
    color: '#1c211a',
    padding: '9px 14px',
    fontSize: 15,
    fontWeight: 700,
    cursor: 'pointer',
  },
  primaryButton: {
    background: '#1f7a4f',
    borderColor: '#1f7a4f',
    color: '#fff',
    boxShadow: '0 8px 18px rgba(31,122,79,0.18)',
  },
  main: { padding: '28px', boxSizing: 'border-box' },
  phaseText: {
    color: '#8b9288',
    width: 'min(1120px, calc(100vw - 48px))',
    margin: '0 auto 10px',
    fontSize: 12,
    fontWeight: 800,
    letterSpacing: 1,
  },
  turnRow: { display: 'flex', alignItems: 'center', gap: 16, marginBottom: 38 },
  turnBadge: {
    background: '#ecf4ed',
    color: '#1f6f49',
    border: '1px solid #d5e7d8',
    borderRadius: 999,
    padding: '10px 18px',
    fontSize: 17,
    fontWeight: 800,
  },
  roundText: { fontSize: 16, fontWeight: 750, color: '#555d52' },
  clips: { display: 'flex', gap: 8, alignItems: 'center', marginBottom: 18, color: '#626a5f', fontWeight: 700 },
  clip: active => ({
    width: 14,
    height: 14,
    borderRadius: '50%',
    background: active ? '#1f7a4f' : '#dce1d9',
    boxShadow: active ? '0 0 0 4px rgba(31,122,79,0.12)' : 'none',
  }),
  diceTray: {
    width: 365,
    minHeight: 118,
    background: '#f0f2ee',
    border: '1px solid #dfe3dc',
    borderRadius: 10,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 14,
    marginBottom: 18,
  },
  die: (kept, interactive = false) => ({
    width: 50,
    height: 50,
    border: kept ? '1px solid #1f7a4f' : '1px solid #d0d5cd',
    borderRadius: 8,
    background: kept ? '#1f7a4f' : '#fff',
    color: kept ? '#fff' : '#1b1f19',
    fontSize: 21,
    fontWeight: 800,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: interactive ? 'pointer' : 'default',
    boxShadow: kept ? '0 8px 16px rgba(31,122,79,0.16)' : '0 4px 10px rgba(31,35,29,0.05)',
  }),
  actionRow: { display: 'flex', gap: 10, flexWrap: 'wrap' },
  rollMessage: {
    marginTop: 42,
    maxWidth: 430,
    padding: '14px 16px',
    border: '1px solid #dfe8db',
    borderRadius: 10,
    background: '#f7faf5',
    color: '#364034',
    fontSize: 16,
    fontWeight: 650,
    lineHeight: 1.45,
  },
  scoreWrap: {
    padding: '28px 28px 28px 0',
    boxSizing: 'border-box',
  },
  scoreboard: {
    borderCollapse: 'separate',
    borderSpacing: 0,
    width: '100%',
    fontSize: 15,
    overflow: 'hidden',
    border: '1px solid #e2e6df',
    borderRadius: 10,
  },
  th: { background: '#f4f6f1', textAlign: 'left', padding: '12px 14px', fontWeight: 800, color: '#343a31' },
  tdName: { padding: '10px 14px', borderBottom: '1px solid #edf0ea', fontWeight: 700 },
  tdScore: { padding: '10px 14px', borderBottom: '1px solid #edf0ea', textAlign: 'right', fontVariantNumeric: 'tabular-nums' },
  scoreRow: clickable => ({
    background: clickable ? '#dff0ff' : '#fff',
    cursor: clickable ? 'pointer' : 'default',
  }),
  bonusRow: { background: '#f3f8ef', color: '#4d7538', fontWeight: 800 },
  bonusCell: {
    display: 'flex',
    justifyContent: 'flex-end',
    alignItems: 'center',
    gap: 8,
  },
  bonusBadge: earned => ({
    display: 'inline-flex',
    alignItems: 'center',
    height: 22,
    padding: '0 8px',
    borderRadius: 999,
    background: earned ? '#1f7a4f' : '#e5eae2',
    color: earned ? '#fff' : '#6a7167',
    fontSize: 12,
    fontWeight: 850,
  }),
  totalRow: { fontWeight: 800 },
  modalShade: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(22,27,20,0.18)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backdropFilter: 'blur(2px)',
  },
  leaderboard: {
    width: 'min(920px, calc(100vw - 64px))',
    background: '#fff',
    border: '1px solid #dfe3dc',
    borderRadius: 10,
    overflow: 'hidden',
    boxShadow: '0 20px 60px rgba(31,35,29,0.16)',
  },
  leaderboardHeader: {
    height: 68,
    background: '#f4f6f1',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 20,
    fontWeight: 800,
    position: 'relative',
    borderBottom: '1px solid #e2e6df',
  },
  close: {
    position: 'absolute',
    right: 22,
    top: 15,
    color: '#6e766a',
    fontSize: 24,
    border: 0,
    background: 'transparent',
    cursor: 'pointer',
  },
  endShell: {
    width: 'min(920px, calc(100vw - 48px))',
    minHeight: 560,
    margin: '0 auto',
    background: '#fff',
    border: '1px solid #dfe3dc',
    borderRadius: 10,
    boxShadow: '0 18px 42px rgba(31,35,29,0.08)',
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
    background: '#f4f6f1',
    border: '1px solid #e2e6df',
    borderRadius: 8,
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
  const statusMessage = useMemo(() => {
    const latest = messages.find(m => m.msg_type === 'tts_play' || m.msg_type === 'error')
    return latest?.payload?.text || latest?.payload?.message || state?.last_message
  }, [messages, state?.last_message])
  const canUndo = state?.can_undo ?? true
  const canManualRoll =
    ['AWAITING_ROLL', 'AWAITING_KEEP'].includes(state?.phase) &&
    Number(state?.remaining_rolls || 0) > 0

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
      <div style={s.phaseText}>
        {state.phase}
      </div>
      <div style={s.shell}>
        <header style={s.header}>
          <div style={s.title}>요트다이스</div>
          <div style={s.headerActions}>
            <button
              style={{ ...s.button, ...(canUndo ? {} : s.buttonDisabled) }}
              onClick={() => send('UNDO_ROUND')}
              disabled={!canUndo}
            >
              되돌리기
            </button>
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
                style={s.die(Boolean(state.keep_mask?.[index]), canToggleKeep(state))}
                onClick={() => toggleKeep(index, state, send)}
                disabled={!canToggleKeep(state)}
                title="보관"
              >
                {value}
              </button>
            ))}
          </div>

          <div style={s.actionRow}>
            <button style={s.buttonSmall} onClick={() => setLeaderboardOpen(true)}>리더보드 보기</button>
            {canManualRoll && (
              <button style={{ ...s.buttonSmall, ...s.primaryButton }} onClick={() => send('ROLL_DICE')}>굴리기</button>
            )}
          </div>

          <div style={s.rollMessage}>{statusMessage}</div>
        </main>

        <aside style={s.scoreWrap}>
          <ScoreTable state={state} currentOnly onScore={(category) => scoreCategory(category, state, send)} />
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
            const earned = subtotal >= 63
            const remaining = Math.max(0, 63 - subtotal)
            return (
              <tr key={key} style={s.bonusRow}>
                <td style={s.tdName}>{label}</td>
                <td style={s.tdScore}>
                  <div style={s.bonusCell}>
                    <span>{subtotal} / 63</span>
                    <span style={s.bonusBadge(earned)}>
                      {earned ? '+35' : `${remaining}점 남음`}
                    </span>
                  </div>
                </td>
              </tr>
            )
          }

          const score = player?.scores?.[key]
          const hasScore = score != null
          const available = compact ? hasScore : state.available_categories?.includes(key)
          const canScore =
            !compact &&
            player?.player_id === state.current_player_id &&
            available &&
            state.dice_values?.length
          const displayScore = hasScore ? score : (compact ? '—' : predictedScore(key, state))

          return (
            <tr key={key} style={s.scoreRow(canScore)} onClick={canScore ? () => onScore(key) : undefined}>
              <td style={{ ...s.tdName, color: !hasScore && !available ? '#aaa' : '#111' }}>{label}</td>
              <td style={{ ...s.tdScore, color: hasScore ? '#111' : '#999' }}>
                {displayScore}
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

function canToggleKeep(state) {
  return Boolean(state.dice_values?.length) && state.phase !== 'AWAITING_SCORE'
}

function toggleKeep(index, state, send) {
  if (!canToggleKeep(state)) return
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
