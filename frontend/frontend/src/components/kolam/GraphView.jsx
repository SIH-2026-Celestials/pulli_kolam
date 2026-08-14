/**
 * Shared graph-structure SVG view. Renders the REAL dot_points/edges
 * array returned by GET /api/v1/generations/{id}/graph (or the `graph`
 * field already embedded in a POST /api/v1/generations candidate) --
 * no synthetic graph data is ever generated here.
 *
 * Two modes:
 *  - `interactive=false` (default, used by GeneratedVariations' compact
 *    per-card detail panel): a small static render, no controls.
 *  - `interactive=true` (used by Playground's Graph Inspector): adds
 *    hover-to-highlight-edges, a node-label toggle, and zoom/reset --
 *    all pure client-side view state over the same real data, nothing
 *    fabricated.
 */
import { useMemo, useState } from 'react'
import { ZoomIn, ZoomOut, RotateCcw, Tag } from 'lucide-react'
import './GraphView.css'

export default function GraphView({ graph, interactive = false, height = 420 }) {
  const [hoverNode, setHoverNode] = useState(null)
  const [showLabels, setShowLabels] = useState(false)
  const [zoom, setZoom] = useState(1)

  const layout = useMemo(() => {
    if (!graph || !graph.dot_points || graph.dot_points.length === 0) return null
    const scale = 14
    const margin = 18
    const xs = graph.dot_points.map((p) => p[0])
    const ys = graph.dot_points.map((p) => p[1])
    const minX = Math.min(...xs)
    const minY = Math.min(...ys)
    const width = (Math.max(...xs) - minX) * scale + margin * 2
    const height = (Math.max(...ys) - minY) * scale + margin * 2
    const toPx = ([x, y]) => [margin + (x - minX) * scale, margin + (y - minY) * scale]
    return { width, height, toPx }
  }, [graph])

  if (!layout) {
    return <p className="graph-empty">Graph data not available for this pattern.</p>
  }

  const { width, height: h, toPx } = layout
  const edges = graph.edges || []
  const nodeKey = (p) => `${p[0]},${p[1]}`

  const connectedTo = (nodeIdx) => {
    if (nodeIdx == null) return null
    const p = graph.dot_points[nodeIdx]
    const key = nodeKey(p)
    const set = new Set()
    edges.forEach(([a, b], i) => {
      if (nodeKey(a) === key || nodeKey(b) === key) set.add(i)
    })
    return set
  }
  const highlighted = interactive ? connectedTo(hoverNode) : null

  return (
    <div className="graph-view-wrap">
      {interactive && (
        <div className="graph-view-toolbar" role="toolbar" aria-label="Graph view controls">
          <button type="button" className="graph-tool-btn" onClick={() => setZoom((z) => Math.min(z + 0.25, 3))} title="Zoom in" aria-label="Zoom in">
            <ZoomIn size={13} />
          </button>
          <button type="button" className="graph-tool-btn" onClick={() => setZoom((z) => Math.max(z - 0.25, 0.5))} title="Zoom out" aria-label="Zoom out">
            <ZoomOut size={13} />
          </button>
          <button type="button" className="graph-tool-btn" onClick={() => setZoom(1)} title="Reset zoom" aria-label="Reset zoom">
            <RotateCcw size={13} />
          </button>
          <button
            type="button"
            className={`graph-tool-btn${showLabels ? ' active' : ''}`}
            onClick={() => setShowLabels((s) => !s)}
            title="Toggle node labels"
            aria-label="Toggle node labels"
            aria-pressed={showLabels}
          >
            <Tag size={13} />
          </button>
        </div>
      )}
      <div className="graph-view-svg-wrap" style={{ maxHeight: height }}>
        <svg
          width={Math.min(width * zoom, 640)}
          height={Math.min(h * zoom, height)}
          viewBox={`0 0 ${width} ${h}`}
        >
          <rect x="0" y="0" width={width} height={h} fill="#FFFFFF" />
          {edges.map(([a, b], i) => {
            const [ax, ay] = toPx(a)
            const [bx, by] = toPx(b)
            const isHi = highlighted && highlighted.has(i)
            return (
              <line
                key={i}
                x1={ax}
                y1={ay}
                x2={bx}
                y2={by}
                stroke={isHi ? '#8A3324' : '#CFC5B8'}
                strokeWidth={isHi ? 2.5 : 1.5}
              />
            )
          })}
          {graph.dot_points.map((p, i) => {
            const [px, py] = toPx(p)
            const isHi = hoverNode === i
            return (
              <g key={i}>
                <circle
                  cx={px}
                  cy={py}
                  r={isHi ? 4.5 : 2.5}
                  fill={isHi ? '#5A0615' : '#8A3324'}
                  onMouseEnter={interactive ? () => setHoverNode(i) : undefined}
                  onMouseLeave={interactive ? () => setHoverNode(null) : undefined}
                  style={interactive ? { cursor: 'pointer' } : undefined}
                />
                {showLabels && (
                  <text x={px + 5} y={py - 5} fontSize="6" fill="#4B4843">{`${p[0]},${p[1]}`}</text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
      {interactive && (
        <p className="graph-view-hint">
          {hoverNode != null
            ? `Node (${graph.dot_points[hoverNode][0]}, ${graph.dot_points[hoverNode][1]}) — ${highlighted?.size ?? 0} incident edge${highlighted?.size === 1 ? '' : 's'}`
            : 'Hover a node to highlight its edges.'}
        </p>
      )}
    </div>
  )
}
