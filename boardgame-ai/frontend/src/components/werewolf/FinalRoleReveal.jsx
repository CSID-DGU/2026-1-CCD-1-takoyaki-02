import { useEffect, useState } from 'react'

const AUTO_TIMEOUT_SEC = 15

const ROLE_NAMES = {
  doppelganger: '도플갱어',
  werewolf: '늑대인간', werewolf_1: '늑대인간', werewolf_2: '늑대인간',
  minion: '하수인',
  seer: '예언자',
  robber: '강도',
  troublemaker: '말썽쟁이',
  drunk: '주정뱅이',
  insomniac: '불면증환자',
  tanner: '무두장이',
  hunter: '사냥꾼',
  mason: '프리메이슨', mason_1: '프리메이슨', mason_2: '프리메이슨',
  villager: '마을주민', villager_1: '마을주민', villager_2: '마을주민', villager_3: '마을주민',
}

const normalizeRoleId = (id) => (id ?? '').replace(/_\d+$/, '')

export default function FinalRoleReveal({ player, detectedRoleId, timedOut, allRoles = [], send, onConfirm, onTimeout }) {
  const [countdown, setCountdown] = useState(AUTO_TIMEOUT_SEC)
  const [selectedRole, setSelectedRole] = useState(null)

  useEffect(() => {
    if (!player?.playername || !send) return
    send('TTS_REQUEST', { text: `${player.playername}님, 현재 가지고 있는 카드를 카메라에 보여주세요.` })
  }, [player?.player_id])

  useEffect(() => {
    setCountdown(AUTO_TIMEOUT_SEC)
    setSelectedRole(null)
    let remaining = AUTO_TIMEOUT_SEC
    const interval = setInterval(() => {
      remaining -= 1
      setCountdown(remaining)
      if (remaining <= 0) {
        clearInterval(interval)
        onTimeout?.()
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [player?.player_id])

  // 역할 감지되면 TTS 안내
  useEffect(() => {
    if (!detectedRoleId || !send) return
    const name = ROLE_NAMES[detectedRoleId] ?? detectedRoleId
    send('TTS_REQUEST', { text: `${name} 카드가 감지됐습니다. 확인해주세요.` })
  }, [detectedRoleId])

  const uniqueRoles = [...new Set(allRoles.map(normalizeRoleId))].filter(Boolean)
  const confirmed = detectedRoleId || (timedOut && selectedRole)
  const confirmRoleId = detectedRoleId || selectedRole

  const handleConfirm = () => {
    if (!confirmRoleId) return
    onConfirm?.(confirmRoleId)
    setSelectedRole(null)
  }

  return (
    <>
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes moonGlow {
          0%, 100% { box-shadow: 0 0 40px 16px rgba(220,195,120,0.18); }
          50%       { box-shadow: 0 0 60px 24px rgba(220,195,120,0.3); }
        }
        @keyframes shimmer { 0%, 100% { opacity: 0.5; } 50% { opacity: 1; } }
        @keyframes popIn {
          0%   { opacity: 0; transform: scale(0.9); }
          100% { opacity: 1; transform: scale(1); }
        }
      `}</style>

      <div style={styles.page}>
        {/* 배경 */}
        <div style={styles.sky} />

        {/* 달 */}
        <div style={styles.moon} />

        {/* 별 */}
        {[
          { top: '8%', left: '12%', size: 2 }, { top: '14%', left: '35%', size: 1.5 },
          { top: '6%', left: '62%', size: 2.5 }, { top: '18%', left: '78%', size: 1.5 },
          { top: '22%', left: '20%', size: 1 },  { top: '10%', left: '50%', size: 1 },
        ].map((s, i) => (
          <div key={i} style={{
            position: 'absolute', top: s.top, left: s.left,
            width: s.size, height: s.size, borderRadius: '50%',
            background: '#fff', opacity: 0.7,
            animation: `shimmer ${2 + i * 0.4}s ease-in-out infinite`,
          }} />
        ))}

        {/* 마을 실루엣 */}
        <svg viewBox="0 0 800 160" preserveAspectRatio="xMidYMax slice" style={styles.silhouette}>
          <polygon points="40,160 62,95 84,160"    fill="#0a0614" />
          <polygon points="58,160 84,72 110,160"   fill="#0a0614" />
          <polygon points="95,160 118,100 141,160" fill="#0a0614" />
          <rect x="155" y="118" width="58" height="42" fill="#0a0614" />
          <polygon points="150,120 184,92 218,120"  fill="#0a0614" />
          <rect x="245" y="86" width="32" height="74" fill="#0a0614" />
          <polygon points="240,88 261,62 282,88"   fill="#0a0614" />
          <rect x="300" y="112" width="52" height="48" fill="#0a0614" />
          <polygon points="295,114 326,86 357,114" fill="#0a0614" />
          <polygon points="372,160 394,90 416,160" fill="#0a0614" />
          <rect x="524" y="96" width="72" height="64" fill="#0a0614" />
          <polygon points="519,98 560,68 601,98"   fill="#0a0614" />
          <rect x="710" y="118" width="54" height="42" fill="#0a0614" />
          <polygon points="705,120 737,94 769,120" fill="#0a0614" />
        </svg>

        {/* 상단 레이블 */}
        <div style={styles.phaseLabel}>최종 역할 확인</div>

        {/* 중앙 컨텐츠 */}
        <div style={styles.center}>

          {/* 플레이어 이름 */}
          <div style={{ ...styles.name, animation: 'fadeIn 0.6s ease-out both' }}>
            {player?.playername} 님
          </div>

          {!detectedRoleId && !timedOut && (
            <div style={{ ...styles.guideBox, animation: 'fadeIn 0.6s ease-out 0.15s both' }}>
              <div style={styles.guideLine}>현재 가지고 있는 카드를 카메라에 보여주세요</div>
              {countdown > 0 && (
                <div style={styles.countdown}>{countdown}초 후 직접 선택으로 전환됩니다</div>
              )}
            </div>
          )}

          {/* 역할 감지됨 → 확인 */}
          {detectedRoleId && (
            <div style={{ ...styles.detectedBox, animation: 'popIn 0.4s ease-out both' }}>
              <div style={styles.detectedLabel}>감지된 역할</div>
              <div style={styles.detectedRole}>{ROLE_NAMES[detectedRoleId] ?? detectedRoleId}</div>
              <button onClick={handleConfirm} style={styles.confirmBtn}>
                확인 →
              </button>
            </div>
          )}

          {/* 타임아웃 → 직접 선택 */}
          {!detectedRoleId && timedOut && (
            <div style={{ ...styles.manualBox, animation: 'fadeIn 0.4s ease-out both' }}>
              <div style={styles.manualLabel}>역할 카드를 직접 선택해주세요</div>
              <div style={styles.roleGrid}>
                {uniqueRoles.map(roleId => (
                  <button
                    key={roleId}
                    onClick={() => setSelectedRole(roleId)}
                    style={{
                      ...styles.roleBtn,
                      ...(selectedRole === roleId ? styles.roleBtnSelected : {}),
                    }}
                  >
                    {ROLE_NAMES[roleId] ?? roleId}
                  </button>
                ))}
              </div>
              <button
                onClick={handleConfirm}
                disabled={!selectedRole}
                style={{ ...styles.confirmBtn, opacity: selectedRole ? 1 : 0.4 }}
              >
                확인 →
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

const styles = {
  page: {
    height: '100vh',
    overflow: 'hidden',
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    userSelect: 'none',
  },

  sky: {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(180deg, #04020e 0%, #0d0821 30%, #1a1035 60%, #12082a 100%)',
  },

  moon: {
    position: 'absolute',
    top: 82,
    right: 154,
    width: 90,
    height: 90,
    borderRadius: '50%',
    background: 'radial-gradient(circle at 38% 36%, #fffde7, #f5e070 40%, #c8a820 80%)',
    animation: 'moonGlow 3s ease-in-out infinite',
  },

  silhouette: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    width: '100%',
    height: 160,
    pointerEvents: 'none',
  },

  phaseLabel: {
    position: 'absolute',
    top: 28,
    left: '50%',
    transform: 'translateX(-50%)',
    fontSize: 13,
    fontWeight: 700,
    letterSpacing: 3,
    color: 'rgba(220,195,120,0.55)',
    textTransform: 'uppercase',
    zIndex: 1,
  },

  center: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 24,
    marginBottom: 80,
    width: '100%',
    maxWidth: 480,
    padding: '0 24px',
  },

  name: {
    fontSize: 48,
    fontWeight: 800,
    color: '#F8F1DD',
    letterSpacing: 2,
    textShadow: '0 0 40px rgba(220,195,120,0.4), 0 2px 12px rgba(0,0,0,0.6)',
  },

  guideBox: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 10,
    background: 'rgba(0,0,0,0.35)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(220,195,120,0.15)',
    borderRadius: 16,
    padding: '20px 36px',
    width: '100%',
  },

  guideLine: {
    fontSize: 18,
    fontWeight: 500,
    color: 'rgba(248,241,221,0.75)',
    textAlign: 'center',
    lineHeight: 1.6,
  },

  countdown: {
    fontSize: 13,
    color: 'rgba(248,241,221,0.35)',
    letterSpacing: 0.5,
  },

  detectedBox: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 12,
    background: 'rgba(220,185,80,0.1)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(220,185,80,0.35)',
    borderRadius: 20,
    padding: '28px 48px',
    width: '100%',
  },

  detectedLabel: {
    fontSize: 13,
    fontWeight: 700,
    letterSpacing: 2,
    color: 'rgba(220,185,80,0.6)',
    textTransform: 'uppercase',
  },

  detectedRole: {
    fontSize: 36,
    fontWeight: 800,
    color: '#F8F1DD',
    letterSpacing: 1,
    textShadow: '0 0 20px rgba(220,185,80,0.4)',
  },

  confirmBtn: {
    padding: '12px 32px',
    border: 'none',
    borderRadius: 12,
    background: 'linear-gradient(135deg, #dcc350, #a07818)',
    color: '#1a0a00',
    fontSize: 16,
    fontWeight: 700,
    cursor: 'pointer',
    letterSpacing: 0.5,
    marginTop: 4,
  },

  manualBox: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 16,
    background: 'rgba(0,0,0,0.35)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(220,195,120,0.15)',
    borderRadius: 20,
    padding: '24px 28px',
    width: '100%',
  },

  manualLabel: {
    fontSize: 16,
    fontWeight: 600,
    color: 'rgba(248,241,221,0.65)',
    textAlign: 'center',
  },

  roleGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: 10,
    width: '100%',
  },

  roleBtn: {
    padding: '12px 8px',
    border: '1px solid rgba(220,195,120,0.2)',
    borderRadius: 10,
    background: 'rgba(255,255,255,0.05)',
    color: 'rgba(248,241,221,0.7)',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    textAlign: 'center',
  },

  roleBtnSelected: {
    background: 'rgba(220,185,80,0.2)',
    border: '1.5px solid rgba(220,185,80,0.7)',
    color: '#F8F1DD',
    boxShadow: '0 0 12px rgba(220,185,80,0.2)',
  },
}
