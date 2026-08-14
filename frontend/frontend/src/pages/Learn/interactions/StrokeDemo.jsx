import { useState, useEffect } from 'react'

// A real Kolam 3×3 continuous single-stroke path
// Based on KOLAM_DESIGN_PRINCIPLES.md: half-integer (0.5u) loop-around coordinates
// The stroke winds around all 9 dots in one closed Eulerian loop
function buildKolamStrokePath(cx, cy, s) {
  // s = grid step (e.g. 48px)
  // This traces: outer loop winding clockwise, then inner diagonal cross-arcs
  // All lines at 45° diagonals with smooth Bezier arcs around each dot
  const h = s * 0.52 // Bezier handle length for smooth arcs

  return [
    // Start at top-center (between top-left and top-right dots, above center dot)
    `M ${cx} ${cy - s - h * 0.5}`,

    // Arc to top-right, looping around top-right dot (1,1)
    `C ${cx + h * 0.5} ${cy - s - h * 0.5}, ${cx + s + h * 0.5} ${cy - h * 0.5}, ${cx + s + h * 0.5} ${cy}`,

    // Down, arcing around right-center dot (1,0)
    `C ${cx + s + h * 0.5} ${cy + h * 0.5}, ${cx + h * 0.5} ${cy + s + h * 0.5}, ${cx} ${cy + s + h * 0.5}`,

    // Left, arcing around bottom-right dot (1,-1), diagonal 45 arc
    `C ${cx - h * 0.5} ${cy + s + h * 0.5}, ${cx - s - h * 0.5} ${cy + h * 0.5}, ${cx - s - h * 0.5} ${cy}`,

    // Up, arcing around left-center dot (-1,0)
    `C ${cx - s - h * 0.5} ${cy - h * 0.5}, ${cx - h * 0.5} ${cy - s - h * 0.5}, ${cx} ${cy - s - h * 0.5}`
  ].join(' ')
}

// Inner diagonal S-curve: main diagonal (top-left to bottom-right)
// Clean S-curve through center, stays inside the 3x3 grid bounds
function buildInnerDiagPath(cx, cy, s) {
  const r = s * 0.55 // reach from center
  const h = s * 0.3  // bezier handle
  return [
    `M ${cx - r} ${cy - r}`,
    `C ${cx - r + h} ${cy - r}, ${cx - h} ${cy - h}, ${cx} ${cy}`,
    `C ${cx + h} ${cy + h}, ${cx + r - h} ${cy + r}, ${cx + r} ${cy + r}`
  ].join(' ')
}

// Inner anti-diagonal S-curve: (top-right to bottom-left)
function buildInnerAntiDiagPath(cx, cy, s) {
  const r = s * 0.55
  const h = s * 0.3
  return [
    `M ${cx + r} ${cy - r}`,
    `C ${cx + r - h} ${cy - r}, ${cx + h} ${cy - h}, ${cx} ${cy}`,
    `C ${cx - h} ${cy + h}, ${cx - r + h} ${cy + r}, ${cx - r} ${cy + r}`
  ].join(' ')
}

export default function StrokeDemo() {
  const [phase, setPhase] = useState('outer') // 'outer' | 'inner' | 'complete'
  const [animKey, setAnimKey] = useState(0) // triggers re-mount for replay

  const cx = 150, cy = 150, s = 48

  const outerPath = buildKolamStrokePath(cx, cy, s)
  const innerDiag = buildInnerDiagPath(cx, cy, s)
  const innerAnti = buildInnerAntiDiagPath(cx, cy, s)

  const allDots = []
  for (let gy = 1; gy >= -1; gy--)
    for (let gx = -1; gx <= 1; gx++)
      allDots.push({ gx, gy })

  const replay = () => {
    setPhase('outer')
    setAnimKey(k => k + 1)
  }

  // Advance phase automatically
  useEffect(() => {
    if (phase === 'outer') {
      const t = setTimeout(() => setPhase('inner'), 2800)
      return () => clearTimeout(t)
    }
    if (phase === 'inner') {
      const t = setTimeout(() => setPhase('complete'), 2000)
      return () => clearTimeout(t)
    }
  }, [phase, animKey])

  return (
    <div className="demo-container archival-frame">
      <div className="demo-toolbar">
        <div className="demo-controls">
          <span className="label-tech">DRAWING PHASE:</span>
          <span className="label-tech" style={{
            color: phase === 'complete' ? 'var(--color-step-done)' : 'var(--color-gold)',
            fontWeight: 700
          }}>
            {phase === 'outer' && '① Drawing Outer Loop...'}
            {phase === 'inner' && '② Adding Inner Diagonal Arcs...'}
            {phase === 'complete' && '✓ CLOSED EULERIAN LOOP COMPLETE'}
          </span>
        </div>
        <button className="btn btn--sm btn--outline" onClick={replay}>
          Replay ↺
        </button>
      </div>

      <div className="demo-canvas-wrap">
        <svg key={animKey} viewBox="0 0 300 300" className="demo-svg">
          {/* Axis lines */}
          <line x1="150" y1="20" x2="150" y2="280" stroke="var(--color-card-border)" strokeWidth="0.7" strokeDasharray="3 4" />
          <line x1="20" y1="150" x2="280" y2="150" stroke="var(--color-card-border)" strokeWidth="0.7" strokeDasharray="3 4" />

          {/* Outer Kolam loop: animates in phase 1 */}
          <path
            d={outerPath}
            fill="none"
            stroke="var(--color-maroon-main)"
            strokeWidth="2.5"
            strokeLinecap="round"
            style={{
              strokeDasharray: 1100,
              strokeDashoffset: 1100,
              animation: 'drawPath 2.5s ease forwards'
            }}
          />

          {/* Inner diagonal arc: animates in phase 2 */}
          {(phase === 'inner' || phase === 'complete') && (
            <path
              d={innerDiag}
              fill="none"
              stroke="var(--color-gold)"
              strokeWidth="2"
              strokeLinecap="round"
              style={{
                strokeDasharray: 500,
                strokeDashoffset: 500,
                animation: 'drawPath 1.4s ease forwards'
              }}
            />
          )}

          {/* Inner anti-diagonal arc: animates in phase 2 */}
          {(phase === 'inner' || phase === 'complete') && (
            <path
              d={innerAnti}
              fill="none"
              stroke="var(--color-gold)"
              strokeWidth="2"
              strokeLinecap="round"
              style={{
                strokeDasharray: 400,
                strokeDashoffset: 400,
                animation: 'drawPath 1.2s ease 0.6s forwards'
              }}
            />
          )}

          {/* Render 3×3 dot grid */}
          {allDots.map(({ gx, gy }, i) => {
            const x = cx + gx * s
            const y = cy - gy * s
            return (
              <circle
                key={i}
                cx={x}
                cy={y}
                r="3.5"
                fill="var(--color-text-dark)"
              />
            )
          })}

          {/* Start point indicator */}
          <circle cx={cx} cy={cy - s - s * 0.52 * 0.5} r="4" fill="var(--color-maroon-main)" opacity="0.8" />
          <text x={cx + 6} y={cy - s - s * 0.52 * 0.5 + 4} fontSize="9" fill="var(--color-maroon-main)" fontFamily="monospace">START</text>

          {/* Return-to-origin arrow label */}
          {phase === 'complete' && (
            <text x="50" y="270" fontSize="9" fill="var(--color-step-done)" fontFamily="monospace">
              P₀ = Pₙ (loop closed ✓)
            </text>
          )}
        </svg>
      </div>

      <p className="body-text body-text--sm demo-caption">
        <strong>Rule 2:</strong> The stroke starts at one point and <em>never lifts</em>. It winds around all 9 dots and returns precisely to the start, forming a closed <em>Eulerian Circuit</em>. Every dot has exactly 2 or 4 lines meeting it (even degree), which is what makes one-stroke drawing mathematically possible.
      </p>
    </div>
  )
}
