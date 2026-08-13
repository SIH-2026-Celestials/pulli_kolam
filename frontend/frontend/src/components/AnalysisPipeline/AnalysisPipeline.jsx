import { Check } from 'lucide-react'
import './AnalysisPipeline.css'

export default function AnalysisPipeline({ customImage, progress = 56 }) {
  const steps = [
    { num: 1, label: 'Upload Image', status: 'completed' },
    { num: 2, label: 'Detect Dots', status: 'completed' },
    { num: 3, label: 'Trace Stroke', status: 'completed' },
    { num: 4, label: 'Build Graph', status: 'active' },
    { num: 5, label: 'Detect Symmetry', status: 'pending' },
    { num: 6, label: 'Find Motifs', status: 'pending' },
    { num: 7, label: 'Validate Stroke', status: 'pending' },
    { num: 8, label: 'Extract Rules', status: 'pending' }
  ]

  return (
    <div className="analysis-card">
      <h2 className="analysis-title">Analyze Your Kolam – Live Process</h2>

      {/* STEPPER BAR */}
      <div className="stepper-container">
        <div className="stepper-line-bg" />
        <div className="stepper-line-active" style={{ width: '42%' }} />

        <div className="stepper-steps">
          {steps.map((step) => (
            <div key={step.num} className={`step-item step-${step.status}`}>
              <div className="step-circle">
                {step.status === 'completed' ? (
                  <Check size={14} strokeWidth={3} />
                ) : (
                  <span>{step.num}</span>
                )}
              </div>
              <span className="step-label">{step.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 5 IMAGE PANELS WITH ARROWS */}
      <div className="pipeline-panels-row">
        {/* PANEL 1: Uploaded Image */}
        <div className="panel-box">
          <div className="panel-img-frame wood-bg">
            {customImage ? (
              <img src={customImage} alt="Uploaded Kolam" className="custom-uploaded-img" />
            ) : (
              <svg width="100%" height="100%" viewBox="0 0 160 160">
                {/* Wood Texture Pattern Simulation */}
                <rect width="160" height="160" fill="#7A5230" />
                <path d="M 0 20 Q 80 30 160 15 M 0 60 Q 80 50 160 70 M 0 100 Q 80 110 160 95 M 0 140 Q 80 135 160 145" stroke="#603E22" strokeWidth="3" opacity="0.6" fill="none" />
                {/* White Traditional Kolam Pattern */}
                <circle cx="80" cy="80" r="4" fill="#FFFFFF" />
                <circle cx="50" cy="50" r="3" fill="#FFFFFF" />
                <circle cx="110" cy="50" r="3" fill="#FFFFFF" />
                <circle cx="50" cy="110" r="3" fill="#FFFFFF" />
                <circle cx="110" cy="110" r="3" fill="#FFFFFF" />
                <path d="M 50 50 Q 80 20 110 50 Q 140 80 110 110 Q 80 140 50 110 Q 20 80 50 50 Z" stroke="#FFFFFF" strokeWidth="2.5" fill="none" />
                <path d="M 80 35 Q 125 35 125 80 Q 125 125 80 125 Q 35 125 35 80 Q 35 35 80 35 Z" stroke="#FFFFFF" strokeWidth="2" strokeDasharray="3 3" fill="none" />
              </svg>
            )}
          </div>
          <span className="panel-caption">Uploaded Image</span>
        </div>

        <span className="panel-arrow">&rarr;</span>

        {/* PANEL 2: Detected Dots */}
        <div className="panel-box">
          <div className="panel-img-frame dark-bg">
            <svg width="100%" height="100%" viewBox="0 0 160 160">
              <rect width="160" height="160" fill="#0C0A09" />
              {/* 5x5 Grid of glowing red dots */}
              {[32, 56, 80, 104, 128].map((y) =>
                [32, 56, 80, 104, 128].map((x) => (
                  <g key={`${x}-${y}`}>
                    <circle cx={x} cy={y} r="4" fill="#FF2A2A" opacity="0.4" />
                    <circle cx={x} cy={y} r="2.5" fill="#FF5555" />
                  </g>
                ))
              )}
            </svg>
          </div>
          <span className="panel-caption">Detected Dots</span>
        </div>

        <span className="panel-arrow">&rarr;</span>

        {/* PANEL 3: Traced Stroke */}
        <div className="panel-box">
          <div className="panel-img-frame dark-bg">
            <svg width="100%" height="100%" viewBox="0 0 160 160">
              <rect width="160" height="160" fill="#0C0A09" />
              {/* Background faint dots */}
              {[32, 56, 80, 104, 128].map((y) =>
                [32, 56, 80, 104, 128].map((x) => (
                  <circle key={`t-${x}-${y}`} cx={x} cy={y} r="1.5" fill="#444444" />
                ))
              )}
              {/* Traced stroke in crisp white */}
              <path
                d="
                  M 80 24
                  C 40 24 32 60 48 80
                  C 24 100 24 136 80 136
                  C 136 136 136 100 112 80
                  C 128 60 120 24 80 24 Z
                "
                stroke="#FFFFFF"
                strokeWidth="2"
                fill="none"
              />
              <path
                d="
                  M 24 80
                  C 24 40 60 32 80 48
                  C 100 24 136 24 136 80
                  C 136 136 100 136 80 112
                  C 60 128 24 120 24 80 Z
                "
                stroke="#FFFFFF"
                strokeWidth="1.8"
                fill="none"
              />
            </svg>
          </div>
          <span className="panel-caption">Traced Stroke</span>
        </div>

        <span className="panel-arrow">&rarr;</span>

        {/* PANEL 4: Graph Representation (ACTIVE PANEL WITH MAROON BORDER) */}
        <div className="panel-box panel-active">
          <div className="panel-img-frame dark-bg">
            <svg width="100%" height="100%" viewBox="0 0 160 160">
              <rect width="160" height="160" fill="#0C0A09" />
              {/* Graph Edges in Red */}
              <g stroke="#E63946" strokeWidth="1.2">
                <line x1="80" y1="32" x2="48" y2="64" />
                <line x1="80" y1="32" x2="112" y2="64" />
                <line x1="48" y1="64" x2="80" y2="96" />
                <line x1="112" y1="64" x2="80" y2="96" />
                <line x1="48" y1="64" x2="24" y2="80" />
                <line x1="112" y1="64" x2="136" y2="80" />
                <line x1="24" y1="80" x2="48" y2="96" />
                <line x1="136" y1="80" x2="112" y2="96" />
                <line x1="48" y1="96" x2="80" y2="128" />
                <line x1="112" y1="96" x2="80" y2="128" />
                <line x1="80" y1="32" x2="80" y2="128" />
                <line x1="24" y1="80" x2="136" y2="80" />
              </g>
              {/* Graph Nodes in White */}
              {[
                { x: 80, y: 32 }, { x: 48, y: 64 }, { x: 112, y: 64 },
                { x: 24, y: 80 }, { x: 80, y: 80 }, { x: 136, y: 80 },
                { x: 48, y: 96 }, { x: 112, y: 96 }, { x: 80, y: 128 }
              ].map((n, i) => (
                <circle key={i} cx={n.x} cy={n.y} r="3" fill="#FFFFFF" stroke="#E63946" strokeWidth="1" />
              ))}
            </svg>
          </div>
          <span className="panel-caption caption-active">Graph Representation</span>
        </div>

        <span className="panel-arrow">&rarr;</span>

        {/* PANEL 5: Symmetry (D4) */}
        <div className="panel-box">
          <div className="panel-img-frame dark-bg">
            <svg width="100%" height="100%" viewBox="0 0 160 160">
              <rect width="160" height="160" fill="#0C0A09" />
              {/* Kolam stroke */}
              <path
                d="M 80 32 C 48 32 32 64 80 128 C 128 64 112 32 80 32 Z"
                stroke="#FFFFFF"
                strokeWidth="1.5"
                fill="none"
              />
              <path
                d="M 32 80 C 32 48 64 32 128 80 C 64 128 32 112 32 80 Z"
                stroke="#FFFFFF"
                strokeWidth="1.5"
                fill="none"
              />
              {/* D4 Symmetry Axes (Dashed Red Lines) */}
              <line x1="80" y1="10" x2="80" y2="150" stroke="#FF4D4D" strokeWidth="1" strokeDasharray="3 3" />
              <line x1="10" y1="80" x2="150" y2="80" stroke="#FF4D4D" strokeWidth="1" strokeDasharray="3 3" />
              <line x1="20" y1="20" x2="140" y2="140" stroke="#FF4D4D" strokeWidth="1" strokeDasharray="3 3" />
              <line x1="140" y1="20" x2="20" y2="140" stroke="#FF4D4D" strokeWidth="1" strokeDasharray="3 3" />
            </svg>
          </div>
          <span className="panel-caption">Symmetry (D4)</span>
        </div>
      </div>

      {/* BOTTOM PROGRESS BOX: BUILDING GRAPH */}
      <div className="building-graph-box">
        <div className="graph-box-text">
          <h3 className="graph-box-title">Building Graph</h3>
          <p className="graph-box-desc">
            Converting the traced stroke into a mathematical graph with nodes and edges.
          </p>
        </div>

        <div className="progress-bar-row">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="progress-percent">{progress}%</span>
        </div>
      </div>
    </div>
  )
}
