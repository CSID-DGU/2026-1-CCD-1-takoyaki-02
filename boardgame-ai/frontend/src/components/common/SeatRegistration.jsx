import { useState } from 'react'

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
    if (editingId === id) { setEditingId(null); setEditName('') }
  }

  const startEdit = (player) => {
    setEditingId(player.id)
    setEditName(player.name)
  }

  const canStart = players.length > 0 && players.every(p => p.registered)

  return (
    <div style={{
      minHeight: '100vh',
      background: '#eef0f8',
      display: 'flex',
      padding: '40px 48px',
      gap: 40,
      fontFamily: "'Segoe UI', sans-serif",
      color: '#111',
      boxSizing: 'border-box',
    }}>

      {/* ── 왼쪽: 타이틀 + 카메라 ── */}
      <div style={{ flex: 1.3, display: 'flex', flexDirection: 'column', gap: 24 }}>

        {/* 타이틀 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ position: 'relative', width: 48, height: 48 }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%',
              background: '#dde1f5',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 22,
            }}>👤</div>
            <div style={{
              position: 'absolute', bottom: 0, right: 0,
              width: 17, height: 17, borderRadius: '50%',
              background: '#5b74f5',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, color: '#fff', fontWeight: 700,
              border: '2px solid #eef0f8',
            }}>+</div>
          </div>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>플레이어 등록</div>
            <div style={{ fontSize: 13, color: '#888', marginTop: 3 }}>게임에 참여할 플레이어를 등록해주세요.</div>
          </div>
        </div>

        {/* 카메라 영역 */}
        <div style={{
          flex: 1,
          background: '#e2e4ee',
          borderRadius: 20,
          position: 'relative',
          overflow: 'hidden',
          minHeight: 380,
        }}>
          {/* LIVE 뱃지 */}
          <div style={{
            position: 'absolute', top: 16, left: 16, zIndex: 1,
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(255,255,255,0.88)',
            borderRadius: 20, padding: '5px 12px',
            fontSize: 12, fontWeight: 600, color: '#333',
          }}>
            <span style={{ color: '#e33', fontSize: 9 }}>●</span> LIVE
          </div>

          {/* 코너 브라켓 4개 */}
          {[
            { top: 14, right: 14, borderTop: true, borderRight: true, borderRadius: '0 6px 0 0' },
            { top: 14, left: 14,  borderTop: true, borderLeft: true,  borderRadius: '6px 0 0 0' },
            { bottom: 14, right: 14, borderBottom: true, borderRight: true, borderRadius: '0 0 6px 0' },
            { bottom: 14, left: 14,  borderBottom: true, borderLeft: true,  borderRadius: '0 0 0 6px' },
          ].map((corner, i) => {
            const { borderRadius, borderTop, borderRight, borderBottom, borderLeft, ...pos } = corner
            const bStyle = '2.5px solid #8a93b8'
            return (
              <div key={i} style={{
                position: 'absolute', width: 22, height: 22,
                borderRadius,
                borderTop: borderTop ? bStyle : 'none',
                borderRight: borderRight ? bStyle : 'none',
                borderBottom: borderBottom ? bStyle : 'none',
                borderLeft: borderLeft ? bStyle : 'none',
                ...pos,
              }} />
            )
          })}

          {/* 하단 안내 */}
          <div style={{
            position: 'absolute', bottom: 18, left: '50%', transform: 'translateX(-50%)',
            background: 'rgba(255,255,255,0.92)',
            borderRadius: 12, padding: '9px 18px',
            fontSize: 13, color: '#444', whiteSpace: 'nowrap',
            display: 'flex', alignItems: 'center', gap: 8,
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          }}>
            📷 카메라에 손을 비춰 인식을 시작해주세요
          </div>
        </div>
      </div>

      {/* ── 오른쪽: 플레이어 목록 ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 56 }}>

        {/* 플레이어 목록 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {players.map((p, idx) => (
            <div key={p.id} style={{
              background: '#fff',
              border: '1px solid #eaecf4',
              borderRadius: 14,
              padding: '14px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}>
              <div style={{
                width: 34, height: 34, borderRadius: '50%',
                background: '#e8eaf8',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700, color: '#5b74f5', flexShrink: 0,
              }}>
                {String(idx + 1).padStart(2, '0')}
              </div>

              {editingId === p.id ? (
                <>
                  <input
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && saveName(p.id)}
                    autoFocus
                    placeholder="이름 입력"
                    style={{
                      flex: 1, border: '1.5px solid #b0b8e8',
                      borderRadius: 8, padding: '7px 11px',
                      fontSize: 14, outline: 'none',
                    }}
                  />
                  <button onClick={() => saveName(p.id)} style={{
                    padding: '7px 16px', border: 'none', borderRadius: 8,
                    background: '#5b74f5', color: '#fff', fontSize: 13,
                    fontWeight: 600, cursor: 'pointer',
                  }}>저장</button>
                  <button onClick={() => deletePlayer(p.id)} style={{
                    padding: '7px 12px', border: '1px solid #e44',
                    borderRadius: 8, background: '#fff',
                    color: '#e44', fontSize: 13, cursor: 'pointer',
                  }}>삭제</button>
                </>
              ) : (
                <>
                  <span style={{ flex: 1, fontSize: 15, fontWeight: 600 }}>{p.name}</span>
                  <span style={{
                    background: '#5b74f5', color: '#fff',
                    borderRadius: 20, padding: '4px 13px',
                    fontSize: 12, fontWeight: 500, flexShrink: 0,
                  }}>등록됨</span>
                  <button onClick={() => startEdit(p)} style={{
                    background: 'none', border: 'none',
                    cursor: 'pointer', fontSize: 19,
                    color: '#bbb', padding: '0 4px', lineHeight: 1,
                  }}>⋮</button>
                </>
              )}
            </div>
          ))}
        </div>

        {/* 플레이어 추가 */}
        <button onClick={addPlayer} style={{
          border: '1.5px dashed #c0c6dc',
          borderRadius: 14,
          background: 'transparent',
          padding: '17px',
          fontSize: 14, fontWeight: 600,
          color: '#5b74f5',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          + 플레이어 추가
        </button>

        <div style={{ flex: 1 }} />

        {/* 게임 시작 버튼 */}
        <button
          onClick={canStart ? onStart : undefined}
          style={{
            padding: '20px 0',
            border: 'none',
            borderRadius: 16,
            background: canStart
              ? 'linear-gradient(135deg, #5b74f5 0%, #7b5ff5 100%)'
              : '#d8dae8',
            color: canStart ? '#fff' : '#aaa',
            fontSize: 17,
            fontWeight: 700,
            cursor: canStart ? 'pointer' : 'default',
            letterSpacing: 0.5,
            transition: 'background 0.2s',
          }}
        >
          게임 시작 →
        </button>
      </div>
    </div>
  )
}
