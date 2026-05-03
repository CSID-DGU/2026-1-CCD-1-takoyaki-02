import { useState } from 'react'

function WerewolfBg() {
  return (
    <>
      <style>{`
        @keyframes moonGlowPulse {
          0%,100% { box-shadow: 0 0 48px 18px rgba(220,185,80,0.22); }
          50%      { box-shadow: 0 0 72px 28px rgba(220,185,80,0.38); }
        }
        @keyframes fogDrift {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-8%); }
        }
        @keyframes starFlicker { 0%,100%{opacity:.6} 50%{opacity:.2} }
      `}</style>

      {/* 달 */}
      <div style={{
        position: 'absolute', top: 32, right: 72,
        width: 80, height: 80, borderRadius: '50%',
        background: 'radial-gradient(circle at 38% 36%, #fffde7, #f5e070 40%, #c8a820 80%)',
        animation: 'moonGlowPulse 3.5s ease-in-out infinite',
        zIndex: 0,
      }} />

      {/* 별 */}
      {[{t:'7%',l:'10%',s:2.2},{t:'13%',l:'32%',s:1.4},{t:'5%',l:'55%',s:1.8},
        {t:'19%',l:'75%',s:1.2},{t:'25%',l:'18%',s:1},{t:'9%',l:'44%',s:1.5},
        {t:'28%',l:'90%',s:2},{t:'4%',l:'82%',s:1.4}].map((st, i) => (
        <div key={i} style={{
          position: 'absolute', top: st.t, left: st.l,
          width: st.s, height: st.s, borderRadius: '50%',
          background: '#fff', opacity: 0.6,
          animation: `starFlicker ${2.2 + i * 0.35}s ease-in-out infinite`,
          zIndex: 0,
        }} />
      ))}

      {/* 늑대인간 실루엣 */}
      <svg
        viewBox="0 0 200 360"
        style={{
          position: 'absolute', bottom: '8%', left: '50%',
          transform: 'translateX(-50%)',
          width: 220, height: 'auto',
          opacity: 0.09, fill: '#c8a0ff',
          filter: 'blur(1.5px)',
          zIndex: 0, pointerEvents: 'none',
        }}
      >
        {/* 오른쪽 귀 */}
        <polygon points="122,32 148,0 128,58" />
        {/* 왼쪽 귀 */}
        <polygon points="78,32 52,0 72,58" />
        {/* 머리 */}
        <ellipse cx="100" cy="72" rx="38" ry="40" />
        {/* 주둥이 */}
        <ellipse cx="100" cy="98" rx="20" ry="14" />
        {/* 몸통 */}
        <path d="M52,114 Q26,130 24,182 Q26,228 52,238 Q74,248 100,248 Q126,248 148,238 Q174,228 176,182 Q174,130 148,114 Q126,108 100,108 Q74,108 52,114z" />
        {/* 왼쪽 팔 (위로 뻗음) */}
        <path d="M42,124 Q12,104 2,72 Q14,78 24,70 Q30,98 44,118z" />
        {/* 왼쪽 발톱 */}
        <polygon points="2,72 -8,56 6,70" />
        <polygon points="2,72 0,53 12,67" />
        <polygon points="2,72 14,56 16,70" />
        {/* 오른쪽 팔 */}
        <path d="M158,124 Q188,104 198,72 Q186,78 176,70 Q170,98 156,118z" />
        {/* 오른쪽 발톱 */}
        <polygon points="198,72 208,56 194,70" />
        <polygon points="198,72 200,53 188,67" />
        <polygon points="198,72 186,56 184,70" />
        {/* 왼쪽 다리 */}
        <path d="M68,242 Q54,282 46,318 Q58,312 68,322 Q74,290 80,262z" />
        {/* 오른쪽 다리 */}
        <path d="M132,242 Q146,282 154,318 Q142,312 132,322 Q126,290 120,262z" />
        {/* 꼬리 */}
        <path d="M150,196 Q176,218 190,252" fill="none" stroke="#c8a0ff" strokeWidth="11" strokeLinecap="round" />
      </svg>

      {/* 안개 */}
      <div style={{
        position: 'absolute', bottom: 0, left: '-8%',
        width: '116%', height: '28%',
        background: 'linear-gradient(to top, rgba(60,30,90,0.45) 0%, rgba(40,20,70,0.2) 50%, transparent 100%)',
        animation: 'fogDrift 18s linear infinite alternate',
        filter: 'blur(12px)',
        zIndex: 0, pointerEvents: 'none',
      }} />
    </>
  )
}

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
      background: 'radial-gradient(ellipse at 70% 8%, rgba(180,140,40,0.18) 0%, transparent 38%), radial-gradient(ellipse at 15% 85%, rgba(90,20,140,0.32) 0%, transparent 48%), linear-gradient(160deg, #160d38 0%, #0c1628 35%, #180c28 65%, #081420 100%)',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px 20px',
      gap: 12,
      fontFamily: "'Segoe UI', sans-serif",
      color: '#F8F1DD',
      position: 'relative',
    }}>

      <WerewolfBg />

      {/* 상단: 플레이어 이름 + 버튼 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0, position: 'relative', zIndex: 1 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: '#F8F1DD' }}>플레이어 {player?.playername}님</div>
        <button
          onClick={() => onConfirm(selected)}
          style={{
            padding: '10px 26px',
            border: 'none',
            borderRadius: 8,
            background: 'linear-gradient(135deg, #E6B85C, #B48A3C)',
            color: '#1A0800',
            fontSize: 16,
            fontWeight: 700,
            cursor: 'pointer',
            boxShadow: '0 4px 0 #8A6A2A',
          }}
        >
          확인 / 다음 →
        </button>
      </div>

      {/* 인식된 역할 정보 */}
      <div style={{ display: 'flex', gap: 16, flexShrink: 0, alignItems: 'center', position: 'relative', zIndex: 1 }}>
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
          <div style={{ fontSize: 28, fontWeight: 700, color: '#F8F1DD' }}>{selected.name}</div>
          <div style={{ fontSize: 18, color: 'rgba(248,241,221,0.55)', lineHeight: 1.8 }}>{selected.desc}</div>
        </div>
      </div>

      {/* 역할 수동 수정 */}
      <div style={{ fontSize: 15, fontWeight: 600, color: 'rgba(248,241,221,0.45)', flexShrink: 0, letterSpacing: 1, position: 'relative', zIndex: 1 }}>역할 수동 수정</div>

      {/* 그리드 */}
      <div style={{ position: 'relative', zIndex: 1,
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
                <span style={{ fontSize: 11, color: isSelected ? '#f5d78e' : '#ccc', fontWeight: 600 }}>
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
