const s = {
  page: {
    minHeight: '100vh',
    background: '#f5f5f7',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', sans-serif",
    color: '#111',
  },
  title: { fontSize: 48, fontWeight: 700, marginBottom: 14 },
  subtitle: { fontSize: 22, color: '#555', marginBottom: 56 },
  cards: { display: 'flex', gap: 36, marginBottom: 64 },
  card: disabled => ({
    width: 320,
    padding: 40,
    background: '#fff',
    border: '1px solid #e0e0e0',
    borderRadius: 22,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.45 : 1,
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    transition: 'box-shadow 0.15s, border-color 0.15s',
  }),
  icon: { fontSize: 48, marginBottom: 8 },
  gameName: { fontSize: 26, fontWeight: 600 },
  gameInfo: { fontSize: 19, color: '#666' },
  badge: {
    display: 'inline-block',
    marginTop: 14,
    padding: '5px 16px',
    background: '#efefef',
    borderRadius: 100,
    fontSize: 17,
    color: '#555',
    width: 'fit-content',
  },
  exitButton: {
    border: '1px solid #d7d7d9',
    borderRadius: 8,
    background: '#fff',
    color: '#333',
    padding: '11px 22px',
    fontSize: 17,
    fontWeight: 700,
    cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
  },
  footer: { fontSize: 18, color: '#aaa' },
}

function GameCard({ icon, name, info1, info2, onClick, disabled = false }) {
  return (
    <div
      style={s.card(disabled)}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={e => {
        if (disabled) return
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.12)'
        e.currentTarget.style.borderColor = '#bbb'
      }}
      onMouseLeave={e => {
        if (disabled) return
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)'
        e.currentTarget.style.borderColor = '#e0e0e0'
      }}
    >
      <div style={s.icon}>{icon}</div>
      <div style={s.gameName}>{name}</div>
      <div style={s.gameInfo}>{info1}</div>
      <div style={s.gameInfo}>{info2}</div>
    </div>
  )
}

export default function Lobby({ players, send, onSelectYacht, onSelectWerewolf, onExit }) {
  const yachtDisabled = players.length >= 7

  return (
    <div style={s.page}>
      <div style={s.title}>보드게임 AI 테이블</div>
      <div style={s.subtitle}>게임을 선택해 시작하세요</div>
      <div style={s.cards}>
        <GameCard
          icon="🎲"
          name="요트 다이스"
          info1="1-6인 플레이어"
          info2="주사위 자동 인식"
          disabled={yachtDisabled}
          onClick={() => {
            send?.('select_game', { game_type: 'yacht' })
            onSelectYacht()
          }}
        />
        <GameCard
          icon="🌙"
          name="한밤의 늑대인간"
          info1="4-10인 플레이어"
          info2="카드·제스처 인식"
          onClick={() => {
            send('select_game', { game_type: 'werewolf' })
            onSelectWerewolf()
          }}
        />
      </div>
      <button style={s.exitButton} onClick={onExit}>나가기</button>
    </div>
  )
}
