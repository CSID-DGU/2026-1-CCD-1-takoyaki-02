// 늑대인간 공용 대기/로딩 화면. 기존의 밋밋한 검은 화면 대신 테마 배경 위에
// 메시지를 띄운다. 플레이어 전환 대기·게임 시작 대기 등 짧은 막간에 사용.
export default function WerewolfLoading({ message = '잠시만 기다려주세요' }) {
  return (
    <div style={styles.page}>
      <style>{`
        @keyframes wlMoonGlow {
          0%,100% { box-shadow: 0 0 48px 18px rgba(220,185,80,0.22); }
          50%      { box-shadow: 0 0 72px 28px rgba(220,185,80,0.38); }
        }
        @keyframes wlStar { 0%,100%{opacity:.6} 50%{opacity:.2} }
        @keyframes wlDots { 0%{opacity:.25} 50%{opacity:1} 100%{opacity:.25} }
        @keyframes wlFadeIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

      <div style={styles.sky} />

      {/* 달 */}
      <div style={styles.moon} />

      {/* 별 */}
      {[{t:'8%',l:'12%',s:2},{t:'14%',l:'35%',s:1.5},{t:'6%',l:'62%',s:2.5},
        {t:'18%',l:'78%',s:1.5},{t:'22%',l:'20%',s:1},{t:'10%',l:'50%',s:1},
        {t:'30%',l:'88%',s:2},{t:'5%',l:'90%',s:1.5}].map((s, i) => (
        <div key={i} style={{
          position: 'absolute', top: s.t, left: s.l,
          width: s.s, height: s.s, borderRadius: '50%',
          background: '#fff', opacity: 0.7,
          animation: `wlStar ${2 + i * 0.4}s ease-in-out infinite`,
        }} />
      ))}

      <div style={styles.center}>
        <div style={styles.message}>{message}</div>
        <div style={styles.dots}>
          <span style={{ ...styles.dot, animationDelay: '0s' }} />
          <span style={{ ...styles.dot, animationDelay: '0.2s' }} />
          <span style={{ ...styles.dot, animationDelay: '0.4s' }} />
        </div>
      </div>
    </div>
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
    background: 'radial-gradient(ellipse at 70% 8%, rgba(180,140,40,0.18) 0%, transparent 38%), radial-gradient(ellipse at 15% 85%, rgba(90,20,140,0.32) 0%, transparent 48%), linear-gradient(160deg, #160d38 0%, #0c1628 35%, #180c28 65%, #081420 100%)',
  },
  moon: {
    position: 'absolute',
    top: 70,
    right: 90,
    width: 78,
    height: 78,
    borderRadius: '50%',
    background: 'radial-gradient(circle at 38% 36%, #fffde7, #f5e070 40%, #c8a820 80%)',
    animation: 'wlMoonGlow 3s ease-in-out infinite',
  },
  center: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 18,
    animation: 'wlFadeIn 0.6s ease-out both',
  },
  message: {
    fontSize: 28,
    fontWeight: 700,
    color: '#F8F1DD',
    letterSpacing: 1,
    textShadow: '0 0 30px rgba(220,195,120,0.35), 0 2px 10px rgba(0,0,0,0.5)',
  },
  dots: {
    display: 'flex',
    gap: 10,
  },
  dot: {
    width: 9,
    height: 9,
    borderRadius: '50%',
    background: 'rgba(248,241,221,0.75)',
    animation: 'wlDots 1.2s ease-in-out infinite',
  },
}
