import { useEffect, useState } from 'react'
import { YachtDiceArt, WerewolfArt } from '../components/common/GameArt'
import { colorForIndex } from '../components/common/seatColors'

const GAME_META = {
  yacht: {
    title: '요트 다이스',
    tagline: '주사위 운빨과 전략의 만남',
    accent: 'var(--yacht)',
    art: 'yacht',
  },
  yacht_tutorial: {
    title: '요트 다이스',
    tagline: '튜토리얼 모드',
    accent: 'var(--yacht)',
    art: 'yacht',
  },
  werewolf: {
    title: '한밤의 늑대인간',
    tagline: '한 밤의 추리와 거짓말',
    accent: 'var(--werewolf)',
    art: 'wolf',
  },
  werewolf_practice: {
    title: '한밤의 늑대인간',
    tagline: '연습 모드',
    accent: 'var(--werewolf)',
    art: 'wolf',
  },
}

/**
 * Countdown은 frontend-only.
 * 3초 카운트 → 0이 되면 onReady 호출(여기서 select_game을 보내고 게임 페이지로 이동).
 * 그 전에 onCancel 누르면 백엔드 미통신 상태로 lobby 복귀.
 */
export default function Countdown({
  players,        // ordered ui players ({id, name, color, position})
  gameId,         // 'yacht' | 'yacht_tutorial' | 'werewolf' | 'werewolf_practice'
  mode,           // 'play' | 'tutorial' | 'practice'
  onCancel,
  onReady,
}) {
  const [count, setCount] = useState(3)

  useEffect(() => {
    if (count <= 0) {
      const t = setTimeout(() => onReady(), 400)
      return () => clearTimeout(t)
    }
    const t = setTimeout(() => setCount((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [count, onReady])

  const meta = GAME_META[gameId] || GAME_META.yacht
  // 늑대인간 'tutorial'은 실제로 '연습 모드'에 매핑됨.
  const isWerewolf = gameId === 'werewolf' || gameId === 'werewolf_practice'
  const eyebrow = (
    mode === 'tutorial'
      ? (isWerewolf ? '연습 모드' : '튜토리얼 모드')
    : mode === 'practice' ? '연습 모드'
    : '게임 시작 준비'
  )

  return (
    <div className="cd-wrap fade-in" style={{ '--cd-accent': meta.accent }}>
      <div className="cd-art-bg">
        {meta.art === 'yacht' && <YachtDiceArt />}
        {meta.art === 'wolf'  && <WerewolfArt />}
      </div>
      <div className="cd-veil" />

      <div className="cd-content slide-up">
        <div className="cd-eyebrow">{eyebrow}</div>
        <h1 className="cd-title">{meta.title}</h1>
        <div className="cd-subtitle">{meta.tagline}</div>

        <div className="cd-roster">
          {players.map((p, i) => (
            <div
              key={p.id}
              className="cd-slot"
              style={{ '--seat-color': p.color || colorForIndex(i) }}
            >
              <div className="cd-slot-no">{i + 1}</div>
              <div className="cd-slot-av">{(p.name || '?').charAt(0)}</div>
              <div className="cd-slot-name">{p.name}</div>
            </div>
          ))}
        </div>
        <div className="cd-roster-hint">
          위 순서대로 턴이 진행됩니다 · 첫 번째 차례:{' '}
          <b>{players[0]?.name || '-'}</b>
        </div>

        <div className="cd-number-row">
          {count > 0 ? (
            <>
              <div className="cd-number" key={count}>{count}</div>
              <div className="cd-go-label">초 후 시작</div>
            </>
          ) : (
            <>
              <div className="cd-number cd-go" key="go">GO</div>
              <div className="cd-go-label">불러오는 중…</div>
            </>
          )}
        </div>

        <div className="cd-actions">
          <button className="btn cd-cancel" onClick={onCancel}>시작 취소</button>
        </div>
      </div>

      <style>{`
        .cd-wrap {
          position: absolute; inset: 0;
          overflow: hidden;
          display: grid; place-items: center;
        }
        .cd-art-bg {
          position: absolute; inset: 0;
          opacity: 0.55;
          filter: blur(8px) saturate(110%);
          transform: scale(1.06);
        }
        .cd-veil {
          position: absolute; inset: 0;
          background:
            radial-gradient(ellipse at 50% 50%, transparent 0%, color-mix(in oklch, var(--bg-deep) 75%, transparent) 70%),
            linear-gradient(180deg, color-mix(in oklch, var(--bg-deep) 60%, transparent), color-mix(in oklch, var(--bg-deep) 80%, transparent));
        }
        .cd-content {
          position: relative;
          z-index: 2;
          width: min(820px, 86%);
          text-align: center;
          display: flex; flex-direction: column; align-items: center;
          gap: 8px;
          padding: 24px;
        }
        .cd-eyebrow {
          font-size: 13px; letter-spacing: 0.18em;
          text-transform: uppercase; font-weight: 600;
          color: var(--cd-accent);
          white-space: nowrap;
        }
        .cd-title {
          font-size: 44px; font-weight: 800; letter-spacing: -0.03em;
          text-shadow: 0 4px 24px rgba(0,0,0,0.5);
        }
        .cd-subtitle {
          font-size: 15px; color: var(--fg-soft);
          margin-bottom: 18px;
          white-space: nowrap;
        }

        .cd-roster {
          display: flex; gap: 8px; flex-wrap: wrap;
          justify-content: center;
          padding: 14px 18px;
          background: color-mix(in oklch, var(--bg-deep) 55%, transparent);
          border: 1px solid color-mix(in oklch, white 6%, transparent);
          backdrop-filter: blur(20px);
          border-radius: 18px;
          max-width: 100%;
        }
        .cd-slot {
          position: relative;
          padding: 10px 16px 10px 10px;
          background: color-mix(in oklch, var(--bg-app) 80%, transparent);
          border: 1px solid color-mix(in oklch, var(--seat-color) 35%, transparent);
          border-radius: 999px;
          display: flex; align-items: center; gap: 8px;
          font-size: 15px; font-weight: 500;
          white-space: nowrap;
        }
        .cd-slot-no {
          font-size: 12px;
          color: var(--seat-color);
          font-weight: 700;
          font-variant-numeric: tabular-nums;
          width: 18px; text-align: center;
        }
        .cd-slot-av {
          width: 28px; height: 28px;
          border-radius: 50%;
          background: linear-gradient(145deg,
            color-mix(in oklch, var(--seat-color) 95%, white 5%),
            color-mix(in oklch, var(--seat-color) 100%, black 14%));
          color: #1a1410;
          display: grid; place-items: center;
          font-weight: 700; font-size: 13px;
          box-shadow: 0 1px 0 rgba(255,255,255,0.2) inset;
        }
        .cd-slot-name { color: var(--fg); }

        .cd-roster-hint {
          font-size: 14px; color: var(--fg-mute);
          margin-bottom: 10px;
          white-space: nowrap;
        }
        .cd-roster-hint b { color: var(--fg); }

        .cd-number-row {
          display: flex; flex-direction: column; align-items: center; gap: 2px;
          margin-top: 8px;
        }
        .cd-number {
          font-size: 120px; line-height: 1; font-weight: 800;
          font-variant-numeric: tabular-nums;
          letter-spacing: -0.04em;
          color: var(--cd-accent);
          text-shadow: 0 12px 60px color-mix(in oklch, var(--cd-accent) 40%, transparent);
          animation: cd-pop 0.85s cubic-bezier(.2,.7,.2,1.05);
        }
        .cd-number.cd-go {
          font-size: 90px;
          letter-spacing: -0.02em;
          color: var(--ok);
          animation: cd-pop 0.6s cubic-bezier(.2,.7,.2,1.05);
        }
        @keyframes cd-pop {
          0%   { transform: scale(1.6); }
          30%  { transform: scale(1); }
          100% { transform: scale(1); }
        }
        .cd-go-label { font-size: 15px; color: var(--fg-mute); white-space: nowrap; }

        .cd-actions {
          display: flex; gap: 8px; justify-content: center;
          margin-top: 18px;
        }
        .cd-cancel {
          background: color-mix(in oklch, var(--bg-deep) 70%, transparent);
          border-color: color-mix(in oklch, var(--fg) 12%, transparent);
          color: var(--fg-soft);
          backdrop-filter: blur(20px);
          padding: 12px 28px;
        }
        .cd-cancel:hover { background: var(--bg-elev); color: var(--fg); }
      `}</style>
    </div>
  )
}
