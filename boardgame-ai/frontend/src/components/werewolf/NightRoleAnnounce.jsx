import { useState, useEffect } from 'react'
import { audio } from '../../hooks/useAudioPlayer'

// 튜토리얼 모드는 눈을 감지 않고 진행하므로 "깨어나세요" 대신 차례 안내,
// action도 해당 역할 플레이어가 직접 행동을 수행하는 방식으로 설명한다.
const ROLE_NIGHT_DATA = {
  doppelganger: {
    name: '도플갱어',
    image: '/roles/doppelganger.png',
    announce: '도플갱어는 깨어나세요.',
    action: '다른 플레이어 1명의 카드를 확인하세요.\n그 역할이 됩니다.',
    tutorialAnnounce: '도플갱어는 기본적으로 마을주민팀이지만 팀이 바뀔 수 있는 역할입니다.',
    tutorialAction: '밤 시간에 다른 플레이어 1명의 카드를 확인하고 본인도 그 역할이 됩니다.\n확인한 역할이 늑대인간·하수인이면 늑대인간팀, 무두장이면 무두장이팀으로 변경됩니다.\n낮 시간에 바뀐 역할을 주장하며 혼란을 줄 수 있습니다.',
  },
  werewolf: {
    name: '늑대인간',
    image: '/roles/werewolf.png',
    announce: '늑대인간은 깨어나세요.',
    action: '서로를 확인하고 다시 눈을 감으세요.',
    tutorialAnnounce: '늑대인간은 늑대인간팀 역할입니다.',
    tutorialAction: '밤 시간에 눈을 떠 다른 늑대인간들과 서로를 확인합니다.\n낮 시간에 마을주민인 척 행동하며 다른 늑대인간들과 협력해 마을주민들을 처단하도록 유도합니다.',
  },
  minion: {
    name: '하수인',
    image: '/roles/minion.png',
    announce: '하수인은 깨어나세요.',
    action: '늑대인간들은 엄지를 들어올려\n자신을 알려주세요.',
    tutorialAnnounce: '하수인은 늑대인간팀 역할입니다.',
    tutorialAction: '밤 시간에 늑대인간들이 엄지를 들면 눈을 떠 누가 늑대인간인지 확인합니다.\n단, 늑대인간들은 하수인이 누구인지 모릅니다.\n낮 시간에 늑대인간으로 의심받을 행동을 하여 늑대인간 대신 본인이 처단당하도록 유도합니다.',
  },
  mason: {
    name: '프리메이슨',
    image: '/roles/mason.png',
    announce: '프리메이슨은 깨어나세요.',
    action: '서로를 확인하고 다시 눈을 감으세요.',
    tutorialAnnounce: '프리메이슨은 마을주민팀 역할입니다.',
    tutorialAction: '프리메이슨은 항상 두 명입니다.\n밤 시간에 다른 프리메이슨과 눈을 마주치며 서로를 확인합니다.\n낮 시간에 서로를 믿고 협력하며 함께 늑대인간을 찾아냅니다.',
  },
  seer: {
    name: '예언자',
    image: '/roles/seer.png',
    announce: '예언자는 깨어나세요.',
    action: '다른 플레이어 1명 또는\n중앙 카드 2장을 확인할 수 있습니다.',
    tutorialAnnounce: '예언자는 마을주민팀 역할입니다.',
    tutorialAction: '밤 시간에 다른 플레이어 1명의 카드를 확인하거나, 중앙 카드 2장을 확인할 수 있습니다.\n낮 시간에 본인이 확인한 정보를 바탕으로 마을주민들의 추리를 돕습니다.',
  },
  robber: {
    name: '강도',
    image: '/roles/robber.png',
    announce: '강도는 깨어나세요.',
    action: '다른 플레이어 1명의 카드와\n자신의 카드를 교환할 수 있습니다.',
    tutorialAnnounce: '강도는 마을주민팀 역할입니다.',
    tutorialAction: '밤 시간에 다른 플레이어 1명의 카드를 자신의 카드와 맞교환하고 바뀐 역할을 확인합니다.\n단, 카드를 빼앗긴 플레이어는 이 사실을 모릅니다.\n낮 시간에 바뀐 역할로 행동하며 역할을 빼앗긴 플레이어에게 혼란을 줍니다.',
  },
  troublemaker: {
    name: '말썽쟁이',
    image: '/roles/troublemaker.png',
    announce: '말썽쟁이는 깨어나세요.',
    action: '자신을 제외한 두 플레이어의\n카드를 서로 교환하세요.',
    tutorialAnnounce: '말썽쟁이는 마을주민팀 역할입니다.',
    tutorialAction: '밤 시간에 자신을 제외한 두 플레이어의 카드를 맞교환하며 두 플레이어의 역할은 확인하지 않습니다.\n단, 역할이 맞교환된 두 플레이어는 이 사실을 모릅니다.\n낮 시간에 플레이어들이 본인의 역할을 잘못 알고 행동하도록 합니다.',
  },
  drunk: {
    name: '주정뱅이',
    image: '/roles/drunk.png',
    announce: '주정뱅이는 깨어나세요.',
    action: '중앙 카드 1장을 가져와\n자신의 카드와 교환하세요.\n새 카드는 볼 수 없습니다.',
    tutorialAnnounce: '주정뱅이는 마을주민팀 역할입니다.',
    tutorialAction: '밤 시간에 중앙 카드 1장과 자신의 카드를 교환하며 본인의 바뀐 역할은 확인하지 않습니다.\n낮 시간에 자신이 어떤 역할인지 전혀 모른 채 추리에 참여해야 하는 역할입니다.',
  },
  insomniac: {
    name: '불면증환자',
    image: '/roles/insomniac.png',
    announce: '불면증환자는 깨어나세요.',
    action: '자신의 카드를 확인하세요.',
    tutorialAnnounce: '불면증환자는 마을주민팀 역할입니다.',
    tutorialAction: '밤 시간이 끝날 무렵 가장 마지막으로 자신의 카드를 확인합니다.\n카드가 바뀌어 있다면 누군가 본인의 역할을 교환했다는 것을 알 수 있습니다.\n낮 시간에 이 정보를 바탕으로 마을주민들의 추리를 돕습니다.',
  },
}

const PASSIVE_ROLES = new Set(['werewolf', 'minion', 'mason'])
const PASSIVE_DURATION = 10  // 백엔드 PASSIVE_PHASE_DURATION과 일치
const ACTIVE_DURATION = 12   // 백엔드 ACTIVE_PHASE_TIMEOUT과 일치
const PRACTICE_POST_TTS_SECONDS = 5  // 튜토리얼: 안내 TTS 종료 후 자동 전이까지 대기

const KOREAN_NUMS = { 1: '한', 2: '두', 3: '세' }
function toKoreanTTS(text) {
  return text.replace(/([123])(명|장|개)/g, (_, n, counter) => `${KOREAN_NUMS[Number(n)]} ${counter}`)
}

export default function NightRoleAnnounce({ roleId, onComplete, onExit, isPracticeMode }) {
  const role = ROLE_NIGHT_DATA[roleId]
  const isPassive = PASSIVE_ROLES.has(roleId)
  const duration = isPassive ? PASSIVE_DURATION : ACTIVE_DURATION
  const [countdown, setCountdown] = useState(duration)
  // 튜토리얼: 안내 TTS가 끝난 뒤부터 카운트다운/자동 전이를 시작한다.
  const [practiceCounting, setPracticeCounting] = useState(false)

  // 역할 안내 TTS는 ProgressAgent가 담당 — 프론트에서 TTS_REQUEST 중복 발화 제거

  useEffect(() => {
    // 일반 모드: 백엔드 타이머가 전환을 담당. 여기서는 표시용 카운트다운만 운영.
    if (!isPracticeMode) {
      const dur = PASSIVE_ROLES.has(roleId) ? PASSIVE_DURATION : ACTIVE_DURATION
      setCountdown(dur)
      const interval = setInterval(() => {
        setCountdown(prev => Math.max(0, prev - 1))
      }, 1000)
      return () => clearInterval(interval)
    }

    // 튜토리얼 모드: 백엔드 고정 타이머가 없으므로 안내 TTS가 끝까지 재생된 뒤
    // PRACTICE_POST_TTS_SECONDS 카운트다운 후 onComplete(start_now)로 전이를 주도한다.
    // (액티브 역할은 그 전에 카드 감지로 전이되면 컴포넌트가 언마운트되어 정리됨.)
    setPracticeCounting(false)
    setCountdown(PRACTICE_POST_TTS_SECONDS)
    let interval = null
    let completeTimer = null
    let unsubscribeEnd = null

    const startCountdown = () => {
      setPracticeCounting(true)
      interval = setInterval(() => {
        setCountdown(prev => Math.max(0, prev - 1))
      }, 1000)
      completeTimer = setTimeout(onComplete, PRACTICE_POST_TTS_SECONDS * 1000)
    }

    // 안전장치: 안내 TTS가 전혀 시작되지 않으면(합성 실패 등) 멈추지 않도록 폴백.
    const startWatchdog = setTimeout(startCountdown, 10000)

    // 안내 TTS가 "시작"된 뒤에 종료를 기다린다. 마운트 시점에 직전 발화가 남아 있어도
    // 그 종료로 조기 전이되는 것을 막는다(이미 재생 중인 발화는 start 콜백이 소비됨).
    const unsubscribeStart = audio.onNextTtsStarted(() => {
      clearTimeout(startWatchdog)
      unsubscribeEnd = audio.onNextTtsEnded(startCountdown)
    })

    return () => {
      clearTimeout(startWatchdog)
      unsubscribeStart()
      if (unsubscribeEnd) unsubscribeEnd()
      if (interval) clearInterval(interval)
      if (completeTimer) clearTimeout(completeTimer)
    }
  }, [roleId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!role) return null

  const displayAnnounce = isPracticeMode ? (role.tutorialAnnounce ?? role.announce) : role.announce
  const displayAction = isPracticeMode ? (role.tutorialAction ?? role.action) : role.action

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

      <div style={styles.page}>
        <button onClick={onExit} style={exitBtn}>나가기</button>

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
            <p style={styles.announceText}>{displayAnnounce}</p>
            <p style={styles.actionText}>{displayAction}</p>
            {(!isPracticeMode || practiceCounting) ? (
              <p style={styles.countdownText}>{countdown}초 후 자동으로 넘어갑니다</p>
            ) : (
              <p style={styles.countdownText}>안내가 끝나면 다음으로 넘어갑니다</p>
            )}
          </div>

          {/* 건너뛰기 버튼 */}
          <button onClick={onComplete} style={styles.skipBtn}>건너뛰기 →</button>

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

  countdownText: {
    margin: 0,
    fontSize: 14,
    color: 'rgba(248,241,221,0.35)',
    textAlign: 'center',
    letterSpacing: 0.5,
  },

  skipBtn: {
    padding: '8px 20px',
    border: '1px solid rgba(248,241,221,0.25)',
    borderRadius: 8,
    background: 'rgba(255,255,255,0.08)',
    color: 'rgba(248,241,221,0.5)',
    cursor: 'pointer',
    fontSize: 13,
  },

}

const exitBtn = {
  position: 'absolute', top: 20, right: 20, zIndex: 10,
  padding: '8px 18px',
  border: '1px solid rgba(248,241,221,0.2)',
  borderRadius: 8,
  background: 'rgba(255,255,255,0.08)',
  color: 'rgba(248,241,221,0.7)',
  fontSize: 14, fontWeight: 600, cursor: 'pointer',
  backdropFilter: 'blur(8px)',
}
