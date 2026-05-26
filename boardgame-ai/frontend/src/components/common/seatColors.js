export const SEAT_COLORS = [
  'oklch(0.72 0.13 35)',   // cognac
  'oklch(0.70 0.12 145)',  // sage
  'oklch(0.70 0.11 250)',  // periwinkle
  'oklch(0.72 0.13 320)',  // rose
  'oklch(0.74 0.12 75)',   // amber
  'oklch(0.68 0.10 195)',  // teal
  'oklch(0.72 0.13 5)',    // coral
  'oklch(0.70 0.10 280)',  // lavender
  'oklch(0.74 0.10 110)',  // moss
  'oklch(0.72 0.12 45)',   // peach
]

export function colorForIndex(i) {
  return SEAT_COLORS[i % SEAT_COLORS.length]
}

/**
 * player_id로 안정적인 색상 결정.
 * id는 `p_<hex8>` 형태이므로 끝 hex 자리들의 합으로 인덱스 계산.
 * id가 비어있으면 fallback으로 0번 색.
 */
export function colorForPlayerId(playerId) {
  if (!playerId) return SEAT_COLORS[0]
  let sum = 0
  for (let i = 0; i < playerId.length; i++) {
    sum = (sum + playerId.charCodeAt(i)) >>> 0
  }
  return SEAT_COLORS[sum % SEAT_COLORS.length]
}
