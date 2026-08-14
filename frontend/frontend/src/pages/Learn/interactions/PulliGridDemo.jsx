import { useState } from 'react'

// Convert grid coordinates to SVG pixel space
function toSVG(gx, gy, cx = 150, cy = 150, step = 40) {
  return { x: cx + gx * step, y: cy - gy * step }
}

export default function PulliGridDemo() {
  const [gridType, setGridType] = useState('square')
  const [showLoopHint, setShowLoopHint] = useState(false)

  // Square 3x3 grid: integer coords from -1 to +1
  const squareDots = []
  for (let gy = 1; gy >= -1; gy--) {
    for (let gx = -1; gx <= 1; gx++) {
      squareDots.push({ id: `${gx},${gy}`, gx, gy })
    }
  }

  // Interlocking 1-3-5-3-1 triangular grid (diamond)
  const triangularDots = [
    { id: '0,2', gx: 0, gy: 2 },
    { id: '-1,1', gx: -1, gy: 1 }, { id: '0,1', gx: 0, gy: 1 }, { id: '1,1', gx: 1, gy: 1 },
    { id: '-2,0', gx: -2, gy: 0 }, { id: '-1,0', gx: -1, gy: 0 }, { id: '0,0', gx: 0, gy: 0 },
    { id: '1,0', gx: 1, gy: 0 }, { id: '2,0', gx: 2, gy: 0 },
    { id: '-1,-1', gx: -1, gy: -1 }, { id: '0,-1', gx: 0, gy: -1 }, { id: '1,-1', gx: 1, gy: -1 },
    { id: '0,-2', gx: 0, gy: -2 },
  ]

  const squareStep = 48
  const triangularStep = 28

  const currentDots = gridType === 'square' ? squareDots : triangularDots
  const step = gridType === 'square' ? squareStep : triangularStep

  // Square grid: rounded square outer loop winding around all 9 dots
  const makeSquareLoop = (cx, cy, s) => {
    const h = s * 0.55
    return [
      `M ${cx} ${cy - s - s * 0.3}`,
      `C ${cx + h} ${cy - s - s * 0.3}, ${cx + s + s * 0.3} ${cy - h}, ${cx + s + s * 0.3} ${cy}`,
      `C ${cx + s + s * 0.3} ${cy + h}, ${cx + h} ${cy + s + s * 0.3}, ${cx} ${cy + s + s * 0.3}`,
      `C ${cx - h} ${cy + s + s * 0.3}, ${cx - s - s * 0.3} ${cy + h}, ${cx - s - s * 0.3} ${cy}`,
      `C ${cx - s - s * 0.3} ${cy - h}, ${cx - h} ${cy - s - s * 0.3}, ${cx} ${cy - s - s * 0.3}`
    ].join(' ')
  }

  // Triangular grid: diamond-shaped outer loop winding around all 13 dots
  // The outermost dots sit at (0,2), (2,0), (0,-2), (-2,0) in grid coords
  // The loop traces a smooth diamond shape curving around each tip
  const makeTriangularLoop = (cx, cy, s) => {
    // outermost tips in SVG coords
    const top   = { x: cx,       y: cy - s * 2 }  // (0, 2)
    const right  = { x: cx + s * 2, y: cy }        // (2, 0)
    const bottom = { x: cx,       y: cy + s * 2 }  // (0,-2)
    const left   = { x: cx - s * 2, y: cy }        // (-2,0)
    const m = s * 0.55 // margin beyond each tip for the loop to wrap around

    return [
      // Start at top tip
      `M ${top.x} ${top.y - m}`,
      // Top to right: arc around top vertex then right vertex
      `C ${top.x + m} ${top.y - m}, ${right.x + m} ${right.y - m}, ${right.x + m} ${right.y}`,
      // Right to bottom
      `C ${right.x + m} ${right.y + m}, ${bottom.x + m} ${bottom.y + m}, ${bottom.x} ${bottom.y + m}`,
      // Bottom to left
      `C ${bottom.x - m} ${bottom.y + m}, ${left.x - m} ${left.y + m}, ${left.x - m} ${left.y}`,
      // Left to top
      `C ${left.x - m} ${left.y - m}, ${top.x - m} ${top.y - m}, ${top.x} ${top.y - m}`
    ].join(' ')
  }

  // Triangular inner cross arcs: from top to bottom along vertical axis
  const makeTriangularInnerV = (cx, cy, s) => {
    const h = s * 0.4
    return [
      `M ${cx} ${cy - s}`,
      `C ${cx + h} ${cy - s}, ${cx + h} ${cy + s}, ${cx} ${cy + s}`,
      `C ${cx - h} ${cy + s}, ${cx - h} ${cy - s}, ${cx} ${cy - s}`
    ].join(' ')
  }

  // Triangular inner cross arcs: from left to right along horizontal axis
  const makeTriangularInnerH = (cx, cy, s) => {
    const h = s * 0.4
    return [
      `M ${cx - s} ${cy}`,
      `C ${cx - s} ${cy - h}, ${cx + s} ${cy - h}, ${cx + s} ${cy}`,
      `C ${cx + s} ${cy + h}, ${cx - s} ${cy + h}, ${cx - s} ${cy}`
    ].join(' ')
  }

  const squareLoopPath = makeSquareLoop(150, 150, squareStep)
  const squareInnerPath = [
    `M ${150} ${150 - squareStep * 0.4}`,
    `C ${150 + squareStep * 0.4} ${150 - squareStep * 0.4},`,
    `${150 + squareStep * 0.4} ${150 + squareStep * 0.4},`,
    `${150} ${150 + squareStep * 0.4}`,
    `C ${150 - squareStep * 0.4} ${150 + squareStep * 0.4},`,
    `${150 - squareStep * 0.4} ${150 - squareStep * 0.4},`,
    `${150} ${150 - squareStep * 0.4}`
  ].join(' ')

  const triOuterPath = makeTriangularLoop(150, 150, triangularStep)
  const triInnerV = makeTriangularInnerV(150, 150, triangularStep)
  const triInnerH = makeTriangularInnerH(150, 150, triangularStep)

  return (
    <div className="demo-container archival-frame">
      <div className="demo-toolbar">
        <div className="demo-controls">
          <span className="label-tech">GRID TYPE:</span>
          <button
            className={`btn btn--sm ${gridType === 'square' ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => { setGridType('square'); setShowLoopHint(false) }}
          >
            Square 3x3 Grid
          </button>
          <button
            className={`btn btn--sm ${gridType === 'triangular' ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => { setGridType('triangular'); setShowLoopHint(false) }}
          >
            Interlocking (1-3-5-3-1)
          </button>
        </div>
        <button
          className={`btn btn--sm ${showLoopHint ? 'btn--primary' : 'btn--outline'}`}
          onClick={() => setShowLoopHint(v => !v)}
        >
          {showLoopHint ? 'Hide Loop Preview' : 'Show Loop Preview'}
        </button>
      </div>

      <div className="demo-canvas-wrap">
        <svg viewBox="0 0 300 300" className="demo-svg">
          {/* Grid reference lines for square grid */}
          {gridType === 'square' && (
            <>
              <line x1="150" y1="20" x2="150" y2="280" stroke="var(--color-card-border)" strokeWidth="0.7" strokeDasharray="3 4" />
              <line x1="20" y1="150" x2="280" y2="150" stroke="var(--color-card-border)" strokeWidth="0.7" strokeDasharray="3 4" />
              <line x1="60" y1="60" x2="240" y2="240" stroke="var(--color-card-border)" strokeWidth="0.5" strokeDasharray="2 5" opacity="0.5" />
              <line x1="240" y1="60" x2="60" y2="240" stroke="var(--color-card-border)" strokeWidth="0.5" strokeDasharray="2 5" opacity="0.5" />
            </>
          )}

          {/* Diamond axis lines for triangular grid */}
          {gridType === 'triangular' && (
            <>
              <line x1="150" y1="30" x2="150" y2="270" stroke="var(--color-card-border)" strokeWidth="0.7" strokeDasharray="3 4" />
              <line x1="30" y1="150" x2="270" y2="150" stroke="var(--color-card-border)" strokeWidth="0.7" strokeDasharray="3 4" />
            </>
          )}

          {/* Square loop preview */}
          {gridType === 'square' && showLoopHint && (
            <g opacity="0.85">
              <path
                d={squareLoopPath}
                fill="none"
                stroke="var(--color-maroon-main)"
                strokeWidth="2.2"
                strokeLinecap="round"
                style={{ strokeDasharray: 1200, strokeDashoffset: 1200, animation: 'drawPath 2.8s ease forwards' }}
              />
              <path
                d={squareInnerPath}
                fill="none"
                stroke="var(--color-gold)"
                strokeWidth="1.6"
                strokeLinecap="round"
                style={{ strokeDasharray: 600, strokeDashoffset: 600, animation: 'drawPath 2s ease 1.5s forwards' }}
              />
            </g>
          )}

          {/* Triangular diamond loop preview */}
          {gridType === 'triangular' && showLoopHint && (
            <g opacity="0.85">
              <path
                d={triOuterPath}
                fill="none"
                stroke="var(--color-maroon-main)"
                strokeWidth="2.2"
                strokeLinecap="round"
                style={{ strokeDasharray: 1400, strokeDashoffset: 1400, animation: 'drawPath 3s ease forwards' }}
              />
              <path
                d={triInnerV}
                fill="none"
                stroke="var(--color-gold)"
                strokeWidth="1.6"
                strokeLinecap="round"
                style={{ strokeDasharray: 500, strokeDashoffset: 500, animation: 'drawPath 1.5s ease 1.5s forwards' }}
              />
              <path
                d={triInnerH}
                fill="none"
                stroke="var(--color-gold)"
                strokeWidth="1.6"
                strokeLinecap="round"
                style={{ strokeDasharray: 500, strokeDashoffset: 500, animation: 'drawPath 1.5s ease 2.2s forwards' }}
              />
            </g>
          )}

          {/* Render dots */}
          {currentDots.map(dot => {
            const { x, y } = toSVG(dot.gx, dot.gy, 150, 150, step)
            return (
              <g key={dot.id}>
                <circle cx={x} cy={y} r="3.5" fill="var(--color-text-dark)" />
                {showLoopHint && (
                  <circle cx={x} cy={y} r="9" fill="none" stroke="var(--color-maroon-main)" strokeWidth="0.7" strokeDasharray="2 2" opacity="0.35" />
                )}
              </g>
            )
          })}

          {/* Coordinate labels */}
          {gridType === 'square' && (
            <>
              <text x="155" y="145" fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace">(0,0)</text>
              <text x="195" y="103" fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace">(1,1)</text>
            </>
          )}
          {gridType === 'triangular' && (
            <>
              <text x="154" y="145" fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace">(0,0)</text>
              <text x="154" y={150 - triangularStep * 2 - 8} fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace">(0,2)</text>
            </>
          )}
        </svg>
      </div>

      <p className="body-text body-text--sm demo-caption">
        <strong>Rule 1:</strong> {gridType === 'square'
          ? 'The square grid arranges Pullis in equal rows and columns. Each dot sits at an integer coordinate like (0,0) or (1,1). Toggle "Show Loop Preview" to see how a Kolam stroke winds around the dots.'
          : 'The interlocking (1-3-5-3-1) grid arranges dots in a diamond pattern with decreasing rows. This creates a rhombus lattice used for traditional Sikku Kolams. Toggle "Show Loop Preview" to see how the winding loop follows the diamond outline.'
        }
      </p>
    </div>
  )
}
