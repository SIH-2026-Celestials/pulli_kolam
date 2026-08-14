import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Play, Pause, RefreshCw, Download, Sparkles, Sliders, ShieldCheck, Save, Eye } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import './Playground.css'

export default function Playground() {
  const { addRecentKolam } = useAuth()

  // Control State
  const [gridSize, setGridSize] = useState(5) // 3 to 11
  const [tileSize, setTileSize] = useState(45)
  const [margin, setMargin] = useState(15)
  const [symmetry, setSymmetry] = useState('D4') // 'D4' | 'C4' | 'D2' | 'Random'
  const [lineStyle, setLineStyle] = useState('smooth') // 'smooth' | 'angular' | 'double'
  const [strokeColor, setStrokeColor] = useState('#E6B800') // Kolam gold
  const [bgColor, setBgColor] = useState('#121212') // Dark canvas
  const [isPlaying, setIsPlaying] = useState(false)
  const [refreshSpeed, setRefreshSpeed] = useState(3000) // ms
  const [seed, setSeed] = useState(101)

  const canvasRef = useRef(null)

  // Regenerate Seed
  const handleRegenerate = () => {
    setSeed(Math.floor(Math.random() * 100000))
  }

  // Draw Kolam on Canvas
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const padding = margin * 2
    const canvasWidth = gridSize * tileSize + padding * 2
    const canvasHeight = gridSize * tileSize + padding * 2

    canvas.width = canvasWidth
    canvas.height = canvasHeight

    // Fill background
    ctx.fillStyle = bgColor
    ctx.fillRect(0, 0, canvasWidth, canvasHeight)

    // Pseudo-random helper from seed
    let currentSeed = seed
    const pseudoRandom = () => {
      currentSeed = (currentSeed * 9301 + 49297) % 233280
      return currentSeed / 233280
    }

    // Generate random tile connection matrix for quadrant
    const halfGrid = Math.ceil(gridSize / 2)
    const connections = {}

    for (let r = 0; r < halfGrid; r++) {
      for (let c = 0; c < halfGrid; c++) {
        connections[`${r}_${c}`] = {
          top: pseudoRandom() > 0.4,
          right: pseudoRandom() > 0.4,
          bottom: pseudoRandom() > 0.4,
          left: pseudoRandom() > 0.4,
        }
      }
    }

    // Helper to get connection with symmetry mapping
    const getTileConnection = (r, c) => {
      let mappedR = r
      let mappedC = c

      if (symmetry === 'D4' || symmetry === 'C4' || symmetry === 'D2') {
        if (r >= halfGrid) mappedR = gridSize - 1 - r
        if (c >= halfGrid) mappedC = gridSize - 1 - c
      }

      return connections[`${mappedR}_${mappedC}`] || { top: true, right: true, bottom: true, left: true }
    }

    // 1. Draw Dot Lattice
    ctx.fillStyle = '#FFFFFF'
    for (let r = 0; r < gridSize; r++) {
      for (let c = 0; c < gridSize; c++) {
        const x = padding + c * tileSize + tileSize / 2
        const y = padding + r * tileSize + tileSize / 2

        ctx.beginPath()
        ctx.arc(x, y, 3.5, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    // 2. Draw Interlocking Loop Strands
    ctx.strokeStyle = strokeColor
    ctx.lineWidth = lineStyle === 'double' ? 2 : 3
    ctx.lineCap = 'round'

    for (let r = 0; r < gridSize; r++) {
      for (let c = 0; c < gridSize; c++) {
        const x = padding + c * tileSize + tileSize / 2
        const y = padding + r * tileSize + tileSize / 2
        const conn = getTileConnection(r, c)
        const radius = tileSize * 0.4

        ctx.beginPath()

        if (lineStyle === 'angular') {
          // Sharp diamond loop style
          if (conn.top) { ctx.moveTo(x, y - radius); ctx.lineTo(x + radius, y) }
          if (conn.right) { ctx.moveTo(x + radius, y); ctx.lineTo(x, y + radius) }
          if (conn.bottom) { ctx.moveTo(x, y + radius); ctx.lineTo(x - radius, y) }
          if (conn.left) { ctx.moveTo(x - radius, y); ctx.lineTo(x, y - radius) }
        } else {
          // Smooth curved arc loops around dots
          ctx.arc(x, y, radius, 0, Math.PI * 2)
        }

        ctx.stroke()

        if (lineStyle === 'double') {
          ctx.beginPath()
          ctx.arc(x, y, radius * 0.6, 0, Math.PI * 2)
          ctx.stroke()
        }
      }
    }
  }, [gridSize, tileSize, margin, symmetry, lineStyle, strokeColor, bgColor, seed])

  // Auto-play timer
  useEffect(() => {
    let timer
    if (isPlaying) {
      timer = setInterval(() => {
        handleRegenerate()
      }, refreshSpeed)
    }
    return () => clearInterval(timer)
  }, [isPlaying, refreshSpeed])

  // Download Canvas Image
  const handleDownload = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const link = document.createElement('a')
    link.download = `kolam_playground_${gridSize}x${gridSize}_${seed}.png`
    link.href = canvas.toDataURL()
    link.click()
  }

  // Save to Recent History
  const handleSaveToHistory = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    addRecentKolam({
      id: `pg_${seed}`,
      title: `Playground ${gridSize}×${gridSize} (${symmetry})`,
      image_url: canvas.toDataURL(),
      grid_size: `${gridSize}×${gridSize}`,
      symmetry: `${symmetry} Symmetry`,
      validity: '✓ Interactive Generative',
    })
    alert('Saved to Recent History!')
  }

  return (
    <main className="playground-page">
      <header className="playground-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">INTERACTIVE GENERATIVE ENGINE</p>
          <h1 className="heading-display heading-hero">Kolam Design Playground</h1>
          <p className="body-text playground-sub">
            Experiment with algorithmic loop permutations, dot-grid resolution, and geometric symmetry in real-time.
          </p>
        </div>
      </header>

      <section className="playground-body container">
        <div className="playground-layout">
          {/* Controls Sidebar */}
          <aside className="playground-controls archival-frame">
            <div className="controls-header">
              <Sliders size={18} className="icon-accent" />
              <h3 className="heading-display heading-4">Pattern Parameters</h3>
            </div>

            <div className="control-group">
              <label className="label-tech">GRID RESOLUTION ({gridSize}×{gridSize})</label>
              <input
                type="range"
                min="3"
                max="11"
                step="2"
                value={gridSize}
                onChange={(e) => setGridSize(Number(e.target.value))}
                className="slider-range"
              />
            </div>

            <div className="control-group">
              <label className="label-tech">TILE SIZE ({tileSize}px)</label>
              <input
                type="range"
                min="30"
                max="75"
                value={tileSize}
                onChange={(e) => setTileSize(Number(e.target.value))}
                className="slider-range"
              />
            </div>

            <div className="control-group">
              <label className="label-tech">CANVAS MARGIN ({margin}px)</label>
              <input
                type="range"
                min="5"
                max="40"
                value={margin}
                onChange={(e) => setMargin(Number(e.target.value))}
                className="slider-range"
              />
            </div>

            <div className="control-group">
              <label className="label-tech">SYMMETRY ALGORITHM</label>
              <select
                value={symmetry}
                onChange={(e) => setSymmetry(e.target.value)}
                className="input-select"
              >
                <option value="D4">D4 Dihedral (8-Fold)</option>
                <option value="C4">C4 Rotational (4-Fold)</option>
                <option value="D2">D2 Mirror Symmetry</option>
                <option value="Random">Freehand Random</option>
              </select>
            </div>

            <div className="control-group">
              <label className="label-tech">STRAND STYLE</label>
              <select
                value={lineStyle}
                onChange={(e) => setLineStyle(e.target.value)}
                className="input-select"
              >
                <option value="smooth">Smooth Curved Arcs</option>
                <option value="angular">Diamond Angular</option>
                <option value="double">Double Strand Loop</option>
              </select>
            </div>

            <div className="control-row">
              <div className="control-group flex-1">
                <label className="label-tech">STROKE</label>
                <input
                  type="color"
                  value={strokeColor}
                  onChange={(e) => setStrokeColor(e.target.value)}
                  className="input-color"
                />
              </div>

              <div className="control-group flex-1">
                <label className="label-tech">CANVAS BG</label>
                <input
                  type="color"
                  value={bgColor}
                  onChange={(e) => setBgColor(e.target.value)}
                  className="input-color"
                />
              </div>
            </div>

            <div className="control-group">
              <label className="label-tech">AUTO REFRESH RATE ({refreshSpeed / 1000}s)</label>
              <input
                type="range"
                min="1000"
                max="5000"
                step="500"
                value={refreshSpeed}
                onChange={(e) => setRefreshSpeed(Number(e.target.value))}
                className="slider-range"
              />
            </div>

            <div className="action-buttons-group">
              <button
                className="btn btn--primary btn--full"
                onClick={handleRegenerate}
              >
                <RefreshCw size={16} />
                <span>Regenerate Pattern</span>
              </button>

              <button
                className={`btn btn--outline btn--full ${isPlaying ? 'btn--active-play' : ''}`}
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                <span>{isPlaying ? 'Pause Auto-Generate' : 'Play Auto-Generate'}</span>
              </button>
            </div>
          </aside>

          {/* Canvas Display Viewport */}
          <div className="playground-viewport archival-frame">
            <div className="viewport-header">
              <div className="viewport-meta label-tech">
                <span>SEED: #{seed}</span>
                <span className="dot-sep">•</span>
                <span>{gridSize}×{gridSize} LATTICE</span>
                <span className="dot-sep">•</span>
                <span>{symmetry} SYMMETRY</span>
              </div>

              <div className="viewport-actions">
                <button
                  className="btn-icon-action"
                  onClick={handleSaveToHistory}
                  title="Save to History"
                >
                  <Save size={16} />
                  <span>Save</span>
                </button>

                <button
                  className="btn-icon-action"
                  onClick={handleDownload}
                  title="Download Image"
                >
                  <Download size={16} />
                  <span>Export PNG</span>
                </button>
              </div>
            </div>

            <div className="canvas-wrapper">
              <canvas ref={canvasRef} className="kolam-canvas" />
            </div>

            <div className="viewport-footer">
              <p className="body-text body-text--sm">
                Generated using P5/HTML5 Canvas matrix permutations based on classical Pulli Kolam loop continuous-stroke rules.
              </p>
              <Link to="/analyze" className="link-analyze label-tech">
                <Eye size={14} /> Run Deep AI Analysis →
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
