import { useState } from 'react'

export default function SymmetryDemo() {
  const [activeOp, setActiveOp] = useState('ALL') // 'IDENTITY', 'R90', 'R180', 'R270', 'MH', 'MV', 'MD1', 'MD2', 'ALL'

  const cx = 150
  const cy = 150

  // Seed motif path in Quadrant 1 (top-right)
  const seedMotif = `M ${cx + 15} ${cy - 15} C ${cx + 35} ${cy - 65} ${cx + 65} ${cy - 35} ${cx + 15} ${cy - 15}`
  const loopMotif = `M ${cx + 25} ${cy - 75} C ${cx + 5} ${cy - 95} ${cx + 95} ${cy - 95} ${cx + 75} ${cy - 25}`

  const operations = [
    { key: 'IDENTITY', label: 'Identity (0°)', transform: 'rotate(0, 150, 150)' },
    { key: 'R90', label: 'Rotate 90°', transform: 'rotate(90, 150, 150)' },
    { key: 'R180', label: 'Rotate 180°', transform: 'rotate(180, 150, 150)' },
    { key: 'R270', label: 'Rotate 270°', transform: 'rotate(270, 150, 150)' },
    { key: 'MH', label: 'Mirror Horizontal', transform: 'matrix(1 0 0 -1 0 300)' },
    { key: 'MV', label: 'Mirror Vertical', transform: 'matrix(-1 0 0 1 300 0)' },
    { key: 'MD1', label: 'Mirror Diagonal (y = x)', transform: 'matrix(0 1 1 0 0 0)' },
    { key: 'MD2', label: 'Mirror Anti-Diag (y = -x)', transform: 'matrix(0 -1 -1 0 300 300)' },
  ]

  const shouldRenderOp = (opKey) => {
    if (activeOp === 'ALL') return true
    if (activeOp === 'IDENTITY' && opKey === 'IDENTITY') return true
    if (activeOp === 'R90' && (opKey === 'IDENTITY' || opKey === 'R90')) return true
    if (activeOp === 'R180' && (opKey === 'IDENTITY' || opKey === 'R90' || opKey === 'R180')) return true
    if (activeOp === 'R270' && (opKey === 'IDENTITY' || opKey === 'R90' || opKey === 'R180' || opKey === 'R270')) return true
    if (activeOp === 'MH' && (opKey === 'IDENTITY' || opKey === 'MH')) return true
    if (activeOp === 'MV' && (opKey === 'IDENTITY' || opKey === 'MV')) return true
    if (activeOp === 'MD1' && (opKey === 'IDENTITY' || opKey === 'MD1')) return true
    if (activeOp === 'MD2' && (opKey === 'IDENTITY' || opKey === 'MD2')) return true
    return false
  }

  return (
    <div className="demo-container archival-frame">
      <div className="demo-toolbar">
        <div className="demo-controls" style={{ flexWrap: 'wrap', gap: '8px' }}>
          <span className="label-tech" style={{ display: 'block', width: '100%', marginBottom: '4px' }}>D₄ DIHEDRAL OPERATIONS:</span>
          {operations.map(op => (
            <button
              key={op.key}
              className={`btn btn--sm ${activeOp === op.key ? 'btn--primary' : 'btn--outline'}`}
              style={{ textTransform: 'none' }}
              onClick={() => setActiveOp(op.key)}
            >
              {op.label}
            </button>
          ))}
          <button
            className={`btn btn--sm ${activeOp === 'ALL' ? 'btn--primary' : 'btn--outline'}`}
            style={{ textTransform: 'none' }}
            onClick={() => setActiveOp('ALL')}
          >
            Full D₄ Group (All 8 Symmetries)
          </button>
        </div>
      </div>

      <div className="demo-canvas-wrap">
        <svg viewBox="0 0 300 300" className="demo-svg">
          {/* D4 Symmetry Axes */}
          <line x1="150" y1="10" x2="150" y2="290" stroke="var(--color-gold)" strokeWidth="0.8" strokeDasharray="4 4" opacity="0.4" />
          <line x1="10" y1="150" x2="290" y2="150" stroke="var(--color-gold)" strokeWidth="0.8" strokeDasharray="4 4" opacity="0.4" />
          <line x1="40" y1="40" x2="260" y2="260" stroke="var(--color-text-muted)" strokeWidth="0.5" strokeDasharray="2 4" opacity="0.3" />
          <line x1="260" y1="40" x2="40" y2="260" stroke="var(--color-text-muted)" strokeWidth="0.5" strokeDasharray="2 4" opacity="0.3" />

          {/* Render 5x5 Dot Lattice */}
          {[-2, -1, 0, 1, 2].map(gx => (
            [-2, -1, 0, 1, 2].map(gy => (
              <circle
                key={`${gx},${gy}`}
                cx={150 + gx * 40}
                cy={150 + gy * 40}
                r="2.5"
                fill="var(--color-text-dark)"
              />
            ))
          ))}

          {/* Render Transformed Motifs */}
          {operations.map(op => {
            if (!shouldRenderOp(op.key)) return null
            const isSeed = op.key === 'IDENTITY'
            return (
              <g key={op.key} transform={op.transform} style={{ transition: 'all 0.4s ease' }}>
                <path
                  d={seedMotif}
                  fill="none"
                  stroke={isSeed ? 'var(--color-maroon-main)' : 'var(--color-text-muted)'}
                  strokeWidth={isSeed ? '2.5' : '1.8'}
                  strokeLinecap="round"
                />
                <path
                  d={loopMotif}
                  fill="none"
                  stroke={isSeed ? 'var(--color-maroon-main)' : 'var(--color-text-muted)'}
                  strokeWidth={isSeed ? '2' : '1.5'}
                  strokeLinecap="round"
                />
              </g>
            )
          })}
        </svg>
      </div>

      <p className="body-text body-text--sm demo-caption">
        <strong>D₄ Dihedral Symmetry Walkthrough:</strong> The terracotta shape is the <em>seed motif</em>. By rotating it by 90°, 180°, and 270° around the center origin, PULLI generates a complete 4-fold dihedral pattern automatically.
      </p>
    </div>
  )
}
