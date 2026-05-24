import { useMemo, useState } from 'react'
import {
  IconPlus, IconCheck, IconArrowRight, IconEdit, IconTrash, IconUsers,
} from './Icons'
import TableVisualization from './TableVisualization'
import HandRegistrationModal from './HandRegistrationModal'
import { colorForPlayerId } from './seatColors'

/** position이 없는 등록 중 플레이어를 위해 균등 분배(임시) */
function fillMissingPositions(players) {
  const N = players.length
  if (N === 0) return []
  return players.map((p, i) => ({
    ...p,
    position: p.position == null ? i / N : p.position,
  }))
}

/** firstPlayerId/direction에 맞게 좌석 순서로 정렬 */
function orderForTurn(players, firstPlayerId, direction) {
  if (players.length === 0) return []
  const byPos = [...players].sort((a, b) => (a.position ?? 0) - (b.position ?? 0))
  const startIdx = Math.max(0, byPos.findIndex((p) => p.id === firstPlayerId))
  const walked = [...byPos.slice(startIdx), ...byPos.slice(0, startIdx)]
  if (direction === 'ccw') {
    return [walked[0], ...walked.slice(1).reverse()]
  }
  return walked
}

export default function SeatRegistration({
  players,            // backend snapshot players (raw)
  registeringId,
  seatStep = 'idle',
  connected,
  firstPlayerId,
  direction,
  onChangeFirst,
  onChangeDirection,
  send,
  onStart,
}) {
  const [editingId, setEditingId] = useState(null)
  const [activeId, setActiveId] = useState(null)

  // backend players → UI players (id, name, position, color)
  const uiPlayers = useMemo(() => {
    const named = players
      .filter((p) => p.playername || p.player_id === registeringId)
      .map((p) => ({
        id: p.player_id,
        name: p.playername || '',
        position: p.position ?? null,
        registered: p.registered,
        color: colorForPlayerId(p.player_id),
        raw: p,
      }))
    return fillMissingPositions(named)
  }, [players, registeringId])

  const ordered = useMemo(
    () => orderForTurn(uiPlayers, firstPlayerId, direction),
    [uiPlayers, firstPlayerId, direction],
  )

  const totalPlayers = ordered.length
  const namedPlayers = ordered.filter((p) => p.name)
  const canStart =
    namedPlayers.length > 0 && namedPlayers.every((p) => p.registered)

  const cameraLabel = connected
    ? { dot: 'ok', text: '카메라 연결됨', sub: '테이블 전체 인식 중' }
    : { dot: 'err', text: '카메라 오류', sub: '연결 상태를 확인해 주세요' }

  const startRegistration = () => send('start_registration', {})
  const cancelRegistration = () => {
    if (registeringId) send('cancel_seat_registration', { player_id: registeringId })
    setEditingId(null)
  }
  const finalizePlayer = (name) => {
    if (!registeringId) return
    send('finalize_player', { player_id: registeringId, playername: name })
  }
  const submitEdit = (player_id, name) => {
    send('player_edit', { player_id, playername: name })
    setEditingId(null)
  }
  const removePlayer = (player_id) => {
    send('player_remove', { player_id })
    if (editingId === player_id) setEditingId(null)
  }
  const restartRegistration = (player_id) => {
    send('start_seat_registration', { player_id })
  }

  const showHandModal = !!registeringId
  const editingPlayer =
    editingId && uiPlayers.find((p) => p.id === editingId)

  const defaultName = `플레이어${namedPlayers.length + 1}`

  return (
    <div className="scr scr-register">
      <div className="topbar">
        <div className="logo"><span>보드게임 AI</span></div>
        <div className="crumbs">
          <span>플레이어 등록</span>
          <span className="sep">→</span>
          <span style={{ opacity: 0.5 }}>게임 선택</span>
          <span className="sep">→</span>
          <span style={{ opacity: 0.5 }}>플레이</span>
        </div>
        <div className="right">
          <div className="camera-badge">
            <span className={`status-dot ${cameraLabel.dot} pulse`} />
            <div>
              <div style={{ color: 'var(--fg)', fontWeight: 500 }}>{cameraLabel.text}</div>
              <div style={{ fontSize: 13, color: 'var(--fg-mute)' }}>{cameraLabel.sub}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="reg-grid">
        <div className="reg-left scroll">
          <div className="reg-hd">
            <h1 className="reg-title">플레이어 등록</h1>
          </div>

          <div className="player-list">
            {ordered.map((p, i) => (
              <PlayerRow
                key={p.id}
                player={p}
                index={i}
                isActive={activeId === p.id}
                onHover={() => setActiveId(p.id)}
                onLeave={() => setActiveId(null)}
                onEdit={() => setEditingId(p.id)}
                onRemove={() => removePlayer(p.id)}
                onReregister={() => restartRegistration(p.id)}
              />
            ))}

            {!showHandModal && (
              <button className="add-player" onClick={startRegistration}>
                <div className="ap-icon"><IconPlus size={24} /></div>
                <div className="ap-text">
                  <div className="ap-title">플레이어 추가</div>
                  <div className="ap-sub">손 동작으로 자리를 등록합니다</div>
                </div>
              </button>
            )}
          </div>
        </div>

        <div className="reg-right">
          <div className="rr-header">
            <h1 className="rr-title">실제 좌석 배치</h1>
            <div className="rr-hint">등록한 자리 위치에 그대로 표시됩니다</div>
          </div>

          <div className="rr-table">
            <TableVisualization
              players={ordered}
              activeId={activeId}
              onSelect={setActiveId}
              shape="rect"
              showTablet={totalPlayers > 0}
            />
            {totalPlayers === 0 && (
              <div className="rr-empty">
                <IconUsers size={40} />
                <p>플레이어를 추가하면 좌석이 여기에 표시됩니다</p>
              </div>
            )}
          </div>

          <TurnControls
            players={ordered}
            firstPlayerId={firstPlayerId}
            onChangeFirst={onChangeFirst}
            direction={direction}
            onChangeDirection={onChangeDirection}
          />
        </div>
      </div>

      <div className="reg-foot">
        <div className="foot-info">
          {totalPlayers > 0 ? (
            <>
              <IconCheck size={16} style={{ color: 'var(--ok)' }} />
              <span><b>{namedPlayers.length}명</b>의 플레이어가 준비되었습니다</span>
            </>
          ) : (
            <span style={{ color: 'var(--fg-mute)' }}>
              플레이어를 한 명 이상 추가해 주세요
            </span>
          )}
        </div>
        <button
          className="btn btn-primary btn-lg"
          disabled={!canStart}
          onClick={canStart ? onStart : undefined}
        >
          게임 선택 <IconArrowRight size={18} />
        </button>
      </div>

      {showHandModal && (
        <HandRegistrationModal
          seatStep={seatStep}
          defaultName={defaultName}
          existingNames={uiPlayers
            .filter((p) => p.id !== registeringId && p.name)
            .map((p) => p.name)}
          onCancel={cancelRegistration}
          onSubmit={finalizePlayer}
        />
      )}

      {editingPlayer && (
        <EditNameModal
          initialName={editingPlayer.name}
          existingNames={uiPlayers
            .filter((p) => p.id !== editingPlayer.id && p.name)
            .map((p) => p.name)}
          onCancel={() => setEditingId(null)}
          onSubmit={(name) => submitEdit(editingPlayer.id, name)}
        />
      )}

      <style>{`
        .scr-register {
          position: absolute; inset: 0;
          display: flex; flex-direction: column;
          padding-top: 56px;
        }
        .scr-register .camera-badge {
          display: flex; align-items: center; gap: 10px;
          padding: 8px 16px;
          background: var(--bg-surface);
          border: 1px solid var(--border-soft);
          border-radius: 999px;
          font-size: 14px;
        }
        .reg-grid {
          flex: 1;
          display: grid;
          grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
          min-height: 0;
        }
        .reg-left {
          padding: 18px 24px 14px 32px;
          overflow-y: auto;
          display: flex; flex-direction: column; gap: 18px;
          border-right: 1px solid var(--border-soft);
        }
        .reg-hd { display: flex; flex-direction: column; gap: 6px; margin-bottom: 0; }
        .reg-title { font-size: 26px; font-weight: 700; letter-spacing: -0.025em; }
        .reg-left .reg-hd { margin-bottom: 0; }
        .player-list { display: flex; flex-direction: column; gap: 8px; }
        .add-player {
          appearance: none; border: 1.5px dashed var(--border);
          background: transparent; color: var(--fg-soft);
          padding: 16px 18px;
          border-radius: var(--radius);
          display: flex; align-items: center; gap: 14px;
          transition: all 160ms ease;
          margin-top: 4px;
        }
        .add-player:hover {
          border-color: var(--accent);
          background: color-mix(in oklch, var(--accent) 8%, transparent);
          color: var(--fg);
        }
        .ap-icon {
          width: 40px; height: 40px; border-radius: 50%;
          background: var(--bg-surface);
          display: grid; place-items: center;
          color: var(--accent);
        }
        .ap-text { text-align: left; }
        .ap-title { font-weight: 600; font-size: 17px; }
        .ap-sub { font-size: 14px; color: var(--fg-mute); margin-top: 3px; }

        .reg-right {
          padding: 18px 32px 14px 24px;
          display: flex; flex-direction: column;
          min-height: 0;
          gap: 0;
        }
        .rr-header { display: flex; flex-direction: column; gap: 6px; margin-bottom: 18px; }
        .rr-title { font-size: 26px; font-weight: 700; letter-spacing: -0.025em; }
        .rr-hint  { font-size: 14px; color: var(--fg-mute); }
        .rr-table {
          flex: 1;
          position: relative;
          background:
            radial-gradient(ellipse at 50% 30%, color-mix(in oklch, var(--accent) 4%, transparent), transparent 60%),
            var(--bg-app);
          border: 1px solid var(--border-soft);
          border-radius: var(--radius-lg);
          padding: 36px 48px;
          display: grid;
          place-items: center;
          container-type: inline-size;
          min-height: 0;
        }
        .rr-empty {
          position: absolute; inset: 0;
          display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          gap: 12px;
          color: var(--fg-faint);
          font-size: 13px;
          pointer-events: none;
        }

        .reg-foot {
          height: 76px;
          padding: 0 32px;
          display: flex; align-items: center; gap: 16px;
          border-top: 1px solid var(--border-soft);
          background: linear-gradient(180deg, transparent, color-mix(in oklch, var(--bg-deep) 50%, transparent));
        }
        .foot-info {
          display: flex; align-items: center; gap: 8px;
          font-size: 16px; color: var(--fg-soft);
          white-space: nowrap;
        }
        .reg-foot .btn-primary { margin-left: auto; }
      `}</style>
    </div>
  )
}

function PlayerRow({ player, index, isActive, onHover, onLeave, onEdit, onRemove, onReregister }) {
  return (
    <div
      className={`prow ${isActive ? 'active' : ''}`}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      style={{ '--row-color': player.color }}
    >
      <div className="prow-order">{index + 1}</div>
      <div className="prow-avatar">
        <span>{(player.name || '?').charAt(0)}</span>
      </div>
      <div className="prow-main">
        <div className="prow-name">{player.name || '등록 중…'}</div>
        {!player.registered && (
          <div className="prow-sub">등록 미완료</div>
        )}
      </div>
      <div className="prow-actions">
        {!player.registered && (
          <button className="btn-icn" onClick={onReregister} title="재등록">
            ↻
          </button>
        )}
        <button className="btn-icn" onClick={onEdit} title="수정">
          <IconEdit size={16} />
        </button>
        <button className="btn-icn danger" onClick={onRemove} title="삭제">
          <IconTrash size={16} />
        </button>
      </div>

      <style>{`
        .prow {
          display: flex; align-items: center; gap: 12px;
          padding: 12px 14px;
          background: var(--bg-surface);
          border: 1px solid var(--border-soft);
          border-radius: var(--radius);
          transition: all 160ms ease;
          position: relative;
        }
        .prow.active {
          border-color: color-mix(in oklch, var(--row-color) 50%, var(--border));
          background: color-mix(in oklch, var(--row-color) 6%, var(--bg-surface));
        }
        .prow-order {
          width: 24px; flex-shrink: 0;
          font-size: 14px; font-weight: 600;
          color: var(--fg-mute);
          font-variant-numeric: tabular-nums;
          text-align: center;
        }
        .prow.active .prow-order { color: var(--row-color); }
        .prow-avatar {
          width: 38px; height: 38px; border-radius: 50%;
          background: linear-gradient(145deg,
            color-mix(in oklch, var(--row-color) 95%, white 5%),
            color-mix(in oklch, var(--row-color) 100%, black 14%));
          color: #1a1410;
          display: grid; place-items: center;
          font-weight: 700; font-size: 16px;
          box-shadow: 0 1px 0 rgba(255,255,255,0.2) inset, 0 2px 6px rgba(0,0,0,0.3);
          flex-shrink: 0;
        }
        .prow-main { flex: 1; min-width: 0; }
        .prow-name {
          font-size: 17px; font-weight: 600; color: var(--fg);
          letter-spacing: -0.01em;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .prow-sub { font-size: 13px; color: var(--warn); margin-top: 3px; }
        .prow-actions { display: flex; gap: 4px; }
        .btn-icn {
          appearance: none; border: 1px solid transparent;
          background: transparent;
          color: var(--fg-mute);
          width: 32px; height: 32px; border-radius: 8px;
          display: grid; place-items: center;
          cursor: pointer;
          transition: all 120ms ease;
          font-size: 16px;
        }
        .btn-icn:hover { background: var(--bg-elev); color: var(--fg); }
        .btn-icn.danger:hover { color: var(--err); background: color-mix(in oklch, var(--err) 14%, transparent); }
      `}</style>
    </div>
  )
}

function TurnControls({ players, firstPlayerId, onChangeFirst, direction, onChangeDirection }) {
  const [open, setOpen] = useState(false)
  if (!players.length) return null
  const first = players[0]

  return (
    <div className="turn-ctrls">
      <div className="tc-first">
        <span className="tc-eyebrow">시작 플레이어</span>
        <button className="tc-first-pick" onClick={() => setOpen((o) => !o)}>
          <span className="tc-first-av" style={{ '--seat-color': first.color }}>
            {(first.name || '?').charAt(0)}
          </span>
          <span className="tc-first-name">{first.name || '등록 중'}</span>
          <span className="tc-chev">▾</span>
        </button>
        {open && (
          <div className="tc-menu">
            {players.map((p) => (
              <button
                key={p.id}
                className={`tc-menu-item ${p.id === firstPlayerId ? 'active' : ''}`}
                onClick={() => { onChangeFirst(p.id); setOpen(false) }}
              >
                <span className="tc-menu-av" style={{ '--seat-color': p.color }}>
                  {(p.name || '?').charAt(0)}
                </span>
                <span className="tc-menu-name">{p.name || '등록 중'}</span>
                {p.id === firstPlayerId && (
                  <IconCheck size={14} style={{ marginLeft: 'auto', color: 'var(--accent)' }} />
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="tc-dir">
        <span className="tc-eyebrow">진행 방향</span>
        <div className="tc-dir-seg" role="radiogroup">
          <button
            className={`tc-dir-btn ${direction === 'cw' ? 'active' : ''}`}
            onClick={() => onChangeDirection('cw')}
            role="radio"
            aria-checked={direction === 'cw'}
          >
            <DirIcon kind="cw" />
            <span>시계방향</span>
          </button>
          <button
            className={`tc-dir-btn ${direction === 'ccw' ? 'active' : ''}`}
            onClick={() => onChangeDirection('ccw')}
            role="radio"
            aria-checked={direction === 'ccw'}
          >
            <DirIcon kind="ccw" />
            <span>반시계방향</span>
          </button>
        </div>
      </div>

      <style>{`
        .turn-ctrls {
          margin-top: 10px;
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 14px;
          align-items: end;
        }
        .tc-eyebrow {
          font-size: 13px; letter-spacing: 0.08em;
          text-transform: uppercase; font-weight: 600;
          color: var(--fg-mute);
          display: block; margin-bottom: 6px;
        }
        .tc-first { position: relative; min-width: 0; }
        .tc-first-pick {
          appearance: none;
          background: var(--bg-surface);
          border: 1px solid var(--border-soft);
          border-radius: 999px;
          padding: 7px 14px 7px 7px;
          color: var(--fg);
          display: inline-flex; align-items: center; gap: 10px;
          font: inherit;
          font-size: 15px; font-weight: 500;
          cursor: pointer;
          transition: all 120ms ease;
          max-width: 100%;
        }
        .tc-first-pick:hover { background: var(--bg-elev); border-color: var(--border); }
        .tc-first-av {
          width: 30px; height: 30px; border-radius: 50%;
          background: linear-gradient(145deg,
            color-mix(in oklch, var(--seat-color) 95%, white 5%),
            color-mix(in oklch, var(--seat-color) 100%, black 14%));
          color: #1a1410;
          display: grid; place-items: center;
          font-weight: 700; font-size: 14px;
          flex-shrink: 0;
        }
        .tc-first-name {
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
          min-width: 0;
        }
        .tc-chev { font-size: 12px; color: var(--fg-mute); margin-left: 2px; }

        .tc-menu {
          position: absolute;
          bottom: calc(100% + 4px);
          left: 0;
          min-width: 200px; max-width: 280px;
          background: var(--bg-elev);
          border: 1px solid var(--border);
          border-radius: 10px;
          box-shadow: var(--shadow);
          padding: 4px;
          z-index: 30;
          max-height: 240px;
          overflow-y: auto;
        }
        .tc-menu-item {
          appearance: none; border: 0;
          background: transparent;
          color: var(--fg);
          width: 100%;
          padding: 7px 10px;
          border-radius: 7px;
          display: flex; align-items: center; gap: 8px;
          cursor: pointer;
          font: inherit; font-size: 15px;
          text-align: left;
        }
        .tc-menu-name {
          flex: 1; min-width: 0;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .tc-menu-item:hover { background: var(--bg-hover); }
        .tc-menu-item.active { background: color-mix(in oklch, var(--accent) 12%, transparent); }
        .tc-menu-av {
          width: 24px; height: 24px; border-radius: 50%;
          background: linear-gradient(145deg,
            color-mix(in oklch, var(--seat-color) 95%, white 5%),
            color-mix(in oklch, var(--seat-color) 100%, black 14%));
          color: #1a1410;
          display: grid; place-items: center;
          font-weight: 700; font-size: 12px;
          flex-shrink: 0;
        }

        .tc-dir-seg {
          display: inline-flex;
          background: var(--bg-surface);
          border: 1px solid var(--border-soft);
          border-radius: 999px;
          padding: 3px; gap: 2px;
        }
        .tc-dir-btn {
          appearance: none; border: 0;
          background: transparent;
          color: var(--fg-mute);
          padding: 8px 16px;
          border-radius: 999px;
          font: inherit; font-size: 14px; font-weight: 500;
          display: inline-flex; align-items: center; gap: 6px;
          cursor: pointer;
          transition: all 140ms ease;
          white-space: nowrap;
        }
        .tc-dir-btn:hover { color: var(--fg); }
        .tc-dir-btn.active {
          background: var(--accent);
          color: #1a1410;
          box-shadow: 0 1px 3px rgba(0,0,0,0.25);
        }
        :root[data-mode="light"][data-accent="white"] .tc-dir-btn.active { color: #fff; }
        .tc-dir-btn svg { flex-shrink: 0; }
      `}</style>
    </div>
  )
}

function DirIcon({ kind, size = 14 }) {
  if (kind === 'cw') {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M21 12a9 9 0 1 1-4.5-7.8" />
        <polyline points="21 4 21 9 16 9" />
      </svg>
    )
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 12a9 9 0 1 0 4.5-7.8" />
      <polyline points="3 4 3 9 8 9" />
    </svg>
  )
}

function EditNameModal({ initialName, existingNames, onCancel, onSubmit }) {
  const [name, setName] = useState(initialName)
  const isUsed = existingNames.includes(name.trim()) && name.trim().length > 0

  const submit = () => {
    const trimmed = name.trim()
    if (!trimmed || isUsed) return
    onSubmit(trimmed)
  }

  return (
    <>
      <div className="backdrop" onClick={onCancel} />
      <div className="enm-modal">
        <div className="enm-head">
          <div className="enm-title">이름 변경</div>
        </div>
        <div className="enm-body">
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            maxLength={16}
            autoFocus
          />
          {isUsed && (
            <div className="enm-warn">
              <span className="status-dot warn" /> 이미 사용 중인 이름이에요.
            </div>
          )}
        </div>
        <div className="enm-foot">
          <button className="btn btn-ghost" onClick={onCancel}>취소</button>
          <button className="btn btn-primary" onClick={submit} disabled={!name.trim() || isUsed}>
            저장 <IconCheck size={18} />
          </button>
        </div>

        <style>{`
          .enm-modal {
            position: absolute;
            left: 50%; top: 50%;
            transform: translate(-50%, -50%);
            width: min(480px, 88%);
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow-lg);
            z-index: 100;
            display: flex; flex-direction: column;
            overflow: hidden;
            animation: enm-pop 240ms cubic-bezier(.2,.7,.2,1.05) both;
          }
          @keyframes enm-pop {
            from { transform: translate(-50%, -50%) scale(0.96); }
            to   { transform: translate(-50%, -50%) scale(1); }
          }
          .enm-head {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-soft);
          }
          .enm-title {
            font-size: 17px; font-weight: 700; letter-spacing: -0.01em;
            color: var(--fg);
          }
          .enm-body {
            padding: 20px 24px;
            display: flex; flex-direction: column; gap: 12px;
          }
          .enm-warn {
            font-size: 14px; color: var(--warn);
            display: flex; align-items: center; gap: 8px;
          }
          .enm-foot {
            display: flex; gap: 10px; justify-content: flex-end;
            padding: 14px 20px;
            border-top: 1px solid var(--border-soft);
            background: color-mix(in oklch, var(--bg-deep) 30%, transparent);
          }
        `}</style>
      </div>
    </>
  )
}
