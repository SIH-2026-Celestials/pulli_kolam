import { useState } from 'react'

// A single seed motif in the top-right quadrant
// (a small petal-like Kolam stroke around the dot at (1,1))
const SEED_PATH = `
  M 170 120
  C 185 105, 205 105, 210 120
  C 215 135, 205 148, 190 148
  C 178 148, 168 138, 170 120
`

// The 4 rotation operations as CSS transforms around the center (150, 150)
const QUADRANT_STEPS = [
  {
    key: 'q1',
    label: '① Seed Motif (Top-Right)',
    transform: 'rotate(0 150 150)',
    color: 'var(--color-maroon-main)',
    description: 'We start by drawing a single petal motif in the top-right quadrant. This is the "seed": the minimal repeating unit of the Kolam.'
  },
  {
    key: 'q2',
    label: '② Rotate 90° (Top-Left)',
    transform: 'rotate(90 150 150)',
    color: 'var(--color-gold)',
    description: 'Apply R₉₀: rotate the seed 90° clockwise around the center. The same petal now appears in the top-left quadrant.'
  },
  {
    key: 'q3',
    label: '③ Rotate 180° (Bottom-Left)',
    transform: 'rotate(180 150 150)',
    color: 'var(--color-step-done)',
    description: 'Apply R₁₈₀: rotate 180°. The petal appears in the bottom-left quadrant, forming 3-fold partial symmetry.'
  },
  {
    key: 'q4',
    label: '④ Rotate 270° (Bottom-Right)',
    transform: 'rotate(270 150 150)',
    color: 'var(--color-text-muted)',
    description: 'Apply R₂₇₀: rotate 270°. All 4 quadrants are now filled, creating a complete D₄ rotationally-symmetric Kolam pattern.'
  }
]

// 5×5 dot grid in center of canvas for visual context
function DotGrid({ cx, cy, step }) {
  const dots = []
  for (let gy = -2; gy <= 2; gy++)
    for (let gx = -2; gx <= 2; gx++)
      dots.push({ x: cx + gx * step, y: cy + gy * step })
  return dots.map((d, i) => (
    <circle key={i} cx={d.x} cy={d.y} r="2.5" fill="var(--color-text-dark)" opacity="0.7" />
  ))
}

export default function SymmetryBuildDemo() {
  const [visibleCount, setVisibleCount] = useState(1)

  const visibleSteps = QUADRANT_STEPS.slice(0, visibleCount)
  const currentStep = QUADRANT_STEPS[visibleCount - 1]

  const isComplete = visibleCount === 4

  return (
    <div className="demo-container archival-frame">
      <div className="demo-toolbar" style={{ flexWrap: 'wrap', gap: '8px' }}>
        <div className="demo-controls" style={{ flexWrap: 'wrap', gap: '6px' }}>
          <span className="label-tech" style={{ display: 'block', width: '100%' }}>BUILD THE PATTERN STEP BY STEP:</span>
          {QUADRANT_STEPS.map((step, i) => (
            <button
              key={step.key}
              className={`btn btn--sm ${visibleCount > i ? 'btn--primary' : 'btn--outline'}`}
              onClick={() => setVisibleCount(i + 1)}
            >
              {step.label}
            </button>
          ))}
          <button
            className={`btn btn--sm ${isComplete ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setVisibleCount(1)}
          >
            Reset ↺
          </button>
        </div>
      </div>

      <div className="demo-canvas-wrap">
        <svg viewBox="0 0 300 300" className="demo-svg">
          {/* Symmetry axes */}
          <line x1="150" y1="20" x2="150" y2="280" stroke="var(--color-card-border)" strokeWidth="0.8" strokeDasharray="4 4" opacity="0.7" />
          <line x1="20" y1="150" x2="280" y2="150" stroke="var(--color-card-border)" strokeWidth="0.8" strokeDasharray="4 4" opacity="0.7" />
          <line x1="40" y1="40" x2="260" y2="260" stroke="var(--color-card-border)" strokeWidth="0.5" strokeDasharray="2 5" opacity="0.4" />
          <line x1="260" y1="40" x2="40" y2="260" stroke="var(--color-card-border)" strokeWidth="0.5" strokeDasharray="2 5" opacity="0.4" />

          {/* Dot lattice */}
          <DotGrid cx={150} cy={150} step={38} />

          {/* Quadrant labels */}
          <text x="165" y="35" fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace" opacity="0.6">Q1 (+,+)</text>
          <text x="35" y="35" fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace" opacity="0.6">Q2 (-,+)</text>
          <text x="35" y="278" fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace" opacity="0.6">Q3 (-,-)</text>
          <text x="165" y="278" fontSize="9" fill="var(--color-text-muted)" fontFamily="monospace" opacity="0.6">Q4 (+,-)</text>

          {/* Render the visible motif petals */}
          {visibleSteps.map((step, i) => (
            <g key={step.key} transform={step.transform} style={{ transition: 'all 0.4s ease' }}>
              <path
                d={SEED_PATH}
                fill={step.color}
                fillOpacity="0.15"
                stroke={step.color}
                strokeWidth={i === 0 ? '2.5' : '2'}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </g>
          ))}

          {/* Render Upright Operation Labels at distinct coordinates to prevent overlap */}
          {visibleCount >= 2 && (
            <text x="94" y="128" fontSize="8" fill={QUADRANT_STEPS[1].color} fontFamily="monospace" fontWeight="700" textAnchor="middle">R₉₀°</text>
          )}
          {visibleCount >= 3 && (
            <text x="112" y="190" fontSize="8" fill={QUADRANT_STEPS[2].color} fontFamily="monospace" fontWeight="700" textAnchor="middle">R₁₈₀°</text>
          )}
          {visibleCount >= 4 && (
            <text x="186" y="190" fontSize="8" fill={QUADRANT_STEPS[3].color} fontFamily="monospace" fontWeight="700" textAnchor="middle">R₂₇₀°</text>
          )}

          {/* Seed indicator label */}
          <text x="190" y="128" fontSize="8" fill="var(--color-maroon-main)" fontFamily="monospace" fontWeight="700">SEED</text>

          {/* Complete badge */}
          {isComplete && (
            <g>
              <rect x="88" y="133" width="75" height="18" rx="9" fill="var(--color-step-done)" opacity="0.9" />
              <text x="125" y="146" fontSize="9" fill="white" textAnchor="middle" fontFamily="monospace" fontWeight="700">
                D₄ COMPLETE ✓
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* Step description callout */}
      <div style={{
        marginTop: '12px',
        padding: '10px 14px',
        background: 'var(--color-bg-subtle)',
        borderRadius: '8px',
        borderTopLeftRadius: '0px',
        borderBottomLeftRadius: '0px',
        borderLeft: `3px solid ${currentStep.color}`
      }}>
        <span className="label-tech" style={{ fontSize: '10px', color: currentStep.color }}>{currentStep.label}</span>
        <p className="body-text body-text--sm" style={{ margin: '4px 0 0', lineHeight: '1.55' }}>
          {currentStep.description}
        </p>
      </div>

      <p className="body-text body-text--sm demo-caption" style={{ marginTop: '10px' }}>
        <strong>Rule 5:</strong> Instead of drawing all 4 corners independently, a Kolam artist draws one seed motif and applies 4 rotations (0°, 90°, 180°, 270°) to generate the complete D₄ symmetric pattern. Step through the sequence above to watch the pattern build.
      </p>
    </div>
  )
}
