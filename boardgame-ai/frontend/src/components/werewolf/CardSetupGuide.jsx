import { useState, useEffect, useRef } from 'react'

const ROLE_NAMES = {
  doppelganger: '도플갱어',
  werewolf:     '늑대인간',
  minion:       '하수인',
  mason:        '프리메이슨',
  seer:         '예언자',
  robber:       '강도',
  troublemaker: '말썽쟁이',
  drunk:        '주정뱅이',
  insomniac:    '불면증환자',
  tanner:       '무두장이',
  hunter:       '사냥꾼',
  villager:     '마을주민',
}

const SENTENCES_NORMAL = [
  { text: '이번 게임에 사용할 역할 카드입니다.',                               showCards: true },
  { text: '모든 카드를 역할이 보이지 않게 뒤집어주세요.',                       holdMs: 10000 },
  { text: '각자 카드를 한 장씩 가져가고, 본인만 확인해주세요.',                 holdMs: 10000 },
  { text: '본인의 카드는 각자 자기 앞에 엎어서 놓아주세요.',                   holdMs: 10000 },
  { text: '나머지 카드는 역할이 보이지 않게 뒤집어 중앙에 놓아주세요.',         holdMs: 10000 },
  { text: '역할 등록을 위해 모두 눈을 잠시 감아주세요.' },
]

const SENTENCES_PRACTICE = [
  { text: '이번 게임에 사용할 역할 카드입니다.',                               showCards: true },
  { text: '모든 카드를 역할이 보이지 않게 뒤집어주세요.',                       holdMs: 10000 },
  { text: '각자 카드를 한 장씩 가져가주세요.',                                 holdMs: 10000 },
  { text: '연습모드이므로 역할을 숨기지 않고 진행합니다.',                       holdMs: 10000 },
  { text: '본인의 카드는 각자 자기 앞에 엎어서 놓아주세요.',                   holdMs: 10000 },
  { text: '나머지 카드는 역할이 보이지 않게 뒤집어 중앙에 놓아주세요.',         holdMs: 10000 },
  { text: '역할 등록을 위해 모두 눈을 잠시 감아주세요.' },
]

const CHAR_MS = 60    // 글자당 타이핑 속도 (ms)
const HOLD_MS = 5000  // 타이핑 완료 후 대기 시간 (ms) — 개별 holdMs로 오버라이드 가능
const FADE_MS = 600   // 페이드 전환 시간 (ms)
const CONFIRM_TEXT = '모든 준비가 완료 되었으면 OK 싸인을 해주세요.'

export default function CardSetupGuide({ roles = [], onComplete, send, wsState, onExit, isPracticeMode }) {
  const SENTENCES = isPracticeMode ? SENTENCES_PRACTICE : SENTENCES_NORMAL
  const [step, setStep]             = useState(0)
  const [typed, setTyped]           = useState('')
  const [visible, setVisible]       = useState(false)
  const [confirming, setConfirming] = useState(false)
  const prevGestureRef = useRef(wsState?.gesture_confirmed ?? null)
  const skipRef        = useRef(null)

  useEffect(() => {
    if (step >= SENTENCES.length) {
      setConfirming(true)
      return
    }

    const sentence = SENTENCES[step]
    setTyped('')
    setVisible(true)

    // 문장 시작 시 TTS 재생 (tts 필드가 있으면 우선 사용 — 숫자를 한국어 고유어로 읽히도록)
    send?.('TTS_REQUEST', { text: sentence.tts ?? sentence.text })

    // 타이핑 애니메이션
    let charIdx = 0
    const typeTimer = setInterval(() => {
      charIdx++
      setTyped(sentence.text.slice(0, charIdx))
      if (charIdx >= sentence.text.length) clearInterval(typeTimer)
    }, CHAR_MS)

    const typingMs = sentence.text.length * CHAR_MS
    const holdMs   = sentence.holdMs ?? HOLD_MS

    // 타이핑 완료 + holdMs 후 페이드 아웃
    const fadeOut = setTimeout(() => setVisible(false), typingMs + holdMs)
    // 페이드 완료 후 다음 문장
    const next    = setTimeout(() => setStep(s => s + 1), typingMs + holdMs + FADE_MS)

    // 건너뛰기 버튼이 호출할 콜백: 현재 타이머 취소 후 즉시 다음 문장으로
    skipRef.current = () => {
      clearInterval(typeTimer)
      clearTimeout(fadeOut)
      clearTimeout(next)
      setTyped(sentence.text)
      setVisible(false)
      setTimeout(() => setStep(s => s + 1), FADE_MS)
    }

    return () => {
      clearInterval(typeTimer)
      clearTimeout(fadeOut)
      clearTimeout(next)
      skipRef.current = null
    }
  }, [step])

  // 확인 단계 진입: 타이핑 애니메이션 + TTS + 제스처 가드 초기화
  useEffect(() => {
    if (!confirming) return
    setTyped('')
    setVisible(true)
    send?.('CARD_SETUP_CONFIRM_READY', {})
    send?.('TTS_REQUEST', { text: CONFIRM_TEXT })
    let charIdx = 0
    const typeTimer = setInterval(() => {
      charIdx++
      setTyped(CONFIRM_TEXT.slice(0, charIdx))
      if (charIdx >= CONFIRM_TEXT.length) clearInterval(typeTimer)
    }, CHAR_MS)
    return () => clearInterval(typeTimer)
  }, [confirming])

  // OK 싸인 감지 → 즉시 진행
  useEffect(() => {
    const cur = wsState?.gesture_confirmed ?? null
    if (confirming && cur && cur !== prevGestureRef.current) {
      onComplete()
    }
    prevGestureRef.current = cur
  }, [wsState?.gesture_confirmed, confirming])

  const sentence = step < SENTENCES.length ? SENTENCES[step] : null

  return (
    <>
      <style>{`
        @keyframes moonGlowPulse {
          0%,100% { box-shadow: 0 0 48px 18px rgba(220,185,80,0.22); }
          50%      { box-shadow: 0 0 72px 28px rgba(220,185,80,0.38); }
        }
        @keyframes starFlicker { 0%,100%{opacity:.6} 50%{opacity:.2} }
        @keyframes fogDrift {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-8%); }
        }
        @keyframes cursorBlink { 0%,100%{opacity:1} 50%{opacity:0} }
      `}</style>

      <div style={s.page} onClick={confirming ? onComplete : undefined}>
        <button onClick={(e) => { e.stopPropagation(); onExit?.() }} style={exitBtn}>나가기</button>
        {!confirming && (
          <button style={skipBtn} onClick={(e) => { e.stopPropagation(); skipRef.current?.() }}>
            건너뛰기 ▶
          </button>
        )}
        <div style={s.sky} />
        <div style={s.moon} />

        {[
          {t:'7%',l:'10%',sz:2.2},{t:'13%',l:'32%',sz:1.4},
          {t:'5%',l:'55%',sz:1.8},{t:'19%',l:'75%',sz:1.2},
          {t:'25%',l:'18%',sz:1.0},{t:'9%', l:'44%',sz:1.5},
          {t:'28%',l:'90%',sz:2.0},{t:'4%', l:'82%',sz:1.4},
          {t:'35%',l:'60%',sz:1.2},{t:'40%',l:'5%', sz:1.8},
        ].map((st, i) => (
          <div key={i} style={{
            position:'absolute', top:st.t, left:st.l,
            width:st.sz, height:st.sz, borderRadius:'50%',
            background:'#fff', opacity:0.6,
            animation:`starFlicker ${2.2+i*0.35}s ease-in-out infinite`,
          }} />
        ))}

        <svg viewBox="0 0 800 160" preserveAspectRatio="xMidYMax slice" style={s.silhouette}>
          <polygon points="40,160 62,95 84,160"    fill="#06030f" />
          <polygon points="58,160 84,72 110,160"   fill="#06030f" />
          <polygon points="95,160 118,100 141,160" fill="#06030f" />
          <rect x="155" y="118" width="58" height="42" fill="#06030f" />
          <polygon points="150,120 184,92 218,120"  fill="#06030f" />
          <rect x="162" y="130" width="13" height="30" fill="#030108" />
          <rect x="245" y="86" width="32" height="74" fill="#06030f" />
          <polygon points="240,88 261,62 282,88"   fill="#06030f" />
          <rect x="300" y="112" width="52" height="48" fill="#06030f" />
          <polygon points="295,114 326,86 357,114" fill="#06030f" />
          <polygon points="372,160 394,90 416,160" fill="#06030f" />
          <polygon points="390,160 416,70 442,160" fill="#06030f" />
          <rect x="455" y="120" width="46" height="40" fill="#06030f" />
          <polygon points="450,122 478,98 506,122" fill="#06030f" />
          <rect x="524" y="96" width="72" height="64" fill="#06030f" />
          <polygon points="519,98 560,68 601,98"   fill="#06030f" />
          <rect x="552" y="74" width="16" height="26" fill="#06030f" />
          <polygon points="618,160 638,102 658,160" fill="#06030f" />
          <polygon points="646,160 670,84 694,160" fill="#06030f" />
          <rect x="710" y="118" width="54" height="42" fill="#06030f" />
          <polygon points="705,120 737,94 769,120" fill="#06030f" />
        </svg>

        <div style={{
          position:'absolute', bottom:0, left:'-8%',
          width:'116%', height:'30%',
          background:'linear-gradient(to top, rgba(60,30,90,0.5) 0%, rgba(40,20,70,0.22) 55%, transparent 100%)',
          animation:'fogDrift 18s linear infinite alternate',
          filter:'blur(14px)',
          pointerEvents:'none',
        }} />

        {/* 중앙 콘텐츠 */}
        <div style={{
          ...s.inner,
          opacity: visible ? 1 : 0,
          transition: `opacity ${FADE_MS}ms ease`,
        }}>
          <p style={s.sentence}>
            {typed}
            {!confirming && sentence && <span style={s.cursor}>|</span>}
          </p>


          {confirming && typed.length >= CONFIRM_TEXT.length && (
            <p style={s.hint}>화면을 터치하거나 OK 싸인을 해주세요</p>
          )}

          {sentence?.showCards && roles.length > 0 && (
            <div style={s.cardGrid}>
              {roles.map((roleId, i) => (
                <div key={i} style={s.cardItem}>
                  <div style={s.cardImgBox}>
                    <img
                      src={`/roles/${roleId}.png`}
                      alt={ROLE_NAMES[roleId] || roleId}
                      style={s.cardImg}
                    />
                  </div>
                  <div style={s.cardName}>{ROLE_NAMES[roleId] || roleId}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

const s = {
  page: {
    height: '100vh',
    overflow: 'hidden',
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    userSelect: 'none',
  },

  sky: {
    position: 'absolute',
    inset: 0,
    background: [
      'radial-gradient(ellipse at 72% 8%, rgba(180,140,40,0.18) 0%, transparent 38%)',
      'radial-gradient(ellipse at 15% 85%, rgba(90,20,140,0.32) 0%, transparent 48%)',
      'linear-gradient(160deg, #160d38 0%, #0c1628 35%, #180c28 65%, #081420 100%)',
    ].join(', '),
  },

  moon: {
    position: 'absolute',
    top: 48,
    right: 90,
    width: 90,
    height: 90,
    borderRadius: '50%',
    background: 'radial-gradient(circle at 38% 36%, #fffde7, #f5e070 40%, #c8a820 80%)',
    animation: 'moonGlowPulse 3.5s ease-in-out infinite',
  },

  silhouette: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    width: '100%',
    height: 160,
    pointerEvents: 'none',
  },

  inner: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 36,
    maxWidth: 900,
    width: '90%',
    marginBottom: 80,
  },

  sentence: {
    margin: 0,
    fontSize: 38,
    fontWeight: 600,
    color: '#F8F1DD',
    textAlign: 'center',
    letterSpacing: 1,
    textShadow: '0 0 32px rgba(220,185,120,0.4)',
    lineHeight: 1.6,
    minHeight: 60,
    whiteSpace: 'nowrap',
  },

  cursor: {
    display: 'inline-block',
    marginLeft: 2,
    fontWeight: 200,
    color: 'rgba(248,241,221,0.7)',
    animation: 'cursorBlink 0.7s step-start infinite',
  },

  cardGrid: {
    display: 'flex',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 14,
    maxWidth: 820,
  },

  cardItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 6,
  },

  cardImgBox: {
    width: 76,
    height: 96,
    borderRadius: 10,
    overflow: 'hidden',
    background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(220,185,120,0.25)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 4px 18px rgba(0,0,0,0.45)',
  },

  cardImg: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  },

  cardName: {
    fontSize: 11,
    color: 'rgba(248,241,221,0.55)',
    textAlign: 'center',
  },

  hint: {
    margin: 0,
    fontSize: 15,
    color: 'rgba(248,241,221,0.38)',
    textAlign: 'center',
    letterSpacing: 0.5,
  },
}

const exitBtn = {
  position: 'absolute', top: 20, right: 20, zIndex: 10,
  padding: '8px 18px',
  border: '1px solid rgba(248,241,221,0.2)',
  borderRadius: 8,
  background: 'rgba(255,255,255,0.08)',
  color: 'rgba(248,241,221,0.7)',
  fontSize: 14, fontWeight: 600, cursor: 'pointer',
  backdropFilter: 'blur(8px)',
}

const skipBtn = {
  position: 'absolute', bottom: 36, right: 36, zIndex: 10,
  padding: '10px 28px',
  border: '1px solid rgba(220,185,120,0.35)',
  borderRadius: 24,
  background: 'rgba(220,185,120,0.12)',
  color: 'rgba(248,241,221,0.75)',
  fontSize: 15, fontWeight: 600, cursor: 'pointer',
  letterSpacing: 1,
  backdropFilter: 'blur(6px)',
  transition: 'background 0.2s, color 0.2s',
}
