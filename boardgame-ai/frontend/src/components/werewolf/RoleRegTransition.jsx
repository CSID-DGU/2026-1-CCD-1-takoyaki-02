import { useEffect, useRef } from 'react'
import { audio as audioApi } from '../../hooks/useAudioPlayer'

// 안내 TTS가 끝난 뒤 다음 페이지로 넘어가기까지의 대기 시간.
const TTS_END_DELAY_MS = 3000
// TTS가 끝내 "시작"되지 않을 때(합성 실패·TTS 비활성·autoplay 차단)의 짧은 폴백.
// TTS가 실제로 재생되면 이 타이머는 취소되고 TTS 종료 + 3초 경로로 진행한다.
const NO_TTS_FALLBACK_MS = 4000
// TTS가 시작은 했으나 종료 신호가 끝내 오지 않을 때의 절대 안전 진행.
const SAFETY_MS = 9000

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

export default function RoleRegTransition({ player, send, onComplete }) {
  const advancedRef = useRef(false)

  useEffect(() => {
    // 안내 TTS가 끝나고 3초 뒤 백엔드에 진행을 요청한다. 실제 다음 플레이어 전환은
    // 백엔드가 player_id를 갱신하며 주도하고(WerewolfGame이 화면을 닫음), 여기서는 그 시점을
    // TTS 종료 + 3초로 페이싱한다.
    const advance = () => {
      if (advancedRef.current) return
      advancedRef.current = true
      send?.('REG_TRANSITION_ADVANCE', {})
    }

    let delayTimer = null
    let unregisterEnd = null
    let ttsStarted = false
    // 이 화면의 TTS가 실제로 재생을 시작한 뒤에야 종료를 기다린다.
    // (직전 화면의 TTS 종료 이벤트에 걸려 조기 진행되는 것을 방지)
    const unregisterStart = audioApi.onNextTtsStarted(() => {
      ttsStarted = true
      // TTS가 실제로 재생됐으므로 "TTS 미시작" 폴백은 취소하고 종료+3초 경로로 진행한다.
      clearTimeout(noTtsFallback)
      unregisterEnd = audioApi.onNextTtsEnded(() => {
        delayTimer = setTimeout(advance, TTS_END_DELAY_MS)
      })
    })

    send?.('TTS_REQUEST', { text: `${player.playername}님 카드를 본인 앞에 엎어두고 다시 눈을 감아주세요.` })

    // TTS가 끝내 시작되지 않으면(합성 실패·TTS 비활성·autoplay 차단) 짧게 폴백 진행.
    // TTS 콜백 체인이 발화하지 않는 환경에서도 전환이 멈추지 않도록 보장한다.
    const noTtsFallback = setTimeout(() => {
      if (!ttsStarted) advance()
    }, NO_TTS_FALLBACK_MS)
    // TTS가 시작은 했으나 종료 신호가 끝내 오지 않는 경우의 절대 안전장치.
    const safety = setTimeout(advance, SAFETY_MS)
    // 백엔드 전환 신호까지 유실된 극단적 상황의 로컬 폴백.
    const localFallback = setTimeout(onComplete, SAFETY_MS + 5000)

    return () => {
      unregisterStart()
      unregisterEnd?.()
      if (delayTimer) clearTimeout(delayTimer)
      clearTimeout(noTtsFallback)
      clearTimeout(safety)
      clearTimeout(localFallback)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{
      height: '100vh',
      overflow: 'hidden',
      position: 'relative',
      background: 'radial-gradient(ellipse at 70% 8%, rgba(180,140,40,0.18) 0%, transparent 38%), radial-gradient(ellipse at 15% 85%, rgba(90,20,140,0.32) 0%, transparent 48%), linear-gradient(160deg, #160d38 0%, #0c1628 35%, #180c28 65%, #081420 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'Segoe UI', sans-serif",
    }}>
      <style>{`
        @keyframes textFadeIn {
          0%   { opacity: 0; transform: translateY(14px); }
          100% { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <WerewolfBg />

      <div style={{
        position: 'relative',
        zIndex: 1,
        textAlign: 'center',
        animation: 'textFadeIn 0.8s ease-out both',
      }}>
        <div style={{
          fontSize: 36,
          fontWeight: 700,
          color: '#F8F1DD',
          marginBottom: 14,
          textShadow: '0 2px 16px rgba(180,140,40,0.4)',
        }}>
          {player.playername}님
        </div>
        <div style={{
          fontSize: 24,
          color: 'rgba(248,241,221,0.78)',
          letterSpacing: 0.5,
        }}>
          카드를 본인 앞에 엎어두고<br />다시 눈을 감아주세요.
        </div>
      </div>
    </div>
  )
}
