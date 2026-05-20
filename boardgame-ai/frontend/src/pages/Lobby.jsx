import { useState } from 'react'

const s = {
  page: {
    minHeight: '100vh',
    background: '#f5f5f7',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', sans-serif",
    color: '#111',
  },
  title: { fontSize: 48, fontWeight: 700, marginBottom: 14 },
  subtitle: { fontSize: 22, color: '#555', marginBottom: 56 },
  cards: { display: 'flex', gap: 36, marginBottom: 36, alignItems: 'flex-start' },
  gameColumn: { width: 400, display: 'flex', flexDirection: 'column', gap: 12 },
  card: disabled => ({
    width: '100%',
    minHeight: 300,
    padding: '36px 40px',
    boxSizing: 'border-box',
    background: '#fff',
    border: '1px solid #e0e0e0',
    borderRadius: 22,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.45 : 1,
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    transition: 'box-shadow 0.15s, border-color 0.15s',
  }),
  icon: { fontSize: 48, marginBottom: 8 },
  gameName: { fontSize: 26, fontWeight: 600 },
  gameInfo: { fontSize: 19, color: '#666' },
  badge: {
    display: 'inline-block',
    marginTop: 14,
    padding: '5px 16px',
    background: '#efefef',
    borderRadius: 100,
    fontSize: 17,
    color: '#555',
    width: 'fit-content',
  },
  tutorialInlineButton: {
    border: '1px solid #cfd8cc',
    borderRadius: 8,
    background: '#eef6ed',
    color: '#1f6f49',
    padding: '11px 16px',
    fontSize: 17,
    fontWeight: 800,
    cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(31,122,79,0.08)',
    width: '100%',
    alignSelf: 'stretch',
    boxSizing: 'border-box',
  },
  practiceBtn: {
    marginTop: 6,
    padding: '7px 0',
    border: 'none',
    borderRadius: 0,
    background: 'transparent',
    color: '#7040c0',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    textDecoration: 'underline',
    textUnderlineOffset: 3,
    textAlign: 'left',
    width: 'fit-content',
  },
  exitButton: {
    border: '1px solid #d7d7d9',
    borderRadius: 8,
    background: '#fff',
    color: '#333',
    padding: '11px 22px',
    fontSize: 17,
    fontWeight: 700,
    cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
  },
  bottomActions: { display: 'flex', gap: 14, marginBottom: 24 },
  footer: { fontSize: 18, color: '#aaa' },
}

// ── 연습모드 설명 팝업 ──────────────────────────────────────────────────────

const FLOW_STEPS = [
  { icon: '🃏', label: '역할 등록' },
  { icon: '🌙', label: '밤 행동' },
  { icon: '💬', label: '낮 토론' },
  { icon: '🗳️', label: '투표' },
]

function PracticeModal({ onClose, onPlay }) {
  return (
    <div style={pm.backdrop} onClick={onClose}>
      <div style={pm.modal} onClick={e => e.stopPropagation()}>

        {/* 헤더 */}
        <div style={pm.header}>
          <span style={pm.moonIcon}>🌙</span>
          <div>
            <div style={pm.title}>한밤의 늑대인간</div>
            <div style={pm.subtitle}>연습 모드</div>
          </div>
        </div>

        {/* 게임 개요 */}
        <div style={pm.desc}>
          비밀 역할 카드를 받은 뒤, 밤에 행동하고 낮에 늑대인간을 추리해 처형하는 게임입니다.
          카드는 플레이어 수보다 <b>3장 많게</b> 준비하고, 남은 카드는 테이블 중앙에 놓으세요.
        </div>

        {/* 팀 카드 */}
        <div style={pm.teamRow}>
          <div style={{ ...pm.teamCard, borderColor: '#4a90d9', background: 'rgba(74,144,217,0.06)' }}>
            <div style={pm.teamIcon}>🏘️</div>
            <div style={{ ...pm.teamName, color: '#2563a8' }}>마을 팀</div>
            <div style={pm.teamGoal}>늑대인간을 찾아 처형하면 승리</div>
          </div>
          <div style={pm.teamVs}>VS</div>
          <div style={{ ...pm.teamCard, borderColor: '#c0392b', background: 'rgba(192,57,43,0.06)' }}>
            <div style={pm.teamIcon}>🐺</div>
            <div style={{ ...pm.teamName, color: '#b22222' }}>늑대인간 팀</div>
            <div style={pm.teamGoal}>정체를 숨기고 마을 팀이 처형되면 승리</div>
          </div>
        </div>

        {/* 진행 흐름 */}
        <div style={pm.flowRow}>
          {FLOW_STEPS.map((step, i) => (
            <div key={i} style={pm.flowItem}>
              <div style={pm.flowChip}>
                <span style={pm.flowIcon}>{step.icon}</span>
                <span style={pm.flowLabel}>{step.label}</span>
              </div>
              {i < FLOW_STEPS.length - 1 && <span style={pm.flowArrow}>›</span>}
            </div>
          ))}
        </div>

        {/* 연습모드 안내 */}
        <div style={pm.note}>
          <span style={pm.noteDot} />
          <span>눈을 감지 않고 진행합니다. 차례가 되면 해당 역할 플레이어가 직접 행동하세요. 역할 등록 시 <b>역할 설명 보기</b>로 행동과 승리 조건을 확인할 수 있습니다.</span>
        </div>

        {/* 하단 버튼 */}
        <div style={pm.footer}>
          <button style={pm.cancelBtn} onClick={onClose}>나가기</button>
          <button style={pm.playBtn} onClick={onPlay}>플레이 시작</button>
        </div>
      </div>
    </div>
  )
}

const pm = {
  backdrop: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.48)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 200,
  },
  modal: {
    background: '#fff',
    borderRadius: 20,
    padding: '32px 36px 28px',
    width: 540,
    boxShadow: '0 16px 56px rgba(0,0,0,0.2)',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
  },
  moonIcon: {
    fontSize: 44,
    lineHeight: 1,
  },
  title: {
    fontSize: 22,
    fontWeight: 800,
    color: '#111',
    lineHeight: 1.2,
  },
  subtitle: {
    fontSize: 13,
    fontWeight: 600,
    color: '#7040c0',
    marginTop: 3,
    letterSpacing: 0.5,
  },
  desc: {
    fontSize: 14,
    color: '#555',
    lineHeight: 1.7,
    margin: 0,
  },
  teamRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  teamCard: {
    flex: 1,
    borderRadius: 12,
    border: '1.5px solid',
    padding: '14px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  teamIcon: { fontSize: 22, lineHeight: 1 },
  teamName: { fontSize: 15, fontWeight: 700, marginTop: 2 },
  teamGoal: { fontSize: 12, color: '#666', lineHeight: 1.45, marginTop: 2 },
  teamVs: {
    fontSize: 13,
    fontWeight: 700,
    color: '#aaa',
    flexShrink: 0,
  },
  flowRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    padding: '14px 0',
    background: '#f9f9fb',
    borderRadius: 12,
  },
  flowItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  flowChip: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 4,
    padding: '8px 14px',
  },
  flowIcon: { fontSize: 20, lineHeight: 1 },
  flowLabel: { fontSize: 12, fontWeight: 600, color: '#333', whiteSpace: 'nowrap' },
  flowArrow: { fontSize: 18, color: '#bbb', fontWeight: 300, marginTop: -2 },
  note: {
    fontSize: 13,
    color: '#555',
    lineHeight: 1.65,
    background: 'rgba(130,80,220,0.06)',
    border: '1px solid rgba(130,80,220,0.18)',
    borderRadius: 10,
    padding: '12px 16px',
    display: 'flex',
    alignItems: 'flex-start',
    gap: 8,
  },
  noteDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#7040c0',
    flexShrink: 0,
    marginTop: 5,
  },
  footer: {
    display: 'flex',
    gap: 10,
    justifyContent: 'flex-end',
    marginTop: 4,
  },
  cancelBtn: {
    padding: '10px 22px',
    border: '1px solid #ddd',
    borderRadius: 10,
    background: '#fff',
    color: '#666',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
  },
  playBtn: {
    padding: '10px 28px',
    border: 'none',
    borderRadius: 10,
    background: '#7040c0',
    color: '#fff',
    fontSize: 14,
    fontWeight: 700,
    cursor: 'pointer',
  },
}

// ─────────────────────────────────────────────────────────────────────────────

function GameCard({ icon, name, info1, info2, onClick, disabled = false }) {
  return (
    <div
      style={s.card(disabled)}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={e => {
        if (disabled) return
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.12)'
        e.currentTarget.style.borderColor = '#bbb'
      }}
      onMouseLeave={e => {
        if (disabled) return
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)'
        e.currentTarget.style.borderColor = '#e0e0e0'
      }}
    >
      <div style={s.icon}>{icon}</div>
      <div style={s.gameName}>{name}</div>
      <div style={s.gameInfo}>{info1}</div>
      <div style={s.gameInfo}>{info2}</div>
    </div>
  )
}

export default function Lobby({
  players,
  send,
  onSelectYacht,
  onSelectYachtTutorial,
  onSelectWerewolf,
  onSelectWerewolfPractice,
  onExit,
}) {
  const yachtDisabled = players.length >= 7
  const [showPractice, setShowPractice] = useState(false)

  return (
    <div style={s.page}>
      <div style={s.title}>보드게임 AI 테이블</div>
      <div style={s.subtitle}>게임을 선택해 시작하세요</div>
      <div style={s.cards}>
        <div style={s.gameColumn}>
          <GameCard
            icon="🎲"
            name="요트 다이스"
            info1="1-6인 플레이어"
            info2="주사위 자동 인식"
            disabled={yachtDisabled}
            onClick={() => {
              send?.('select_game', { game_type: 'yacht' })
              onSelectYacht()
            }}
          />
          <button
            style={{
              ...s.tutorialInlineButton,
              ...(yachtDisabled ? { opacity: 0.45, cursor: 'not-allowed' } : {}),
            }}
            disabled={yachtDisabled}
            onClick={(event) => {
              event.stopPropagation()
              send?.('select_game', { game_type: 'yacht_tutorial' })
              onSelectYachtTutorial()
            }}
          >
            튜토리얼 모드
          </button>
        </div>
        <div style={s.gameColumn}>
          <GameCard
            icon="🌙"
            name="한밤의 늑대인간"
            info1="4-10인 플레이어"
            info2="카드·제스처 인식"
            onClick={() => {
              send('select_game', { game_type: 'werewolf' })
              onSelectWerewolf()
            }}
          />
          <button style={s.practiceBtn} onClick={() => setShowPractice(true)}>
            연습 모드로 해보기
          </button>
        </div>
      </div>
      <div style={s.bottomActions}>
        <button style={s.exitButton} onClick={onExit}>나가기</button>
      </div>

      {showPractice && (
        <PracticeModal
          onClose={() => setShowPractice(false)}
          onPlay={() => {
            setShowPractice(false)
            onSelectWerewolfPractice()
          }}
        />
      )}
    </div>
  )
}
