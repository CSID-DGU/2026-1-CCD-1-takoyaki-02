import { useEffect, useMemo, useRef, useState } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { audio as audioApi, useAudioPlayer } from '../hooks/useAudioPlayer'
import { IconMusic, IconVolume } from '../components/common/Icons'

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
const SHOW_MANUAL_ROLL = import.meta.env.VITE_SHOW_MANUAL_ROLL === 'true'
const SHOW_DICE_MANUAL_INPUT = import.meta.env.VITE_SHOW_DICE_MANUAL_INPUT !== 'false'
const TUTORIAL_GUIDE_STEPS = [
  '요트다이스는 주사위 조합으로 족보를 만들고, 점수판의 칸을 하나씩 채워나가는 게임입니다. 먼저 점수판 오른쪽 위 물음표 버튼을 눌러 어떤 족보를 만들 수 있는지 확인해보세요.',
  '원하는 족보에 가까운 눈은 킵해두고, 나머지 주사위만 다시 굴려 더 좋은 조합을 만들 수 있습니다. 킵할 주사위를 보드 위 주사위 공간으로 옮긴 뒤, 끝났다면 태블릿의 다음 버튼을 눌러주세요.',
  '킵했던 주사위도 언제든 굴림 영역으로 옮겨 다시 굴릴 수 있습니다.',
  '주사위는 세 번까지 굴릴 수 있습니다. 다시 굴리거나 그 전에 점수 칸을 선택해 턴을 끝낼 수도 있습니다.',
  '점수판에서 원하는 점수 칸을 선택하면 이번 턴의 점수가 기록됩니다. 주사위를 더 굴리거나, 원하시는 족보를 선택해주세요.',
]
const TUTORIAL_SCORE_HELP_TTS =
  '족보를 간단히 설명하겠습니다. Aces부터 Sixes는 해당 숫자와 같은 주사위만 더합니다. 이 상단 점수의 합이 63점 이상이면 상단 보너스 35점을 추가로 받습니다. Full House는 같은 눈 세 개와 같은 눈 두 개를 함께 만드는 족보입니다. Four of a Kind는 같은 눈 네 개 이상을 만드는 족보입니다. Small Straight는 연속된 숫자 네 개, Large Straight는 연속된 숫자 다섯 개를 만드는 족보입니다. Yacht는 주사위 다섯 개가 모두 같은 눈일 때 완성됩니다. Choice는 조건 없이 주사위 다섯 개의 합계를 그대로 기록합니다.'
const sentTutorialTtsKeys = new Set()

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
  iconButton: active => ({
    width: 40,
    height: 40,
    border: active ? '1px solid color-mix(in oklch, var(--yacht) 55%, transparent)' : '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    background: active ? 'color-mix(in oklch, var(--yacht) 18%, var(--bg-elev))' : 'var(--bg-elev)',
    color: active ? 'color-mix(in oklch, var(--yacht) 82%, var(--fg))' : 'var(--fg-mute)',
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer',
    padding: 0,
  }),
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
  tutorialBlurredContent: {
    filter: 'blur(7px)',
    opacity: 0.34,
    pointerEvents: 'none',
    userSelect: 'none',
  },
  tutorialBubbleText: {
    marginBottom: 14,
  },
  tutorialNextButton: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid color-mix(in oklch, var(--yacht) 45%, transparent)',
    borderRadius: 'var(--radius)',
    background: 'var(--yacht)',
    color: '#17110c',
    padding: '8px 14px',
    fontSize: 15,
    fontWeight: 850,
    cursor: 'pointer',
  },
  tutorialBubbleFooter: {
    display: 'flex',
    justifyContent: 'flex-end',
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
    padding: '20px 42px 20px 0',
    boxSizing: 'border-box',
    height: '100%',
    overflowY: 'auto',
    minHeight: 0,
  },
  scoreHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    position: 'relative',
  },
  helpButton: {
    width: 32,
    height: 32,
    borderRadius: '50%',
    border: '1px solid var(--border)',
    background: 'var(--bg-elev)',
    color: 'var(--fg-soft)',
    fontSize: 18,
    fontWeight: 800,
    cursor: 'pointer',
    boxShadow: 'var(--shadow-sm)',
    padding: 0,
    flexShrink: 0,
  },
  helpButtonRequired: {
    border: '2px solid var(--yacht)',
    background: 'var(--yacht)',
    color: '#17110c',
    boxShadow: '0 0 0 6px color-mix(in oklch, var(--yacht) 24%, transparent)',
  },
  scoreHelpModal: {
    width: 'min(1120px, calc(100vw - 24px))',
    maxHeight: 'calc(100vh - 24px)',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-soft)',
    borderRadius: 'var(--radius-xl)',
    overflow: 'hidden',
    boxShadow: 'var(--shadow-lg)',
  },
  scoreHelpBody: {
    padding: 24,
    overflowY: 'auto',
    maxHeight: 'calc(100vh - 92px)',
    color: 'var(--fg-soft)',
  },
  scoreHelpGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: 14,
  },
  scoreHelpCard: {
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    background: 'var(--bg-elev)',
    padding: 16,
    minHeight: 156,
    boxSizing: 'border-box',
  },
  scoreHelpCardTitle: {
    display: 'flex',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: 10,
    marginBottom: 8,
  },
  scoreHelpName: {
    color: 'var(--yacht)',
    fontSize: 20,
    fontWeight: 850,
  },
  scoreHelpScore: {
    color: 'var(--fg-soft)',
    fontSize: 15,
    fontWeight: 800,
  },
  scoreHelpDesc: {
    fontSize: 16,
    lineHeight: 1.45,
    color: 'var(--fg-soft)',
    fontWeight: 650,
    marginBottom: 14,
  },
  scoreHelpExample: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  helpDiceRow: {
    display: 'flex',
    gap: 7,
    flexShrink: 0,
  },
  helpDie: {
    width: 36,
    height: 36,
    border: '1px solid var(--border)',
    borderRadius: 7,
    background: 'var(--bg-surface)',
    color: 'var(--fg)',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 18,
    fontWeight: 850,
    boxShadow: 'var(--shadow-sm)',
  },
  helpDieActive: {
    border: '1px solid var(--yacht)',
    background: 'var(--yacht)',
    color: '#17110c',
    boxShadow: '0 7px 16px color-mix(in oklch, var(--yacht) 26%, transparent)',
  },
  helpDieAlt: {
    border: '1px solid #31c46b',
    background: '#31c46b',
    color: '#07130b',
    boxShadow: '0 7px 16px rgba(49, 196, 107, 0.25)',
  },
  scoreHelpExampleText: {
    color: 'var(--fg-mute)',
    fontSize: 14,
    fontWeight: 700,
    lineHeight: 1.35,
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
  th: { background: 'var(--bg-elev)', textAlign: 'left', padding: '13px 18px', fontWeight: 800, color: 'var(--fg)', fontSize: 18 },
  tdName: { padding: '11px 18px', borderBottom: '1px solid var(--border-soft)', fontWeight: 700 },
  tdScore: { padding: '11px 18px', borderBottom: '1px solid var(--border-soft)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' },
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
    zIndex: 50,
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
  manualModal: {
    width: 'min(520px, calc(100vw - 32px))',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-soft)',
    borderRadius: 'var(--radius-xl)',
    boxShadow: 'var(--shadow-lg)',
    padding: 28,
    boxSizing: 'border-box',
  },
  manualTitle: {
    fontSize: 24,
    fontWeight: 850,
    marginBottom: 10,
    color: 'var(--fg)',
  },
  manualText: {
    color: 'var(--fg-soft)',
    fontSize: 15,
    fontWeight: 650,
    lineHeight: 1.45,
    marginBottom: 20,
  },
  manualDiceRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
    gap: 10,
    marginBottom: 16,
  },
  manualSelect: {
    width: '100%',
    height: 58,
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    background: 'var(--bg-elev)',
    color: 'var(--fg)',
    fontSize: 24,
    fontWeight: 800,
    textAlign: 'center',
    cursor: 'pointer',
  },
  manualError: {
    minHeight: 22,
    color: 'var(--danger)',
    fontSize: 14,
    fontWeight: 750,
    marginBottom: 14,
  },
  manualActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 10,
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
  const [manualDiceOpen, setManualDiceOpen] = useState(false)
  const [manualDiceValues, setManualDiceValues] = useState(['', '', '', '', ''])
  const [manualDiceError, setManualDiceError] = useState('')
  const [tutorialGuideStep, setTutorialGuideStep] = useState(0)
  const [tutorialScoreHelpSeen, setTutorialScoreHelpSeen] = useState(false)
  const [ttsEnabled, setTtsEnabled] = useState(true)
  const [bgmEnabled, setBgmEnabled] = useState(true)
  const [turnPulseKey, setTurnPulseKey] = useState(0)
  const [recentScore, setRecentScore] = useState(null)
  const [scoreRowPaddingY, setScoreRowPaddingY] = useState(null)
  const scoreWrapRef = useRef(null)
  const startedRef = useRef(false)
  const previousTurnRef = useRef(null)
  const previousRollRef = useRef(null)
  const previousScoresRef = useRef(new Map())
  const previousTutorialResetKeyRef = useRef('')
  const lastTutorialTtsKeyRef = useRef('')

  useEffect(() => {
    audioApi.setTtsEnabled(true)
  }, [])

  // 점수판 컨테이너 높이에 맞춰 행 padding 동적 계산.
  // 행 수 15(헤더 1 + 카테고리 13 + 합계 1)로 가용 공간을 분배.
  useEffect(() => {
    const el = scoreWrapRef.current
    if (!el) return
    const compute = () => {
      const h = el.clientHeight
      // 한 행의 텍스트(폰트 18 → 라인 약 24) + 1px border 고려.
      const ROW_TEXT = 25
      const ROW_COUNT = 15
      const totalText = ROW_TEXT * ROW_COUNT
      const free = h - totalText
      // 행당 추가 여유 공간 → 위/아래로 절반씩 padding.
      let pad = Math.floor(free / (ROW_COUNT * 2))
      pad = Math.max(4, Math.min(20, pad))
      setScoreRowPaddingY(pad)
    }
    compute()
    const ro = new ResizeObserver(compute)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // 재연결 시 START_YACHT를 다시 보낼 수 있도록 ref를 리셋.
  // (vite WS 프록시가 IP 접근 환경에서 첫 핸드셰이크를 흘려보내고 재연결하는 케이스 대응)
  useEffect(() => {
    if (!connected) {
      startedRef.current = false
    }
  }, [connected])

  useEffect(() => {
    if (!state?.tutorial_mode) return
    const resetKey = `${state.current_player_id || ''}:${state.phase || ''}`
    if (previousTutorialResetKeyRef.current === resetKey) return
    previousTutorialResetKeyRef.current = resetKey
    setTutorialGuideStep(0)
    setTutorialScoreHelpSeen(false)
  }, [state?.current_player_id, state?.phase, state?.tutorial_mode])

  // 백엔드가 보낸 hello 메시지 수신을 확인한 뒤에 START_YACHT 송신.
  // accept 직후 onopen이 뜨더라도 receive loop가 아직 시작되기 전일 수 있으므로,
  // 백엔드가 보낸 hello가 도착해야 receive 가능 상태임을 보장할 수 있다.
  const helloSeen = useMemo(
    () => messages.some(m => m.msg_type === 'hello'),
    [messages],
  )

  useEffect(() => {
    if (!connected || !helloSeen) return
    if (startedRef.current) return
    startedRef.current = true
    send('START_YACHT', { players: normalizePlayers(players), tutorial_mode: tutorialMode })
  }, [connected, helloSeen, players, send, tutorialMode])

  useEffect(() => {
    if (!state?.players?.length) return

    const previousRoll = previousRollRef.current
    const currentRoll = {
      playerId: state.current_player_id,
      rollCount: Number(state.roll_count || 0),
    }
    if (
      previousRoll &&
      previousRoll.playerId === currentRoll.playerId &&
      currentRoll.rollCount > previousRoll.rollCount
    ) {
      playLocalSfx('dice_roll')
    }
    previousRollRef.current = currentRoll

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
      playLocalSfx('score_select')
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
  const tutorialScoreHelpRequired =
    isTutorial &&
    state?.phase === 'AWAITING_KEEP' &&
    tutorialGuideStep === 0 &&
    !tutorialScoreHelpSeen
  const canManualRoll =
    SHOW_MANUAL_ROLL &&
    !tutorialScoreHelpRequired &&
    ['AWAITING_ROLL', 'AWAITING_KEEP'].includes(state?.phase) &&
    Number(state?.remaining_rolls || 0) > 0
  const canManualDiceInput =
    SHOW_DICE_MANUAL_INPUT &&
    !tutorialScoreHelpRequired &&
    (
      (state?.phase === 'AWAITING_ROLL' && Number(state?.remaining_rolls || 0) > 0) ||
      ['AWAITING_KEEP', 'AWAITING_SCORE'].includes(state?.phase)
    )
  const tutorialGuide = isTutorial ? getTutorialGuide(state, currentPlayer, tutorialGuideStep) : null
  const tutorialText = tutorialGuide?.text || null
  const tutorialOverlayActive = Boolean(tutorialText && tutorialGuide?.hasNext)
  const visibleStatusMessage =
    isTutorial && ['AWAITING_ROLL', 'AWAITING_KEEP'].includes(state?.phase)
      ? null
      : statusMessage

  useEffect(() => {
    if (!connected || !tutorialText) return
    if (state?.phase === 'AWAITING_ROLL') return
    const key = `${state?.current_player_id || ''}:${state?.phase || ''}:${state?.roll_count || 0}:${tutorialGuideStep}:${tutorialText}`
    if (lastTutorialTtsKeyRef.current === key) return
    if (sentTutorialTtsKeys.has(key)) return
    lastTutorialTtsKeyRef.current = key
    sentTutorialTtsKeys.add(key)
    send('TTS_REQUEST', { text: tutorialText })
  }, [connected, send, state?.current_player_id, state?.phase, state?.roll_count, tutorialGuideStep, tutorialText])

  const startFullGame = () => {
    send('START_YACHT', { players: normalizePlayers(players), tutorial_mode: false })
  }

  const nextTutorialGuide = () => {
    setTutorialGuideStep(step => Math.min(step + 1, TUTORIAL_GUIDE_STEPS.length - 1))
  }

  const completeTutorialScoreHelp = () => {
    if (!tutorialScoreHelpRequired) return
    setTutorialScoreHelpSeen(true)
    setTutorialGuideStep(1)
  }

  const playTutorialScoreHelpTts = () => {
    if (!tutorialScoreHelpRequired) return
    send('TTS_REQUEST', { text: TUTORIAL_SCORE_HELP_TTS })
  }

  const toggleBgm = () => {
    const next = !bgmEnabled
    setBgmEnabled(next)
    send('BGM_SET', { enabled: next })
  }

  const toggleTts = () => {
    const next = !ttsEnabled
    setTtsEnabled(next)
    audioApi.setTtsEnabled(next)
  }

  const openManualDiceInput = () => {
    const values =
      state?.dice_values?.length === 5
        ? state.dice_values.map(value => String(value || 1))
        : ['1', '1', '1', '1', '1']
    setManualDiceValues(values)
    setManualDiceError('')
    setManualDiceOpen(true)
  }

  const updateManualDie = (index, value) => {
    setManualDiceValues(prev => prev.map((item, i) => (i === index ? value : item)))
    setManualDiceError('')
  }

  const submitManualDiceInput = () => {
    const diceValues = manualDiceValues.map(value => Number(value))
    if (diceValues.length !== 5 || diceValues.some(value => !Number.isInteger(value) || value < 1 || value > 6)) {
      setManualDiceError('1부터 6까지의 값을 5개 모두 선택해주세요.')
      return
    }
    send('MANUAL_DICE_INPUT', { dice_values: diceValues })
    setManualDiceOpen(false)
  }

  const exitGame = () => {
    audioApi.setTtsEnabled(true)
    send('BGM_STOP')
    onExit?.()
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
              <button style={s.buttonSmall} onClick={exitGame}>게임 변경</button>
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
              <button style={s.buttonSmall} onClick={exitGame}>게임 선택화면</button>
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

        @keyframes yachtScoreSuggest {
          0%, 100% {
            background: color-mix(in oklch, var(--info) 14%, var(--bg-surface));
            box-shadow: inset 0 0 0 1px color-mix(in oklch, var(--info) 20%, transparent);
          }
          50% {
            background: color-mix(in oklch, #31c46b 16%, var(--bg-surface));
            box-shadow: inset 0 0 0 1px rgba(49, 196, 107, 0.28);
          }
        }

        .yacht-turn-pulse {
          animation: yachtTurnPulse 420ms ease-out;
        }

        .yacht-score-flash {
          animation: yachtScoreFlash 900ms ease-out;
        }

        .yacht-score-suggest {
          animation: yachtScoreSuggest 1.8s ease-in-out infinite;
        }

      `}</style>
      <div style={tutorialOverlayActive ? s.tutorialBlurredContent : undefined}>
        <div style={s.phaseText}>
          <span style={s.phaseTitle}>요트다이스</span>
          <span style={s.phaseActions}>
            <button
              type="button"
              style={s.iconButton(ttsEnabled)}
              onClick={toggleTts}
              title={ttsEnabled ? 'TTS 끄기' : 'TTS 켜기'}
              aria-label={ttsEnabled ? 'TTS 끄기' : 'TTS 켜기'}
            >
              <IconVolume size={19} />
            </button>
            <button
              type="button"
              style={s.iconButton(bgmEnabled)}
              onClick={toggleBgm}
              title={bgmEnabled ? '배경음 끄기' : '배경음 켜기'}
              aria-label={bgmEnabled ? '배경음 끄기' : '배경음 켜기'}
            >
              <IconMusic size={19} />
            </button>
            <button
              style={{ ...s.buttonSmall, ...(canUndo ? {} : s.buttonDisabled) }}
              onClick={() => send('UNDO_ROUND')}
              disabled={!canUndo}
            >
              되돌리기
            </button>
            <button style={s.buttonSmall} onClick={exitGame}>나가기</button>
          </span>
        </div>
      </div>
      <div style={s.shell}>
        <main style={s.main}>
          {tutorialText && (
            <div style={s.tutorialBubble}>
              <div style={tutorialGuide?.hasNext ? s.tutorialBubbleText : undefined}>
                {tutorialText}
              </div>
              {tutorialGuide?.hasNext && (
                <div style={s.tutorialBubbleFooter}>
                  <button type="button" style={s.tutorialNextButton} onClick={nextTutorialGuide}>
                    다음
                  </button>
                </div>
              )}
            </div>
          )}

          <div style={tutorialOverlayActive ? s.tutorialBlurredContent : undefined}>
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
                  style={s.die(Boolean(state.keep_mask?.[index]), canToggleKeep(state) && !tutorialScoreHelpRequired)}
                  onClick={() => toggleKeep(index, state, send)}
                  disabled={!canToggleKeep(state) || tutorialScoreHelpRequired}
                  title="보관"
                >
                  {value}
                </button>
              ))}
            </div>

            <div style={s.actionRow}>
              <button style={s.buttonSmall} onClick={() => setLeaderboardOpen(true)}>리더보드 보기</button>
              {canManualDiceInput && (
                <button style={s.buttonSmall} onClick={openManualDiceInput}>인식이 잘못되었나요?</button>
              )}
              {canManualRoll && (
                <button style={{ ...s.buttonSmall, ...s.primaryButton }} onClick={() => send('ROLL_DICE')}>굴리기</button>
              )}
            </div>

            {visibleStatusMessage && <div style={s.rollMessage}>{visibleStatusMessage}</div>}
          </div>
        </main>

        <aside
          ref={scoreWrapRef}
          style={tutorialOverlayActive ? { ...s.scoreWrap, ...s.tutorialBlurredContent } : s.scoreWrap}
        >
          <ScoreTable
            state={state}
            currentOnly
            recentScore={recentScore}
            onScore={(category) => scoreCategory(category, state, send)}
            rowPaddingY={scoreRowPaddingY}
            scoreDisabled={tutorialScoreHelpRequired}
            requireHelpOpen={tutorialScoreHelpRequired}
            onHelpOpen={playTutorialScoreHelpTts}
            onHelpClose={completeTutorialScoreHelp}
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

      {manualDiceOpen && (
        <div style={s.modalShade}>
          <div style={s.manualModal}>
            <div style={s.manualTitle}>인식값 수정</div>
            <div style={s.manualText}>
              실제 주사위 눈과 다르게 표시됐다면 올바른 값을 선택해주세요.
            </div>
            <div style={s.manualDiceRow}>
              {manualDiceValues.map((value, index) => (
                <select
                  key={index}
                  style={s.manualSelect}
                  value={value}
                  onChange={event => updateManualDie(index, event.target.value)}
                  aria-label={`주사위 ${index + 1}`}
                >
                  {[1, 2, 3, 4, 5, 6].map(face => (
                    <option key={face} value={face}>{face}</option>
                  ))}
                </select>
              ))}
            </div>
            <div style={s.manualError}>{manualDiceError}</div>
            <div style={s.manualActions}>
              <button style={s.buttonSmall} onClick={() => setManualDiceOpen(false)}>취소</button>
              <button style={{ ...s.buttonSmall, ...s.primaryButton }} onClick={submitManualDiceInput}>적용</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreHelp({ onClose }) {
  const rows = [
    {
      name: 'Aces-Sixes',
      score: '눈별 합계',
      desc: '선택한 눈과 같은 주사위만 모두 더합니다. Aces는 1만, Sixes는 6만 더합니다.',
      dice: [1, 1, 3, 4, 6],
      active: [0, 1],
      example: '1 + 1 = 2점',
    },
    {
      name: '상단 보너스',
      score: '+35점',
      desc: 'Aces부터 Sixes까지 기록한 점수 합계가 63점 이상이면 보너스 35점을 받습니다.',
      dice: [],
      active: [],
      example: '',
    },
    {
      name: 'Full House',
      score: '총합',
      desc: '같은 눈 3개와 다른 같은 눈 2개가 함께 있으면 성공입니다. 주사위 5개의 합계를 점수로 기록합니다.',
      dice: [2, 2, 5, 5, 5],
      active: [0, 1],
      alt: [2, 3, 4],
      example: '2 + 2 + 5 + 5 + 5 = 19점',
    },
    {
      name: '4 of a Kind',
      score: '총합',
      desc: '같은 눈이 4개 이상 있으면 성공입니다. 나머지 주사위까지 포함한 5개 합계를 점수로 기록합니다.',
      dice: [3, 3, 3, 3, 6],
      active: [0, 1, 2, 3],
      alt: [4],
      example: '3 + 3 + 3 + 3 + 6 = 18점',
    },
    {
      name: 'S. Straight',
      score: '15점',
      desc: '연속된 숫자 4개 이상이 있으면 성공입니다. 1-2-3-4, 2-3-4-5, 3-4-5-6 중 하나면 됩니다.',
      dice: [1, 2, 3, 4, 6],
      active: [0, 1, 2, 3],
      example: '',
    },
    {
      name: 'L. Straight',
      score: '30점',
      desc: '주사위 5개가 모두 연속이면 성공입니다. 1-2-3-4-5 또는 2-3-4-5-6만 해당합니다.',
      dice: [2, 3, 4, 5, 6],
      active: [0, 1, 2, 3, 4],
      example: '',
    },
    {
      name: 'Yacht',
      score: '50점',
      desc: '주사위 5개가 모두 같은 눈이면 성공입니다. 가장 높은 고정 점수 족보입니다.',
      dice: [4, 4, 4, 4, 4],
      active: [0, 1, 2, 3, 4],
      example: '',
    },
    {
      name: 'Choice',
      score: '총합',
      desc: '아무 조건 없이 주사위 5개의 합계를 그대로 기록합니다. 애매한 조합을 처리할 때 유용합니다.',
      dice: [1, 3, 4, 5, 6],
      active: [0, 1, 2, 3, 4],
      example: '1 + 3 + 4 + 5 + 6 = 19점',
    },
  ]

  return (
    <div style={s.modalShade}>
      <div style={s.scoreHelpModal}>
        <div style={s.leaderboardHeader}>
          족보 설명
          <button style={s.close} onClick={onClose}>x</button>
        </div>
        <div style={s.scoreHelpBody}>
          <div style={s.scoreHelpGrid}>
            {rows.map(row => (
              <div key={row.name} style={s.scoreHelpCard}>
                <div style={s.scoreHelpCardTitle}>
                  <span style={s.scoreHelpName}>{row.name}</span>
                  <span style={s.scoreHelpScore}>{row.score}</span>
                </div>
                <div style={s.scoreHelpDesc}>{row.desc}</div>
                {row.dice.length > 0 && (
                  <div style={s.scoreHelpExample}>
                    <div style={s.helpDiceRow}>
                      {row.dice.map((value, index) => (
                        <span
                          key={`${row.name}-${index}`}
                          style={{
                            ...s.helpDie,
                            ...(row.active.includes(index) ? s.helpDieActive : {}),
                            ...(row.alt?.includes(index) ? s.helpDieAlt : {}),
                          }}
                        >
                          {value}
                        </span>
                      ))}
                    </div>
                    {row.example && <div style={s.scoreHelpExampleText}>{row.example}</div>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function ScoreTable({
  state,
  currentOnly = false,
  compact = false,
  recentScore,
  onScore,
  rowPaddingY,
  scoreDisabled = false,
  requireHelpOpen = false,
  onHelpOpen,
  onHelpClose,
}) {
  const [scoreHelpOpen, setScoreHelpOpen] = useState(false)
  const openScoreHelp = () => {
    setScoreHelpOpen(true)
    onHelpOpen?.()
  }
  const closeScoreHelp = () => {
    setScoreHelpOpen(false)
    onHelpClose?.()
  }
  const players = currentOnly
    ? state.players.filter(player => player.player_id === state.current_player_id)
    : state.players
  const player = players[0]
  const thStyle = rowPaddingY != null
    ? { ...s.th, paddingTop: rowPaddingY + 2, paddingBottom: rowPaddingY + 2 }
    : s.th
  const tdNameStyle = rowPaddingY != null
    ? { ...s.tdName, paddingTop: rowPaddingY, paddingBottom: rowPaddingY }
    : s.tdName
  const tdScoreStyle = rowPaddingY != null
    ? { ...s.tdScore, paddingTop: rowPaddingY, paddingBottom: rowPaddingY }
    : s.tdScore
  const suggestedCategories = new Set(
    !compact && state.phase !== 'AWAITING_ROLL' && state.dice_values?.length
      ? DISPLAY_CATEGORIES
        .filter(key => state.available_categories?.includes(key))
        .map(key => [key, Number(previewScore(key, state.dice_values))])
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([key]) => key)
      : [],
  )

  return (
    <>
    <table style={s.scoreboard}>
      <thead>
        <tr>
          <th colSpan="2" style={thStyle}>
            <div style={s.scoreHeader}>
              <span>점수판 · {player?.playername || '-'}</span>
              {!compact && (
                <>
                  <button
                    style={requireHelpOpen ? { ...s.helpButton, ...s.helpButtonRequired } : s.helpButton}
                    aria-label="족보 설명"
                    onClick={openScoreHelp}
                  >
                    ?
                  </button>
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
                <td style={tdNameStyle}>{label}</td>
                <td style={tdScoreStyle}>
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
            !scoreDisabled &&
            state.dice_values?.length
          const displayScore = hasScore ? score : (compact ? '—' : predictedScore(key, state))
          const highlightScore =
            recentScore?.playerId === player?.player_id &&
            recentScore?.category === key
          const suggested = canScore && suggestedCategories.has(key)

          return (
            <tr
              key={key}
              className={[
                highlightScore ? 'yacht-score-flash' : '',
                suggested ? 'yacht-score-suggest' : '',
              ].filter(Boolean).join(' ') || undefined}
              style={s.scoreRow(canScore)}
              onClick={canScore ? () => onScore(key) : undefined}
            >
              <td style={{ ...tdNameStyle, color: !hasScore && !available ? 'var(--fg-faint)' : 'var(--fg)' }}>{label}</td>
              <td style={{ ...tdScoreStyle, color: hasScore ? 'var(--fg)' : 'var(--fg-mute)' }}>
                {displayScore}
              </td>
            </tr>
          )
        })}
        <tr style={s.totalRow}>
          <td style={tdNameStyle}>합계</td>
          <td style={tdScoreStyle}>{player?.total ?? 0}</td>
        </tr>
      </tbody>
    </table>
    {scoreHelpOpen && <ScoreHelp onClose={closeScoreHelp} />}
    </>
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

function getTutorialGuide(state, currentPlayer, guideStep) {
  const name = currentPlayer?.playername || '플레이어'
  if (state.phase === 'AWAITING_ROLL') {
    return {
      text: `${name}님 차례입니다. 주사위 5개를 굴리면 카메라가 결과를 인식합니다. 주사위 다섯개를 원형굴림통에 넣고 트레이 안에 굴려주세요.`,
      hasNext: false,
    }
  }
  if (state.phase === 'AWAITING_KEEP') {
    const safeStep = Math.max(0, Math.min(guideStep, TUTORIAL_GUIDE_STEPS.length - 1))
    return {
      text: TUTORIAL_GUIDE_STEPS[safeStep],
      hasNext: safeStep > 0 && safeStep < TUTORIAL_GUIDE_STEPS.length - 1,
    }
  }
  if (state.phase === 'AWAITING_SCORE') {
    return {
      text: '이제 점수 칸을 선택할 차례입니다. 예상 점수를 보고 원하는 칸에 기록하세요. 족보가 헷갈리면 점수판 오른쪽 위 물음표 버튼을 확인하세요.',
      hasNext: false,
    }
  }
  return {
    text: '요트다이스의 한 턴 흐름을 따라가고 있습니다.',
    hasNext: false,
  }
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

function playLocalSfx(name) {
  const audio = new Audio(`/sfx/${name}.mp3`)
  audio.play().catch(() => {})
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
