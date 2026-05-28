import { useState, useEffect, useRef } from 'react'

const CONFIRM_TIMEOUT = 7

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
  {
    id: 'doppelganger', name: '도플갱어', image: '/roles/doppelganger.png',
    gradient: 'linear-gradient(135deg, #4a1a6b, #2a0a3a)',
    desc: '다른 플레이어의 카드를 보고 그 역할이 됩니다.',
    action: '밤에 깨어나 다른 플레이어 1명의 카드를 확인합니다. 확인한 즉시 그 역할이 되어 해당 역할의 행동을 수행합니다.',
    winCondition: '복사한 역할의 팀이 승리하면 함께 승리합니다. 어떤 역할을 복사했느냐에 따라 승리 조건이 달라집니다.',
  },
  {
    id: 'werewolf_1', name: '늑대인간', image: '/roles/werewolf.png',
    gradient: 'linear-gradient(135deg, #6b1a1a, #3a0a0a)',
    desc: '밤에 깨어나 동료 늑대인간을 확인합니다. 혼자라면 중앙 카드 1장을 볼 수 있습니다.',
    action: '밤에 깨어나 동료 늑대인간과 눈을 맞춥니다. 혼자인 경우 중앙 카드 1장을 몰래 확인할 수 있습니다.',
    winCondition: '투표 결과 늑대인간 팀(늑대인간·하수인) 중 아무도 처형되지 않으면 늑대인간 팀 승리입니다.',
  },
  {
    id: 'minion', name: '하수인', image: '/roles/minion.png',
    gradient: 'linear-gradient(135deg, #5a1a7a, #2a0a4a)',
    desc: '늑대인간 팀이지만 누가 늑대인간인지 알 수 없습니다.',
    action: '밤에 깨어나 늑대인간이 누구인지 확인합니다. 단, 늑대인간은 하수인이 누구인지 모릅니다.',
    winCondition: '늑대인간이 처형되지 않으면 늑대인간 팀 승리입니다. 단, 늑대인간이 없는데 자신이 처형되면 마을 팀이 승리합니다.',
  },
  {
    id: 'seer', name: '예언자', image: '/roles/seer.png',
    gradient: 'linear-gradient(135deg, #1a3a7a, #0a1a4a)',
    desc: '다른 플레이어 1명의 카드 또는 중앙 카드 2장을 볼 수 있습니다.',
    action: '밤에 깨어나 다른 플레이어 1명의 카드를 확인하거나, 중앙에 놓인 카드 중 2장을 확인할 수 있습니다.',
    winCondition: '마을 팀이 늑대인간을 처형하면 승리합니다. 얻은 정보를 토론에서 잘 활용하세요.',
  },
  {
    id: 'robber', name: '강도', image: '/roles/robber.png',
    gradient: 'linear-gradient(135deg, #3a3a1a, #1a1a0a)',
    desc: '다른 플레이어의 카드와 자신의 카드를 교환할 수 있습니다.',
    action: '밤에 깨어나 다른 플레이어 1명의 카드와 자신의 카드를 교환합니다. 가져온 새 카드를 확인합니다. 교환하지 않을 수도 있습니다.',
    winCondition: '교환 후 자신의 최종 역할 팀이 승리하면 함께 승리합니다.',
  },
  {
    id: 'troublemaker', name: '말썽쟁이', image: '/roles/troublemaker.png',
    gradient: 'linear-gradient(135deg, #1a5a4a, #0a2a2a)',
    desc: '자신을 제외한 두 플레이어의 카드를 서로 교환합니다.',
    action: '밤에 깨어나 자신을 제외한 두 플레이어의 카드를 서로 몰래 교환합니다. 교환된 카드의 내용은 확인하지 않습니다.',
    winCondition: '마을 팀이 늑대인간을 처형하면 승리합니다. 말썽쟁이 자신의 카드는 바뀌지 않습니다.',
  },
  {
    id: 'drunk', name: '주정뱅이', image: '/roles/drunk.png',
    gradient: 'linear-gradient(135deg, #5a3a1a, #2a1a0a)',
    desc: '중앙 카드 1장과 자신의 카드를 교환합니다. 단, 새 카드를 볼 수 없습니다.',
    action: '밤에 깨어나 중앙 카드 중 1장을 가져와 자신의 카드와 교환합니다. 새로 받은 카드가 무엇인지 알 수 없습니다.',
    winCondition: '자신의 최종 역할(새로 받은 카드) 팀이 승리하면 함께 승리합니다.',
  },
  {
    id: 'insomniac', name: '불면증환자', image: '/roles/insomniac.png',
    gradient: 'linear-gradient(135deg, #1a2a5a, #0a0a2a)',
    desc: '밤이 끝나고 자신의 카드를 다시 확인합니다.',
    action: '모든 야간 행동이 끝난 후 마지막으로 깨어나 자신의 현재 카드를 확인합니다. 다른 역할에 의해 카드가 바뀌었을 수 있습니다.',
    winCondition: '마을 팀이 늑대인간을 처형하면 승리합니다. 자신의 최종 역할을 확실히 파악할 수 있습니다.',
  },
  {
    id: 'tanner', name: '무두장이', image: '/roles/tanner.png',
    gradient: 'linear-gradient(135deg, #3a2a1a, #1a0a0a)',
    desc: '처형되면 무두장이 팀이 승리합니다.',
    action: '야간 행동이 없습니다. 낮에 토론에서 의심받도록 유도하여 처형되는 것이 목표입니다.',
    winCondition: '투표로 자신이 처형되면 무두장이 단독 승리합니다. 마을도 늑대인간도 아닌 제3의 팀입니다.',
  },
  {
    id: 'hunter', name: '사냥꾼', image: '/roles/hunter.png',
    gradient: 'linear-gradient(135deg, #1a4a1a, #0a2a0a)',
    desc: '처형되면 자신이 지목한 플레이어도 함께 처형됩니다.',
    action: '야간 행동이 없습니다. 낮 토론에서 의심스러운 플레이어를 지목해두세요.',
    winCondition: '마을 팀이 늑대인간을 처형하면 승리합니다. 자신이 처형될 경우 자신이 지목한 플레이어도 함께 처형됩니다.',
  },
  {
    id: 'mason_1', name: '프리메이슨', image: '/roles/mason.png',
    gradient: 'linear-gradient(135deg, #1a3a5a, #0a1a3a)',
    desc: '밤에 깨어나 동료 프리메이슨을 확인합니다.',
    action: '밤에 깨어나 동료 프리메이슨과 눈을 맞춥니다. 서로가 같은 편임을 확인합니다.',
    winCondition: '마을 팀이 늑대인간을 처형하면 승리합니다. 서로를 신뢰하며 함께 늑대인간을 찾으세요.',
  },
  {
    id: 'villager_1', name: '마을주민', image: '/roles/villager.png',
    gradient: 'linear-gradient(135deg, #1a5a1a, #0a2a0a)',
    desc: '특별한 능력이 없지만 마을 팀입니다.',
    action: '야간 행동이 없습니다. 눈을 감고 조용히 기다립니다.',
    winCondition: '마을 팀이 늑대인간을 처형하면 승리합니다. 토론에서 단서를 모아 늑대인간을 찾아내세요.',
  },
]

export default function RoleRegConfirm({ player, detectedRoleId, allRoles = [], onConfirm, wsState, isPracticeMode }) {
  const isInGame = (roleId) =>
    allRoles.length === 0 || allRoles.includes(roleId.replace(/_\d+$/, ''))
  const detected = detectedRoleId ? (ROLES.find(r => r.id === detectedRoleId) ?? ROLES[1]) : null
  const [selected, setSelected] = useState(detected)
  const [countdown, setCountdown] = useState(CONFIRM_TIMEOUT)
  const [showExplain, setShowExplain] = useState(false)
  const selectedRef = useRef(selected)
  selectedRef.current = selected

  // 7초 카운트다운 → 자동 확인 (역할이 선택된 경우에만)
  useEffect(() => {
    if (!detected) return
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(interval)
          onConfirm(selectedRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // OK 사인 감지 → 즉시 확인
  useEffect(() => {
    if (wsState?.gesture_confirmed === player?.player_id) {
      onConfirm(selectedRef.current)
    }
  }, [wsState?.gesture_confirmed]) // eslint-disable-line react-hooks/exhaustive-deps

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
          onClick={() => { if (selected) onConfirm(selected) }}
          style={{
            padding: '10px 26px',
            border: 'none',
            borderRadius: 8,
            background: selected
              ? 'linear-gradient(135deg, #E6B85C, #B48A3C)'
              : 'rgba(255,255,255,0.12)',
            color: selected ? '#1A0800' : 'rgba(248,241,221,0.4)',
            fontSize: 16,
            fontWeight: 700,
            cursor: selected ? 'pointer' : 'default',
            boxShadow: selected ? '0 4px 0 #8A6A2A' : 'none',
          }}
        >
          확인 / 다음 → {countdown > 0 && detected && <span style={{ fontSize: 13, opacity: 0.65 }}>({countdown})</span>}
        </button>
      </div>

      {/* 인식된 역할 정보 */}
      <div style={{ display: 'flex', gap: 16, flexShrink: 0, alignItems: 'center', position: 'relative', zIndex: 1 }}>
        <div style={{
          width: 140,
          height: 180,
          borderRadius: 12,
          background: selected ? selected.gradient : 'rgba(255,255,255,0.06)',
          flexShrink: 0,
          border: '2px solid rgba(255,255,255,0.2)',
          overflow: 'hidden',
          boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          {selected
            ? <img src={selected.image} alt={selected.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
            : <span style={{ fontSize: 36, opacity: 0.35 }}>?</span>
          }
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {selected ? (
            <>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#F8F1DD' }}>{selected.name}</div>
              <div style={{ fontSize: 18, color: 'rgba(248,241,221,0.55)', lineHeight: 1.8 }}>{selected.desc}</div>
              {isPracticeMode && (
                <button onClick={() => setShowExplain(true)} style={explainBtn}>
                  역할 설명 보기
                </button>
              )}
            </>
          ) : (
            <>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'rgba(248,241,221,0.5)' }}>인식 실패</div>
              <div style={{ fontSize: 16, color: 'rgba(248,241,221,0.38)', lineHeight: 1.8 }}>아래 목록에서 역할을 직접 선택해주세요</div>
            </>
          )}
        </div>
      </div>

      {/* 역할 설명 팝업 */}
      {showExplain && selected && (
        <div style={popupOverlay} onClick={() => setShowExplain(false)}>
          <div style={popupCard} onClick={e => e.stopPropagation()}>
            <div style={popupHeader}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  width: 64, height: 80, borderRadius: 8, overflow: 'hidden',
                  background: selected.gradient, border: '1px solid rgba(255,255,255,0.2)', flexShrink: 0,
                }}>
                  <img src={selected.image} alt={selected.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                </div>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, color: 'rgba(220,185,80,0.6)', textTransform: 'uppercase', marginBottom: 4 }}>연습모드 역할 설명</div>
                  <div style={{ fontSize: 26, fontWeight: 800, color: '#F8F1DD' }}>{selected.name}</div>
                </div>
              </div>
              <button onClick={() => setShowExplain(false)} style={popupCloseBtn}>✕</button>
            </div>

            <div style={popupSection}>
              <div style={popupSectionTitle}>🌙 야간 행동</div>
              <div style={popupSectionBody}>{selected.action}</div>
            </div>

            <div style={popupSection}>
              <div style={popupSectionTitle}>🏆 승리 조건</div>
              <div style={popupSectionBody}>{selected.winCondition}</div>
            </div>
          </div>
        </div>
      )}

      <div style={{ fontSize: 15, fontWeight: 600, color: 'rgba(248,241,221,0.45)', flexShrink: 0, letterSpacing: 1, position: 'relative', zIndex: 1 }}>
        {detected ? '역할 수동 수정' : '역할을 탭하여 선택하세요'}
      </div>

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
          const isSelected = selected?.id === role.id
          const inGame = isInGame(role.id)
          return (
            <div
              key={role.id}
              onClick={() => inGame && setSelected(role)}
              title={role.name}
              style={{
                position: 'relative',
                borderRadius: 8,
                background: role.gradient,
                border: isSelected ? '2px solid #f5a623' : '2px solid rgba(255,255,255,0.08)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                cursor: inGame ? 'pointer' : 'default',
                boxShadow: isSelected ? '0 0 10px rgba(245,166,35,0.4)' : 'none',
                transition: 'border-color 0.12s, box-shadow 0.12s',
                opacity: inGame ? 1 : 0.38,
              }}
            >
              <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', filter: inGame ? 'none' : 'blur(2px) grayscale(60%)' }}>
                <img src={role.image} alt={role.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
              </div>
              <div style={{ padding: '3px 2px', textAlign: 'center', background: 'rgba(0,0,0,0.3)', flexShrink: 0 }}>
                <span style={{ fontSize: 11, color: isSelected ? '#f5d78e' : (inGame ? '#ccc' : 'rgba(255,255,255,0.35)'), fontWeight: 600 }}>
                  {role.name}
                </span>
              </div>
              {!inGame && (
                <div style={{
                  position: 'absolute', inset: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'rgba(0,0,0,0.18)',
                }}>
                  <span style={{
                    fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.6)',
                    background: 'rgba(0,0,0,0.6)', borderRadius: 4,
                    padding: '3px 7px', letterSpacing: 0.5,
                  }}>미사용</span>
                </div>
              )}
            </div>
          )
        })}
      </div>

    </div>
  )
}

const explainBtn = {
  marginTop: 6,
  padding: '7px 16px',
  border: '1px solid rgba(220,185,80,0.4)',
  borderRadius: 8,
  background: 'rgba(220,185,80,0.1)',
  color: 'rgba(220,185,80,0.9)',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  letterSpacing: 0.3,
  alignSelf: 'flex-start',
}

const popupOverlay = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.72)',
  backdropFilter: 'blur(6px)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 100,
  padding: '0 20px',
}

const popupCard = {
  background: 'linear-gradient(160deg, #1a0f3a 0%, #0e1a30 60%, #160a28 100%)',
  border: '1px solid rgba(220,185,80,0.25)',
  borderRadius: 20,
  padding: '24px 28px',
  width: '100%',
  maxWidth: 480,
  display: 'flex',
  flexDirection: 'column',
  gap: 20,
  boxShadow: '0 8px 40px rgba(0,0,0,0.6)',
}

const popupHeader = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: 12,
}

const popupCloseBtn = {
  padding: '6px 12px',
  border: '1px solid rgba(248,241,221,0.2)',
  borderRadius: 8,
  background: 'rgba(255,255,255,0.07)',
  color: 'rgba(248,241,221,0.7)',
  fontSize: 16,
  cursor: 'pointer',
  flexShrink: 0,
}

const popupSection = {
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 12,
  padding: '14px 18px',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

const popupSectionTitle = {
  fontSize: 13,
  fontWeight: 700,
  letterSpacing: 1,
  color: 'rgba(220,185,80,0.75)',
}

const popupSectionBody = {
  fontSize: 15,
  color: 'rgba(248,241,221,0.8)',
  lineHeight: 1.75,
}
