import { useState } from 'react'

const s = {
  page: {
    minHeight: '100vh',
    background: '#f5f5f7',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', sans-serif",
    color: '#111',
  },
  card: {
    background: '#fff',
    border: '1px solid #e0e0e0',
    borderRadius: 16,
    padding: 32,
    width: 660,
    boxShadow: '0 2px 12px rgba(0,0,0,0.07)',
  },
  title: { fontSize: 20, fontWeight: 600, marginBottom: 24 },
  body: { display: 'flex', gap: 28 },
  camera: {
    width: 280,
    minHeight: 360,
    background: '#d9d9d9',
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#666',
    fontSize: 14,
    flexShrink: 0,
  },
  listArea: { flex: 1, display: 'flex', flexDirection: 'column', gap: 8 },
  playerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '9px 12px',
    background: '#f7f7f7',
    borderRadius: 8,
    border: '1px solid #ebebeb',
  },
  nameText: { flex: 1, fontSize: 14, fontWeight: 500 },
  statusText: (registered) => ({
    fontSize: 12,
    color: registered ? '#1a7a4a' : '#888',
    marginRight: 4,
    minWidth: 44,
  }),
  editBtn: {
    fontSize: 12,
    padding: '4px 10px',
    border: '1px solid #ccc',
    borderRadius: 6,
    background: '#fff',
    cursor: 'pointer',
  },
  nameInput: {
    flex: 1,
    padding: '6px 10px',
    border: '1px solid #bbb',
    borderRadius: 6,
    fontSize: 14,
    outline: 'none',
  },
  saveBtn: {
    fontSize: 12,
    padding: '5px 12px',
    border: 'none',
    borderRadius: 6,
    background: '#111',
    color: '#fff',
    cursor: 'pointer',
  },
  deleteBtn: {
    fontSize: 12,
    padding: '5px 10px',
    border: '1px solid #d44',
    borderRadius: 6,
    background: '#fff',
    color: '#d44',
    cursor: 'pointer',
  },
  addBtn: {
    alignSelf: 'center',
    padding: '6px 20px',
    border: '1px solid #ccc',
    borderRadius: 8,
    background: '#fff',
    cursor: 'pointer',
    fontSize: 18,
    marginTop: 4,
    color: '#555',
  },
  footer: { display: 'flex', justifyContent: 'flex-end', marginTop: 28 },
  startBtn: (enabled) => ({
    padding: '10px 26px',
    border: '1px solid #ccc',
    borderRadius: 8,
    background: enabled ? '#111' : '#e8e8e8',
    color: enabled ? '#fff' : '#aaa',
    cursor: enabled ? 'pointer' : 'default',
    fontSize: 15,
    fontWeight: 500,
  }),
}

export default function SeatRegistration({ players, setPlayers, onStart }) {
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')

  const addPlayer = () => {
    const newPlayer = { id: Date.now(), name: '', registered: false }
    setPlayers(prev => [...prev, newPlayer])
    setEditingId(newPlayer.id)
    setEditName('')
  }

  const saveName = (id) => {
    const trimmed = editName.trim()
    if (!trimmed) return
    setPlayers(prev => prev.map(p => p.id === id ? { ...p, name: trimmed, registered: true } : p))
    setEditingId(null)
    setEditName('')
  }

  const deletePlayer = (id) => {
    setPlayers(prev => prev.filter(p => p.id !== id))
    if (editingId === id) {
      setEditingId(null)
      setEditName('')
    }
  }

  const startEdit = (player) => {
    setEditingId(player.id)
    setEditName(player.name)
  }

  const canStart = players.length > 0 && players.every(p => p.registered)

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.title}>플레이어 등록</div>
        <div style={s.body}>
          <div style={s.camera}>실시간 카메라</div>
          <div style={s.listArea}>
            {players.map(p => (
              <div key={p.id} style={s.playerRow}>
                {editingId === p.id ? (
                  <>
                    <input
                      value={editName}
                      onChange={e => setEditName(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && saveName(p.id)}
                      style={s.nameInput}
                      autoFocus
                      placeholder="이름 입력"
                    />
                    <button style={s.saveBtn} onClick={() => saveName(p.id)}>저장</button>
                    <button style={s.deleteBtn} onClick={() => deletePlayer(p.id)}>삭제</button>
                  </>
                ) : (
                  <>
                    <span style={s.nameText}>{p.name}</span>
                    <span style={s.statusText(p.registered)}>
                      {p.registered ? '등록됨' : '등록 중'}
                    </span>
                    <button style={s.editBtn} onClick={() => startEdit(p)}>수정</button>
                  </>
                )}
              </div>
            ))}
            <button style={s.addBtn} onClick={addPlayer}>+</button>
          </div>
        </div>
        <div style={s.footer}>
          <button style={s.startBtn(canStart)} onClick={canStart ? onStart : undefined}>
            게임 시작 →
          </button>
        </div>
      </div>
    </div>
  )
}
