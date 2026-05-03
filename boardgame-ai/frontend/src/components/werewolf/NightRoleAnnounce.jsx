const ROLE_NIGHT_DATA = {
  doppelganger: {
    name: '도플갱어',
    image: '/roles/doppelganger.png',
    announce: '도플갱어는 깨어나세요.',
    action: '다른 플레이어 1명의 카드를 확인하세요.\n그 역할이 됩니다.',
  },
  werewolf: {
    name: '늑대인간',
    image: '/roles/werewolf.png',
    announce: '늑대인간은 깨어나세요.',
    action: '서로를 확인하고 다시 눈을 감으세요.',
  },
  minion: {
    name: '하수인',
    image: '/roles/minion.png',
    announce: '하수인은 깨어나세요.',
    action: '늑대인간들은 엄지를 들어올려\n자신을 알려주세요.',
  },
  mason: {
    name: '프리메이슨',
    image: '/roles/mason.png',
    announce: '프리메이슨은 깨어나세요.',
    action: '서로를 확인하고 다시 눈을 감으세요.',
  },
  seer: {
    name: '예언자',
    image: '/roles/seer.png',
    announce: '예언자는 깨어나세요.',
    action: '다른 플레이어 1명 또는\n중앙 카드 2장을 확인할 수 있습니다.',
  },
  robber: {
    name: '강도',
    image: '/roles/robber.png',
    announce: '강도는 깨어나세요.',
    action: '다른 플레이어 1명의 카드와\n자신의 카드를 교환할 수 있습니다.',
  },
  troublemaker: {
    name: '말썽쟁이',
    image: '/roles/troublemaker.png',
    announce: '말썽쟁이는 깨어나세요.',
    action: '자신을 제외한 두 플레이어의\n카드를 서로 교환하세요.',
  },
  drunk: {
    name: '주정뱅이',
    image: '/roles/drunk.png',
    announce: '주정뱅이는 깨어나세요.',
    action: '중앙 카드 1장을 가져와\n자신의 카드와 교환하세요.\n새 카드는 볼 수 없습니다.',
  },
  insomniac: {
    name: '불면증환자',
    image: '/roles/insomniac.png',
    announce: '불면증환자는 깨어나세요.',
    action: '자신의 카드를 확인하세요.',
  },
}

export default function NightRoleAnnounce({ roleId, onComplete }) {
  const role = ROLE_NIGHT_DATA[roleId]
  if (!role) return null

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
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes cardReveal {
          0%   { opacity: 0; transform: scale(0.88) translateY(8px); }
          100% { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>

      <div onClick={onComplete} style={styles.page}>

        {/* 배경 */}
        <div style={styles.sky} />

        {/* 달 */}
        <div style={styles.moon} />

        {/* 별 */}
        {[
          {t:'7%', l:'10%', s:2.2}, {t:'13%', l:'32%', s:1.4},
          {t:'5%', l:'55%', s:1.8}, {t:'19%', l:'75%', s:1.2},
          {t:'25%', l:'18%', s:1.0}, {t:'9%',  l:'44%', s:1.5},
          {t:'28%', l:'90%', s:2.0}, {t:'4%',  l:'82%', s:1.4},
          {t:'35%', l:'60%', s:1.2}, {t:'40%', l:'5%',  s:1.8},
        ].map((st, i) => (
          <div key={i} style={{
            position: 'absolute', top: st.t, left: st.l,
            width: st.s, height: st.s, borderRadius: '50%',
            background: '#fff', opacity: 0.6,
            animation: `starFlicker ${2.2 + i * 0.35}s ease-in-out infinite`,
          }} />
        ))}

        {/* 마을 실루엣 */}
        <svg viewBox="0 0 800 160" preserveAspectRatio="xMidYMax slice" style={styles.silhouette}>
          <polygon points="40,160 62,95 84,160"    fill="#06030f" />
          <polygon points="58,160 84,72 110,160"   fill="#06030f" />
          <polygon points="95,160 118,100 141,160" fill="#06030f" />
          <rect x="155" y="118" width="58" height="42" fill="#06030f" />
          <polygon points="150,120 184,92 218,120"  fill="#06030f" />
          <rect x="162" y="130" width="13" height="30" fill="#030108" />
          <rect x="245" y="86" width="32" height="74" fill="#06030f" />
          <polygon points="240,88 261,62 282,88"   fill="#06030f" />
          <rect x="300" y="112" width="52" height="48" fill="#06030f" />
          <polygon points="295,114 326,86 357,114" fill="#06030f" />
          <polygon points="372,160 394,90 416,160" fill="#06030f" />
          <polygon points="390,160 416,70 442,160" fill="#06030f" />
          <rect x="455" y="120" width="46" height="40" fill="#06030f" />
          <polygon points="450,122 478,98 506,122" fill="#06030f" />
          <rect x="524" y="96" width="72" height="64" fill="#06030f" />
          <polygon points="519,98 560,68 601,98"   fill="#06030f" />
          <rect x="552" y="74" width="16" height="26" fill="#06030f" />
          <polygon points="618,160 638,102 658,160" fill="#06030f" />
          <polygon points="646,160 670,84 694,160" fill="#06030f" />
          <rect x="710" y="118" width="54" height="42" fill="#06030f" />
          <polygon points="705,120 737,94 769,120" fill="#06030f" />
        </svg>

        {/* 안개 */}
        <div style={{
          position: 'absolute', bottom: 0, left: '-8%',
          width: '116%', height: '30%',
          background: 'linear-gradient(to top, rgba(60,30,90,0.5) 0%, rgba(40,20,70,0.22) 55%, transparent 100%)',
          animation: 'fogDrift 18s linear infinite alternate',
          filter: 'blur(14px)',
          pointerEvents: 'none',
        }} />

        {/* 중앙 컨텐츠 */}
        <div style={styles.inner}>

          <div style={{ ...styles.roleName, animation: 'fadeIn 0.6s ease-out both' }}>
            {role.name}
          </div>

          <div style={{ ...styles.imageBox, animation: 'cardReveal 0.6s cubic-bezier(0.22,0.61,0.36,1) 0.1s both' }}>
            <img src={role.image} alt={role.name} style={styles.image} />
          </div>

          <div style={{ ...styles.textBlock, animation: 'fadeIn 0.6s ease-out 0.25s both' }}>
            <p style={styles.announceText}>{role.announce}</p>
            <p style={styles.actionText}>{role.action}</p>
          </div>

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
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    cursor: 'pointer',
    userSelect: 'none',
  },

  sky: {
    position: 'absolute',
    inset: 0,
    background: 'radial-gradient(ellipse at 72% 8%, rgba(180,140,40,0.18) 0%, transparent 38%), radial-gradient(ellipse at 15% 85%, rgba(90,20,140,0.32) 0%, transparent 48%), linear-gradient(160deg, #160d38 0%, #0c1628 35%, #180c28 65%, #081420 100%)',
  },

  moon: {
    position: 'absolute',
    top: 48,
    right: 90,
    width: 90,
    height: 90,
    borderRadius: '50%',
    background: 'radial-gradient(circle at 38% 36%, #fffde7, #f5e070 40%, #c8a820 80%)',
    animation: 'moonGlowPulse 3.5s ease-in-out infinite',
  },

  silhouette: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    width: '100%',
    height: 160,
    pointerEvents: 'none',
  },

  inner: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 28,
    marginBottom: 80,
  },

  roleName: {
    fontSize: 32,
    fontWeight: 700,
    color: '#F8F1DD',
    letterSpacing: 3,
    textShadow: '0 0 24px rgba(220,185,120,0.5)',
  },

  imageBox: {
    width: 180,
    height: 224,
    borderRadius: 18,
    overflow: 'hidden',
    background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(220,185,120,0.25)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
  },

  image: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  },

  textBlock: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 12,
    background: 'rgba(0,0,0,0.3)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(220,185,120,0.15)',
    borderRadius: 16,
    padding: '22px 40px',
  },

  announceText: {
    margin: 0,
    fontSize: 24,
    fontWeight: 600,
    color: '#F8F1DD',
    textAlign: 'center',
  },

  actionText: {
    margin: 0,
    fontSize: 18,
    color: 'rgba(248,241,221,0.6)',
    textAlign: 'center',
    lineHeight: 1.9,
    whiteSpace: 'pre-line',
  },
}
