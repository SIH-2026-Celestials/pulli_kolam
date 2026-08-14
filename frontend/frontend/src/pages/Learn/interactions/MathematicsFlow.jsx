import { useState } from 'react'

export default function MathematicsFlow() {
  const [step, setStep] = useState(1) // 1: Dots, 2: MultiGraph, 3: Degrees, 4: Eulerian

  const cx = 150
  const cy = 150
  const r = 50

  const nodes = [
    { id: 'v0', x: cx, y: cy - r, label: 'deg=4' },
    { id: 'v1', x: cx + r, y: cy, label: 'deg=4' },
    { id: 'v2', x: cx, y: cy + r, label: 'deg=4' },
    { id: 'v3', x: cx - r, y: cy, label: 'deg=4' },
  ]

  return (
    <div className="demo-container archival-frame" style={{ padding: '24px' }}>
      {/* User-friendly onboarding & instruction header */}
      <div className="demo-instruction-panel" style={{ borderBottom: '1px solid var(--color-card-border)', paddingBottom: '16px', marginBottom: '20px' }}>
        <h4 className="heading-display heading-5" style={{ color: 'var(--color-maroon-main)', marginBottom: '6px', fontSize: '16px', fontWeight: '700' }}>
          Interactive Proof: How Graph Theory Defines Kolam
        </h4>
        <p className="body-text body-text--sm" style={{ color: 'var(--color-text-body)', margin: 0, lineHeight: '1.5' }}>
          A traditional Kolam is drawn on a grid of dots (vertices) using continuous lines (edges). Click the pipeline buttons below sequentially to see how a set of dots is mathematically verified into a single-stroke closed loop (Eulerian Circuit).
        </p>
      </div>

      <div className="demo-toolbar" style={{ marginBottom: '16px' }}>
        <div className="demo-controls" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="label-tech" style={{ fontSize: '11px', fontWeight: '700', color: 'var(--color-text-muted)', marginRight: '8px' }}>PIPELINE STAGE:</span>
          <button
            className={`btn btn--sm ${step === 1 ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setStep(1)}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              borderRadius: '4px',
              cursor: 'pointer',
              border: '1px solid var(--color-maroon-main)',
              backgroundColor: step === 1 ? 'var(--color-maroon-main)' : 'transparent',
              color: step === 1 ? '#FFFFFF' : 'var(--color-maroon-main)',
              fontWeight: '600'
            }}
          >
            1. Pulli Lattice
          </button>
          <button
            className={`btn btn--sm ${step === 2 ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setStep(2)}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              borderRadius: '4px',
              cursor: 'pointer',
              border: '1px solid var(--color-maroon-main)',
              backgroundColor: step === 2 ? 'var(--color-maroon-main)' : 'transparent',
              color: step === 2 ? '#FFFFFF' : 'var(--color-maroon-main)',
              fontWeight: '600'
            }}
          >
            2. MultiGraph (k≥1)
          </button>
          <button
            className={`btn btn--sm ${step === 3 ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setStep(3)}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              borderRadius: '4px',
              cursor: 'pointer',
              border: '1px solid var(--color-maroon-main)',
              backgroundColor: step === 3 ? 'var(--color-maroon-main)' : 'transparent',
              color: step === 3 ? '#FFFFFF' : 'var(--color-maroon-main)',
              fontWeight: '600'
            }}
          >
            3. Even Degree Check
          </button>
          <button
            className={`btn btn--sm ${step === 4 ? 'btn--primary' : 'btn--outline'}`}
            onClick={() => setStep(4)}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              borderRadius: '4px',
              cursor: 'pointer',
              border: '1px solid var(--color-maroon-main)',
              backgroundColor: step === 4 ? 'var(--color-maroon-main)' : 'transparent',
              color: step === 4 ? '#FFFFFF' : 'var(--color-maroon-main)',
              fontWeight: '600'
            }}
          >
            4. Eulerian Circuit ✓
          </button>
        </div>
      </div>

      <div className="demo-canvas-wrap" style={{ display: 'flex', justifyContent: 'center', backgroundColor: 'var(--color-paper-light)', borderRadius: '8px', padding: '20px', marginBottom: '16px' }}>
        <svg viewBox="0 0 300 300" style={{ width: '100%', maxWidth: '280px', height: 'auto' }}>
          {/* Stage 1: Dots */}
          {nodes.map(n => (
            <circle
              key={n.id}
              cx={n.x}
              cy={n.y}
              r={step >= 3 ? '6' : '4'}
              fill={step >= 3 ? 'var(--color-step-done)' : 'var(--color-text-dark)'}
            />
          ))}

          {/* Stage 2 & 3: MultiGraph Parallel Edges */}
          {step >= 2 && (
            <g>
              {/* Outer square single strands */}
              <line x1={nodes[0].x} y1={nodes[0].y} x2={nodes[1].x} y2={nodes[1].y} stroke="var(--color-text-dark)" strokeWidth="2.5" />
              <line x1={nodes[1].x} y1={nodes[1].y} x2={nodes[2].x} y2={nodes[2].y} stroke="var(--color-text-dark)" strokeWidth="2.5" />
              <line x1={nodes[2].x} y1={nodes[2].y} x2={nodes[3].x} y2={nodes[3].y} stroke="var(--color-text-dark)" strokeWidth="2.5" />
              <line x1={nodes[3].x} y1={nodes[3].y} x2={nodes[0].x} y2={nodes[0].y} stroke="var(--color-text-dark)" strokeWidth="2.5" />

              {/* Parallel double-strand edges (MultiGraph k=2) */}
              <path d={`M ${nodes[0].x - 8} ${nodes[0].y} Q ${cx} ${cy} ${nodes[2].x - 8} ${nodes[2].y}`} fill="none" stroke="var(--color-gold)" strokeWidth="3" />
              <path d={`M ${nodes[0].x + 8} ${nodes[0].y} Q ${cx} ${cy} ${nodes[2].x + 8} ${nodes[2].y}`} fill="none" stroke="var(--color-gold)" strokeWidth="3" />
            </g>
          )}

          {/* Stage 3: Node Degree Annotations */}
          {step >= 3 && nodes.map((n, idx) => {
            const degree = idx % 2 === 0 ? 4 : 2;
            return (
              <text key={`text-${n.id}`} x={n.x > cx ? n.x + 14 : n.x < cx ? n.x - 72 : n.x - 32} y={n.y < cy ? n.y - 12 : n.y > cy ? n.y + 24 : n.y + 5} style={{ fontSize: '11px', fill: 'var(--color-step-done)', fontWeight: '700', fontFamily: 'var(--font-sans)' }}>
                deg(v)={degree} ✓
              </text>
            );
          })}

          {/* Stage 4: Eulerian Closed Stroke */}
          {step === 4 && (
            <path
              d={`M ${nodes[0].x} ${nodes[0].y} 
                 L ${nodes[1].x} ${nodes[1].y} 
                 L ${nodes[2].x} ${nodes[2].y} 
                 L ${nodes[3].x} ${nodes[3].y} 
                 Z 
                 M ${nodes[0].x} ${nodes[0].y} 
                 Q ${cx} ${cy} ${nodes[2].x} ${nodes[2].y}
                 M ${nodes[2].x} ${nodes[2].y}
                 Q ${cx} ${cy} ${nodes[0].x} ${nodes[0].y}`}
              fill="none"
              stroke="var(--color-step-done)"
              strokeWidth="4"
              strokeDasharray="6 4"
            />
          )}
        </svg>
      </div>

      <div className="body-text body-text--sm demo-caption" style={{ backgroundColor: 'var(--color-paper-light)', padding: '16px', borderRadius: '6px', border: '1px solid var(--color-card-border)' }}>
        {step === 1 && <p style={{ margin: 0, color: 'var(--color-text-body)' }}><strong>Stage 1: Pulli Lattice:</strong> We begin with a discrete set of dots representing coordinates in space. In graph theory, these are represented as <strong>vertices (V)</strong>.</p>}
        {step === 2 && <p style={{ margin: 0, color: 'var(--color-text-body)' }}><strong>Stage 2: MultiGraph Formulation:</strong> Paths are drawn connecting adjacent dots. To model complex overlapping lines, we construct a <strong>MultiGraph</strong> which allows multiple parallel connections (edges) between vertices.</p>}
        {step === 3 && <p style={{ margin: 0, color: 'var(--color-text-body)' }}><strong>Stage 3: Degree Verification:</strong> We check the degree (number of lines meeting at each dot). According to Eulerian path theorems, if every dot has an <strong>even degree</strong> (here, deg = 4), the loop is valid and solvable.</p>}
        {step === 4 && <p style={{ margin: 0, color: 'var(--color-text-body)' }}><strong>Stage 4: Eulerian Circuit Complete:</strong> Because the graph is connected and all vertices have even degrees, Euler's theorem guarantees the pattern can be drawn in a <strong>single continuous stroke without lifting the pen</strong>!</p>}
      </div>
    </div>
  )
}
