import { useEffect, useState } from 'react'

const AUTO_ADVANCE_SEC = 15

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
        @keyframes cardFadeIn {
          0%   { opacity: 0; transform: translateY(20px); }
          100% { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div style={{
        position: 'absolute', top: 32, right: 72,
        width: 80, height: 80, borderRadius: '50%',
        background: 'radial-gradient(circle at 38% 36%, #fffde7, #f5e070 40%, #c8a820 80%)',
        animation: 'moonGlowPulse 3.5s ease-in-out infinite',
        zIndex: 0,
      }} />

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

      <svg viewBox="0 0 200 360" style={{
        position: 'absolute', bottom: '8%', left: '50%',
        transform: 'translateX(-50%)',
        width: 220, height: 'auto',
        opacity: 0.09, fill: '#c8a0ff',
        filter: 'blur(1.5px)',
        zIndex: 0, pointerEvents: 'none',
      }}>
        <polygon points="122,32 148,0 128,58" />
        <polygon points="78,32 52,0 72,58" />
        <ellipse cx="100" cy="72" rx="38" ry="40" />
        <ellipse cx="100" cy="98" rx="20" ry="14" />
        <path d="M52,114 Q26,130 24,182 Q26,228 52,238 Q74,248 100,248 Q126,248 148,238 Q174,228 176,182 Q174,130 148,114 Q126,108 100,108 Q74,108 52,114z" />
        <path d="M42,124 Q12,104 2,72 Q14,78 24,70 Q30,98 44,118z" />
        <polygon points="2,72 -8,56 6,70" />
        <polygon points="2,72 0,53 12,67" />
        <polygon points="2,72 14,56 16,70" />
        <path d="M158,124 Q188,104 198,72 Q186,78 176,70 Q170,98 156,118z" />
        <polygon points="198,72 208,56 194,70" />
        <polygon points="198,72 200,53 188,67" />
        <polygon points="198,72 186,56 184,70" />
        <path d="M68,242 Q54,282 46,318 Q58,312 68,322 Q74,290 80,262z" />
        <path d="M132,242 Q146,282 154,318 Q142,312 132,322 Q126,290 120,262z" />
        <path d="M150,196 Q176,218 190,252" fill="none" stroke="#c8a0ff" strokeWidth="11" strokeLinecap="round" />
      </svg>

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

export default function RoleRegRoleExplain({ role, send, onComplete }) {
  const [countdown, setCountdown] = useState(AUTO_ADVANCE_SEC)

  useEffect(() => {
    send?.('TTS_REQUEST', { text: role.desc })
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(interval)
          onComplete()
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      onClick={onComplete}
      style={{
        height: '100vh',
        overflow: 'hidden',
        position: 'relative',
        background: 'radial-gradient(ellipse at 70% 8%, rgba(180,140,40,0.18) 0%, transparent 38%), radial-gradient(ellipse at 15% 85%, rgba(90,20,140,0.32) 0%, transparent 48%), linear-gradient(160deg, #160d38 0%, #0c1628 35%, #180c28 65%, #081420 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: "'Segoe UI', sans-serif",
        cursor: 'pointer',
        userSelect: 'none',
      }}
    >
      <WerewolfBg />

      <div style={{
        position: 'relative',
        zIndex: 1,
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        gap: 48,
        maxWidth: 860,
        width: '90%',
        animation: 'cardFadeIn 0.7s ease-out both',
      }}>
        {/* 역할 이미지 */}
        <div style={{
          flexShrink: 0,
          width: 160,
          height: 200,
          borderRadius: 16,
          background: role.gradient,
          border: '2px solid rgba(255,255,255,0.2)',
          overflow: 'hidden',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        }}>
          <img
            src={role.image}
            alt={role.name}
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        </div>

        {/* 텍스트 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, flex: 1 }}>
          <div style={{
            fontSize: 32,
            fontWeight: 800,
            color: '#F8F1DD',
            textShadow: '0 2px 12px rgba(180,140,40,0.4)',
          }}>
            {role.name}
          </div>

          <div style={sectionStyle}>
            <div style={labelStyle}>역할 설명</div>
            <div style={bodyStyle}>{role.desc}</div>
          </div>

          <div style={sectionStyle}>
            <div style={labelStyle}>승리 조건</div>
            <div style={bodyStyle}>{role.winCondition}</div>
          </div>
        </div>
      </div>

      {/* 하단 힌트 */}
      <div style={{
        position: 'absolute',
        bottom: 32,
        left: 0,
        right: 0,
        textAlign: 'center',
        fontSize: 14,
        color: 'rgba(248,241,221,0.35)',
        zIndex: 1,
      }}>
        화면을 터치하면 넘어갑니다 ({countdown})
      </div>
    </div>
  )
}

const sectionStyle = {
  background: 'rgba(255,255,255,0.05)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 12,
  padding: '12px 16px',
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
}

const labelStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: 1.5,
  color: 'rgba(220,185,80,0.7)',
  textTransform: 'uppercase',
}

const bodyStyle = {
  fontSize: 15,
  color: 'rgba(248,241,221,0.82)',
  lineHeight: 1.7,
}
