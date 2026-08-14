/**
 * Utility helpers for converting normalized Cartesian math grid coordinates (x, y)
 * into SVG ViewBox pixel coordinates.
 */

export function toSvgCoords(gridX, gridY, center = { x: 150, y: 150 }, scale = 35) {
  return {
    cx: center.x + gridX * scale,
    cy: center.y - gridY * scale // Cartesian inverted Y axis for SVG
  }
}

export function gridToPathString(points, center = { x: 150, y: 150 }, scale = 35) {
  if (!points || points.length === 0) return ''
  return points.map((pt, idx) => {
    const { cx, cy } = toSvgCoords(pt.x, pt.y, center, scale)
    return `${idx === 0 ? 'M' : 'L'} ${cx} ${cy}`
  }).join(' ')
}
