import { useEffect, useMemo, useState } from 'react'

const AUTO_ADVANCE_SEC = 10

export default function VoteResult({ players = [], votes = {}, onComplete, editable = false, send, onConfirm }) {
  const [countdown, setCountdown] = useState(AUTO_ADVANCE_SEC)
  const [selectedVoter, setSelectedVoter] = useState(null)

  // 비편집 모드: 자동 진행 타이머
  useEffect(() => {
    if (editable) return
    let remaining = AUTO_ADVANCE_SEC
    const interval = setInterval(() => {
      remaining -= 1
      setCountdown(remaining)
      if (remaining <= 0) {
        clearInterval(interval)
        onComplete?.()
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [editable]) // eslint-disable-line react-hooks/exhaustive-deps

  // votes: { voter_player_id: target_player_id }
  const { tally, condemned } = useMemo(() => {
    const count = {}
    players.forEach(p => { count[p.player_id] = 0 })
    Object.values(votes).forEach(targetId => {
      if (count[targetId] !== undefined) count[targetId]++
    })

    const maxVotes = Math.max(...Object.values(count), 0)
    const cond = players.filter(p => count[p.player_id] === maxVotes && maxVotes > 0)

    const t = [...players]
      .sort((a, b) => count[b.player_id] - count[a.player_id])
      .map(p => ({ ...p, voteCount: count[p.player_id] }))

    return { tally: t, condemned: cond }
  }, [players, votes])

  const maxVotes = tally[0]?.voteCount ?? 0
  const condemnedNames = condemned.map(p => p.playername).join(', ')

  // editable 모드: 2-탭 투표 보정
  const handleCorrectionClick = (playerId) => {
    if (!editable || !send) return
    if (!selectedVoter) {
      setSelectedVoter(playerId)
    } else if (selectedVoter === playerId) {
      setSelectedVoter(null)
    } else {
      send('werewolf_vote_player', { target_id: playerId }, selectedVoter)
      setSelectedVoter(null)
    }
  }

  const handleConfirm = () => {
    if (!send) return
    send('werewolf_vote_result_confirm', {})
    onConfirm?.()
  }

  return (
    <>
      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes cardReveal {
          0%   { opacity: 0; transform: scale(0.88) translateY(10px); }
          100% { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes barGrow {
          from { width: 0; }
        }
        @keyframes flicker {
          0%, 100% { opacity: 1; }
          45%      { opacity: 0.85; }
          50%      { opacity: 0.55; }
          55%      { opacity: 0.9; }
        }
      `}</style>

      <div onClick={editable ? undefined : onComplete} style={{ ...styles.page, cursor: editable ? 'default' : 'pointer' }}>

        {/* 배경 */}
        <div style={styles.sky} />
        <div style={styles.overlay} />

        {/* 마을 실루엣 */}
        <svg viewBox="0 0 800 160" preserveAspectRatio="xMidYMax slice" style={styles.silhouette}>
          <polygon points="40,160 62,95 84,160"    fill="#110500" />
          <polygon points="58,160 84,72 110,160"   fill="#110500" />
          <polygon points="95,160 118,100 141,160" fill="#110500" />
          <rect x="155" y="118" width="58" height="42" fill="#110500" />
          <polygon points="150,120 184,92 218,120"  fill="#110500" />
          <rect x="162" y="130" width="13" height="30" fill="#0a0300" />
          <rect x="245" y="86" width="32" height="74" fill="#110500" />
          <polygon points="240,88 261,62 282,88"   fill="#110500" />
          <rect x="300" y="112" width="52" height="48" fill="#110500" />
          <polygon points="295,114 326,86 357,114" fill="#110500" />
          <polygon points="372,160 394,90 416,160" fill="#110500" />
          <polygon points="390,160 416,70 442,160" fill="#110500" />
          <rect x="455" y="120" width="46" height="40" fill="#110500" />
          <polygon points="450,122 478,98 506,122" fill="#110500" />
          <rect x="524" y="96" width="72" height="64" fill="#110500" />
          <polygon points="519,98 560,68 601,98"   fill="#110500" />
          <rect x="552" y="74" width="16" height="26" fill="#110500" />
          <polygon points="618,160 638,102 658,160" fill="#110500" />
          <polygon points="646,160 670,84 694,160" fill="#110500" />
          <rect x="710" y="118" width="54" height="42" fill="#110500" />
          <polygon points="705,120 737,94 769,120" fill="#110500" />
        </svg>

        {/* 컨텐츠 */}
        <div style={{ ...styles.content, marginBottom: editable ? 16 : 80 }}>

          {/* 타이틀 */}
          <div style={{ ...styles.title, animation: 'flicker 4s ease-in-out infinite' }}>
            {editable ? '투표 결과 맞나요?' : '투표 결과'}
          </div>

          {/* 심판 플레이어 카드 */}
          <div style={{ animation: 'cardReveal 0.6s cubic-bezier(0.22,0.61,0.36,1) 0.1s both' }}>
            <div style={styles.condemnedCard}>
              <div style={styles.avatar}>
                <svg viewBox="0 0 48 48" width="42" height="42" fill="none">
                  <circle cx="24" cy="18" r="9" fill="rgba(245,180,160,0.5)" />
                  <path d="M8 42c0-8.837 7.163-16 16-16s16 7.163 16 16" stroke="rgba(245,180,160,0.5)" strokeWidth="2.5" strokeLinecap="round" />
                </svg>
              </div>
              <div style={styles.condemnedLabel}>
                <span style={styles.condemnedName}>{condemnedNames || '—'}</span>
                <span style={styles.condemnedSuffix}> 님 심판</span>
              </div>
            </div>
          </div>

          {/* 득표 목록 */}
          <div style={styles.tallyList}>
            {tally.map((p, i) => (
              <div
                key={p.player_id}
                style={{
                  ...styles.tallyRow,
                  animation: `fadeUp 0.5s ease-out ${0.25 + i * 0.08}s both`,
                  ...(p.voteCount === maxVotes && maxVotes > 0 ? styles.tallyRowHighlight : {}),
                }}
              >
                <span style={styles.tallyName}>{p.playername}</span>
                <div style={styles.barTrack}>
                  <div
                    style={{
                      ...styles.barFill,
                      width: maxVotes > 0 ? `${(p.voteCount / maxVotes) * 100}%` : '0%',
                      background: p.voteCount === maxVotes && maxVotes > 0
                        ? 'linear-gradient(90deg, #c84010, #ff6030)'
                        : 'rgba(245,200,190,0.25)',
                      animation: 'barGrow 0.6s ease-out both',
                    }}
                  />
                </div>
                <span style={{
                  ...styles.tallyCount,
                  color: p.voteCount === maxVotes && maxVotes > 0 ? '#ff9980' : 'rgba(245,200,190,0.5)',
                }}>
                  {p.voteCount}
                </span>
              </div>
            ))}
          </div>

          {/* editable 모드: 투표 보정 패널 */}
          {editable && (
            <div style={styles.correctionPanel}>
              <div style={styles.correctionHeader}>
                {selectedVoter
                  ? <span>보정할 대상을 선택하세요 — 투표자: <span style={{ color: '#ff9980', fontWeight: 700 }}>{players.find(p => p.player_id === selectedVoter)?.playername}</span></span>
                  : '오인식 수정: 투표자 이름을 누르세요'
                }
              </div>
              <div style={styles.correctionGrid}>
                {players.map(p => {
                  const targetId = votes[p.player_id]
                  const targetName = targetId ? players.find(pp => pp.player_id === targetId)?.playername : '기권'
                  const isSelected = selectedVoter === p.player_id
                  return (
                    <div
                      key={p.player_id}
                      onClick={() => handleCorrectionClick(p.player_id)}
                      style={{
                        ...styles.correctionRow,
                        ...(isSelected ? styles.correctionRowSelected : {}),
                        cursor: 'pointer',
                      }}
                    >
                      <span style={styles.correctionVoter}>{p.playername}</span>
                      <span style={styles.correctionArrow}>→</span>
                      <span style={styles.correctionTarget}>{targetName}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* 하단 힌트 / 확인 버튼 */}
          {editable ? (
            <button onClick={handleConfirm} style={confirmBtn}>
              투표 확정
            </button>
          ) : (
            <div style={styles.tapHint}>
              화면을 터치하면 계속합니다{countdown > 0 && <span style={{ marginLeft: 6, opacity: 0.6 }}>({countdown})</span>}
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
    color: '#F8F1DD',
    userSelect: 'none',
  },

  sky: {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(180deg, #0a0000 0%, #1a0200 20%, #3d0a05 42%, #7a1a08 62%, #b03010 78%, #c84010 100%)',
  },

  overlay: {
    position: 'absolute',
    inset: 0,
    background: 'radial-gradient(ellipse at 50% 40%, rgba(180,30,10,0.15), transparent 65%)',
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
    gap: 16,
    width: '100%',
    maxWidth: 480,
    padding: '0 24px',
    overflowY: 'auto',
    maxHeight: '90vh',
  },

  title: {
    fontSize: 32,
    fontWeight: 800,
    letterSpacing: 3,
    color: '#f5c6c6',
    textShadow: '0 0 30px rgba(200,60,30,0.7), 0 2px 8px rgba(0,0,0,0.6)',
    animation: 'fadeUp 0.6s ease-out both',
    textAlign: 'center',
  },

  condemnedCard: {
    background: 'rgba(180,40,20,0.22)',
    border: '1px solid rgba(255,120,80,0.4)',
    borderRadius: 16,
    padding: '14px 32px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 8,
    backdropFilter: 'blur(8px)',
    boxShadow: '0 0 32px rgba(200,60,30,0.2)',
  },

  avatar: {
    width: 56,
    height: 56,
    borderRadius: '50%',
    background: 'rgba(180,60,40,0.3)',
    border: '1.5px solid rgba(255,120,80,0.3)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  condemnedLabel: {
    fontSize: 17,
    textAlign: 'center',
  },

  condemnedName: {
    fontWeight: 800,
    color: '#ff9980',
  },

  condemnedSuffix: {
    fontWeight: 400,
    color: 'rgba(245,200,190,0.8)',
  },

  tallyList: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },

  tallyRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    background: 'rgba(0,0,0,0.28)',
    border: '1px solid rgba(200,80,50,0.12)',
    borderRadius: 10,
    padding: '10px 14px',
  },

  tallyRowHighlight: {
    background: 'rgba(180,40,20,0.22)',
    border: '1px solid rgba(255,120,80,0.35)',
  },

  tallyName: {
    fontSize: 14,
    fontWeight: 600,
    color: '#f5d8d0',
    width: 56,
    flexShrink: 0,
  },

  barTrack: {
    flex: 1,
    height: 6,
    borderRadius: 4,
    background: 'rgba(255,255,255,0.07)',
    overflow: 'hidden',
  },

  barFill: {
    height: '100%',
    borderRadius: 4,
    transition: 'width 0.6s ease-out',
  },

  tallyCount: {
    fontSize: 17,
    fontWeight: 700,
    width: 22,
    textAlign: 'right',
    flexShrink: 0,
  },

  correctionPanel: {
    width: '100%',
    background: 'rgba(0,0,0,0.3)',
    border: '1px solid rgba(200,80,50,0.2)',
    borderRadius: 14,
    padding: '14px 16px',
    animation: 'fadeUp 0.5s ease-out 0.3s both',
  },

  correctionHeader: {
    fontSize: 13,
    color: 'rgba(245,200,190,0.6)',
    marginBottom: 10,
    textAlign: 'center',
  },

  correctionGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },

  correctionRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 12px',
    borderRadius: 8,
    background: 'rgba(0,0,0,0.2)',
    border: '1px solid rgba(200,80,50,0.1)',
    transition: 'background 0.2s, border-color 0.2s',
  },

  correctionRowSelected: {
    background: 'rgba(255,140,60,0.18)',
    border: '1px solid rgba(255,180,80,0.6)',
  },

  correctionVoter: {
    fontSize: 14,
    fontWeight: 700,
    color: '#f5d8d0',
    width: 60,
    flexShrink: 0,
  },

  correctionArrow: {
    fontSize: 14,
    color: 'rgba(245,200,190,0.4)',
  },

  correctionTarget: {
    fontSize: 13,
    color: '#ff9980',
    flex: 1,
  },

  tapHint: {
    fontSize: 11,
    color: 'rgba(245,200,190,0.3)',
    letterSpacing: 0.5,
    marginTop: 4,
  },
}

const confirmBtn = {
  marginTop: 8,
  padding: '14px 48px',
  background: 'linear-gradient(135deg, #c84010, #ff6030)',
  border: 'none',
  borderRadius: 12,
  color: '#fff',
  fontSize: 18,
  fontWeight: 800,
  letterSpacing: 2,
  cursor: 'pointer',
  boxShadow: '0 0 24px rgba(200,60,30,0.5)',
  fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
}
