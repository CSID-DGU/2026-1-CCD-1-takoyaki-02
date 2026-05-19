/**
 * useBenchBridge — frontend bench hook들이 호출하는 window._bench를 정의하고
 * 모은 라인을 backend에 input으로 자동 전송.
 *
 * App에 한 번만 마운트. send 함수(useWebSocket의 send)를 받음.
 *
 * 활성화:
 * - URL 쿼리 파라미터 `?bench=1` 또는 localStorage `bench=1`일 때만 window._bench 정의.
 * - 활성 아니면 window._bench가 undefined → 모든 hook의 `if (window._bench)` 가드가 false.
 *   → 네트워크 전송·큐 적재 모두 0. 측정 모드 아닐 때 부담 완전 제거.
 *
 * 배칭:
 * - 호출 즉시 큐에 적재
 * - 250ms 또는 큐 길이 32 도달 시 flush → backend에 단일 메시지로 전송
 */

import { useEffect, useRef } from 'react'

const FLUSH_INTERVAL_MS = 250
const FLUSH_THRESHOLD = 32

function isBenchEnabled() {
  try {
    const params = new URLSearchParams(window.location.search)
    if (params.get('bench') === '1') return true
    if (typeof localStorage !== 'undefined' && localStorage.getItem('bench') === '1') return true
  } catch (_) {}
  return false
}

export function useBenchBridge(send) {
  const queueRef = useRef([])
  const timerRef = useRef(null)

  useEffect(() => {
    if (!isBenchEnabled()) {
      // 측정 모드 아님 — window._bench를 정의하지 않아 hook들이 모두 no-op.
      return
    }

    const flush = () => {
      if (queueRef.current.length === 0) return
      const batch = queueRef.current.splice(0, queueRef.current.length)
      try {
        send('bench_trace', { lines: batch })
      } catch (_) {}
    }

    const log = (...args) => {
      const line = args.map(a => {
        if (typeof a === 'number') return Number.isInteger(a) ? a.toString() : a.toFixed(3)
        return String(a)
      }).join(' ')
      queueRef.current.push(line)
      if (queueRef.current.length >= FLUSH_THRESHOLD) {
        flush()
      } else if (!timerRef.current) {
        timerRef.current = setTimeout(() => {
          timerRef.current = null
          flush()
        }, FLUSH_INTERVAL_MS)
      }
    }

    window._bench = { log }
    console.info('[bench] frontend tracing enabled (?bench=1)')

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
      flush()
      delete window._bench
    }
  }, [send])
}
