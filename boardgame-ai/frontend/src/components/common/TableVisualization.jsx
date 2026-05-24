import { useRef } from 'react'
import { colorForIndex } from './seatColors'

function perimeterPoint(t, w, h, inset = 0) {
  const W = w - inset * 2
  const H = h - inset * 2
  const perim = 2 * (W + H)
  const d = (((t % 1) + 1) % 1) * perim
  if (d < W)         return { x: inset + d, y: inset, side: 'top' }
  if (d < W + H)     return { x: inset + W, y: inset + (d - W), side: 'right' }
  if (d < 2 * W + H) return { x: inset + W - (d - W - H), y: inset + H, side: 'bottom' }
  return               { x: inset, y: inset + H - (d - 2 * W - H), side: 'left' }
}

export default function TableVisualization({
  players = [],
  activeId = null,
  onSelect = () => {},
  shape = 'rect',
  compact = false,
  showTablet = true,
}) {
  const W = 100, H = compact ? 64 : 70
  const insetPx = 12
  const wrapRef = useRef(null)

  const seats = players.map((p) => {
    const t = p.position ?? 0
    if (shape === 'round') {
      const cx = W / 2, cy = H / 2
      const rx = (W / 2) - insetPx
      const ry = (H / 2) - insetPx
      const angle = -Math.PI / 2 + t * Math.PI * 2
      return { ...p, x: cx + Math.cos(angle) * rx, y: cy + Math.sin(angle) * ry, side: 'round' }
    }
    const pt = perimeterPoint(t, W, H, insetPx)
    return { ...p, ...pt }
  })

  const seatRadius = compact ? 3.4 : 3.8

  return (
    <div
      className="tv-wrap"
      ref={wrapRef}
      style={{ aspectRatio: `${W} / ${H}` }}
    >
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="tv-svg">
        {shape === 'rect' ? (
          <>
            <rect x="14" y="14" width={W - 28} height={H - 28} rx="4"
              fill="url(#tableSurface)" stroke="var(--border)" strokeWidth="0.2" />
            <rect x="14.6" y="14.6" width={W - 29.2} height={H - 29.2} rx="3.5"
              fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="0.2" />
          </>
        ) : (
          <ellipse cx={W / 2} cy={H / 2} rx={(W / 2) - 14} ry={(H / 2) - 14}
            fill="url(#tableSurface)" stroke="var(--border)" strokeWidth="0.2" />
        )}

        {showTablet && shape === 'rect' && (
          <g opacity="0.7">
            <rect x={W / 2 - 8} y={H / 2 - 5} width="16" height="10" rx="1.2"
              fill="var(--bg-elev)" stroke="var(--border)" strokeWidth="0.25" />
            <rect x={W / 2 - 7} y={H / 2 - 4.2} width="14" height="8.4" rx="0.8"
              fill="var(--bg-deep)" />
            <text x={W / 2} y={H / 2 + 0.6}
              textAnchor="middle" fontSize="2.4" fill="var(--fg-mute)"
              fontFamily="var(--font)" fontWeight="500" letterSpacing="0.15">TABLE</text>
          </g>
        )}
        {showTablet && shape === 'round' && (
          <g opacity="0.7">
            <circle cx={W / 2} cy={H / 2} r="6" fill="var(--bg-elev)" stroke="var(--border)" strokeWidth="0.25" />
            <text x={W / 2} y={H / 2 + 0.8}
              textAnchor="middle" fontSize="2.0" fill="var(--fg-mute)"
              fontFamily="var(--font)" fontWeight="500" letterSpacing="0.12">TABLE</text>
          </g>
        )}

        <defs>
          <linearGradient id="tableSurface" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="var(--bg-surface)" />
            <stop offset="1" stopColor="var(--bg-elev)" />
          </linearGradient>
        </defs>
      </svg>

      <div className="tv-seats">
        {seats.map((s, i) => {
          const px = s.x
          const py = s.y
          const isActive = s.id === activeId
          const color = s.color || colorForIndex(i)
          const initial = (s.name || '?').charAt(0)
          return (
            <div
              key={s.id}
              className={`tv-seat ${isActive ? 'active' : ''}`}
              style={{
                left: `${px}%`,
                top: `${py / H * 100}%`,
                '--seat-color': color,
                width: `${seatRadius * 2}%`,
                aspectRatio: 1,
              }}
              onClick={() => onSelect(s.id)}
              role="button"
              tabIndex={0}
            >
              <div className="tv-seat-ring" />
              <div className="tv-seat-circle">
                <span className="tv-seat-initial">{initial}</span>
              </div>
              <div className={`tv-seat-label tv-seat-label-${s.side || 'bottom'}`}>
                <div className="tv-name">{s.name}</div>
                <div className="tv-order">#{i + 1}</div>
              </div>
            </div>
          )
        })}
      </div>

      <style>{`
        .tv-wrap {
          position: relative;
          width: 100%;
          user-select: none;
          touch-action: none;
        }
        .tv-svg {
          position: absolute; inset: 0;
          width: 100%; height: 100%;
          display: block;
        }
        .tv-seats { position: absolute; inset: 0; }
        .tv-seat {
          position: absolute;
          transform: translate(-50%, -50%);
          cursor: pointer;
          transition: filter 200ms ease;
        }
        .tv-seat-ring {
          position: absolute; inset: -14%;
          border-radius: 50%;
          background: radial-gradient(circle, var(--seat-color), transparent 65%);
          opacity: 0.0;
          transition: opacity 200ms ease;
        }
        .tv-seat.active .tv-seat-ring { opacity: 0.35; }
        .tv-seat-circle {
          position: relative;
          width: 100%; height: 100%;
          border-radius: 50%;
          background: linear-gradient(145deg,
            color-mix(in oklch, var(--seat-color) 95%, white 5%),
            color-mix(in oklch, var(--seat-color) 100%, black 14%));
          color: #1a1410;
          display: grid; place-items: center;
          font-weight: 700;
          font-size: clamp(13px, 1.7cqw, 18px);
          box-shadow:
            0 1px 0 rgba(255,255,255,0.2) inset,
            0 2px 6px rgba(0,0,0,0.3);
          transition: transform 180ms cubic-bezier(.2,.7,.2,1.05);
        }
        .tv-seat.active .tv-seat-circle {
          box-shadow:
            0 1px 0 rgba(255,255,255,0.2) inset,
            0 0 0 3px color-mix(in oklch, var(--accent) 80%, transparent),
            0 4px 10px rgba(0,0,0,0.35);
          transform: scale(1.06);
        }
        .tv-seat-initial {
          display: block;
          font-family: var(--font);
          letter-spacing: -0.02em;
        }
        .tv-seat-label {
          position: absolute;
          font-family: var(--font);
          color: var(--fg);
          text-align: center;
          white-space: nowrap;
          font-weight: 500;
          line-height: 1.15;
          pointer-events: none;
        }
        .tv-seat-label .tv-name {
          font-size: clamp(11px, 1.25cqw, 15px);
          letter-spacing: -0.01em;
        }
        .tv-seat-label .tv-order {
          font-size: clamp(8px, 0.9cqw, 11px);
          color: var(--fg-mute);
          font-variant-numeric: tabular-nums;
          margin-top: 2px;
        }
        .tv-seat-label-top    { left: 50%; bottom: calc(100% + 6px); transform: translateX(-50%); }
        .tv-seat-label-bottom { left: 50%; top:    calc(100% + 6px); transform: translateX(-50%); }
        .tv-seat-label-left   { right:  calc(100% + 10px); top: 50%; transform: translateY(-50%); text-align: right; }
        .tv-seat-label-right  { left:   calc(100% + 10px); top: 50%; transform: translateY(-50%); text-align: left; }
        .tv-seat-label-round  { left: 50%; top: calc(100% + 6px); transform: translateX(-50%); }
      `}</style>
    </div>
  )
}
