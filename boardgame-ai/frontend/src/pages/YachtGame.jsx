import { useEffect, useMemo, useRef, useState } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { audio as audioApi, useAudioPlayer } from '../hooks/useAudioPlayer'

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
const TUTORIAL_INTRO_TEXT =
  '요트다이스는 플레이어가 순서대로 주사위 5개를 굴리고, 나온 눈 조합을 가장 유리한 점수 칸에 기록해 총점을 겨루는 게임입니다. 한 턴에는 최대 세 번까지 굴릴 수 있고, 마음에 드는 주사위는 킵한 뒤 나머지만 다시 굴릴 수 있습니다.'

const s = {
  page: {
    position: 'absolute',
    inset: 0,
    background: 'var(--bg-app)',
    color: 'var(--fg)',
    fontFamily: 'var(--font)',
    padding: '56px 0 0',
    boxSizing: 'border-box',
    overflow: 'hidden',
  },
  shell: {
    width: '100vw',
    height: 'calc(100vh - 56px)',
    margin: 0,
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-soft)',
    borderRadius: 0,
    boxShadow: 'none',
    display: 'grid',
    gridTemplateColumns: '1.05fr 0.95fr',
    gridTemplateRows: '1fr',
    overflow: 'hidden',
  },
  header: {
    gridColumn: '1 / -1',
    height: 64,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 28px',
    boxSizing: 'border-box',
    borderBottom: '1px solid var(--border-soft)',
  },
  title: { fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--fg)' },
  headerActions: { display: 'flex', gap: 12 },
  button: {
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    background: 'var(--bg-elev)',
    color: 'var(--fg)',
    padding: '9px 16px',
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    letterSpacing: '-0.01em',
  },
  buttonDisabled: {
    opacity: 0.45,
    cursor: 'not-allowed',
  },
  buttonSmall: {
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    background: 'var(--bg-elev)',
    color: 'var(--fg)',
    padding: '10px 16px',
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
  },
  primaryButton: {
    background: 'var(--yacht)',
    borderColor: 'transparent',
    color: '#17110c',
    boxShadow: '0 1px 0 rgba(255,255,255,0.25) inset',
  },
  main: { padding: '36px 42px', boxSizing: 'border-box' },
  phaseText: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 56,
    padding: '0 22px',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    color: 'var(--fg-mute)',
    fontSize: 14,
    fontWeight: 600,
    letterSpacing: 0,
    background: 'linear-gradient(180deg, color-mix(in oklch, var(--bg-app) 85%, transparent), transparent)',
    zIndex: 5,
  },
  phaseTitle: {
    color: 'var(--fg)',
    fontWeight: 800,
    fontSize: 20,
    letterSpacing: '-0.02em',
  },
  phaseActions: {
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  turnRow: { display: 'flex', alignItems: 'center', gap: 20, marginBottom: 46 },
  turnBadge: {
    background: 'color-mix(in oklch, var(--yacht) 18%, var(--bg-elev))',
    color: 'color-mix(in oklch, var(--yacht) 80%, var(--fg))',
    border: '1px solid color-mix(in oklch, var(--yacht) 35%, transparent)',
    borderRadius: 999,
    padding: '10px 18px',
    fontSize: 24,
    fontWeight: 800,
  },
  roundText: { fontSize: 21, fontWeight: 750, color: 'var(--fg-soft)' },
  clips: { display: 'flex', gap: 12, alignItems: 'center', marginBottom: 24, color: 'var(--fg-mute)', fontWeight: 750, fontSize: 19 },
  clip: active => ({
    width: 18,
    height: 18,
    borderRadius: '50%',
    background: active ? 'var(--yacht)' : 'var(--bg-elev)',
    boxShadow: active ? '0 0 0 4px color-mix(in oklch, var(--yacht) 20%, transparent)' : 'none',
  }),
  diceTray: {
    width: 'min(520px, 100%)',
    minHeight: 150,
    background: 'var(--bg-elev)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 18,
    marginBottom: 24,
  },
  die: (kept, interactive = false) => ({
    width: 68,
    height: 68,
    border: kept ? '1px solid var(--yacht)' : '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    background: kept ? 'var(--yacht)' : 'var(--bg-surface)',
    color: kept ? '#17110c' : 'var(--fg)',
    fontSize: 28,
    fontWeight: 800,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: interactive ? 'pointer' : 'default',
    boxShadow: kept ? '0 8px 18px color-mix(in oklch, var(--yacht) 25%, transparent)' : 'var(--shadow-sm)',
  }),
  actionRow: { display: 'flex', gap: 12, flexWrap: 'wrap' },
  rollMessage: {
    marginTop: 52,
    maxWidth: 560,
    padding: '18px 20px',
    border: '1px solid var(--border-soft)',
    borderRadius: 'var(--radius)',
    background: 'var(--bg-elev)',
    color: 'var(--fg-soft)',
    fontSize: 20,
    fontWeight: 650,
    lineHeight: 1.45,
  },
  tutorialBubble: {
    maxWidth: 590,
    marginBottom: 24,
    padding: '17px 20px',
    border: '1px solid color-mix(in oklch, var(--yacht) 35%, transparent)',
    borderRadius: 'var(--radius)',
    background: 'color-mix(in oklch, var(--yacht) 12%, var(--bg-elev))',
    color: 'var(--fg)',
    fontSize: 19,
    fontWeight: 750,
    lineHeight: 1.42,
    boxShadow: 'var(--shadow-sm)',
  },
  introShell: {
    width: 'min(900px, calc(100vw - 48px))',
    minHeight: 'calc(100vh - 104px)',
    margin: '0 auto',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-soft)',
    borderRadius: 'var(--radius-xl)',
    boxShadow: 'var(--shadow-lg)',
    padding: 42,
    boxSizing: 'border-box',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
  },
  introKicker: {
    color: 'var(--yacht)',
    fontSize: 14,
    fontWeight: 850,
    marginBottom: 12,
  },
  introTitle: {
    fontSize: 34,
    fontWeight: 850,
    marginBottom: 22,
    color: 'var(--fg)',
  },
  introText: {
    color: 'var(--fg-soft)',
    fontSize: 18,
    fontWeight: 650,
    lineHeight: 1.65,
    marginBottom: 26,
  },
  introList: {
    display: 'grid',
    gap: 10,
    margin: '0 0 30px',
    padding: 0,
    listStyle: 'none',
    color: 'var(--fg-soft)',
    fontSize: 16,
    fontWeight: 700,
    lineHeight: 1.45,
  },
  scoreWrap: {
    padding: '36px 42px 36px 0',
    boxSizing: 'border-box',
  },
  scoreHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    position: 'relative',
  },
  helpButton: {
    width: 24,
    height: 24,
    borderRadius: '50%',
    border: '1px solid var(--border)',
    background: 'var(--bg-elev)',
    color: 'var(--fg-soft)',
    fontSize: 14,
    fontWeight: 800,
    cursor: 'help',
    boxShadow: 'var(--shadow-sm)',
    padding: 0,
    flexShrink: 0,
  },
  scoreHelpPopover: {
    position: 'absolute',
    top: 32,
    right: 0,
    width: 400,
    zIndex: 20,
    padding: '16px 18px',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    background: 'var(--bg-elev)',
    boxShadow: 'var(--shadow-lg)',
    color: 'var(--fg-soft)',
  },
  helpList: {
    display: 'grid',
    gap: 7,
    margin: 0,
    padding: 0,
    listStyle: 'none',
    fontSize: 13,
    lineHeight: 1.35,
  },
  helpItemName: {
    display: 'inline-block',
    minWidth: 104,
    fontWeight: 800,
    color: 'var(--yacht)',
  },
  scoreboard: {
    borderCollapse: 'separate',
    borderSpacing: 0,
    width: '100%',
    fontSize: 18,
    overflow: 'hidden',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
  },
  th: { background: 'var(--bg-elev)', textAlign: 'left', padding: '15px 18px', fontWeight: 800, color: 'var(--fg)', fontSize: 19 },
  tdName: { padding: '13px 18px', borderBottom: '1px solid var(--border-soft)', fontWeight: 700 },
  tdScore: { padding: '13px 18px', borderBottom: '1px solid var(--border-soft)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' },
  scoreRow: clickable => ({
    background: clickable ? 'color-mix(in oklch, var(--info) 16%, var(--bg-surface))' : 'var(--bg-surface)',
    cursor: clickable ? 'pointer' : 'default',
  }),
  bonusRow: { background: 'color-mix(in oklch, var(--yacht) 10%, var(--bg-surface))', color: 'color-mix(in oklch, var(--yacht) 75%, var(--fg))', fontWeight: 800 },
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
    background: earned ? 'var(--yacht)' : 'var(--bg-elev)',
    color: earned ? '#17110c' : 'var(--fg-mute)',
    fontSize: 12,
    fontWeight: 850,
  }),
  totalRow: { fontWeight: 800 },
  modalShade: {
    position: 'fixed',
    inset: 0,
    background: 'color-mix(in oklch, var(--bg-deep) 70%, transparent)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backdropFilter: 'blur(2px)',
  },
  leaderboard: {
    width: 'calc(100vw - 24px)',
    maxHeight: 'calc(100vh - 24px)',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-soft)',
    borderRadius: 'var(--radius-xl)',
    overflow: 'hidden',
    boxShadow: 'var(--shadow-lg)',
  },
  leaderboardHeader: {
    height: 68,
    background: 'var(--bg-elev)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 20,
    fontWeight: 800,
    position: 'relative',
    borderBottom: '1px solid var(--border)',
  },
  close: {
    position: 'absolute',
    right: 22,
    top: 15,
    color: 'var(--fg-mute)',
    fontSize: 24,
    border: 0,
    background: 'transparent',
    cursor: 'pointer',
  },
  endShell: {
    width: '100vw',
    minHeight: 'calc(100vh - 56px)',
    margin: 0,
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-soft)',
    borderRadius: 0,
    boxShadow: 'none',
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
    background: 'var(--bg-elev)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '15px 22px',
    marginBottom: 14,
    fontSize: 22,
  },
  endActions: { display: 'flex', gap: 16, justifyContent: 'center', marginTop: 26 },
  endText: {
    textAlign: 'center',
    color: 'var(--fg-soft)',
    fontSize: 17,
    lineHeight: 1.5,
    marginBottom: 28,
  },
}

export default function YachtGame({ players, tutorialMode = false, onExit, onChangePlayers }) {
  const { state, connected, messages, send } = useWebSocket('/ws/yacht', {
    onAudioMessage: audioApi.enqueue,
  })
  // /ws/yacht 채널로도 audio_ack가 흐르도록 등록 (FSM 멘트는 이 채널로 옴).
  useAudioPlayer(send)
  const [leaderboardOpen, setLeaderboardOpen] = useState(false)
  const [tutorialIntroSeen, setTutorialIntroSeen] = useState(!tutorialMode)
  const [turnPulseKey, setTurnPulseKey] = useState(0)
  const [recentScore, setRecentScore] = useState(null)
  const startedRef = useRef(false)
  const introTtsPlayedRef = useRef(false)
  const previousTurnRef = useRef(null)
  const previousScoresRef = useRef(new Map())

  useEffect(() => {
    if (!connected) return
    if (!tutorialMode || tutorialIntroSeen) return
    if (introTtsPlayedRef.current) return
    introTtsPlayedRef.current = true
    send('TTS_REQUEST', { text: TUTORIAL_INTRO_TEXT })
  }, [connected, send, tutorialIntroSeen, tutorialMode])

  useEffect(() => {
    if (!connected) return
    if (tutorialMode && !tutorialIntroSeen) return
    if (startedRef.current) return
    startedRef.current = true
    send('START_YACHT', { players: normalizePlayers(players), tutorial_mode: tutorialMode })
  }, [connected, players, send, tutorialIntroSeen, tutorialMode])

  useEffect(() => {
    if (!state?.players?.length) return

    if (previousTurnRef.current && previousTurnRef.current !== state.current_player_id) {
      setTurnPulseKey(key => key + 1)
    }
    previousTurnRef.current = state.current_player_id

    const nextScores = new Map()
    let addedScore = null
    for (const player of state.players) {
      const scores = player.scores || {}
      const previousScores = previousScoresRef.current.get(player.player_id) || {}
      nextScores.set(player.player_id, { ...scores })

      for (const [category, score] of Object.entries(scores)) {
        if (previousScores[category] == null) {
          addedScore = {
            playerId: player.player_id,
            playerName: player.playername,
            category,
            score,
          }
        }
      }
    }

    previousScoresRef.current = nextScores
    if (addedScore) {
      setRecentScore(addedScore)
    }
  }, [state])

  useEffect(() => {
    if (!recentScore) return undefined
    const timeout = window.setTimeout(() => setRecentScore(null), 1100)
    return () => window.clearTimeout(timeout)
  }, [recentScore])

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
    const latestError = messages.find(m => m.msg_type === 'error')
    return latestError?.payload?.message || state?.last_message
  }, [messages, state?.last_message])
  const canUndo = state?.can_undo ?? true
  const isTutorial = Boolean(state?.tutorial_mode)
  const canManualRoll =
    ['AWAITING_ROLL', 'AWAITING_KEEP'].includes(state?.phase) &&
    Number(state?.remaining_rolls || 0) > 0
  const tutorialText = isTutorial ? getTutorialText(state, currentPlayer) : null
  const visibleStatusMessage =
    isTutorial && ['AWAITING_ROLL', 'AWAITING_KEEP'].includes(state?.phase)
      ? null
      : statusMessage

  const startFullGame = () => {
    send('START_YACHT', { players: normalizePlayers(players), tutorial_mode: false })
  }

  const startTutorial = () => {
    setTutorialIntroSeen(true)
  }

  if (tutorialMode && !tutorialIntroSeen) {
    return (
      <div style={s.page}>
        <div style={s.introShell}>
          <div style={s.introKicker}>튜토리얼 모드</div>
          <div style={s.introTitle}>요트다이스 한 라운드 체험</div>
          <div style={s.introText}>{TUTORIAL_INTRO_TEXT}</div>
          <ul style={s.introList}>
            <li>이 튜토리얼에서는 각 플레이어가 한 번씩 턴을 진행합니다.</li>
            <li>실제 주사위를 굴리면 카메라가 결과를 인식합니다.</li>
          </ul>
          <div style={s.endActions}>
            <button style={s.buttonSmall} onClick={onExit}>게임 선택화면</button>
            <button
              style={{
                ...s.buttonSmall,
                ...s.primaryButton,
                ...(!connected ? s.buttonDisabled : {}),
              }}
              disabled={!connected}
              onClick={startTutorial}
            >
              튜토리얼 시작
            </button>
          </div>
        </div>
      </div>
    )
  }

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

  if (state.tutorial_complete) {
    return (
      <div style={s.page}>
        <div style={s.endShell}>
          <div style={s.endPanel}>
            <div style={s.winner}>튜토리얼 완료</div>
            <div style={s.endText}>
              모든 플레이어가 한 번씩 굴리고 점수를 기록했습니다.
              이제 정식 게임을 시작할 수 있습니다.
            </div>
            <div style={s.endActions}>
              <button style={s.buttonSmall} onClick={onExit}>게임 선택화면</button>
              <button style={{ ...s.buttonSmall, ...s.primaryButton }} onClick={startFullGame}>게임 시작하기</button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={s.page}>
      <style>{`
        @keyframes yachtTurnPulse {
          0% { transform: scale(0.98); box-shadow: 0 0 0 0 color-mix(in oklch, var(--yacht) 32%, transparent); }
          45% { transform: scale(1.03); box-shadow: 0 0 0 8px color-mix(in oklch, var(--yacht) 18%, transparent); }
          100% { transform: scale(1); box-shadow: 0 0 0 0 transparent; }
        }

        @keyframes yachtScoreFlash {
          0% { background: color-mix(in oklch, var(--yacht) 30%, var(--bg-surface)); }
          55% { background: color-mix(in oklch, var(--yacht) 20%, var(--bg-surface)); }
          100% { background: var(--bg-surface); }
        }

        .yacht-turn-pulse {
          animation: yachtTurnPulse 420ms ease-out;
        }

        .yacht-score-flash {
          animation: yachtScoreFlash 900ms ease-out;
        }

      `}</style>
      <div style={s.phaseText}>
        <span style={s.phaseTitle}>요트다이스</span>
        <span style={s.phaseActions}>
          <button
            style={{ ...s.buttonSmall, ...(canUndo ? {} : s.buttonDisabled) }}
            onClick={() => send('UNDO_ROUND')}
            disabled={!canUndo}
          >
            되돌리기
          </button>
          <button style={s.buttonSmall} onClick={onExit}>나가기</button>
        </span>
      </div>
      <div style={s.shell}>
        <main style={s.main}>
          {tutorialText && <div style={s.tutorialBubble}>{tutorialText}</div>}

          <div style={s.turnRow}>
            <div key={turnPulseKey} className={turnPulseKey ? 'yacht-turn-pulse' : undefined} style={s.turnBadge}>
              {currentPlayer?.playername || '-'} 님 차례
            </div>
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

          {visibleStatusMessage && <div style={s.rollMessage}>{visibleStatusMessage}</div>}
        </main>

        <aside style={s.scoreWrap}>
          <ScoreTable
            state={state}
            currentOnly
            recentScore={recentScore}
            onScore={(category) => scoreCategory(category, state, send)}
          />
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
                  <ScoreTable
                    state={{ ...state, players: [player], current_player_id: player.player_id }}
                    compact
                    recentScore={recentScore}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreHelp() {
  const rows = [
    ['Aces-Sixes', '해당 눈의 주사위만 모두 더합니다'],
    ['상단 보너스', 'Aces부터 Sixes 합계가 63점 이상이면 35점'],
    ['Full House', '같은 눈 3개와 같은 눈 2개 조합이면 총합'],
    ['4 of a Kind', '같은 눈 4개 이상이면 총합'],
    ['S. Straight', '연속된 숫자 4개 이상이면 15점'],
    ['L. Straight', '1-5 또는 2-6이면 30점'],
    ['Yacht', '같은 눈 5개면 50점'],
    ['Choice', '아무 조합이나 주사위 총합'],
  ]

  return (
    <div style={s.scoreHelpPopover}>
      <ul style={s.helpList}>
        {rows.map(([name, desc]) => (
          <li key={name}>
            <span style={s.helpItemName}>{name}</span>
            {desc}
          </li>
        ))}
      </ul>
    </div>
  )
}

function ScoreTable({ state, currentOnly = false, compact = false, recentScore, onScore }) {
  const [scoreHelpOpen, setScoreHelpOpen] = useState(false)
  const players = currentOnly
    ? state.players.filter(player => player.player_id === state.current_player_id)
    : state.players
  const player = players[0]

  return (
    <table style={s.scoreboard}>
      <thead>
        <tr>
          <th colSpan="2" style={s.th}>
            <div style={s.scoreHeader}>
              <span>점수판 · {player?.playername || '-'}</span>
              {!compact && (
                <>
                  <button
                    style={s.helpButton}
                    aria-label="족보 설명"
                    onMouseEnter={() => setScoreHelpOpen(true)}
                    onMouseLeave={() => setScoreHelpOpen(false)}
                    onFocus={() => setScoreHelpOpen(true)}
                    onBlur={() => setScoreHelpOpen(false)}
                  >
                    ?
                  </button>
                  {scoreHelpOpen && <ScoreHelp />}
                </>
              )}
            </div>
          </th>
        </tr>
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
                    {!compact && (
                      <span style={s.bonusBadge(earned)}>
                        {earned ? '+35' : `${remaining}점 남음`}
                      </span>
                    )}
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
          const highlightScore =
            recentScore?.playerId === player?.player_id &&
            recentScore?.category === key

          return (
            <tr
              key={key}
              className={highlightScore ? 'yacht-score-flash' : undefined}
              style={s.scoreRow(canScore)}
              onClick={canScore ? () => onScore(key) : undefined}
            >
              <td style={{ ...s.tdName, color: !hasScore && !available ? 'var(--fg-faint)' : 'var(--fg)' }}>{label}</td>
              <td style={{ ...s.tdScore, color: hasScore ? 'var(--fg)' : 'var(--fg-mute)' }}>
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

function getTutorialText(state, currentPlayer) {
  const name = currentPlayer?.playername || '플레이어'
  if (state.phase === 'AWAITING_ROLL') {
    return `${name}님 차례입니다. 주사위 5개를 굴리면 카메라가 결과를 인식합니다.`
  }
  if (state.phase === 'AWAITING_KEEP') {
    if (state.roll_count >= 2) {
      return '원하는 주사위를 킵할 수 있습니다. 킵한 주사위는 다음 굴림에서 유지되며, 한 번 킵한 주사위를 다시 굴릴 수도 있습니다. 주사위는 세 번까지 굴릴 수 있으며, 그 전에 점수 칸을 선택해 턴을 끝낼 수도 있습니다. 점수판 오른쪽 위 ? 버튼에서 족보 설명을 볼 수 있습니다.'
    }
    return '원하는 주사위를 킵할 수 있습니다. 킵한 주사위는 다음 굴림에서 유지되며, 한 번 킵한 주사위를 다시 굴릴 수도 있습니다. 주사위는 세 번까지 굴릴 수 있으며, 그 전에 점수 칸을 선택해 턴을 끝낼 수도 있습니다. 점수판 오른쪽 위 ? 버튼에서 족보 설명을 볼 수 있습니다.'
  }
  if (state.phase === 'AWAITING_SCORE') {
    return '이제 점수 칸을 선택할 차례입니다. 예상 점수를 보고 원하는 칸에 기록하세요. 족보가 헷갈리면 점수판 오른쪽 위 ? 버튼을 확인하세요.'
  }
  return '요트다이스의 한 턴 흐름을 따라가고 있습니다.'
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
