import { useState, useEffect, useRef, useCallback } from 'react'

const RECONNECT_DELAY_MS = 2000

const AUDIO_MSG_TYPES = new Set([
  'tts_play',
  'tts_interrupt',
  'sfx_play',
  'bgm_play',
  'bgm_duck',
])

/**
 * useWebSocket(path, options?)
 * options:
 *   onAudioMessage(msg) — audio 관련 메시지 수신 시 호출. 기본은 no-op.
 *                         보통 useAudioPlayer(send).enqueue를 넘김.
 */
export function useWebSocket(path, options = {}) {
  const { onAudioMessage } = options
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const [messages, setMessages] = useState([])
  const ws = useRef(null)
  const onAudioRef = useRef(onAudioMessage)
  useEffect(() => { onAudioRef.current = onAudioMessage }, [onAudioMessage])

  useEffect(() => {
    let destroyed = false
    let reconnectTimer = null

    function connect() {
      if (destroyed) return
      const url = `ws://${location.host}${path}`
      const socket = new WebSocket(url)
      ws.current = socket

      socket.onopen = () => {
        setConnected(true)
        // Benchmark hook (window._bench가 true일 때만 의미).
        if (window._bench) {
          try { window._bench.log('ws_event', 'open', path, performance.now()) } catch (_) {}
        }
      }

      socket.onclose = () => {
        setConnected(false)
        if (window._bench) {
          try { window._bench.log('ws_event', 'close', path, performance.now()) } catch (_) {}
        }
        if (!destroyed) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
        }
      }

      socket.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          setMessages(prev => [msg, ...prev].slice(0, 20))
          if (msg.msg_type === 'state_update') {
            setState(msg.state ?? msg.payload)
            // Benchmark hook: UI paint 완료 시각 (state_version별).
            if (window._bench) {
              const state_version = (msg.state ?? msg.payload)?.state_version ?? -1
              requestAnimationFrame(() => {
                try { window._bench.log('ui_painted', state_version, performance.now()) } catch (_) {}
              })
            }
          }
          if (AUDIO_MSG_TYPES.has(msg.msg_type) && onAudioRef.current) {
            try { onAudioRef.current(msg) } catch (_) {}
          }
        } catch (_) {}
      }
    }

    connect()

    return () => {
      destroyed = true
      clearTimeout(reconnectTimer)
      ws.current?.close()
    }
  }, [path])

  // send(input_type, data?, player_id?)
  const send = useCallback((input_type, data = {}, player_id = undefined) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const msg = { msg_type: 'input', input_type, data }
      if (player_id !== undefined) msg.player_id = player_id
      ws.current.send(JSON.stringify(msg))
    }
  }, [])

  return { state, connected, messages, send }
}
