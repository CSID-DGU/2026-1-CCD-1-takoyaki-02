import { useState } from 'react'

const s = {
  page: {
    minHeight: '100vh',
    background: '#f5f5f7',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', sans-serif",
    color: '#111',
  },
  card: {
    background: '#fff',
    border: '1px solid #e0e0e0',
    borderRadius: 16,
    padding: 32,
    width: 720,
    boxShadow: '0 2px 12px rgba(0,0,0,0.07)',
  },
  title: { fontSize: 20, fontWeight: 600, marginBottom: 20 },
  connDot: (ok) => ({
    display: 'inline-block',
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: ok ? '#1a7a4a' : '#d44',
    marginRight: 6,
    verticalAlign: 'middle',
  }),
  hint: { color: '#666', fontSize: 13, marginBottom: 16 },

  listArea: { display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 },
  playerRow: (registering) => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 12px',
    background: registering ? '#fffbec' : '#f7f7f7',
    borderRadius: 8,
    border: registering ? '1px solid #f0c040' : '1px solid #ebebeb',
  }),
  nameText: { flex: 1, fontSize: 14, fontWeight: 500 },
  statusText: (registered) => ({
    fontSize: 12,
    color: registered ? '#1a7a4a' : '#888',
    marginRight: 4,
    minWidth: 44,
  }),
  smallBtn: {
    fontSize: 12,
    padding: '4px 10px',
    border: '1px solid #ccc',
    borderRadius: 6,
    background: '#fff',
    cursor: 'pointer',
  },
  deleteBtn: {
    fontSize: 12,
    padding: '5px 10px',
    border: '1px solid #d44',
    borderRadius: 6,
    background: '#fff',
    color: '#d44',
    cursor: 'pointer',
  },
  addBtn: {
    alignSelf: 'center',
    padding: '8px 24px',
    border: '1px dashed #b8b8b8',
    borderRadius: 10,
    background: '#fafafa',
    cursor: 'pointer',
    fontSize: 18,
    color: '#555',
    width: '100%',
  },
  footer: { display: 'flex', justifyContent: 'flex-end', marginTop: 12 },
  startBtn: (enabled) => ({
    padding: '10px 26px',
    border: '1px solid #ccc',
    borderRadius: 8,
    background: enabled ? '#111' : '#e8e8e8',
    color: enabled ? '#fff' : '#aaa',
    cursor: enabled ? 'pointer' : 'default',
    fontSize: 15,
    fontWeight: 500,
  }),

  // 모달
  backdrop: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.4)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 100,
  },
  modal: {
    background: '#fff',
    borderRadius: 16,
    padding: '24px 28px',
    width: 560,
    boxShadow: '0 6px 32px rgba(0,0,0,0.2)',
  },
  modalTitle: { fontSize: 18, fontWeight: 600, marginBottom: 14, textAlign: 'center' },
  handsRow: {
    display: 'flex',
    justifyContent: 'center',
    gap: 40,
    marginBottom: 12,
  },
  handIcon: (active) => ({
    width: 116, height: 116,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: active ? '#1973e8' : '#cfd2d6',
    boxShadow: active
      ? '0 6px 18px rgba(25, 115, 232, 0.35)'
      : '0 2px 8px rgba(0, 0, 0, 0.08)',
    transition: 'background 0.25s ease, box-shadow 0.25s ease',
  }),
  handLabel: (active) => ({
    fontSize: 14,
    color: active ? '#1973e8' : '#888',
    fontWeight: active ? 600 : 500,
    textAlign: 'center',
    marginTop: 8,
  }),
  guideText: {
    textAlign: 'center',
    fontSize: 19,
    fontWeight: 500,
    color: '#222',
    marginBottom: 16,
    lineHeight: 1.45,
    minHeight: 28,
    letterSpacing: '-0.2px',
  },
  modalFooter: {
    display: 'flex',
    gap: 12,
    justifyContent: 'center',
  },
  cancelBtn: {
    padding: '10px 22px',
    border: '1px solid #ccc',
    borderRadius: 8,
    background: '#fff',
    cursor: 'pointer',
    fontSize: 14,
  },
  primaryBtn: {
    padding: '10px 26px',
    border: 'none',
    borderRadius: 8,
    background: '#111',
    color: '#fff',
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: 500,
  },
  nameInput: {
    width: '100%',
    padding: '12px 14px',
    border: '1px solid #bbb',
    borderRadius: 10,
    fontSize: 16,
    outline: 'none',
    marginBottom: 18,
    boxSizing: 'border-box',
  },
}

/**
 * Microsoft Fluent Emoji High Contrast - victory-hand (V사인)
 * 라이선스: MIT (https://github.com/microsoft/fluentui-emoji)
 */
function VictoryHandIcon() {
  return (
    <svg viewBox="0 0 32 32" width="64" height="64" fill="#fff" aria-hidden>
      <path d="M15.047 30.906c4.518 0 7.144-1.828 8.552-3.363a9.6 9.6 0 0 0 2.328-4.554a4.9 4.9 0 0 0 .195-1.695q.012-.475-.023-.951c-.316-3.655-.446-5.169-.031-6.334l1.772-5.224a4.54 4.54 0 0 0-.083-3.339A3.26 3.26 0 0 0 25.8 3.755a3.55 3.55 0 0 0-4.618 2.132l-.665 1.97a106 106 0 0 0-.268-3.546A3.525 3.525 0 0 0 16.4 1.1a3.44 3.44 0 0 0-2.443 1.234a3.37 3.37 0 0 0-.83 2.316l.229 3.924q-.331-.06-.668-.06a3.4 3.4 0 0 0-1.093.118a3.4 3.4 0 0 0-.966.39q-.482.291-.838.738a3.4 3.4 0 0 0-1.135-.192a3.6 3.6 0 0 0-1.753.396a3.37 3.37 0 0 0-1.293 1.13a3.6 3.6 0 0 0-.641 2.27v2.252q0 .216.023.422a32.5 32.5 0 0 0 .363 6.143c.815 5.381 4.529 8.725 9.692 8.725M7.783 11.761c.237-.12.529-.19.873-.19q.296.002.522.098q.063.027.123.06c0 .339-.018.908-.037 1.552l-.006.185a76 76 0 0 0-.043 2.057c0 .48.081.955.21 1.39c-.19.091-.442.15-.769.15c-.546 0-.973-.166-1.248-.402a1.23 1.23 0 0 1-.417-.763a2 2 0 0 1-.021-.28V13.37l-.001-.01c.001-.551.14-.93.328-1.188a1.6 1.6 0 0 1 .486-.411m-.77 6.979c.51.217 1.073.323 1.643.323c.703 0 1.368-.162 1.925-.504a3.6 3.6 0 0 0 2.044.628c.796 0 1.52-.245 2.11-.673c.045.502.19 1.173.563 1.789q.125.207.284.4a10 10 0 0 0-.907.629c-.842.655-1.648 1.494-2.583 2.67a1 1 0 1 0 1.566 1.245c.878-1.104 1.572-1.813 2.245-2.337c.567-.44 1.145-.772 1.852-1.098q.18.016.37.016c.612 0 .974.267 1.32.718c.177.231.328.485.503.777l.035.06c.168.282.39.654.665.944c.597.632 1.303 1.023 2.06 1.101l.028.003a8 8 0 0 1-.611.761a9.28 9.28 0 0 1-7.078 2.714c-4.164 0-7.048-2.624-7.714-7.024a32 32 0 0 1-.32-3.143m9.3-3.484V12.69c0-1.11-.303-2.08-.876-2.818l-.316-5.382a1.5 1.5 0 0 1 .372-.871a1.47 1.47 0 0 1 1.064-.529a1.53 1.53 0 0 1 1.7 1.415c.19 1.914.393 5.656.483 7.31l.003.054l.009.139a1.23 1.23 0 0 0 .877 1.157A1.21 1.21 0 0 0 21 12.59q.061-.098.1-.208l1.968-5.828a1.546 1.546 0 0 1 2.1-.9a1.25 1.25 0 0 1 .791.656a2.63 2.63 0 0 1 0 1.809l-1.776 5.236c-.317.887-.407 1.801-.362 3.162a7 7 0 0 0-.565-.442c-1.435-1.002-3.243-1.421-5.173-1.34c-.707.03-1.295.225-1.77.52m-4.84 1.451a3.1 3.1 0 0 1-.258-1.184c0-.536.02-1.278.042-1.997l.006-.196c.02-.636.038-1.242.038-1.611c0-.29.043-.51.087-.659l.005-.019a1.4 1.4 0 0 1 .576-.44q.273-.083.656-.085c.476 0 .872.177 1.158.494c.29.321.53.86.53 1.68v2.55c0 1.26-.814 1.947-1.688 1.947a1.58 1.58 0 0 1-1.152-.48m12.649 4.636q-.024.576-.133 1.142c-.124.352-.313.613-.505.767c-.193.154-.385.206-.569.187c-.186-.02-.472-.125-.813-.485c-.098-.104-.212-.28-.404-.6l-.043-.072a10 10 0 0 0-.623-.953c-.58-.757-1.47-1.5-2.907-1.5c-.646 0-.937-.265-1.116-.562c-.22-.362-.29-.83-.29-1.11c0-.206.08-.577.305-.881c.194-.264.52-.516 1.143-.543c1.602-.067 2.949.287 3.943.981c.979.684 1.696 1.752 1.968 3.288q.03.175.044.34m-3.378-9.468v.078z" />
    </svg>
  )
}

/**
 * Microsoft Fluent Emoji High Contrast - ok-hand (엄지+검지 동그라미, 나머지 펴짐)
 * 라이선스: MIT (https://github.com/microsoft/fluentui-emoji)
 */
function OkHandIcon() {
  return (
    <svg viewBox="0 0 32 32" width="64" height="64" fill="#fff" aria-hidden>
      <path d="M16.552 1.189c2.1-.478 3.613 1.011 3.978 2.256l.003.012l.13.466c.578-.591 1.37-.923 2.321-.923a3.28 3.28 0 0 1 3.28 3.28c0 2.093-.011 4.23-.023 6.364v.001c-.011 2.136-.022 4.268-.022 6.355c0 6.848-5.02 11.81-10.62 11.844h-.003c-4.46.01-8.363-2.586-9.732-6.683l-.012-.039a3.53 3.53 0 0 1 .904-3.478a4 4 0 0 1-.361-.437c-.594-.837-.893-1.99-.503-3.101c.81-2.303 2.692-4.256 5.19-5.397L7.968 6.613c-.482-.809-.56-1.774-.363-2.617c.198-.84.702-1.677 1.534-2.159c1.632-.943 3.828-.532 4.78 1.092l.296.478a3.33 3.33 0 0 1 2.336-2.218m-7.41 18.516c.55 0 .86-.22 1.225-.674a10 10 0 0 0 .397-.541q.109-.158.245-.347c.238-.33.533-.71.915-1.04a4.9 4.9 0 0 1 3.325-1.165h.006c1.492.054 2.663.685 3.443 1.638c.764.934 1.114 2.125 1.1 3.275s-.393 2.33-1.18 3.239c-.804.929-1.99 1.52-3.477 1.52c-.98 0-1.974-.352-2.791-.886c-.815-.533-1.546-1.31-1.903-2.253c-.137-.365-.68-.739-1.338-.766l-.074-.002H9.03c-.803 0-1.533.874-1.263 1.844c1.077 3.191 4.15 5.305 7.821 5.297c4.38-.027 8.63-3.974 8.63-9.844c0-2.093.011-4.23.022-6.364v-.001c.012-2.136.023-4.268.023-6.355c0-.708-.572-1.28-1.28-1.28c-.543 0-.84.202-1.039.51l-.034.055a3.4 3.4 0 0 0-.145 1.022v.014l-.12 2.886c-.036.857-1.25.992-1.474.164l-.518-1.926l-.023-.073l-1.022-3.649c-.136-.454-.753-1.047-1.593-.869a1.32 1.32 0 0 0-.773.605q-.01.06-.018.129c-.047.42.015.888.089 1.183l.002.01l1 4.404c.188.831-.935 1.283-1.375.553l-1.019-1.694l-2.708-4.35l-.017-.028c-.314-.544-1.232-.854-2.056-.377c-.257.149-.488.46-.588.885c-.1.423-.04.84.132 1.132l3.338 5.465q.189.166.416.301a.8.8 0 0 1 .356.483c.046.16.049.329.027.478a1.1 1.1 0 0 1-.171.455a.77.77 0 0 1-.526.341a6 6 0 0 0-.243.039l-.012.004c-2.57.855-4.395 2.637-5.09 4.617c-.133.376-.055.857.246 1.281c.289.408.692.635 1.063.653zm2.438.97c.316.293.574.655.738 1.089c.17.452.57.922 1.126 1.286c.555.363 1.176.56 1.697.56c.917 0 1.548-.347 1.966-.83c.434-.502.682-1.207.691-1.953c.01-.747-.22-1.463-.647-1.984c-.41-.5-1.04-.872-1.965-.906a2.9 2.9 0 0 0-1.952.677l-.004.003c-.2.173-.385.399-.598.695q-.083.114-.18.253c-.159.229-.344.494-.527.721q-.158.199-.345.389" />
    </svg>
  )
}

function HandIcon({ side, active }) {
  // side: "left" | "right"
  // 왼쪽 슬롯 = 왼손 OK사인, 오른쪽 슬롯 = 오른손 V사인
  const Icon = side === 'right' ? VictoryHandIcon : OkHandIcon
  const label = side === 'right' ? '오른손 V사인' : '왼손 OK사인'
  return (
    <div>
      <div style={s.handIcon(active)}>
        <Icon />
      </div>
      <div style={s.handLabel(active)}>{label}</div>
    </div>
  )
}

function RegistrationModal({ seatStep, registeringId, defaultName, onCancel, onFinalize }) {
  const [name, setName] = useState('')

  // step별 안내
  const rightActive = seatStep === 'right_done' || seatStep === 'completed'
  const leftActive = seatStep === 'completed'

  let guide = ''
  if (seatStep === 'right_pending') {
    guide = '테이블 중앙으로 오른손을 뻗어 V 사인을 해주세요'
  } else if (seatStep === 'right_done') {
    guide = '오른손 인식 완료! 이번엔 왼손을 뻗어 OK 사인을 해주세요'
  } else if (seatStep === 'completed') {
    guide = '좌석 등록이 완료되었습니다. 이름을 입력해주세요'
  }

  const handleConfirm = () => {
    if (!registeringId) return
    // 빈 입력이면 디폴트 이름(플레이어N)으로 자동 등록
    const n = name.trim() || defaultName
    onFinalize(registeringId, n)
    setName('')
  }

  return (
    <div style={s.backdrop}>
      <div style={s.modal}>
        <div style={s.modalTitle}>플레이어 좌석 등록</div>
        <div style={s.handsRow}>
          <HandIcon side="left" active={leftActive} />
          <HandIcon side="right" active={rightActive} />
        </div>
        <div style={s.guideText}>{guide}</div>
        {seatStep === 'completed' ? (
          <>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
              style={s.nameInput}
              autoFocus
              placeholder={defaultName}
            />
            <div style={s.modalFooter}>
              <button style={s.cancelBtn} onClick={onCancel}>취소</button>
              <button style={s.primaryBtn} onClick={handleConfirm}>등록 완료</button>
            </div>
          </>
        ) : (
          <div style={s.modalFooter}>
            <button style={s.cancelBtn} onClick={onCancel}>취소</button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function SeatRegistration({
  players,
  registeringId,
  seatStep = 'idle',
  connected,
  send,
  onStart,
}) {
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')

  // 등록 모달 표시: registeringId가 있으면 자동으로 모달 노출
  const showModal = !!registeringId

  // 등록 시작: 임시 player_id 발급 + 즉시 카메라 인식 시작
  const startRegistration = () => {
    send('start_registration', {})
  }

  const cancelRegistration = () => {
    if (registeringId) {
      send('player_remove', { player_id: registeringId })
    }
  }

  const finalizePlayer = (player_id, name) => {
    send('finalize_player', { player_id, playername: name })
  }

  const startEdit = (p) => {
    setEditingId(p.player_id)
    setEditName(p.playername || '')
  }

  const confirmEdit = (player_id) => {
    const name = editName.trim()
    if (!name) return
    send('player_edit', { player_id, playername: name })
    setEditingId(null)
    setEditName('')
  }

  const deletePlayer = (player_id) => {
    send('player_remove', { player_id })
    if (editingId === player_id) {
      setEditingId(null)
      setEditName('')
    }
  }

  const restartRegistration = (player_id) => {
    send('start_seat_registration', { player_id })
  }

  // 등록 완료된 플레이어만 게임 시작 가능
  const named = players.filter((p) => p.playername)
  const canStart = named.length > 0 && named.every((p) => p.registered)

  // 디폴트 이름: 등록 중 임시 player_id를 제외한 named.length 기준 다음 번호
  const defaultName = `플레이어${named.length + 1}`

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.title}>
          <span style={s.connDot(connected)} />
          플레이어 등록
        </div>
        <div style={s.hint}>
          "+" 버튼을 누르면 카메라가 즉시 손을 인식합니다.
          본인의 자리에서 테이블 중앙으로 손을 뻗어 <b>오른손 V사인 → 왼손 OK사인</b> 순서로 보여주세요.
          <br />
          등록 중인 사람 외에는 손을 테이블 밖으로 치워주세요.
        </div>

        <div style={s.listArea}>
          {named.map((p) => (
            <div key={p.player_id} style={s.playerRow(false)}>
              {editingId === p.player_id ? (
                <>
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && confirmEdit(p.player_id)}
                    style={{ ...s.nameInput, marginBottom: 0 }}
                    autoFocus
                    placeholder="이름 입력"
                  />
                  <button style={s.primaryBtn} onClick={() => confirmEdit(p.player_id)}>
                    저장
                  </button>
                  <button style={s.deleteBtn} onClick={() => deletePlayer(p.player_id)}>
                    삭제
                  </button>
                </>
              ) : (
                <>
                  <span style={s.nameText}>{p.playername}</span>
                  <span style={s.statusText(p.registered)}>
                    {p.registered ? '등록됨' : '미등록'}
                  </span>
                  {!p.registered && (
                    <button style={s.smallBtn} onClick={() => restartRegistration(p.player_id)}>
                      재등록
                    </button>
                  )}
                  <button style={s.smallBtn} onClick={() => startEdit(p)}>
                    수정
                  </button>
                </>
              )}
            </div>
          ))}

          {!showModal && (
            <button style={s.addBtn} onClick={startRegistration}>
              + 플레이어 추가
            </button>
          )}
        </div>

        <div style={s.footer}>
          <button style={s.startBtn(canStart)} onClick={canStart ? onStart : undefined}>
            게임 시작 →
          </button>
        </div>
      </div>

      {showModal && (
        <RegistrationModal
          seatStep={seatStep}
          registeringId={registeringId}
          defaultName={defaultName}
          onCancel={cancelRegistration}
          onFinalize={finalizePlayer}
        />
      )}
    </div>
  )
}
