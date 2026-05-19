import { useState, useEffect, useRef, useCallback } from 'react'

const RECONNECT_DELAY_MS = 2000

function playTtsMessage(msg) {
  const text = msg?.payload?.text
  if (!text || typeof window === 'undefined' || !window.speechSynthesis) return

  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'ko-KR'
  utterance.rate = 1
  utterance.pitch = 1
  window.speechSynthesis.speak(utterance)
}

export function useWebSocket(path) {
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const [messages, setMessages] = useState([])
  const ws = useRef(null)

  useEffect(() => {
    let destroyed = false
    let reconnectTimer = null

    function connect() {
      if (destroyed) return
      const url = `ws://${location.host}${path}`
      const socket = new WebSocket(url)
      ws.current = socket

      socket.onopen = () => setConnected(true)

      socket.onclose = () => {
        setConnected(false)
        if (!destroyed) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
        }
      }

      socket.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          setMessages(prev => [msg, ...prev].slice(0, 20))
          if (msg.msg_type === 'state_update') setState(msg.state ?? msg.payload)
          if (msg.msg_type === 'tts_play') playTtsMessage(msg)
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
