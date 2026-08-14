import './ResearchMosaic.css'

const panels = [
  {
    id: 'pattern',
    label: 'THE PATTERN',
    description: 'A continuous one-stroke drawing constructed around a field of Pulli dots.',
    visual: <PatternVisual />,
    span: 'large',
  },
  {
    id: 'trace',
    label: 'THE TRACE',
    description: 'Dense coordinate polyline sampled at ~0.5-unit resolution from the dataset CSV.',
    visual: <TraceVisual />,
    span: 'small',
  },
  {
    id: 'graph',
    label: 'THE GRAPH',
    description: 'MultiGraph representation with multiplicity-aware edges for repeated strands.',
    visual: <GraphVisual />,
    span: 'small',
  },
  {
    id: 'structure',
    label: 'THE STRUCTURE',
    description: 'D4 symmetry axes - vertical, horizontal, and 180° rotational.',
    visual: <StructureVisual />,
    span: 'small',
  },
  {
    id: 'motif',
    label: 'THE MOTIF',
    description: 'Recurring local patterns identified via greedy set-cover induction.',
    visual: <MotifVisual />,
    span: 'small',
  },
  {
    id: 'validity',
    label: 'THE VALIDITY',
    description: 'One-stroke constraint verified as an Eulerian path through the graph.',
    visual: <ValidityVisual />,
    span: 'small',
  },
]

export default function ResearchMosaic() {
  return (
    <div className="research-mosaic">
      {panels.map(panel => (
        <div
          key={panel.id}
          className={`mosaic-panel mosaic-panel--${panel.span} mosaic-panel--${panel.id}`}
        >
          <div className="mosaic-panel__visual" aria-hidden="true">
            {panel.visual}
          </div>
          <div className="mosaic-panel__info">
            <span className="mosaic-panel__label eyebrow">{panel.label}</span>
            <p className="mosaic-panel__desc">{panel.description}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── Panel Visuals (SVG) ─────────────────────────────────── */

function PatternVisual() {
  return (
    <svg viewBox="0 0 200 200" fill="none" className="panel-svg">
      {/* Dot grid */}
      {[...Array(5)].map((_, r) =>
        [...Array(5)].map((_, c) => (
          <circle key={`${r}-${c}`} cx={30 + c * 35} cy={30 + r * 35} r="3" fill="var(--color-line-dark)" />
        ))
      )}
      {/* Kolam stroke - a petal-like pattern */}
      <path d="M 100 30 C 140 30 170 60 170 100 C 170 140 140 170 100 170 C 60 170 30 140 30 100 C 30 60 60 30 100 30 Z"
        stroke="var(--color-ink)" strokeWidth="1.5" fill="none"/>
      <path d="M 100 30 C 100 60 130 65 130 100 C 130 135 100 140 100 170"
        stroke="var(--color-ink)" strokeWidth="1.2" fill="none"/>
      <path d="M 100 30 C 100 60 70 65 70 100 C 70 135 100 140 100 170"
        stroke="var(--color-ink)" strokeWidth="1.2" fill="none"/>
      <path d="M 30 100 C 60 100 65 130 100 130 C 135 130 140 100 170 100"
        stroke="var(--color-ink)" strokeWidth="1.2" fill="none"/>
      <path d="M 30 100 C 60 100 65 70 100 70 C 135 70 140 100 170 100"
        stroke="var(--color-ink)" strokeWidth="1.2" fill="none"/>
    </svg>
  )
}

function TraceVisual() {
  // Represents dense coordinate trace as a series of points
  const pts = [
    [40,160],[45,150],[52,140],[60,128],[70,115],[82,103],[95,93],
    [108,85],[122,80],[135,78],[148,80],[158,85],[165,93],[170,103],
    [172,115],[170,128],[164,140],[155,150],[143,157],[130,161],
    [116,162],[103,160]
  ]
  const polyline = pts.map(([x,y]) => `${x},${y}`).join(' ')
  return (
    <svg viewBox="0 0 200 200" fill="none" className="panel-svg">
      <polyline points={polyline} stroke="var(--color-accent)" strokeWidth="1.5"
        fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      {pts.filter((_, i) => i % 3 === 0).map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2" fill="var(--color-accent)" fillOpacity="0.6"/>
      ))}
      <text x="40" y="185" fontSize="8" fill="var(--color-soft-gray)" fontFamily="monospace">
        ~0.5 unit resolution
      </text>
    </svg>
  )
}

function GraphVisual() {
  const nodes = [
    [100,40],[160,80],[160,140],[100,175],[40,140],[40,80],
    [100,100]
  ]
  const edges = [
    [0,1],[1,2],[2,3],[3,4],[4,5],[5,0],
    [0,6],[1,6],[2,6],[3,6],[4,6],[5,6],
  ]
  return (
    <svg viewBox="0 0 200 200" fill="none" className="panel-svg">
      {edges.map(([a,b], i) => (
        <line key={i}
          x1={nodes[a][0]} y1={nodes[a][1]}
          x2={nodes[b][0]} y2={nodes[b][1]}
          stroke="var(--color-ink)" strokeWidth="1" strokeOpacity="0.4"/>
      ))}
      {/* Double edge to show multiplicity */}
      <line x1={nodes[0][0]} y1={nodes[0][1]} x2={nodes[1][0]} y2={nodes[1][1]}
        stroke="var(--color-accent)" strokeWidth="2" strokeOpacity="0.5" strokeDasharray="4 2"/>
      {nodes.map(([x,y], i) => (
        <circle key={i} cx={x} cy={y} r={i === 6 ? 5 : 4}
          fill={i === 6 ? 'var(--color-accent)' : 'var(--color-ink)'}
          fillOpacity={i === 6 ? 1 : 0.7}/>
      ))}
      <text x="40" y="192" fontSize="7.5" fill="var(--color-soft-gray)" fontFamily="monospace">
        MultiGraph - edge multiplicity
      </text>
    </svg>
  )
}

function StructureVisual() {
  return (
    <svg viewBox="0 0 200 200" fill="none" className="panel-svg">
      {/* Pattern outline */}
      <path d="M 100 30 C 140 30 170 60 170 100 C 170 140 140 170 100 170 C 60 170 30 140 30 100 C 30 60 60 30 100 30 Z"
        stroke="var(--color-line-dark)" strokeWidth="1.5" fill="none"/>
      {/* V axis */}
      <line x1="100" y1="15" x2="100" y2="185"
        stroke="var(--color-accent)" strokeWidth="1" strokeDasharray="5 4"/>
      {/* H axis */}
      <line x1="15" y1="100" x2="185" y2="100"
        stroke="var(--color-accent)" strokeWidth="1" strokeDasharray="5 4"/>
      {/* Diagonal */}
      <line x1="40" y1="40" x2="160" y2="160"
        stroke="var(--color-accent)" strokeWidth="0.6" strokeDasharray="3 6" strokeOpacity="0.5"/>
      <line x1="160" y1="40" x2="40" y2="160"
        stroke="var(--color-accent)" strokeWidth="0.6" strokeDasharray="3 6" strokeOpacity="0.5"/>
      {/* Labels */}
      <text x="104" y="20" fontSize="7" fill="var(--color-accent)" fontFamily="sans-serif">V</text>
      <text x="170" y="104" fontSize="7" fill="var(--color-accent)" fontFamily="sans-serif">H</text>
    </svg>
  )
}

function MotifVisual() {
  return (
    <svg viewBox="0 0 200 200" fill="none" className="panel-svg">
      {/* Base pattern */}
      <path d="M 100 30 C 140 30 170 60 170 100 C 170 140 140 170 100 170 C 60 170 30 140 30 100 C 30 60 60 30 100 30 Z"
        stroke="var(--color-line-dark)" strokeWidth="1" fill="none" strokeOpacity="0.4"/>
      {/* Highlighted motif instances */}
      <path d="M 100 30 C 125 30 140 55 130 80 C 120 105 100 100 100 100 C 100 100 80 105 70 80 C 60 55 75 30 100 30 Z"
        stroke="var(--color-accent)" strokeWidth="1.8" fill="var(--color-accent)" fillOpacity="0.08"/>
      {/* Rotation copies */}
      <path d="M 170 100 C 170 125 145 140 120 130 C 95 120 100 100 100 100 C 100 100 105 80 130 70 C 155 60 170 75 170 100 Z"
        stroke="var(--color-accent)" strokeWidth="1.2" fill="var(--color-accent)" fillOpacity="0.05" strokeDasharray="4 3"/>
      <text x="30" y="192" fontSize="7.5" fill="var(--color-soft-gray)" fontFamily="monospace">
        Motif · instance × 4
      </text>
    </svg>
  )
}

function ValidityVisual() {
  const pathPoints = [[100,30],[150,65],[165,115],[140,160],[100,175],[60,160],[35,115],[50,65],[100,30]]
  const d = pathPoints.map(([x,y], i) => `${i===0?'M':'L'} ${x} ${y}`).join(' ')

  return (
    <svg viewBox="0 0 200 200" fill="none" className="panel-svg">
      {/* The closed path */}
      <path d={d} stroke="var(--color-valid)" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Start = end marker */}
      <circle cx="100" cy="30" r="5" fill="var(--color-valid)" fillOpacity="0.8"/>
      <circle cx="100" cy="30" r="9" stroke="var(--color-valid)" strokeWidth="1" fill="none" strokeOpacity="0.4"/>
      {/* Valid badge */}
      <rect x="55" y="80" width="90" height="26" rx="2"
        fill="var(--color-valid)" fillOpacity="0.1" stroke="var(--color-valid)" strokeOpacity="0.3"/>
      <text x="100" y="97" fontSize="8.5" fill="var(--color-valid)" fontFamily="sans-serif"
        textAnchor="middle" fontWeight="600" letterSpacing="1">VALID ONE-STROKE</text>
    </svg>
  )
}
