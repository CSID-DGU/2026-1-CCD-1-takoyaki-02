import { useState, useEffect, useRef, useCallback } from 'react'

export function useWebSocket(path) {
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const ws = useRef(null)

  useEffect(() => {
    const url = `ws://${location.host}${path}`
    ws.current = new WebSocket(url)

    ws.current.onopen = () => setConnected(true)
    ws.current.onclose = () => setConnected(false)
    ws.current.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.msg_type === 'state_update') setState(msg.state)
      } catch (_) {}
    }

    return () => ws.current?.close()
  }, [path])

  const send = useCallback((input_type, data = {}) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ msg_type: 'input', input_type, data }))
    }
  }, [])

  return { state, connected, send }
}
