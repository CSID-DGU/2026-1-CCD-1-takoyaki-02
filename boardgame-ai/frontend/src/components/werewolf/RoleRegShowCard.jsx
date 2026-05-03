export default function RoleRegShowCard({ player, onDetected }) {
  return (
    <>
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes moonGlow {
          0%, 100% { box-shadow: 0 0 40px 16px rgba(220,195,120,0.18); }
          50%       { box-shadow: 0 0 60px 24px rgba(220,195,120,0.3); }
        }
        @keyframes shimmer {
          0%, 100% { opacity: 0.5; }
          50%       { opacity: 1; }
        }
      `}</style>

      <div style={styles.page}>

        {/* 배경 */}
        <div style={styles.sky} />

        {/* 달 */}
        <div style={styles.moon} />

        {/* 별 */}
        {[
          { top: '8%',  left: '12%', size: 2 },
          { top: '14%', left: '35%', size: 1.5 },
          { top: '6%',  left: '62%', size: 2.5 },
          { top: '18%', left: '78%', size: 1.5 },
          { top: '22%', left: '20%', size: 1 },
          { top: '10%', left: '50%', size: 1 },
          { top: '30%', left: '88%', size: 2 },
          { top: '5%',  left: '90%', size: 1.5 },
        ].map((s, i) => (
          <div key={i} style={{
            position: 'absolute',
            top: s.top, left: s.left,
            width: s.size, height: s.size,
            borderRadius: '50%',
            background: '#fff',
            opacity: 0.7,
            animation: `shimmer ${2 + i * 0.4}s ease-in-out infinite`,
          }} />
        ))}

        {/* 마을 실루엣 */}
        <svg viewBox="0 0 800 160" preserveAspectRatio="xMidYMax slice" style={styles.silhouette}>
          <polygon points="40,160 62,95 84,160"    fill="#0a0614" />
          <polygon points="58,160 84,72 110,160"   fill="#0a0614" />
          <polygon points="95,160 118,100 141,160" fill="#0a0614" />
          <rect x="155" y="118" width="58" height="42" fill="#0a0614" />
          <polygon points="150,120 184,92 218,120"  fill="#0a0614" />
          <rect x="162" y="130" width="13" height="30" fill="#060310" />
          <rect x="245" y="86" width="32" height="74" fill="#0a0614" />
          <polygon points="240,88 261,62 282,88"   fill="#0a0614" />
          <rect x="300" y="112" width="52" height="48" fill="#0a0614" />
          <polygon points="295,114 326,86 357,114" fill="#0a0614" />
          <polygon points="372,160 394,90 416,160" fill="#0a0614" />
          <polygon points="390,160 416,70 442,160" fill="#0a0614" />
          <rect x="455" y="120" width="46" height="40" fill="#0a0614" />
          <polygon points="450,122 478,98 506,122" fill="#0a0614" />
          <rect x="524" y="96" width="72" height="64" fill="#0a0614" />
          <polygon points="519,98 560,68 601,98"   fill="#0a0614" />
          <rect x="552" y="74" width="16" height="26" fill="#0a0614" />
          <polygon points="618,160 638,102 658,160" fill="#0a0614" />
          <polygon points="646,160 670,84 694,160" fill="#0a0614" />
          <rect x="710" y="118" width="54" height="42" fill="#0a0614" />
          <polygon points="705,120 737,94 769,120" fill="#0a0614" />
        </svg>

        {/* 중앙 텍스트 */}
        <div style={styles.center}>
          <div style={styles.name}>
            {player?.playername} 님
          </div>
          <div style={styles.divider} />
          <div style={styles.guide}>
            카드를 카메라에 보여주세요
          </div>

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
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    userSelect: 'none',
  },

  sky: {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(180deg, #04020e 0%, #0d0821 30%, #1a1035 60%, #12082a 100%)',
  },

  moon: {
    position: 'absolute',
    top: 60,
    right: 100,
    width: 90,
    height: 90,
    borderRadius: '50%',
    background: 'radial-gradient(circle at 38% 36%, #fffde7, #f5e070 40%, #c8a820 80%)',
    animation: 'moonGlow 3s ease-in-out infinite',
  },

  silhouette: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    width: '100%',
    height: 160,
    pointerEvents: 'none',
  },

  center: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 20,
    animation: 'fadeIn 0.8s ease-out both',
  },

  name: {
    fontSize: 52,
    fontWeight: 800,
    color: '#F8F1DD',
    letterSpacing: 2,
    textShadow: '0 0 40px rgba(220,195,120,0.4), 0 2px 12px rgba(0,0,0,0.6)',
  },

  divider: {
    width: 60,
    height: 1.5,
    background: 'linear-gradient(90deg, transparent, rgba(220,195,120,0.5), transparent)',
    borderRadius: 2,
  },

  guide: {
    fontSize: 22,
    fontWeight: 400,
    color: 'rgba(248,241,221,0.6)',
    letterSpacing: 1,
  },
}
