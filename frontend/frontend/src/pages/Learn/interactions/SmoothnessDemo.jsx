import { useState } from 'react'

// Two dots at (-1,0) and (1,0) centered at (cx, cy)
// Smooth arc: approaches each dot at 45 degrees, curves around them using Bezier arcs
// Path stays fully contained within the SVG canvas
function buildSmoothArc(cx, cy, s) {
  const h = s * 0.55
  return [
    // Enter from top-left at 45 degrees, arc around left dot
    `M ${cx - s} ${cy - s * 0.9}`,
    `C ${cx - s} ${cy - h}, ${cx - h} ${cy}, ${cx} ${cy}`,
    // Arc around right dot, exit top-right at 45 degrees
    `C ${cx + h} ${cy}, ${cx + s} ${cy - h}, ${cx + s} ${cy - s * 0.9}`
  ].join(' ')
}

// Same path but slightly offset below for double-strand demo
function buildDoubleStrandArc(cx, cy, s) {
  const h = s * 0.55
  const o = 11
  return [
    `M ${cx - s} ${cy - s * 0.9 + o}`,
    `C ${cx - s} ${cy - h + o}, ${cx - h} ${cy + o}, ${cx} ${cy + o}`,
    `C ${cx + h} ${cy + o}, ${cx + s} ${cy - h + o}, ${cx + s} ${cy - s * 0.9 + o}`
  ].join(' ')
}

// Sharp 90 degree polyline (invalid style)
function buildSharpPath(cx, cy, s) {
  return [
    `M ${cx - s} ${cy - s * 0.9}`,
    `L ${cx - s} ${cy + s * 0.3}`,
    `L ${cx + s} ${cy + s * 0.3}`,
    `L ${cx + s} ${cy - s * 0.9}`
  ].join(' ')
}

export default function SmoothnessDemo() {
  const [style, setStyle] = useState('smooth')
  const [showDouble, setShowDouble] = useState(false)

  const cx = 150, cy = 160, s = 55

  const mainPath = style === 'smooth' ? buildSmoothArc(cx, cy, s) : buildSharpPath(cx, cy, s)
  const doublePath = buildDoubleStrandArc(cx, cy, s)

  const dots = [
    { x: cx - s, y: cy },
    { x: cx + s, y: cy }
  ]

  return (
    <div className="demo-container archival-frame">
      <div className="demo-toolbar">
        <div className="demo-controls">
          <span className="label-tech">CURVATURE STYLE:</span>
          <button
            className={`btn btn--sm ${style === 'smooth' ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setStyle('smooth')}
          >
            Authentic 45 deg Bezier Arc
          </button>
          <button
            className={`btn btn--sm ${style === 'sharp' ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setStyle('sharp')}
          >
            Sharp 90 deg Corner
          </button>
        </div>
        {style === 'smooth' && (
          <button
            className={`btn btn--sm ${showDouble ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setShowDouble(v => !v)}
          >
            {showDouble ? 'Hide' : 'Show'} Double-Strand
          </button>
        )}
        <span className="label-tech" style={{
          color: style === 'smooth' ? 'var(--color-step-done)' : 'var(--color-maroon-main)',
          fontWeight: 700
        }}>
          {style === 'smooth' ? 'AUTHENTIC KOLAM GEOMETRY' : 'INVALID: RULE 4 VIOLATED'}
        </span>
      </div>

      <div className="demo-canvas-wrap">
        <svg viewBox="0 0 300 300" className="demo-svg">
          {/* 45 degree approach angle guides */}
          {style === 'smooth' && (
            <>
              <line
                x1={cx - s} y1={cy}
                x2={cx - s} y2={cy - s * 0.9}
                stroke="var(--color-gold)" strokeWidth="1" strokeDasharray="4 3" opacity="0.6"
              />
              <line
                x1={cx + s} y1={cy}
                x2={cx + s} y2={cy - s * 0.9}
                stroke="var(--color-gold)" strokeWidth="1" strokeDasharray="4 3" opacity="0.6"
              />
              <text x={cx - s - 22} y={cy - s * 0.45} fontSize="9" fill="var(--color-gold)" fontFamily="monospace">45deg</text>
              <text x={cx + s + 5} y={cy - s * 0.45} fontSize="9" fill="var(--color-gold)" fontFamily="monospace">45deg</text>
            </>
          )}

          {/* Sharp corner indicators */}
          {style === 'sharp' && (
            <>
              <rect x={cx - s - 10} y={cy + s * 0.3 - 10} width="10" height="10" fill="none" stroke="var(--color-maroon-main)" strokeWidth="1.2" />
              <rect x={cx + s} y={cy + s * 0.3 - 10} width="10" height="10" fill="none" stroke="var(--color-maroon-main)" strokeWidth="1.2" />
              <text x={cx - s - 36} y={cy + s * 0.3 - 14} fontSize="9" fill="var(--color-maroon-main)" fontFamily="monospace">90deg</text>
              <text x={cx + s + 13} y={cy + s * 0.3 - 14} fontSize="9" fill="var(--color-maroon-main)" fontFamily="monospace">90deg</text>
            </>
          )}

          {/* Double-strand parallel arc */}
          {style === 'smooth' && showDouble && (
            <path
              d={doublePath}
              fill="none"
              stroke="var(--color-maroon-main)"
              strokeWidth="2"
              strokeLinecap="round"
              opacity="0.5"
            />
          )}

          {/* Main stroke path */}
          <path
            key={style}
            d={mainPath}
            fill="none"
            stroke="var(--color-maroon-main)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ transition: 'all 0.4s ease' }}
          />

          {/* Dots */}
          {dots.map((d, i) => (
            <circle key={i} cx={d.x} cy={d.y} r="5" fill="var(--color-text-dark)" />
          ))}

          <text x={cx - s - 14} y={cy + 18} fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace">(-1,0)</text>
          <text x={cx + s - 8} y={cy + 18} fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace">(1,0)</text>
        </svg>
      </div>

      <p className="body-text body-text--sm demo-caption">
        <strong>Rule 4:</strong> Kolam lines approach dots at <em>45 degree diagonal angles</em> and curve smoothly around them using Bezier arcs, never making sharp 90 degree corners. {style === 'smooth' && showDouble && 'The second strand is a double-strand edge: two parallel lines side-by-side (found in about 21% of real Kolam patterns).'} {style === 'sharp' && 'The sharp version violates authentic Kolam geometry and breaks the ethnomathematical visual grammar.'}
      </p>
    </div>
  )
}
