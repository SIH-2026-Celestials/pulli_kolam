import { useRef } from 'react'
import './KolamCanvas.css'

/**
 * KolamCanvas - SVG animated Kolam visualization for the hero.
 * 
 * Renders a pulli dot-grid and draws a traditional-style Kolam
 * pattern progressively using SVG stroke-dashoffset animation.
 * 
 * No particle effects. No glow. Clean linework on paper background.
 */
export default function KolamCanvas({ className = '' }) {
  const svgRef = useRef(null)

  return (
    <div className={`kolam-canvas ${className}`} aria-label="Animated Kolam visualization">
      <svg
        ref={svgRef}
        viewBox="0 0 300 300"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="kolam-canvas__svg"
        aria-hidden="true"
      >
        {/* Dot grid - the Pulli (dots) */}
        <PulliGrid />

        {/* Main Kolam stroke - animated drawing */}
        <KolamStroke />

        {/* Symmetry axes - subtle */}
        <SymmetryAxes />

        {/* Corner annotation */}
        <text x="10" y="290" className="kolam-canvas__label">kolam19 · 725 pts · 37×37</text>
      </svg>
    </div>
  )
}

function PulliGrid() {
  const dots = []
  const step = 30
  const offsetX = 15
  const offsetY = 15

  for (let row = 0; row < 10; row++) {
    for (let col = 0; col < 10; col++) {
      const x = offsetX + col * step
      const y = offsetY + row * step
      dots.push(
        <circle
          key={`${row}-${col}`}
          cx={x}
          cy={y}
          r="2"
          fill="currentColor"
          className="kolam-canvas__dot"
          style={{ animationDelay: `${(row * 10 + col) * 12}ms` }}
        />
      )
    }
  }
  return <g className="kolam-canvas__dots">{dots}</g>
}

function KolamStroke() {
  // A traditional 5×5 Kolam pattern - continuous one-stroke path
  // Drawn around the dot grid with loops between dots
  const cx = 150
  const cy = 150
  const r1 = 60  // outer loop radius
  const r2 = 30  // inner detail

  // Path encoding a Kolam-like pattern around 5×5 grid
  // This is a representative continuous stroke inspired by kolam19 geometry
  const mainPath = [
    `M ${cx} ${cy - r1}`,
    `C ${cx + r1 * 0.4} ${cy - r1 * 0.9}, ${cx + r1} ${cy - r1 * 0.4}, ${cx + r1} ${cy}`,
    `C ${cx + r1} ${cy + r1 * 0.4}, ${cx + r1 * 0.6} ${cy + r1 * 0.7}, ${cx + r2} ${cy + r2}`,
    `L ${cx - r2} ${cy + r2}`,
    `C ${cx - r1 * 0.6} ${cy + r1 * 0.7}, ${cx - r1} ${cy + r1 * 0.4}, ${cx - r1} ${cy}`,
    `C ${cx - r1} ${cy - r1 * 0.4}, ${cx - r1 * 0.4} ${cy - r1 * 0.9}, ${cx} ${cy - r1}`,
  ].join(' ')

  // Four-fold symmetry loops (simplified representation)
  const loops = [
    // Top loop
    `M ${cx - 30} ${cy - 90} C ${cx - 45} ${cy - 120} ${cx + 45} ${cy - 120} ${cx + 30} ${cy - 90}`,
    // Bottom loop
    `M ${cx - 30} ${cy + 90} C ${cx - 45} ${cy + 120} ${cx + 45} ${cy + 120} ${cx + 30} ${cy + 90}`,
    // Left loop
    `M ${cx - 90} ${cy - 30} C ${cx - 120} ${cy - 45} ${cx - 120} ${cy + 45} ${cx - 90} ${cy + 30}`,
    // Right loop
    `M ${cx + 90} ${cy - 30} C ${cx + 120} ${cy - 45} ${cx + 120} ${cy + 45} ${cx + 90} ${cy + 30}`,
    // Inner cross connections
    `M ${cx - 60} ${cy} L ${cx + 60} ${cy}`,
    `M ${cx} ${cy - 60} L ${cx} ${cy + 60}`,
    // Diagonal details
    `M ${cx - 42} ${cy - 42} L ${cx + 42} ${cy + 42}`,
    `M ${cx + 42} ${cy - 42} L ${cx - 42} ${cy + 42}`,
  ]

  // Outer bounding loops
  const outerLoops = [
    `M ${cx} ${cy - 130} C ${cx - 25} ${cy - 150} ${cx - 50} ${cy - 130} ${cx - 60} ${cy - 90}`,
    `M ${cx} ${cy - 130} C ${cx + 25} ${cy - 150} ${cx + 50} ${cy - 130} ${cx + 60} ${cy - 90}`,
    `M ${cx} ${cy + 130} C ${cx - 25} ${cy + 150} ${cx - 50} ${cy + 130} ${cx - 60} ${cy + 90}`,
    `M ${cx} ${cy + 130} C ${cx + 25} ${cy + 150} ${cx + 50} ${cy + 130} ${cx + 60} ${cy + 90}`,
    `M ${cx - 130} ${cy} C ${cx - 150} ${cy - 25} ${cx - 130} ${cy - 50} ${cx - 90} ${cy - 60}`,
    `M ${cx - 130} ${cy} C ${cx - 150} ${cy + 25} ${cx - 130} ${cy + 50} ${cx - 90} ${cy + 60}`,
    `M ${cx + 130} ${cy} C ${cx + 150} ${cy - 25} ${cx + 130} ${cy - 50} ${cx + 90} ${cy - 60}`,
    `M ${cx + 130} ${cy} C ${cx + 150} ${cy + 25} ${cx + 130} ${cy + 50} ${cx + 90} ${cy + 60}`,
  ]

  return (
    <g className="kolam-canvas__stroke-group">
      {/* Main center path */}
      <path
        d={mainPath}
        stroke="currentColor"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
        className="kolam-canvas__path kolam-canvas__path--main"
      />

      {/* Detail loops */}
      {loops.map((d, i) => (
        <path
          key={i}
          d={d}
          stroke="currentColor"
          strokeWidth="1.2"
          fill="none"
          strokeLinecap="round"
          className="kolam-canvas__path"
          style={{ animationDelay: `${0.4 + i * 0.15}s` }}
        />
      ))}

      {/* Outer loops */}
      {outerLoops.map((d, i) => (
        <path
          key={`outer-${i}`}
          d={d}
          stroke="currentColor"
          strokeWidth="1"
          fill="none"
          strokeLinecap="round"
          className="kolam-canvas__path kolam-canvas__path--outer"
          style={{ animationDelay: `${1.2 + i * 0.1}s` }}
        />
      ))}
    </g>
  )
}

function SymmetryAxes() {
  return (
    <g className="kolam-canvas__axes">
      {/* Vertical axis */}
      <line x1="150" y1="10" x2="150" y2="290" stroke="currentColor" strokeWidth="0.5" strokeDasharray="4 6" />
      {/* Horizontal axis */}
      <line x1="10" y1="150" x2="290" y2="150" stroke="currentColor" strokeWidth="0.5" strokeDasharray="4 6" />
      {/* Diagonal axes */}
      <line x1="50" y1="50" x2="250" y2="250" stroke="currentColor" strokeWidth="0.3" strokeDasharray="3 8" />
      <line x1="250" y1="50" x2="50" y2="250" stroke="currentColor" strokeWidth="0.3" strokeDasharray="3 8" />

      {/* Axis labels */}
      <text x="155" y="16" className="kolam-canvas__axis-label">↕ vertical</text>
      <text x="214" y="148" className="kolam-canvas__axis-label">↔ horizontal</text>
    </g>
  )
}
