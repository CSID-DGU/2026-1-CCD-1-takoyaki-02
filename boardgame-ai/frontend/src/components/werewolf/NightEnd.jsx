export default function NightEnd({ onComplete }) {
  return (
    <>
      <style>{`
        @keyframes sunRise {
          0%   { transform: translateY(80px) scale(0.7); opacity: 0; }
          60%  { opacity: 1; }
          100% { transform: translateY(0px) scale(1); opacity: 1; }
        }
        @keyframes glowPulse {
          0%, 100% { box-shadow: 0 0 60px 24px rgba(255,210,80,0.45), 0 0 120px 60px rgba(255,140,30,0.2); }
          50%       { box-shadow: 0 0 90px 36px rgba(255,230,100,0.65), 0 0 180px 80px rgba(255,160,40,0.3); }
        }
        @keyframes skyFade {
          0%   { opacity: 0; }
          100% { opacity: 1; }
        }
        @keyframes textRise {
          0%   { opacity: 0; transform: translateY(16px); }
          100% { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div onClick={onComplete} style={styles.page}>

        {/* 배경 — 밤에서 여명으로 */}
        <div style={styles.sky} />

        {/* 지평선 글로우 */}
        <div style={styles.horizonGlow} />

        {/* 마을 실루엣 */}
        <svg
          viewBox="0 0 800 160"
          preserveAspectRatio="xMidYMax slice"
          style={styles.silhouette}
        >
          {/* 나무들 */}
          <polygon points="60,160 80,100 100,160" fill="#0a0614" />
          <polygon points="75,160 100,80 125,160" fill="#0a0614" />
          <polygon points="110,160 130,105 150,160" fill="#0a0614" />
          {/* 집들 */}
          <rect x="170" y="120" width="60" height="40" fill="#0a0614" />
          <polygon points="165,120 200,95 235,120" fill="#0a0614" />
          <rect x="175" y="130" width="14" height="30" fill="#1a0a2e" />
          {/* 탑 */}
          <rect x="260" y="90" width="30" height="70" fill="#0a0614" />
          <polygon points="255,92 275,68 295,92" fill="#0a0614" />
          {/* 집 */}
          <rect x="320" y="115" width="50" height="45" fill="#0a0614" />
          <polygon points="315,115 345,88 375,115" fill="#0a0614" />
          {/* 나무 */}
          <polygon points="390,160 410,95 430,160" fill="#0a0614" />
          <polygon points="405,160 430,75 455,160" fill="#0a0614" />
          {/* 집 */}
          <rect x="460" y="125" width="45" height="35" fill="#0a0614" />
          <polygon points="455,125 482,102 510,125" fill="#0a0614" />
          {/* 큰 건물 */}
          <rect x="530" y="100" width="70" height="60" fill="#0a0614" />
          <polygon points="525,102 565,72 605,102" fill="#0a0614" />
          <rect x="558" y="78" width="14" height="24" fill="#0a0614" />
          {/* 나무 */}
          <polygon points="620,160 638,105 656,160" fill="#0a0614" />
          <polygon points="648,160 670,88 692,160" fill="#0a0614" />
          <polygon points="668,160 690,108 712,160" fill="#0a0614" />
          {/* 집 */}
          <rect x="715" y="120" width="55" height="40" fill="#0a0614" />
          <polygon points="710,120 742,96 774,120" fill="#0a0614" />
        </svg>

        {/* 태양 */}
        <div style={styles.sunContainer}>
          <div style={styles.sun} />
        </div>

        {/* 텍스트 */}
        <div style={styles.textBlock}>
          <div style={styles.title}>아침이 밝았습니다</div>
          <div style={styles.subtitle}>모두 눈을 뜨세요</div>
        </div>

      </div>
    </>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    position: 'relative',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    cursor: 'pointer',
    userSelect: 'none',
  },

  sky: {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(180deg, #0d0821 0%, #1e0c3a 22%, #4a1830 45%, #8c3b1e 65%, #d4641c 80%, #f0a030 100%)',
    animation: 'skyFade 1.8s ease-out forwards',
  },

  horizonGlow: {
    position: 'absolute',
    bottom: '20%',
    left: '50%',
    transform: 'translateX(-50%)',
    width: '70%',
    height: 120,
    background: 'radial-gradient(ellipse at center bottom, rgba(255,160,40,0.35), transparent 70%)',
    filter: 'blur(20px)',
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

  sunContainer: {
    position: 'relative',
    zIndex: 1,
    marginBottom: 60,
    animation: 'sunRise 2s cubic-bezier(0.22, 0.61, 0.36, 1) forwards',
  },

  sun: {
    width: 140,
    height: 140,
    borderRadius: '50%',
    background: 'radial-gradient(circle at 40% 38%, #fffde7, #fdd835 40%, #f57f17 80%)',
    animation: 'glowPulse 2.4s ease-in-out 2s infinite',
    boxShadow: '0 0 60px 24px rgba(255,210,80,0.45), 0 0 120px 60px rgba(255,140,30,0.2)',
  },

  textBlock: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 10,
    animation: 'textRise 1s ease-out 1.2s both',
  },

  title: {
    fontSize: 38,
    fontWeight: 700,
    color: '#fff8e1',
    letterSpacing: -0.5,
    textShadow: '0 2px 12px rgba(255,160,40,0.5)',
  },

  subtitle: {
    fontSize: 16,
    color: 'rgba(255,240,200,0.85)',
  },
}
