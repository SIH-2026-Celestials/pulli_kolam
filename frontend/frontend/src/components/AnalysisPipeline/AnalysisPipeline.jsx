import { useRef } from 'react'
import { Check, X, Loader2 } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { KOLAM_STAGES } from '../../lib/analysisStages'
import './AnalysisPipeline.css'

/**
 * AnalysisPipeline — renders the 8-stage stepper driven by real SSE
 * events from the backend.
 *
 * Props:
 *   analysisState  — object from useKolamAnalysis().analysisState
 *   onUpload       — called with (File, detector) when user selects an image
 *   detector       — 'classical' | 'ml'
 *   onDetectorChange — called with new detector string
 *
 * When analysisState is null/undefined the component renders the
 * upload prompt (idle state), exactly preserving the original card
 * appearance.
 */
export default function AnalysisPipeline({
  analysisState,
  onUpload,
  detector = 'classical',
  onDetectorChange,
}) {
  const { t } = useLanguage()
  const fileInputRef = useRef(null)

  const status = analysisState?.status ?? 'idle'
  const stages = analysisState?.stages ?? KOLAM_STAGES.map((s) => ({
    id: s.id, label: s.label, status: 'pending', message: null, result: null,
  }))
  const currentStage = analysisState?.currentStage ?? -1
  const activeMessage = analysisState?.activeMessage ?? null
  const error = analysisState?.error ?? null

  // Completed stages count (for the progress line width)
  const completedCount = stages.filter((s) => s.status === 'completed').length
  const totalStages = KOLAM_STAGES.length
  // The progress line spans from stage 0 to the last completed/running
  const progressPct = totalStages <= 1
    ? 0
    : Math.min(100, Math.round((completedCount / (totalStages - 1)) * 100))

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file && onUpload) onUpload(file, detector)
    // Reset input so the same file can be re-selected
    e.target.value = ''
  }

  // Results from specific completed stages
  const detectResult = analysisState?.results?.detect_dots
  const graphResult = analysisState?.results?.build_graph
  const validityResult = analysisState?.results?.validate_stroke
  const motifResult = analysisState?.results?.find_motifs

  return (
    <div className="analysis-card">
      <div className="analysis-card-top-row">
        <h2 className="analysis-title">{t('analysis.title')}</h2>

        {/* Detector selector — only visible when idle or after completion */}
        {(status === 'idle' || status === 'completed' || status === 'failed') && onDetectorChange && (
          <div className="pipeline-detector-select">
            <label className="pipeline-detector-label" htmlFor="pipeline-detector">Detector:</label>
            <select
              id="pipeline-detector"
              className="pipeline-detector-dropdown"
              value={detector}
              onChange={(e) => onDetectorChange(e.target.value)}
            >
              <option value="classical">Classical</option>
              <option value="ml">ML (Experimental)</option>
            </select>
          </div>
        )}
      </div>

      {/* ── STEPPER BAR ─────────────────────────────────────────────── */}
      <div className="stepper-container">
        <div className="stepper-line-bg" />
        <div className="stepper-line-active" style={{ width: `calc((100% - 90px) * ${progressPct / 100})` }} />

        <div className="stepper-steps">
          {stages.map((stage, idx) => (
            <div key={stage.id} className={`step-item step-${stage.status}`}>
              <div className="step-circle">
                {stage.status === 'completed' && <Check size={13} strokeWidth={3} />}
                {stage.status === 'failed' && <X size={13} strokeWidth={3} />}
                {stage.status === 'running' && <Loader2 size={13} className="step-spinner" />}
                {stage.status === 'pending' && <span>{idx + 1}</span>}
              </div>
              <span className="step-label">{stage.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── 5 ILLUSTRATION PANELS ───────────────────────────────────── */}
      <div className="pipeline-panels-row">
        {/* Panel 1: Uploaded Image */}
        <div className={`panel-box ${stages[0]?.status === 'completed' || stages[0]?.status === 'running' ? 'panel-active' : ''}`}>
          <div className="panel-img-frame wood-bg">
            {analysisState?.uploadedPreview ? (
              <img src={analysisState.uploadedPreview} alt="Uploaded Kolam" className="custom-uploaded-img" />
            ) : (
              <svg width="100%" height="100%" viewBox="0 0 160 160">
                <rect width="160" height="160" fill="#7A5230" />
                <path d="M 0 20 Q 80 30 160 15 M 0 60 Q 80 50 160 70 M 0 100 Q 80 110 160 95 M 0 140 Q 80 135 160 145" stroke="#603E22" strokeWidth="3" opacity="0.6" fill="none" />
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
          <span className={`panel-caption ${stages[0]?.status === 'running' ? 'caption-active' : ''}`}>
            {t('analysis.uploadedImage')}
          </span>
        </div>

        <span className="panel-arrow">&rarr;</span>

        {/* Panel 2: Detected Dots */}
        <div className={`panel-box ${stages[1]?.status === 'running' || stages[1]?.status === 'completed' ? 'panel-active' : ''}`}>
          <div className="panel-img-frame dark-bg">
            <svg width="100%" height="100%" viewBox="0 0 160 160">
              <rect width="160" height="160" fill="#0C0A09" />
              {[32, 56, 80, 104, 128].map((y) =>
                [32, 56, 80, 104, 128].map((x) => (
                  <g key={`${x}-${y}`}>
                    <circle cx={x} cy={y} r="4" fill="#FF2A2A" opacity={stages[1]?.status === 'completed' ? '0.4' : '0.15'} />
                    <circle cx={x} cy={y} r="2.5" fill={stages[1]?.status === 'completed' ? '#FF5555' : '#333'} />
                  </g>
                ))
              )}
              {detectResult && (
                <text x="80" y="150" textAnchor="middle" fill="#FF5555" fontSize="9" fontFamily="monospace">
                  {detectResult.dot_count} dots
                </text>
              )}
            </svg>
          </div>
          <span className={`panel-caption ${stages[1]?.status === 'running' ? 'caption-active' : ''}`}>
            {t('analysis.detectedDots')}
          </span>
        </div>

        <span className="panel-arrow">&rarr;</span>

        {/* Panel 3: Traced Stroke */}
        <div className={`panel-box ${stages[2]?.status === 'running' || stages[2]?.status === 'completed' ? 'panel-active' : ''}`}>
          <div className="panel-img-frame dark-bg">
            <svg width="100%" height="100%" viewBox="0 0 160 160">
              <rect width="160" height="160" fill="#0C0A09" />
              {[32, 56, 80, 104, 128].map((y) =>
                [32, 56, 80, 104, 128].map((x) => (
                  <circle key={`t-${x}-${y}`} cx={x} cy={y} r="1.5" fill="#333" />
                ))
              )}
              <path
                d="M 80 24 C 40 24 32 60 48 80 C 24 100 24 136 80 136 C 136 136 136 100 112 80 C 128 60 120 24 80 24 Z"
                stroke={stages[2]?.status === 'completed' ? '#FFFFFF' : '#444'}
                strokeWidth="2"
                fill="none"
              />
              <path
                d="M 24 80 C 24 40 60 32 80 48 C 100 24 136 24 136 80 C 136 136 100 136 80 112 C 60 128 24 120 24 80 Z"
                stroke={stages[2]?.status === 'completed' ? '#FFFFFF' : '#444'}
                strokeWidth="1.8"
                fill="none"
              />
            </svg>
          </div>
          <span className={`panel-caption ${stages[2]?.status === 'running' ? 'caption-active' : ''}`}>
            {t('analysis.tracedStroke')}
          </span>
        </div>

        <span className="panel-arrow">&rarr;</span>

        {/* Panel 4: Graph — highlight when build_graph is active/complete */}
        <div className={`panel-box ${stages[3]?.status === 'running' || stages[3]?.status === 'completed' ? 'panel-active' : ''}`}>
          <div className="panel-img-frame dark-bg">
            <svg width="100%" height="100%" viewBox="0 0 160 160">
              <rect width="160" height="160" fill="#0C0A09" />
              <g stroke={stages[3]?.status === 'completed' || stages[3]?.status === 'running' ? '#E63946' : '#333'} strokeWidth="1.2">
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
              {[{ x: 80, y: 32 }, { x: 48, y: 64 }, { x: 112, y: 64 },
                { x: 24, y: 80 }, { x: 80, y: 80 }, { x: 136, y: 80 },
                { x: 48, y: 96 }, { x: 112, y: 96 }, { x: 80, y: 128 }
              ].map((n, i) => (
                <circle key={i} cx={n.x} cy={n.y} r="3"
                  fill={stages[3]?.status !== 'pending' ? '#FFFFFF' : '#444'}
                  stroke={stages[3]?.status !== 'pending' ? '#E63946' : '#555'}
                  strokeWidth="1" />
              ))}
              {graphResult && (
                <text x="80" y="150" textAnchor="middle" fill="#E63946" fontSize="8" fontFamily="monospace">
                  {graphResult.nodes}N · {graphResult.edges}E
                </text>
              )}
            </svg>
          </div>
          <span className={`panel-caption ${stages[3]?.status === 'running' ? 'caption-active' : ''}`}>
            {t('analysis.graphRepresentation')}
          </span>
        </div>

        <span className="panel-arrow">&rarr;</span>

        {/* Panel 5: Symmetry */}
        <div className={`panel-box ${stages[4]?.status === 'running' || stages[4]?.status === 'completed' ? 'panel-active' : ''}`}>
          <div className="panel-img-frame dark-bg">
            <svg width="100%" height="100%" viewBox="0 0 160 160">
              <rect width="160" height="160" fill="#0C0A09" />
              <path d="M 80 32 C 48 32 32 64 80 128 C 128 64 112 32 80 32 Z"
                stroke={stages[4]?.status !== 'pending' ? '#FFFFFF' : '#333'}
                strokeWidth="1.5" fill="none" />
              <path d="M 32 80 C 32 48 64 32 128 80 C 64 128 32 112 32 80 Z"
                stroke={stages[4]?.status !== 'pending' ? '#FFFFFF' : '#333'}
                strokeWidth="1.5" fill="none" />
              <line x1="80" y1="10" x2="80" y2="150"
                stroke={stages[4]?.status !== 'pending' ? '#FF4D4D' : '#333'}
                strokeWidth="1" strokeDasharray="3 3" />
              <line x1="10" y1="80" x2="150" y2="80"
                stroke={stages[4]?.status !== 'pending' ? '#FF4D4D' : '#333'}
                strokeWidth="1" strokeDasharray="3 3" />
              <line x1="20" y1="20" x2="140" y2="140"
                stroke={stages[4]?.status !== 'pending' ? '#FF4D4D' : '#333'}
                strokeWidth="1" strokeDasharray="3 3" />
              <line x1="140" y1="20" x2="20" y2="140"
                stroke={stages[4]?.status !== 'pending' ? '#FF4D4D' : '#333'}
                strokeWidth="1" strokeDasharray="3 3" />
            </svg>
          </div>
          <span className={`panel-caption ${stages[4]?.status === 'running' ? 'caption-active' : ''}`}>
            {t('analysis.symmetryD4')}
          </span>
        </div>
      </div>

      {/* ── BOTTOM STATUS BOX ────────────────────────────────────────── */}
      {status === 'idle' && (
        <div className="building-graph-box pipeline-upload-prompt">
          <div className="graph-box-text">
            <h3 className="graph-box-title">Try it live</h3>
            <p className="graph-box-desc">
              Upload a Kolam photo to run the real ML pipeline and watch each stage complete in real time.
            </p>
          </div>
          <div className="pipeline-upload-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/bmp"
              hidden
              onChange={handleFileChange}
            />
            <button
              className="btn-primary pipeline-upload-btn"
              onClick={() => fileInputRef.current?.click()}
            >
              Upload Image
            </button>
          </div>
        </div>
      )}

      {status === 'uploading' && (
        <div className="building-graph-box">
          <div className="graph-box-text">
            <h3 className="graph-box-title">Uploading…</h3>
            <p className="graph-box-desc">Sending image to the analysis server.</p>
          </div>
          <Loader2 size={22} className="pipeline-spinner-icon" />
        </div>
      )}

      {status === 'running' && (
        <div className="building-graph-box">
          <div className="graph-box-text">
            <h3 className="graph-box-title">
              {stages[currentStage]?.label ?? t('analysis.buildingGraph')}
            </h3>
            <p className="graph-box-desc">
              {activeMessage || stages[currentStage]?.message || ''}
            </p>
          </div>
          <div className="progress-bar-row">
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progressPct}%` }} />
            </div>
            <span className="progress-percent">{progressPct}%</span>
          </div>
        </div>
      )}

      {status === 'completed' && (
        <div className="building-graph-box pipeline-done-box">
          <div className="graph-box-text">
            <h3 className="graph-box-title pipeline-done-title">
              ✓ Analysis complete
            </h3>
            <p className="graph-box-desc">
              {detectResult ? `${detectResult.dot_count} dots · ` : ''}
              {motifResult ? `${motifResult.motif_count} motifs · ` : ''}
              {validityResult?.is_eulerian_circuit ? 'Valid Eulerian circuit' : validityResult ? 'No Eulerian circuit' : ''}
            </p>
          </div>
          <button className="btn-secondary pipeline-reset-btn" onClick={() => window.location.reload()}>
            Analyze another
          </button>
        </div>
      )}

      {status === 'failed' && (
        <div className="building-graph-box pipeline-error-box">
          <div className="graph-box-text">
            <h3 className="graph-box-title pipeline-error-title">Analysis failed</h3>
            <p className="graph-box-desc">{error}</p>
          </div>
          <div className="pipeline-upload-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/bmp"
              hidden
              onChange={handleFileChange}
            />
            <button
              className="btn-secondary pipeline-upload-btn"
              onClick={() => fileInputRef.current?.click()}
            >
              Try again
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
