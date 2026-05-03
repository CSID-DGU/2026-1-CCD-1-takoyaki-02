export default function RoleRegShowCard({ player, onDetected }) {
  return (
    <div style={styles.page}>

      {/* 배경 효과 */}
      <div style={styles.moon} />
      <div style={styles.fog} />

      {/* 메인 카드 */}
      <div style={styles.card}>

        {/* 플레이어 이름 */}
        <div style={styles.name}>
          {player?.name} 님
        </div>

        {/* 안내 텍스트 */}
        <div style={styles.guide}>
          카드를 카메라에 보여주세요
        </div>

        {/* 카메라 영역 */}
        <div style={styles.cameraBox}>
          <div style={styles.cameraInner}>
            실시간 카메라
          </div>

          {/* 스캔 프레임 */}
          <div style={styles.scanFrame} />
        </div>

        {/* 버튼 */}
        <button
          onClick={() => onDetected?.(null)}
          style={styles.button}
        >
          카드 인식 완료
        </button>

      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background:
      'radial-gradient(circle at 50% 20%, rgba(240,200,80,0.15), transparent 30%), linear-gradient(180deg, #1C2A35 0%, #0B141A 100%)',
    fontFamily: "'Segoe UI', sans-serif",
    position: 'relative',
    overflow: 'hidden',
    color: '#F5F5F5',
  },

  moon: {
    position: 'absolute',
    top: 60,
    right: 80,
    width: 120,
    height: 120,
    borderRadius: '50%',
    background: 'radial-gradient(circle, #E6B85C, transparent)',
    opacity: 0.25,
  },

  fog: {
    position: 'absolute',
    bottom: 0,
    width: '100%',
    height: '40%',
    background: 'linear-gradient(transparent, rgba(0,0,0,0.6))',
  },

  card: {
    width: 420,
    padding: '40px 32px',
    borderRadius: 24,
    background: 'rgba(20,30,40,0.85)',
    backdropFilter: 'blur(10px)',
    border: '1px solid rgba(255,255,255,0.1)',
    boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },

  name: {
    fontSize: 24,
    fontWeight: 700,
    marginBottom: 8,
  },

  guide: {
    fontSize: 14,
    color: '#B0B8C0',
    marginBottom: 24,
  },

  cameraBox: {
    width: 300,
    height: 220,
    borderRadius: 16,
    background: '#0B141A',
    border: '2px solid rgba(230,184,92,0.4)',
    position: 'relative',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  cameraInner: {
    color: '#555',
    fontSize: 14,
  },

  scanFrame: {
    position: 'absolute',
    width: '80%',
    height: '70%',
    border: '2px dashed rgba(230,184,92,0.6)',
    borderRadius: 12,
  },

  button: {
    marginTop: 32,
    padding: '14px 32px',
    borderRadius: 16,
    border: 'none',
    background: 'linear-gradient(135deg, #E6B85C, #B48A3C)',
    color: '#1A1208',
    fontSize: 16,
    fontWeight: 700,
    cursor: 'pointer',
    boxShadow: '0 6px 0 #8A6A2A',
  },
}