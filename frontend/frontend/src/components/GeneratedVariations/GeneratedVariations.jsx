import { useState } from 'react'
import { RotateCw, Grid, GitFork, Infinity as LoopIcon, Flower2, BarChart2 } from 'lucide-react'
import './GeneratedVariations.css'

export default function GeneratedVariations() {
  const [variationIndex, setVariationIndex] = useState(0)

  const handleGenerateMore = () => {
    setVariationIndex((prev) => (prev + 1) % 2)
  }

  // Set 1 of 4 generated Kolams
  const kolamSet1 = [
    // Pattern 1: Diamond 4-Fold Sikku
    (
      <svg width="100%" height="100%" viewBox="0 0 160 160" key="k1">
        <rect width="160" height="160" fill="#0C0A09" />
        {/* Pulli grid */}
        {[40, 60, 80, 100, 120].map((y) =>
          [40, 60, 80, 100, 120].map((x) => (
            <circle key={`p1-${x}-${y}`} cx={x} cy={y} r="2" fill="#FFFFFF" opacity="0.8" />
          ))
        )}
        {/* Loops */}
        <g stroke="#FFFFFF" strokeWidth="1.8" fill="none">
          <path d="M 80 20 C 40 20 40 60 80 60 C 120 60 120 20 80 20 Z" />
          <path d="M 80 140 C 40 140 40 100 80 100 C 120 100 120 140 80 140 Z" />
          <path d="M 20 80 C 20 40 60 40 60 80 C 60 120 20 120 20 80 Z" />
          <path d="M 140 80 C 140 40 100 40 100 80 C 100 120 140 120 140 80 Z" />
          <path d="M 40 40 C 80 20 140 80 80 140 C 20 80 80 20 40 40 Z" />
          <circle cx="80" cy="80" r="14" />
        </g>
      </svg>
    ),
    // Pattern 2: Star 8-Fold Petals
    (
      <svg width="100%" height="100%" viewBox="0 0 160 160" key="k2">
        <rect width="160" height="160" fill="#0C0A09" />
        {[30, 55, 80, 105, 130].map((y) =>
          [30, 55, 80, 105, 130].map((x) => (
            <circle key={`p2-${x}-${y}`} cx={x} cy={y} r="2" fill="#FFFFFF" opacity="0.8" />
          ))
        )}
        <g stroke="#FFFFFF" strokeWidth="1.8" fill="none">
          <path d="M 80 25 L 95 65 L 135 80 L 95 95 L 80 135 L 65 95 L 25 80 L 65 65 Z" />
          <path d="M 80 40 Q 120 40 120 80 Q 120 120 80 120 Q 40 120 40 80 Q 40 40 80 40 Z" />
          <circle cx="80" cy="80" r="8" />
        </g>
      </svg>
    ),
    // Pattern 3: Radial Interlocking Loops
    (
      <svg width="100%" height="100%" viewBox="0 0 160 160" key="k3">
        <rect width="160" height="160" fill="#0C0A09" />
        {[35, 57, 80, 103, 125].map((y) =>
          [35, 57, 80, 103, 125].map((x) => (
            <circle key={`p3-${x}-${y}`} cx={x} cy={y} r="2" fill="#FFFFFF" opacity="0.8" />
          ))
        )}
        <g stroke="#FFFFFF" strokeWidth="1.8" fill="none">
          <path d="M 80 30 C 130 30 130 130 80 130 C 30 130 30 30 80 30 Z" />
          <path d="M 30 80 C 30 130 130 130 130 80 C 130 30 30 30 30 80 Z" />
          <path d="M 50 50 C 110 50 110 110 50 110 C 110 110 110 50 50 50 Z" />
        </g>
      </svg>
    ),
    // Pattern 4: Outer Diamond Lattice
    (
      <svg width="100%" height="100%" viewBox="0 0 160 160" key="k4">
        <rect width="160" height="160" fill="#0C0A09" />
        {[30, 55, 80, 105, 130].map((y) =>
          [30, 55, 80, 105, 130].map((x) => (
            <circle key={`p4-${x}-${y}`} cx={x} cy={y} r="2" fill="#FFFFFF" opacity="0.8" />
          ))
        )}
        <g stroke="#FFFFFF" strokeWidth="1.8" fill="none">
          <path d="M 80 15 L 145 80 L 80 145 L 15 80 Z" />
          <path d="M 80 35 L 125 80 L 80 125 L 35 80 Z" />
          <path d="M 80 55 L 105 80 L 80 105 L 55 80 Z" />
          <circle cx="80" cy="80" r="4" fill="#FFFFFF" />
        </g>
      </svg>
    )
  ]

  // Set 2 of 4 generated Kolams (alternate when clicking Generate More)
  const kolamSet2 = [
    (
      <svg width="100%" height="100%" viewBox="0 0 160 160" key="k5">
        <rect width="160" height="160" fill="#0C0A09" />
        {[30, 55, 80, 105, 130].map((y) =>
          [30, 55, 80, 105, 130].map((x) => (
            <circle key={`p5-${x}-${y}`} cx={x} cy={y} r="2" fill="#FFFFFF" opacity="0.8" />
          ))
        )}
        <g stroke="#FFFFFF" strokeWidth="1.8" fill="none">
          <circle cx="80" cy="80" r="50" strokeDasharray="6 4" />
          <path d="M 80 20 L 140 80 L 80 140 L 20 80 Z" />
          <path d="M 50 20 Q 80 80 110 20 M 140 50 Q 80 80 140 110 M 110 140 Q 80 80 50 140 M 20 110 Q 80 80 20 50" />
        </g>
      </svg>
    ),
    (
      <svg width="100%" height="100%" viewBox="0 0 160 160" key="k6">
        <rect width="160" height="160" fill="#0C0A09" />
        {[30, 55, 80, 105, 130].map((y) =>
          [30, 55, 80, 105, 130].map((x) => (
            <circle key={`p6-${x}-${y}`} cx={x} cy={y} r="2" fill="#FFFFFF" opacity="0.8" />
          ))
        )}
        <g stroke="#FFFFFF" strokeWidth="1.8" fill="none">
          <path d="M 80 25 C 135 25 135 135 80 135 C 25 135 25 25 80 25 Z" />
          <path d="M 80 45 C 115 45 115 115 80 115 C 45 115 45 45 80 45 Z" />
          <circle cx="80" cy="80" r="10" />
        </g>
      </svg>
    ),
    (
      <svg width="100%" height="100%" viewBox="0 0 160 160" key="k7">
        <rect width="160" height="160" fill="#0C0A09" />
        {[30, 55, 80, 105, 130].map((y) =>
          [30, 55, 80, 105, 130].map((x) => (
            <circle key={`p7-${x}-${y}`} cx={x} cy={y} r="2" fill="#FFFFFF" opacity="0.8" />
          ))
        )}
        <g stroke="#FFFFFF" strokeWidth="1.8" fill="none">
          <path d="M 40 40 L 120 40 L 120 120 L 40 120 Z" />
          <path d="M 80 20 L 140 80 L 80 140 L 20 80 Z" />
        </g>
      </svg>
    ),
    (
      <svg width="100%" height="100%" viewBox="0 0 160 160" key="k8">
        <rect width="160" height="160" fill="#0C0A09" />
        {[30, 55, 80, 105, 130].map((y) =>
          [30, 55, 80, 105, 130].map((x) => (
            <circle key={`p8-${x}-${y}`} cx={x} cy={y} r="2" fill="#FFFFFF" opacity="0.8" />
          ))
        )}
        <g stroke="#FFFFFF" strokeWidth="1.8" fill="none">
          <path d="M 80 30 Q 130 80 80 130 Q 30 80 80 30 Z" />
          <path d="M 30 80 Q 80 30 130 80 Q 80 130 30 80 Z" />
        </g>
      </svg>
    )
  ]

  const activeSet = variationIndex === 0 ? kolamSet1 : kolamSet2

  return (
    <div className="generated-card">
      {/* HEADER ROW */}
      <div className="generated-header-row">
        <div className="generated-title-group">
          <h2 className="generated-title">Generated Kolam Variations</h2>
          <p className="generated-subtitle">Generated using the extracted design rules</p>
        </div>

        <button className="btn-generate-more" onClick={handleGenerateMore}>
          <RotateCw size={14} className="refresh-icon" />
          <span>Generate More</span>
        </button>
      </div>

      {/* 4 THUMBNAILS GRID */}
      <div className="variations-grid">
        {activeSet.map((kolamSvg, i) => (
          <div key={i} className="variation-thumb-box">
            {kolamSvg}
          </div>
        ))}
      </div>

      {/* DESIGN RULE SUMMARY */}
      <div className="rule-summary-container">
        <h3 className="rule-summary-title">Design Rule Summary</h3>

        <div className="rule-metrics-row">
          <div className="metric-col">
            <Grid size={18} className="metric-icon" />
            <div className="metric-text-box">
              <span className="metric-label">Grid</span>
              <span className="metric-val">7 &times; 7 Pulli</span>
            </div>
          </div>

          <div className="metric-col">
            <GitFork size={18} className="metric-icon" />
            <div className="metric-text-box">
              <span className="metric-label">Symmetry</span>
              <span className="metric-val">D4</span>
            </div>
          </div>

          <div className="metric-col">
            <LoopIcon size={18} className="metric-icon" />
            <div className="metric-text-box">
              <span className="metric-label">Stroke</span>
              <span className="metric-val">Single Continuous</span>
            </div>
          </div>

          <div className="metric-col">
            <Flower2 size={18} className="metric-icon" />
            <div className="metric-text-box">
              <span className="metric-label">Motif Families</span>
              <span className="metric-val">4</span>
            </div>
          </div>

          <div className="metric-col">
            <BarChart2 size={18} className="metric-icon" />
            <div className="metric-text-box">
              <span className="metric-label">Complexity</span>
              <span className="metric-val">Medium</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
