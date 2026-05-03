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

const WINNER_CONFIG = {
  village: {
    team: '마을팀 승리',
    headline: '늑대인간을 찾아냈습니다!',
    teamColor: '#F6D568',
    headlineColor: '#fff8e1',
    sky: 'linear-gradient(180deg, #0f0800 0%, #2d1400 25%, #6e3510 50%, #b86018 70%, #d4920a 85%, #e8b830 100%)',
    glow: 'rgba(230,180,40,0.18)',
  },
  werewolf: {
    team: '늑대인간 팀 승리',
    headline: '마을이 어둠에 잠식됐습니다!',
    teamColor: '#c06060',
    headlineColor: '#fce8e8',
    sky: 'linear-gradient(180deg, #050008 0%, #120018 25%, #2a0830 50%, #4a0a20 70%, #6a1010 100%)',
    glow: 'rgba(150,30,30,0.2)',
  },
  tanner: {
    team: '무두장이 승리',
    headline: '무두장이가 처형됐습니다!',
    teamColor: '#a07840',
    headlineColor: '#fff0d0',
    sky: 'linear-gradient(180deg, #080400 0%, #1a0e00 25%, #3a1e08 50%, #6a3a10 70%, #8a5018 100%)',
    glow: 'rgba(150,100,30,0.18)',
  },
}

export default function GameEndWW({ players = [], finalRoles = {}, winner = 'village', onLobby, onRestart }) {
  const cfg = WINNER_CONFIG[winner] ?? WINNER_CONFIG.village

  return (
    <>
      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes headlinePop {
          0%   { opacity: 0; transform: scale(0.88); }
          70%  { transform: scale(1.03); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes flicker {
          0%, 100% { opacity: 1; }
          45% { opacity: 0.85; }
          50% { opacity: 0.55; }
          55% { opacity: 0.9; }
        }
      `}</style>

      <div style={{ ...styles.page, background: cfg.sky }}>

        {/* 배경 오버레이 */}
        <div style={{ ...styles.overlay, background: `radial-gradient(ellipse at 50% 35%, ${cfg.glow}, transparent 60%)` }} />

        {/* 마을 실루엣 */}
        <svg viewBox="0 0 800 160" preserveAspectRatio="xMidYMax slice" style={styles.silhouette}>
          <polygon points="40,160 62,95 84,160"    fill="#0a0400" />
          <polygon points="58,160 84,72 110,160"   fill="#0a0400" />
          <polygon points="95,160 118,100 141,160" fill="#0a0400" />
          <rect x="155" y="118" width="58" height="42" fill="#0a0400" />
          <polygon points="150,120 184,92 218,120"  fill="#0a0400" />
          <rect x="162" y="130" width="13" height="30" fill="#050200" />
          <rect x="245" y="86" width="32" height="74" fill="#0a0400" />
          <polygon points="240,88 261,62 282,88"   fill="#0a0400" />
          <rect x="300" y="112" width="52" height="48" fill="#0a0400" />
          <polygon points="295,114 326,86 357,114" fill="#0a0400" />
          <polygon points="372,160 394,90 416,160" fill="#0a0400" />
          <polygon points="390,160 416,70 442,160" fill="#0a0400" />
          <rect x="455" y="120" width="46" height="40" fill="#0a0400" />
          <polygon points="450,122 478,98 506,122" fill="#0a0400" />
          <rect x="524" y="96" width="72" height="64" fill="#0a0400" />
          <polygon points="519,98 560,68 601,98"   fill="#0a0400" />
          <rect x="552" y="74" width="16" height="26" fill="#0a0400" />
          <polygon points="618,160 638,102 658,160" fill="#0a0400" />
          <polygon points="646,160 670,84 694,160" fill="#0a0400" />
          <rect x="710" y="118" width="54" height="42" fill="#0a0400" />
          <polygon points="705,120 737,94 769,120" fill="#0a0400" />
        </svg>

        {/* 컨텐츠 */}
        <div style={styles.content}>

          {/* 승리 팀 */}
          <div style={{ ...styles.teamLabel, color: cfg.teamColor, animation: 'flicker 4s ease-in-out infinite' }}>
            {cfg.team}
          </div>

          {/* 헤드라인 */}
          <div style={{ ...styles.headline, color: cfg.headlineColor, animation: 'headlinePop 0.7s cubic-bezier(0.22,0.61,0.36,1) 0.1s both' }}>
            {cfg.headline}
          </div>

          {/* 최종 역할 공개 */}
          <div style={{ ...styles.sectionLabel, animation: 'fadeUp 0.5s ease-out 0.3s both' }}>
            최종 역할 공개
          </div>

          <div style={{ ...styles.roleList, animation: 'fadeUp 0.5s ease-out 0.4s both' }}>
            {players.map((p, i) => {
              const roleId = finalRoles[p.player_id]
              const roleName = ROLE_NAMES[roleId] ?? roleId ?? '미공개'
              const isWerewolfTeam = ['werewolf', 'werewolf_1', 'werewolf_2', 'minion', 'doppelganger'].includes(roleId)
              return (
                <div key={p.player_id} style={{
                  ...styles.roleRow,
                  animationDelay: `${0.4 + i * 0.07}s`,
                  animation: `fadeUp 0.4s ease-out ${0.4 + i * 0.07}s both`,
                }}>
                  <span style={styles.playerName}>{p.playername}</span>
                  <span style={{
                    ...styles.roleName,
                    color: isWerewolfTeam ? '#ff9980' : 'rgba(248,241,221,0.85)',
                  }}>
                    {roleName}
                  </span>
                </div>
              )
            })}
          </div>

          {/* 하단 버튼 */}
          <div style={{ ...styles.btnRow, animation: 'fadeUp 0.5s ease-out 0.6s both' }}>
            <button onClick={onLobby} style={styles.btnSecondary}>
              로비
            </button>
            <button onClick={onRestart} style={{ ...styles.btnPrimary, background: `linear-gradient(135deg, ${cfg.teamColor}, #8a5010)` }}>
              게임 재시작
            </button>
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
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    color: '#F8F1DD',
    userSelect: 'none',
  },

  overlay: {
    position: 'absolute',
    inset: 0,
    pointerEvents: 'none',
  },

  silhouette: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    width: '100%',
    height: 160,
    pointerEvents: 'none',
  },

  content: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 20,
    width: '100%',
    maxWidth: 560,
    padding: '0 36px',
    marginBottom: 80,
  },

  teamLabel: {
    fontSize: 18,
    fontWeight: 700,
    letterSpacing: 4,
    textTransform: 'uppercase',
    textShadow: '0 0 20px rgba(255,200,80,0.4)',
  },

  headline: {
    fontSize: 36,
    fontWeight: 800,
    letterSpacing: -0.5,
    textAlign: 'center',
    textShadow: '0 2px 16px rgba(0,0,0,0.5)',
  },

  sectionLabel: {
    fontSize: 15,
    fontWeight: 700,
    letterSpacing: 2,
    color: 'rgba(248,241,221,0.4)',
    textTransform: 'uppercase',
    marginTop: 4,
  },

  roleList: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },

  roleRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    background: 'rgba(0,0,0,0.3)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 12,
    padding: '16px 24px',
    backdropFilter: 'blur(6px)',
  },

  playerName: {
    fontSize: 19,
    fontWeight: 600,
    color: '#F8F1DD',
  },

  roleName: {
    fontSize: 18,
    fontWeight: 600,
  },

  btnRow: {
    display: 'flex',
    gap: 14,
    width: '100%',
    marginTop: 4,
  },

  btnSecondary: {
    flex: 1,
    padding: '18px 0',
    border: '1.5px solid rgba(248,241,221,0.2)',
    borderRadius: 16,
    background: 'rgba(0,0,0,0.4)',
    backdropFilter: 'blur(8px)',
    color: 'rgba(248,241,221,0.75)',
    fontSize: 18,
    fontWeight: 600,
    cursor: 'pointer',
    letterSpacing: 0.5,
  },

  btnPrimary: {
    flex: 2,
    padding: '18px 0',
    border: 'none',
    borderRadius: 16,
    color: '#1A0A00',
    fontSize: 18,
    fontWeight: 700,
    cursor: 'pointer',
    letterSpacing: 0.5,
    boxShadow: '0 6px 0 rgba(0,0,0,0.3), 0 8px 20px rgba(0,0,0,0.4)',
  },
}
