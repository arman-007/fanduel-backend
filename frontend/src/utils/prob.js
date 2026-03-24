/**
 * Background colour for a probability cell (0-100 scale).
 * Matches the original probBg() function exactly.
 */
export function probBg(v) {
  if (v >= 80) return 'rgba(0,212,170,0.55)'
  if (v >= 60) return 'rgba(0,212,170,0.32)'
  if (v >= 40) return 'rgba(0,212,170,0.15)'
  if (v >= 20) return 'rgba(0,212,170,0.06)'
  return 'transparent'
}

/**
 * Text colour for a probability cell.
 */
export function probTextColor(v) {
  if (v >= 60) return '#fff'
  if (v >= 30) return 'var(--text)'
  return 'var(--dim)'
}

/**
 * Heatmap cell background for the CS matrix (t = ratio 0..1 vs max probability).
 */
export function csHeatColor(t) {
  const r = Math.round(7  + t * (0   - 7))
  const g = Math.round(18 + t * (180 - 18))
  const b = Math.round(38 + t * (120 - 38))
  return `rgb(${r},${g},${b})`
}
