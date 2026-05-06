import { useRef, useEffect } from 'react'

const RADIUS = 110
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

// timeLeft는 백엔드 timer_remaining을 그대로 전달받아 사용한다.
// 로컬 setInterval 없이 백엔드 state_update(1초마다)로 동기화된다.
export default function DayDiscussion({ timeLeft = 300, onVote, onAddTime }) {
  const maxTimeRef = useRef(timeLeft)

  useEffect(() => {
    if (timeLeft > maxTimeRef.current) {
      maxTimeRef.current = timeLeft
    }
  }, [timeLeft])

  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }

  const progress = Math.max(0, timeLeft / maxTimeRef.current)
  const strokeDashoffset = CIRCUMFERENCE * (1 - progress)
  const isUrgent = timeLeft <= 30

  return (
    <>
      <style>{`
        @keyframes urgentPulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.55; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div style={styles.page}>

        {/* 배경 */}
        <div style={styles.sky} />
        <div style={styles.haze} />

        {/* 마을 실루엣 */}
        <svg viewBox="0 0 800 160" preserveAspectRatio="xMidYMax slice" style={styles.silhouette}>
          <polygon points="40,160 62,95 84,160"   fill="#1a0800" />
          <polygon points="58,160 84,72 110,160"  fill="#1a0800" />
          <polygon points="95,160 118,100 141,160" fill="#1a0800" />
          <rect x="155" y="118" width="58" height="42" fill="#1a0800" />
          <polygon points="150,120 184,92 218,120" fill="#1a0800" />
          <rect x="162" y="130" width="13" height="30" fill="#120600" />
          <rect x="245" y="86" width="32" height="74" fill="#1a0800" />
          <polygon points="240,88 261,62 282,88"  fill="#1a0800" />
          <rect x="300" y="112" width="52" height="48" fill="#1a0800" />
          <polygon points="295,114 326,86 357,114" fill="#1a0800" />
          <polygon points="372,160 394,90 416,160" fill="#1a0800" />
          <polygon points="390,160 416,70 442,160" fill="#1a0800" />
          <rect x="455" y="120" width="46" height="40" fill="#1a0800" />
          <polygon points="450,122 478,98 506,122" fill="#1a0800" />
          <rect x="524" y="96" width="72" height="64" fill="#1a0800" />
          <polygon points="519,98 560,68 601,98"  fill="#1a0800" />
          <rect x="552" y="74" width="16" height="26" fill="#1a0800" />
          <polygon points="618,160 638,102 658,160" fill="#1a0800" />
          <polygon points="646,160 670,84 694,160" fill="#1a0800" />
          <rect x="710" y="118" width="54" height="42" fill="#1a0800" />
          <polygon points="705,120 737,94 769,120" fill="#1a0800" />
        </svg>

        {/* 중앙 타이머 */}
        <div style={{ ...styles.timerWrapper, animation: isUrgent ? 'urgentPulse 0.8s ease-in-out infinite' : 'fadeIn 0.8s ease-out both' }}>

          {/* 링 레이블 */}
          <div style={styles.timerLabel}>토론 시간</div>

          {/* SVG 링 */}
          <svg width={280} height={280} style={{ display: 'block' }}>
            {/* 광원 효과 */}
            <defs>
              <filter id="glow">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
              <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor={isUrgent ? '#ff6b35' : '#F6D568'} />
                <stop offset="100%" stopColor={isUrgent ? '#c0392b' : '#B8791A'} />
              </linearGradient>
            </defs>

            {/* 트랙 */}
            <circle
              cx={140} cy={140} r={RADIUS}
              fill="none"
              stroke="rgba(255,255,255,0.08)"
              strokeWidth={14}
            />

            {/* 진행 링 */}
            <circle
              cx={140} cy={140} r={RADIUS}
              fill="none"
              stroke="url(#ringGrad)"
              strokeWidth={14}
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={strokeDashoffset}
              transform="rotate(-90 140 140)"
              filter="url(#glow)"
              style={{ transition: 'stroke-dashoffset 1s linear, stroke 0.3s' }}
            />

            {/* 타이머 숫자 */}
            <text
              x={140} y={148}
              textAnchor="middle"
              dominantBaseline="middle"
              fill={isUrgent ? '#ff8c6b' : '#F8F1DD'}
              fontSize={54}
              fontWeight={700}
              fontFamily="'Segoe UI', sans-serif"
              letterSpacing={2}
            >
              {formatTime(timeLeft)}
            </text>
          </svg>
        </div>

        {/* 하단 버튼 */}
        <div style={styles.buttonRow}>
          <button onClick={onAddTime} style={styles.btnSecondary}>
            + 30초 추가
          </button>
          <button onClick={onVote} style={styles.btnPrimary}>
            즉시 투표 →
          </button>
        </div>

      </div>
    </>
  )
}

const styles = {
  page: {
    height: '100vh',
    overflow: 'hidden',
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    color: '#F8F1DD',
    userSelect: 'none',
  },

  sky: {
    position: 'absolute',
    inset: 0,
    background: 'radial-gradient(ellipse at 50% 0%, rgba(240,180,60,0.18), transparent 55%), linear-gradient(180deg, #0f0800 0%, #2d1400 25%, #6e3510 50%, #b86018 70%, #d4920a 85%, #e8b830 100%)',
  },

  haze: {
    position: 'absolute',
    inset: 0,
    background: 'radial-gradient(ellipse at 50% 45%, rgba(255,180,60,0.12), transparent 60%)',
    pointerEvents: 'none',
  },

  silhouette: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    width: '100%',
    height: 160,
    pointerEvents: 'none',
  },

  timerWrapper: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 12,
    marginBottom: 24,
  },

  timerLabel: {
    fontSize: 13,
    fontWeight: 700,
    letterSpacing: 3,
    color: 'rgba(248,241,221,0.55)',
    textTransform: 'uppercase',
  },

  buttonRow: {
    position: 'relative',
    zIndex: 2,
    display: 'flex',
    justifyContent: 'center',
    gap: 20,
    padding: '0 40px',
    width: '100%',
    maxWidth: 480,
  },

  btnSecondary: {
    flex: 1,
    maxWidth: 200,
    padding: '16px 0',
    border: '1.5px solid rgba(246,213,104,0.35)',
    borderRadius: 16,
    background: 'rgba(20,10,0,0.55)',
    backdropFilter: 'blur(8px)',
    color: '#F6D568',
    fontSize: 16,
    fontWeight: 600,
    cursor: 'pointer',
    letterSpacing: 0.3,
  },

  btnPrimary: {
    flex: 1,
    maxWidth: 200,
    padding: '16px 0',
    border: 'none',
    borderRadius: 16,
    background: 'linear-gradient(135deg, #F6D568, #B8791A)',
    color: '#1A0A00',
    fontSize: 16,
    fontWeight: 700,
    cursor: 'pointer',
    letterSpacing: 0.3,
    boxShadow: '0 6px 0 #6B420A, 0 10px 24px rgba(0,0,0,0.4)',
  },
}
