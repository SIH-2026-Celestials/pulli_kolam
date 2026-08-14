import { useState } from 'react'

// A real Kolam loop path around a 3×3 grid: all 9 dots enclosed
function buildValidKolamPath(cx, cy, s) {
  const h = s * 0.52
  return [
    `M ${cx} ${cy - s - h * 0.5}`,
    `C ${cx + h * 0.5} ${cy - s - h * 0.5}, ${cx + s + h * 0.5} ${cy - h * 0.5}, ${cx + s + h * 0.5} ${cy}`,
    `C ${cx + s + h * 0.5} ${cy + h * 0.5}, ${cx + h * 0.5} ${cy + s + h * 0.5}, ${cx} ${cy + s + h * 0.5}`,
    `C ${cx - h * 0.5} ${cy + s + h * 0.5}, ${cx - s - h * 0.5} ${cy + h * 0.5}, ${cx - s - h * 0.5} ${cy}`,
    `C ${cx - s - h * 0.5} ${cy - h * 0.5}, ${cx - h * 0.5} ${cy - s - h * 0.5}, ${cx} ${cy - s - h * 0.5}`
  ].join(' ')
}

// Inner cross loop that encloses center + edge dots
function buildInnerLoopPath(cx, cy, s) {
  const r = s * 0.42
  return [
    `M ${cx} ${cy - r}`,
    `C ${cx + r} ${cy - r}, ${cx + r} ${cy + r}, ${cx} ${cy + r}`,
    `C ${cx - r} ${cy + r}, ${cx - r} ${cy - r}, ${cx} ${cy - r}`
  ].join(' ')
}

// Invalid loop: only covers 7 dots, leaving top-center and bottom-center stranded
function buildInvalidPath(cx, cy, s) {
  const h = s * 0.52
  return [
    `M ${cx - s} ${cy - s - h * 0.5}`,
    `C ${cx - s + h * 0.5} ${cy - s - h * 0.5}, ${cx + s + h * 0.5} ${cy - h * 0.5}, ${cx + s + h * 0.5} ${cy}`,
    `C ${cx + s + h * 0.5} ${cy + h * 0.5}, ${cx - s + h * 0.5} ${cy + s + h * 0.5}, ${cx - s} ${cy + s + h * 0.5}`,
    `C ${cx - s - h * 0.3} ${cy + s + h * 0.5}, ${cx - s - h * 0.5} ${cy + h * 0.5}, ${cx - s - h * 0.5} ${cy}`,
    `C ${cx - s - h * 0.5} ${cy - h * 0.5}, ${cx - s - h * 0.3} ${cy - s - h * 0.5}, ${cx - s} ${cy - s - h * 0.5}`
  ].join(' ')
}

export default function EnclosureDemo() {
  const [mode, setMode] = useState('valid')

  const cx = 150, cy = 150, s = 48

  // All 9 dots in 3×3 grid
  const dots = []
  for (let gy = 1; gy >= -1; gy--)
    for (let gx = -1; gx <= 1; gx++)
      dots.push({ gx, gy })

  const validOuterPath = buildValidKolamPath(cx, cy, s)
  const validInnerPath = buildInnerLoopPath(cx, cy, s)
  const invalidPath = buildInvalidPath(cx, cy, s)

  const isEnclosed = (gx, gy) => {
    if (mode === 'valid') return true
    // In invalid mode, top-center (0,1) and bottom-center (0,-1) are stranded
    if (gx === 0 && (gy === 1 || gy === -1)) return false
    return true
  }

  return (
    <div className="demo-container archival-frame">
      <div className="demo-toolbar">
        <div className="demo-controls">
          <span className="label-tech">ENCLOSURE STATE:</span>
          <button
            className={`btn btn--sm ${mode === 'valid' ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setMode('valid')}
          >
            Valid: All 9 Enclosed
          </button>
          <button
            className={`btn btn--sm ${mode === 'invalid' ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setMode('invalid')}
          >
            Invalid: 2 Dots Stranded
          </button>
        </div>
        <span className="label-tech" style={{
          color: mode === 'valid' ? 'var(--color-step-done)' : 'var(--color-maroon-main)',
          fontWeight: 700
        }}>
          {mode === 'valid' ? '9/9 DOTS ENCLOSED ✓' : '7/9 DOTS · 2 STRANDED ✕'}
        </span>
      </div>

      <div className="demo-canvas-wrap">
        <svg viewBox="0 0 300 300" className="demo-svg">
          {/* Axis lines */}
          <line x1="150" y1="20" x2="150" y2="280" stroke="var(--color-card-border)" strokeWidth="0.7" strokeDasharray="3 4" />
          <line x1="20" y1="150" x2="280" y2="150" stroke="var(--color-card-border)" strokeWidth="0.7" strokeDasharray="3 4" />

          {/* Loop strokes */}
          {mode === 'valid' ? (
            <>
              <path
                d={validOuterPath}
                fill="none"
                stroke="var(--color-step-done)"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
              <path
                d={validInnerPath}
                fill="none"
                stroke="var(--color-gold)"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </>
          ) : (
            <path
              d={invalidPath}
              fill="none"
              stroke="var(--color-maroon-main)"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeDasharray="8 4"
            />
          )}

          {/* Render dots with enclosure status */}
          {dots.map(({ gx, gy }, i) => {
            const x = cx + gx * s
            const y = cy - gy * s
            const enclosed = isEnclosed(gx, gy)
            return (
              <g key={i}>
                {/* Stranded indicator ring */}
                {!enclosed && (
                  <circle cx={x} cy={y} r="13" fill="rgba(139,0,0,0.08)" stroke="var(--color-maroon-main)" strokeWidth="1.5" strokeDasharray="3 2" />
                )}
                <circle
                  cx={x}
                  cy={y}
                  r={enclosed ? 3.5 : 5}
                  fill={enclosed ? 'var(--color-text-dark)' : 'var(--color-maroon-main)'}
                  style={{ transition: 'all 0.3s ease' }}
                />
                {/* Stranded label */}
                {!enclosed && (
                  <text x={x + 8} y={y - 8} fontSize="9" fill="var(--color-maroon-main)" fontFamily="monospace" fontWeight="700">STRANDED</text>
                )}
              </g>
            )
          })}
        </svg>
      </div>

      <p className="body-text body-text--sm demo-caption">
        <strong>Rule 3:</strong> Every dot (Pulli) must be enclosed inside a loop, none can sit outside the boundary. In the invalid view, the top-center and bottom-center dots are stranded (red circles). This breaks the topological completeness rule and makes the Kolam mathematically invalid.
      </p>
    </div>
  )
}
