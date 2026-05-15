import { useEffect } from 'react'

// duration: 전체 애니메이션 시간(ms), midAt: 뒷배경 페이즈 교체 타이밍(ms)
const CONFIGS = {
  eye_close:    { duration: 1500, midAt: 680 },  // 야간→야간: 눈 감기/뜨기
  dawn:         { duration: 2500, midAt: 300 },  // 야간→낮: 일출
  red_vignette: { duration: 1800, midAt: 740 },  // 낮→투표: 붉은 조임
  flash_fade:   { duration: 3900, midAt: 450 },  // 투표→결과: 처형 낙하
  fade:         { duration: 600,  midAt: 270 },  // 기본 페이드
}

const base = {
  position: 'fixed',
  inset: 0,
  zIndex: 9999,
  pointerEvents: 'none',
}

export default function PhaseTransition({ type = 'fade', onDone, onMidpoint }) {
  const { duration, midAt } = CONFIGS[type] ?? CONFIGS.fade

  useEffect(() => {
    const timers = []
    if (midAt != null && onMidpoint) timers.push(setTimeout(onMidpoint, midAt))
    if (onDone)                       timers.push(setTimeout(onDone, duration))
    return () => timers.forEach(clearTimeout)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (type === 'eye_close')    return <EyeClose duration={duration} />
  if (type === 'dawn')         return <Dawn duration={duration} />
  if (type === 'red_vignette') return <RedVignette duration={duration} />
  if (type === 'flash_fade')   return <FlashFade duration={duration} />
  return <Fade duration={duration} />
}

// ── 야간→야간: 위아래 검은 막이 닫혔다가 열림 ─────────────────────────────
function EyeClose({ duration }) {
  const d = `${duration}ms`
  return (
    <>
      <style>{`
        @keyframes ww-lid-top {
          0%,100% { transform: scaleY(0); }
          43%,57% { transform: scaleY(1); }
        }
        @keyframes ww-lid-bot {
          0%,100% { transform: scaleY(0); }
          43%,57% { transform: scaleY(1); }
        }
      `}</style>
      <div style={{ ...base, overflow: 'hidden' }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: '50%',
          background: '#000',
          transformOrigin: 'top',
          animation: `ww-lid-top ${d} cubic-bezier(.4,0,.6,1) forwards`,
        }} />
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: '50%',
          background: '#000',
          transformOrigin: 'bottom',
          animation: `ww-lid-bot ${d} cubic-bezier(.4,0,.6,1) forwards`,
        }} />
      </div>
    </>
  )
}

// ── 야간→낮: 태양이 지평선에서 떠오르는 일출 ────────────────────────────────
function Dawn({ duration }) {
  const d = `${duration}ms`
  return (
    <>
      <style>{`
        @keyframes ww-night-out {
          0%,18% { opacity: 1; }
          62%    { opacity: 0; }
          100%   { opacity: 0; }
        }
        @keyframes ww-sky-dawn {
          0%,10% { opacity: 0; }
          42%    { opacity: 1; }
          80%    { opacity: 1; }
          100%   { opacity: 0; }
        }
        @keyframes ww-horiz {
          0%    { opacity: 0; transform: scaleX(0.5); }
          20%   { opacity: 0.7; transform: scaleX(0.8); }
          52%   { opacity: 1; transform: scaleX(1.15); }
          80%   { opacity: 0.7; }
          100%  { opacity: 0; }
        }
        @keyframes ww-sun-up {
          0%    { opacity: 0; transform: translateY(0px) scale(0.5); }
          18%   { opacity: 0; transform: translateY(-8px) scale(0.6); }
          44%   { opacity: 1; transform: translateY(-50px) scale(0.9); }
          66%   { opacity: 1; transform: translateY(-80px) scale(1); }
          83%   { opacity: 0.85; transform: translateY(-95px) scale(1.03); }
          100%  { opacity: 0; transform: translateY(-108px) scale(1.06); }
        }
        @keyframes ww-rays-op {
          0%,30% { opacity: 0; }
          55%    { opacity: 0.7; }
          72%    { opacity: 0.75; }
          88%    { opacity: 0.3; }
          100%   { opacity: 0; }
        }
        @keyframes ww-bloom {
          0%,62% { opacity: 0; }
          73%    { opacity: 0.7; }
          82%    { opacity: 0.4; }
          100%   { opacity: 0; }
        }
      `}</style>
      <div style={{ ...base, overflow: 'hidden' }}>
        {/* 밤하늘 */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(180deg, #000008 0%, #030114 45%, #090418 100%)',
          animation: `ww-night-out ${d} ease-in-out forwards`,
        }} />
        {/* 새벽 하늘 */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(180deg, #060921 0%, #180530 22%, #7a2008 50%, #e25510 74%, #f5a820 100%)',
          animation: `ww-sky-dawn ${d} ease-in-out forwards`,
        }} />
        {/* 수평선 빛 번짐 */}
        <div style={{
          position: 'absolute', bottom: 0,
          left: '-18%', width: '136%', height: '55%',
          transformOrigin: 'bottom center',
          background: 'radial-gradient(ellipse at 50% 100%, rgba(255,165,40,0.95) 0%, rgba(230,78,10,0.82) 25%, rgba(145,32,5,0.52) 55%, transparent 80%)',
          animation: `ww-horiz ${d} ease-in-out forwards`,
        }} />
        {/* 태양 광선 */}
        <div style={{
          position: 'absolute',
          bottom: '14%', left: 'calc(50% - 350px)',
          width: 700, height: 700,
          background: `conic-gradient(
            from -90deg at 50% 86%,
            transparent 0deg,
            rgba(255,195,65,0.22) 2.5deg, transparent 6deg,
            rgba(255,185,55,0.18) 9.5deg,  transparent 13deg,
            rgba(255,205,75,0.2)  17deg,   transparent 20.5deg,
            rgba(255,190,60,0.15) 24deg,   transparent 27.5deg,
            rgba(255,200,70,0.2)  32deg,   transparent 35.5deg,
            rgba(255,185,55,0.16) 40deg,   transparent 44deg,
            rgba(255,200,68,0.18) 49deg,   transparent 53deg,
            rgba(255,190,60,0.12) 59deg,   transparent 63.5deg,
            rgba(255,195,65,0.15) 70deg,   transparent 75deg,
            rgba(255,185,55,0.1)  82deg,   transparent 90deg,
            transparent 90deg 360deg
          )`,
          animation: `ww-rays-op ${d} ease-in-out forwards`,
        }} />
        {/* 태양 후광 + 디스크: 지평선 위치에서 시작해 위로만 이동 */}
        <div style={{
          position: 'absolute',
          bottom: 'calc(14% - 110px)', left: 'calc(50% - 140px)',
          width: 280, height: 280,
          animation: `ww-sun-up ${d} ease-out forwards`,
        }}>
          <div style={{
            position: 'absolute', inset: 0,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(255,248,180,0.95) 0%, rgba(255,195,65,0.88) 15%, rgba(255,135,22,0.65) 42%, rgba(200,58,8,0.28) 68%, transparent 86%)',
          }} />
          <div style={{
            position: 'absolute', top: 85, left: 85,
            width: 110, height: 110,
            borderRadius: '50%',
            background: 'radial-gradient(circle, #fffeee 0%, #fff8b0 28%, #ffdf50 58%, #ffa818 90%)',
            boxShadow: '0 0 45px 22px rgba(255,225,80,0.75), 0 0 95px 48px rgba(255,148,28,0.4)',
          }} />
        </div>
        {/* 절정 빛 번짐 */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'radial-gradient(ellipse at 50% 80%, rgba(255,225,130,0.42) 0%, rgba(255,165,60,0.22) 28%, transparent 62%)',
          animation: `ww-bloom ${d} ease-in-out forwards`,
        }} />
      </div>
    </>
  )
}

// ── 낮→투표: 화면 가장자리에서 붉은 빛이 안쪽으로 조여옴 ─────────────────
function RedVignette({ duration }) {
  const d = `${duration}ms`
  return (
    <>
      <style>{`
        @keyframes ww-red-vig {
          0%       { opacity: 0; }
          40%,65%  { opacity: 1; }
          100%     { opacity: 0; }
        }
      `}</style>
      <div style={{
        ...base,
        background: 'radial-gradient(ellipse at center, rgba(60,0,0,0.5) 10%, rgba(120,10,10,0.85) 55%, rgba(60,0,0,0.98) 100%)',
        animation: `ww-red-vig ${d} ease-in-out forwards`,
      }} />
    </>
  )
}

// ── 투표→결과: 처형 낙하 ─────────────────────────────────────────────────────
function FlashFade({ duration }) {
  const d = `${duration}ms`
  return (
    <>
      <style>{`
        @keyframes ww-exec-shadow {
          0%    { opacity: 0; transform: scaleY(0); }
          12%   { opacity: 0.75; transform: scaleY(1); }
          30%   { opacity: 0; }
          100%  { opacity: 0; }
        }
        @keyframes ww-exec-curtain {
          0%    { transform: translateY(-100%) skewX(0deg);
                  animation-timing-function: cubic-bezier(0.4,0,1,0.9); }
          26%   { transform: translateY(3%) skewX(1.5deg);
                  animation-timing-function: ease-out; }
          36%   { transform: translateY(0%) skewX(0deg); }
          66%   { transform: translateY(0%); opacity: 1; }
          88%   { opacity: 0.85; }
          100%  { opacity: 0; }
        }
        @keyframes ww-exec-impact {
          0%,27%  { opacity: 0; }
          30%     { opacity: 0.35; }
          38%     { opacity: 0; }
          100%    { opacity: 0; }
        }
      `}</style>
      <div style={base}>
        {/* 낙하 예고 그림자 */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: '45%',
          transformOrigin: 'top',
          background: 'linear-gradient(180deg, rgba(0,0,0,0.96) 0%, transparent 100%)',
          animation: `ww-exec-shadow ${d} ease-in forwards`,
        }} />
        {/* 낙하 커튼 */}
        <div style={{
          position: 'absolute', inset: 0,
          background: '#050505',
          animation: `ww-exec-curtain ${d} linear forwards`,
        }} />
        {/* 충돌 플래시 */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'rgba(255,240,240,0.18)',
          animation: `ww-exec-impact ${d} ease-out forwards`,
        }} />
      </div>
    </>
  )
}

// ── 기본 페이드 ────────────────────────────────────────────────────────────
function Fade({ duration }) {
  const d = `${duration}ms`
  return (
    <>
      <style>{`
        @keyframes ww-fade {
          0%,100% { opacity: 0; }
          43%,57% { opacity: 1; }
        }
      `}</style>
      <div style={{
        ...base,
        background: '#000',
        animation: `ww-fade ${d} ease-in-out forwards`,
      }} />
    </>
  )
}
