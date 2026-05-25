export function physicalSeatOrder(players, idKey = 'id') {
  return [...players].sort((a, b) => {
    const byPosition = (a.position ?? 0) - (b.position ?? 0)
    if (byPosition !== 0) return byPosition
    return String(a[idKey] ?? '').localeCompare(String(b[idKey] ?? ''))
  })
}

export function orderForTurn(players, firstPlayerId, direction, idKey = 'id') {
  if (players.length === 0) return []
  const byPos = physicalSeatOrder(players, idKey)
  const startIdx = Math.max(0, byPos.findIndex((p) => p[idKey] === firstPlayerId))
  if (direction === 'ccw') {
    return [
      byPos[startIdx],
      ...byPos.slice(0, startIdx).reverse(),
      ...byPos.slice(startIdx + 1).reverse(),
    ]
  }
  return [...byPos.slice(startIdx), ...byPos.slice(0, startIdx)]
}
