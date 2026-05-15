/**
 * useAudioPlayer — 태블릿 브라우저 오디오 재생 싱글톤.
 *
 * 모델: backend AudioManager가 ack-driven 푸시. 따라서 frontend는
 * 한 번에 한 메시지만 받고 즉시 재생. 큐는 운영하지 않음 (backend가 큐).
 *
 * 동작:
 * - tts_play / sfx_play: audio_url 즉시 재생. ended 시 audio_ack 전송.
 * - tts_interrupt: 현재 재생을 150ms fade-out 후 정지, audio_ack(status=interrupted).
 * - bgm_play / bgm_duck: 별도 BGM Audio 인스턴스, TTS와 독립적 재생.
 * - iPad Safari autoplay 차단 우회: 첫 user interaction에 무음 unlock.
 */

import { useEffect, useRef } from 'react'

const FADE_OUT_MS = 150 // 인터럽트 시 음량 감쇠 시간. 너무 길면 다음 발화 지연됨.

const player = {
  current: null,       // {playback_id, type, t0, fadeTimer}
  audio: null,         // 단일 재사용 Audio 인스턴스 (TTS/SFX 공용)
  unlocked: false,
  ackSenders: new Set(),
  bgmAudio: null,
  bgmGainDb: 0,
  duckGainDb: 0,
  // backend가 다음을 푸시하기 전 우리에게 새 메시지가 빨리 오는 race 케이스용 슬롯
  pendingNext: null,
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
    } catch (_) {}
  }
}

async function playMessage(msg) {
  const payload = msg.payload || {}
  const audio_url = payload.audio_url
  const playback_id = payload.playback_id || `pb_${Math.random().toString(36).slice(2, 10)}`

  if (!audio_url) {
    // 합성 실패한 text-only — ack만 보내 backend 큐 진행.
    sendAck(playback_id, 'error', Date.now() / 1000)
    return
  }

  const el = ensureAudioElement()
  el.volume = 1.0
  el.src = audio_url
  const t0 = Date.now() / 1000
  player.current = { playback_id, type: msg.msg_type, t0, fadeTimer: null }

  if (msg.msg_type === 'tts_play') {
    // TTS 중 BGM 더킹
    player.duckGainDb = -12
    applyBgmGain()
  }

  const onEnded = (status) => {
    // 멱등성: 이미 인터럽트로 정리됐으면 무시
    if (!player.current || player.current.playback_id !== playback_id) return
    if (player.current.fadeTimer) {
      clearInterval(player.current.fadeTimer)
    }
    if (player.current.type === 'tts_play') {
      player.duckGainDb = 0
      applyBgmGain()
    }
    player.current = null
    sendAck(playback_id, status, t0)
    // pending 메시지가 있으면 즉시 처리
    if (player.pendingNext) {
      const next = player.pendingNext
      player.pendingNext = null
      playMessage(next)
    }
  }

  el.onended = () => onEnded('played')
  el.onerror = () => onEnded('error')

  try {
    await el.play()
  } catch (err) {
    // autoplay 차단 등. 일단 ack로 backend 진행시킴 (block 해제는 unlock에서).
    onEnded('error')
  }
}

/**
 * 현재 재생을 150ms fade-out 후 정지. ack(status=interrupted) 발행.
 * 멱등: 이미 정리됐거나 다른 playback_id면 no-op.
 */
function fadeOutInterrupt(playback_id) {
  if (!player.current) return
  if (playback_id && player.current.playback_id !== playback_id) return

  const cur = player.current
  const el = player.audio
  if (!el) {
    // 안전망
    player.current = null
    sendAck(cur.playback_id, 'interrupted', cur.t0)
    return
  }

  // 이미 fade 중이면 그대로 둠
  if (cur.fadeTimer) return

  const startVolume = el.volume
  const startTime = performance.now()
  cur.fadeTimer = setInterval(() => {
    if (!player.current || player.current.playback_id !== cur.playback_id) {
      clearInterval(cur.fadeTimer)
      return
    }
    const elapsed = performance.now() - startTime
    const ratio = Math.min(1, elapsed / FADE_OUT_MS)
    el.volume = Math.max(0, startVolume * (1 - ratio))
    if (ratio >= 1) {
      clearInterval(cur.fadeTimer)
      try { el.pause() } catch (_) {}
      try { el.currentTime = 0 } catch (_) {}
      el.volume = 1.0
      if (cur.type === 'tts_play') {
        player.duckGainDb = 0
        applyBgmGain()
      }
      player.current = null
      sendAck(cur.playback_id, 'interrupted', cur.t0)
      if (player.pendingNext) {
        const next = player.pendingNext
        player.pendingNext = null
        playMessage(next)
      }
    }
  }, 16) // ~60fps ramp
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
    fadeOutInterrupt(pbid)
    return
  }
  if (t !== 'tts_play' && t !== 'sfx_play') return
  if (!player.unlocked) {
    player.pendingNext = msg
    return
  }
  if (player.current) {
    // backend가 ack-driven이라 보통 안 오지만, CRITICAL 인터럽트 직후엔
    // 진행 중인 fade-out과 새 메시지가 겹침. 슬롯에 저장하고 fade 끝나면 처리.
    player.pendingNext = msg
    return
  }
  playMessage(msg)
}

function handleBgmPlay({ audio_url, loop = true, gain_db = -6 }) {
  // 빈 audio_url은 정지 신호.
  if (!audio_url) {
    if (player.bgmAudio) {
      try { player.bgmAudio.pause() } catch (_) {}
      try { player.bgmAudio.currentTime = 0 } catch (_) {}
      player.bgmAudio.src = ''
    }
    return
  }
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

function unlock() {
  if (player.unlocked) return
  player.unlocked = true
  const el = ensureAudioElement()
  const prev = el.src
  el.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA='
  el.play().then(() => {
    el.pause()
    el.src = prev || ''
  }).catch(() => {})
  // unlock 직전에 도착한 메시지 처리
  if (player.pendingNext && !player.current) {
    const next = player.pendingNext
    player.pendingNext = null
    playMessage(next)
  }
}

/**
 * App에 한 번만 마운트. send 함수(useWebSocket의 send)를 받아 audio_ack를 backend로.
 */
export function useAudioPlayer(send) {
  const registered = useRef(false)
  useEffect(() => {
    if (send && !registered.current) {
      player.ackSenders.add(send)
      registered.current = true
    }
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

  return { enqueue, interrupt: fadeOutInterrupt, unlock }
}

export const audio = { enqueue, interrupt: fadeOutInterrupt, unlock }
