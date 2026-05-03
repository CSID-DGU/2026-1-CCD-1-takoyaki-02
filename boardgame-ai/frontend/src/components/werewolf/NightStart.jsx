export default function NightStart({ onComplete }) {
  return (
    <div
      onClick={onComplete}
      style={styles.page}
    >
      <div style={styles.inner}>
        <div style={styles.ttsLabel}>TTS 재생 중</div>
        <div style={styles.title}>밤이 되었습니다</div>
        <div style={styles.subtitle}>모두 눈을 감아주세요</div>
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    background: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    cursor: 'pointer',
    userSelect: 'none',
  },
  inner: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 12,
    marginTop: '-80px',
  },
  ttsLabel: {
    fontSize: 13,
    color: '#999',
    letterSpacing: 0.2,
  },
  title: {
    fontSize: 40,
    fontWeight: 700,
    color: '#111',
    letterSpacing: -1,
  },
  subtitle: {
    fontSize: 15,
    color: '#666',
    marginTop: 4,
  },
}
