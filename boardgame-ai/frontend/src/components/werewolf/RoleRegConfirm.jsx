import { useState } from 'react'

const ROLES = [
  { id: 'doppelganger', name: '도플갱어',   image: '/roles/doppelganger.png', gradient: 'linear-gradient(135deg, #4a1a6b, #2a0a3a)', desc: '다른 플레이어의 카드를 보고 그 역할이 됩니다.' },
  { id: 'werewolf_1',   name: '늑대인간',   image: '/roles/werewolf.png',     gradient: 'linear-gradient(135deg, #6b1a1a, #3a0a0a)', desc: '밤에 깨어나 동료 늑대인간을 확인합니다. 혼자라면 중앙 카드 1장을 볼 수 있습니다.' },
  { id: 'minion',       name: '하수인',     image: '/roles/minion.png',       gradient: 'linear-gradient(135deg, #5a1a7a, #2a0a4a)', desc: '늑대인간 팀이지만 누가 늑대인간인지 알 수 없습니다.' },
  { id: 'seer',         name: '예언자',     image: '/roles/seer.png',         gradient: 'linear-gradient(135deg, #1a3a7a, #0a1a4a)', desc: '다른 플레이어 1명의 카드 또는 중앙 카드 2장을 볼 수 있습니다.' },
  { id: 'robber',       name: '강도',       image: '/roles/robber.png',       gradient: 'linear-gradient(135deg, #3a3a1a, #1a1a0a)', desc: '다른 플레이어의 카드와 자신의 카드를 교환할 수 있습니다.' },
  { id: 'troublemaker', name: '말썽쟁이',   image: '/roles/troublemaker.png', gradient: 'linear-gradient(135deg, #1a5a4a, #0a2a2a)', desc: '자신을 제외한 두 플레이어의 카드를 서로 교환합니다.' },
  { id: 'drunk',        name: '주정뱅이',   image: '/roles/drunk.png',        gradient: 'linear-gradient(135deg, #5a3a1a, #2a1a0a)', desc: '중앙 카드 1장과 자신의 카드를 교환합니다. 단, 새 카드를 볼 수 없습니다.' },
  { id: 'insomniac',    name: '불면증환자', image: '/roles/insomniac.png',    gradient: 'linear-gradient(135deg, #1a2a5a, #0a0a2a)', desc: '밤이 끝나고 자신의 카드를 다시 확인합니다.' },
  { id: 'tanner',       name: '무두장이',   image: '/roles/tanner.png',       gradient: 'linear-gradient(135deg, #3a2a1a, #1a0a0a)', desc: '처형되면 무두장이 팀이 승리합니다.' },
  { id: 'hunter',       name: '사냥꾼',     image: '/roles/hunter.png',       gradient: 'linear-gradient(135deg, #1a4a1a, #0a2a0a)', desc: '처형되면 자신이 지목한 플레이어도 함께 처형됩니다.' },
  { id: 'mason_1',      name: '프리메이슨', image: '/roles/mason.png',        gradient: 'linear-gradient(135deg, #1a3a5a, #0a1a3a)', desc: '밤에 깨어나 동료 프리메이슨을 확인합니다.' },
  { id: 'villager_1',   name: '마을주민',   image: '/roles/villager.png',     gradient: 'linear-gradient(135deg, #1a5a1a, #0a2a0a)', desc: '특별한 능력이 없지만 마을 팀입니다.' },
]

export default function RoleRegConfirm({ player, detectedRoleId, onConfirm }) {
  const detected = ROLES.find(r => r.id === detectedRoleId) ?? ROLES[1]
  const [selected, setSelected] = useState(detected)

  return (
    <div style={{
      height: '100vh',
      overflow: 'hidden',
      boxSizing: 'border-box',
      background: '#fff',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px 20px',
      gap: 12,
      fontFamily: "'Segoe UI', sans-serif",
      color: '#111',
    }}>

      {/* 상단: 플레이어 이름 + 버튼 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div style={{ fontSize: 16, fontWeight: 600 }}>플레이어 {player?.name}님</div>
        <button
          onClick={() => onConfirm(selected)}
          style={{
            padding: '8px 22px',
            border: 'none',
            borderRadius: 8,
            background: '#111',
            color: '#fff',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          확인 / 다음 →
        </button>
      </div>

      {/* 인식된 역할 정보 */}
      <div style={{ display: 'flex', gap: 16, flexShrink: 0, alignItems: 'center' }}>
        <div style={{
          width: 140,
          height: 180,
          borderRadius: 12,
          background: selected.gradient,
          flexShrink: 0,
          border: '2px solid rgba(255,255,255,0.2)',
          overflow: 'hidden',
          boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
        }}>
          <img src={selected.image} alt={selected.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{selected.name}</div>
          <div style={{ fontSize: 13, color: '#555', lineHeight: 1.7 }}>{selected.desc}</div>
        </div>
      </div>

      {/* 역할 수동 수정 */}
      <div style={{ fontSize: 13, fontWeight: 600, color: '#444', flexShrink: 0 }}>역할 수동 수정</div>

      {/* 그리드 */}
      <div style={{
        flex: 1,
        minHeight: 0,
        display: 'grid',
        gridTemplateColumns: 'repeat(6, 1fr)',
        gridTemplateRows: 'repeat(2, 1fr)',
        gap: 6,
      }}>
        {ROLES.map(role => {
          const isSelected = selected.id === role.id
          return (
            <div
              key={role.id}
              onClick={() => setSelected(role)}
              title={role.name}
              style={{
                borderRadius: 8,
                background: role.gradient,
                border: isSelected ? '2px solid #f5a623' : '2px solid rgba(255,255,255,0.08)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                cursor: 'pointer',
                boxShadow: isSelected ? '0 0 10px rgba(245,166,35,0.4)' : 'none',
                transition: 'border-color 0.12s, box-shadow 0.12s',
              }}
            >
              <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                <img src={role.image} alt={role.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
              </div>
              <div style={{ padding: '3px 2px', textAlign: 'center', background: 'rgba(0,0,0,0.3)', flexShrink: 0 }}>
                <span style={{ fontSize: 9, color: isSelected ? '#f5d78e' : '#ccc', fontWeight: 600 }}>
                  {role.name}
                </span>
              </div>
            </div>
          )
        })}
      </div>

    </div>
  )
}
