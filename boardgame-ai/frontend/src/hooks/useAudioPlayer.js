/**
 * useAudioPlayer — 태블릿 브라우저 오디오 재생 싱글톤.
 *
 * M1 범위:
 * - HTML5 Audio API로 wav/mp3 재생.
 * - 단순 FIFO 큐 (우선순위는 M2에서 추가).
 * - iPad Safari autoplay 차단 우회: 첫 사용자 인터랙션 시 무음 unlock.
 * - 재생 완료 시 backend로 audio_ack 전송 (제공된 send 함수 사용).
 *
 * 사용:
 *   const audio = useAudioPlayer()   // App에 한 번만 마운트
 *   audio.enqueue(msg)               // 페이지/훅에서 호출
 *   audio.interrupt(playback_id)
 *
 * 메시지 형식: backend가 보내는 tts_play / sfx_play / bgm_play / bgm_duck WSMessage.
 */

import { useEffect, useRef } from 'react'

// 모듈 레벨 싱글톤. React 컴포넌트가 리렌더돼도 같은 인스턴스.
const player = {
  queue: [],          // 대기 중인 audio 메시지
  current: null,      // {playback_id, audio, type} 재생 중
  audio: null,        // 재생용 Audio 인스턴스 (한 개 재사용)
  unlocked: false,    // 사용자 인터랙션 이후 true
  ackSenders: new Set(), // audio_ack를 보낼 send 함수 (여러 ws 대응)
  bgmAudio: null,
  bgmGainDb: 0,
  duckGainDb: 0,
}

function dbToGain(db) {
  return Math.pow(10, db / 20)
}

function ensureAudioElement() {
  if (!player.audio) {
    player.audio = new Audio()
    player.audio.preload = 'auto'
  }
  return player.audio
}

function ensureBgmElement() {
  if (!player.bgmAudio) {
    player.bgmAudio = new Audio()
    player.bgmAudio.loop = true
  }
  return player.bgmAudio
}

function applyBgmGain() {
  if (player.bgmAudio) {
    player.bgmAudio.volume = Math.max(0, Math.min(1, dbToGain(player.bgmGainDb + player.duckGainDb)))
  }
}

function sendAck(playback_id, status, t0) {
  const now = Date.now() / 1000
  const data = { playback_id, status, started_at: t0, ended_at: now }
  for (const send of player.ackSenders) {
    try {
      send('audio_ack', data)
    } catch (e) {
      // 무시 — ws가 닫혔을 수 있음
    }
  }
}

async function playNext() {
  if (player.current || player.queue.length === 0) return
  const msg = player.queue.shift()
  const payload = msg.payload || {}
  const audio_url = payload.audio_url
  const playback_id = payload.playback_id || `pb_${Math.random().toString(36).slice(2, 10)}`
  if (!audio_url) {
    // 합성 실패한 text-only TTS. 그냥 ack만 보내고 다음으로.
    sendAck(playback_id, 'error', Date.now() / 1000)
    setTimeout(playNext, 0)
    return
  }

  const el = ensureAudioElement()
  el.src = audio_url
  const t0 = Date.now() / 1000
  player.current = { playback_id, type: msg.msg_type, t0 }

  // TTS 중에는 BGM 더킹
  if (msg.msg_type === 'tts_play') {
    player.duckGainDb = -12
    applyBgmGain()
  }

  const cleanup = (status) => {
    player.current = null
    if (msg.msg_type === 'tts_play') {
      player.duckGainDb = 0
      applyBgmGain()
    }
    sendAck(playback_id, status, t0)
    setTimeout(playNext, 50)
  }

  el.onended = () => cleanup('played')
  el.onerror = () => cleanup('error')

  try {
    await el.play()
  } catch (err) {
    // autoplay 차단 등. 큐 앞쪽에 다시 넣고 unlock 대기.
    console.warn('audio.play() blocked:', err)
    player.queue.unshift(msg)
    player.current = null
    if (msg.msg_type === 'tts_play') {
      player.duckGainDb = 0
      applyBgmGain()
    }
  }
}

function enqueue(msg) {
  if (!msg || typeof msg !== 'object') return
  const t = msg.msg_type
  if (t === 'bgm_play') {
    handleBgmPlay(msg.payload || {})
    return
  }
  if (t === 'bgm_duck') {
    handleBgmDuck(msg.payload || {})
    return
  }
  if (t === 'tts_interrupt') {
    const pbid = (msg.payload || {}).playback_id
    interrupt(pbid)
    return
  }
  if (t !== 'tts_play' && t !== 'sfx_play') return
  player.queue.push(msg)
  if (player.unlocked) {
    playNext()
  }
}

function handleBgmPlay({ audio_url, loop = true, gain_db = -6, fade_ms = 500 }) {
  if (!audio_url) return
  const el = ensureBgmElement()
  el.src = audio_url
  el.loop = !!loop
  player.bgmGainDb = gain_db
  applyBgmGain()
  if (player.unlocked) {
    el.play().catch(() => {})
  }
}

function handleBgmDuck({ on, attenuation_db = -12 }) {
  player.duckGainDb = on ? attenuation_db : 0
  applyBgmGain()
}

function interrupt(playback_id) {
  // 현재 재생 중이 일치하거나 playback_id 없으면 즉시 중단
  if (!player.current) return
  if (playback_id && player.current.playback_id !== playback_id) {
    // 큐에서 제거
    player.queue = player.queue.filter(
      (m) => (m.payload || {}).playback_id !== playback_id,
    )
    return
  }
  if (player.audio) {
    player.audio.pause()
    // onended는 안 부르므로 수동 cleanup 트리거
    const status = 'interrupted'
    const t0 = player.current.t0
    const pbid = player.current.playback_id
    const type = player.current.type
    player.current = null
    if (type === 'tts_play') {
      player.duckGainDb = 0
      applyBgmGain()
    }
    sendAck(pbid, status, t0)
    setTimeout(playNext, 0)
  }
}

function unlock() {
  if (player.unlocked) return
  player.unlocked = true
  // 무음 wav를 한 번 재생해 Safari/iPad의 autoplay 정책을 해제
  const el = ensureAudioElement()
  const prev = el.src
  // 1-sample 무음 wav data URI
  el.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA='
  el.play().then(() => {
    el.pause()
    el.src = prev || ''
  }).catch(() => {})
  // 큐에 남은 거 진행
  setTimeout(playNext, 50)
}

/**
 * App에 한 번만 마운트되는 훅. send 함수(useWebSocket의 send)를 전달해
 * audio_ack가 backend로 가도록 함.
 */
export function useAudioPlayer(send) {
  const registered = useRef(false)
  useEffect(() => {
    if (send && !registered.current) {
      player.ackSenders.add(send)
      registered.current = true
    }
    // 첫 사용자 인터랙션으로 unlock
    const onFirstInteraction = () => {
      unlock()
      window.removeEventListener('pointerdown', onFirstInteraction)
      window.removeEventListener('keydown', onFirstInteraction)
    }
    if (!player.unlocked) {
      window.addEventListener('pointerdown', onFirstInteraction)
      window.addEventListener('keydown', onFirstInteraction)
    }
    return () => {
      if (send) {
        player.ackSenders.delete(send)
        registered.current = false
      }
      window.removeEventListener('pointerdown', onFirstInteraction)
      window.removeEventListener('keydown', onFirstInteraction)
    }
  }, [send])

  return { enqueue, interrupt, unlock }
}

// 페이지/훅에서 useAudioPlayer 마운트 없이도 enqueue만 호출하고 싶을 때.
export const audio = { enqueue, interrupt, unlock }
