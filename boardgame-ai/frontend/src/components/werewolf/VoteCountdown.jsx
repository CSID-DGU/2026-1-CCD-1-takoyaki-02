import { useEffect } from 'react'

export default function VoteCountdown({ players = [], votes = {}, onComplete }) {
  // votes: { player_id: target_player_id } — 지목 완료된 플레이어 매핑

  const doneCount = Object.keys(votes).length
  const total = players.length
  const allDone = total > 0 && doneCount >= total

  useEffect(() => {
    if (allDone) onComplete?.()
  }, [allDone])

  return (
    <>
      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes flicker {
          0%, 100% { opacity: 1; }
          45%      { opacity: 0.85; }
          50%      { opacity: 0.55; }
          55%      { opacity: 0.9; }
        }
        @keyframes checkPop {
          0%   { transform: scale(0.5); opacity: 0; }
          70%  { transform: scale(1.2); }
          100% { transform: scale(1);   opacity: 1; }
        }
      `}</style>

      <div style={styles.page}>

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

        {/* 타이틀 */}
        <div style={{ ...styles.title, animation: 'flicker 4s ease-in-out infinite' }}>
          투표
        </div>

        {/* 안내 텍스트 */}
        <div style={styles.guideBox}>
          <div style={styles.guideLine}>지목할 플레이어를 손가락으로 가리키세요.</div>
          <div style={styles.guideLineSub}>자기 자신 지목은 기권입니다.</div>
        </div>

        {/* 진행 현황 */}
        <div style={styles.progressLabel}>
          {doneCount} / {total} 완료
        </div>

        {/* 플레이어 카드 그리드 */}
        <div style={styles.grid}>
          {players.map((p, i) => {
            const done = votes[p.player_id] !== undefined
            return (
              <div
                key={p.player_id}
                style={{ ...styles.card, ...(done ? styles.cardDone : styles.cardPending) }}
                // 딜레이로 순서대로 등장
              >
                {/* 번호 */}
                <div style={{ ...styles.cardNum, color: done ? '#ff9980' : 'rgba(245,200,190,0.4)' }}>
                  {String(i + 1).padStart(2, '0')}
                </div>

                {/* 이름 */}
                <div style={{ ...styles.cardName, color: done ? '#fff' : 'rgba(245,200,190,0.6)' }}>
                  {p.playername}
                </div>

                {/* 상태 뱃지 */}
                {done ? (
                  <div style={styles.badgeDone}>
                    <span style={{ animation: 'checkPop 0.3s ease-out both' }}>✓</span> 완료
                  </div>
                ) : (
                  <div style={styles.badgePending}>대기 중</div>
                )}
              </div>
            )
          })}
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
    gap: 20,
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

  title: {
    position: 'relative',
    zIndex: 1,
    fontSize: 52,
    fontWeight: 800,
    letterSpacing: 8,
    color: '#f5c6c6',
    textShadow: '0 0 30px rgba(200,60,30,0.7), 0 2px 8px rgba(0,0,0,0.6)',
  },

  guideBox: {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 8,
    background: 'rgba(0,0,0,0.35)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(200,80,50,0.25)',
    borderRadius: 16,
    padding: '18px 40px',
    animation: 'fadeUp 0.7s ease-out both',
  },

  guideLine: {
    fontSize: 20,
    fontWeight: 600,
    color: '#f5d8d0',
    textAlign: 'center',
  },

  guideLineSub: {
    fontSize: 15,
    color: 'rgba(245,200,190,0.6)',
    textAlign: 'center',
  },

  progressLabel: {
    position: 'relative',
    zIndex: 1,
    fontSize: 16,
    fontWeight: 700,
    letterSpacing: 2,
    color: 'rgba(245,200,190,0.5)',
    textTransform: 'uppercase',
  },

  grid: {
    position: 'relative',
    zIndex: 1,
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 12,
    width: '100%',
    maxWidth: 680,
    padding: '0 24px',
    animation: 'fadeUp 0.7s ease-out 0.15s both',
  },

  card: {
    borderRadius: 14,
    padding: '18px 12px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 8,
    transition: 'background 0.3s, border-color 0.3s',
  },

  cardPending: {
    background: 'rgba(0,0,0,0.3)',
    border: '1px solid rgba(200,80,50,0.18)',
  },

  cardDone: {
    background: 'rgba(180,40,20,0.25)',
    border: '1px solid rgba(255,120,80,0.45)',
    boxShadow: '0 0 14px rgba(200,60,30,0.2)',
  },

  cardNum: {
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: 1,
  },

  cardName: {
    fontSize: 18,
    fontWeight: 700,
    textAlign: 'center',
  },

  badgeDone: {
    fontSize: 13,
    fontWeight: 700,
    color: '#ff9980',
    background: 'rgba(200,60,30,0.3)',
    borderRadius: 20,
    padding: '4px 14px',
  },

  badgePending: {
    fontSize: 13,
    color: 'rgba(245,200,190,0.4)',
    background: 'rgba(0,0,0,0.2)',
    borderRadius: 20,
    padding: '4px 14px',
  },
}
