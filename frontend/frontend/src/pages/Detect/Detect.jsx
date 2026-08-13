import { useCallback, useEffect, useRef, useState } from 'react'
import { detect, analyze, reconstruct, compareDetectors, getModelInfo } from '../../lib/api/kolam'
import { categorizeCompareDots } from '../../lib/api/kolam'
import './Detect.css'

const MODES = [
  { id: 'classical', label: 'Classical' },
  { id: 'ml', label: 'ML' },
  { id: 'compare', label: 'Compare' },
]

export default function Detect() {
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [mode, setMode] = useState('classical')
  const [status, setStatus] = useState('idle') // idle | loading | success | error
  const [stage, setStage] = useState(null) // detecting | analyzing | reconstructing (only while status === 'loading')
  const [errorMsg, setErrorMsg] = useState(null)
  const [detectResult, setDetectResult] = useState(null)
  const [compareResult, setCompareResult] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [reconstruction, setReconstruction] = useState(null)
  const [imgNaturalSize, setImgNaturalSize] = useState(null)
  const [imgRenderedSize, setImgRenderedSize] = useState(null)
  const imgRef = useRef(null)
  const fileInputRef = useRef(null)
  // 'loading' | 'available' | 'unavailable' -- reflects GET /api/v1/model,
  // not merely whether this frontend code exists.
  const [modelStatus, setModelStatus] = useState('loading')
  const [modelInfo, setModelInfo] = useState(null)

  useEffect(() => {
    let cancelled = false
    getModelInfo().then(({ data }) => {
      if (cancelled) return
      if (data && data.ml_checkpoint_exists) {
        setModelInfo(data)
        setModelStatus('available')
      } else {
        setModelStatus('unavailable')
      }
    })
    return () => { cancelled = true }
  }, [])

  const onFileSelected = useCallback((f) => {
    if (!f) return
    setFile(f)
    setPreviewUrl(URL.createObjectURL(f))
    setDetectResult(null)
    setCompareResult(null)
    setAnalysis(null)
    setReconstruction(null)
    setStatus('idle')
    setStage(null)
    setErrorMsg(null)
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0]
    if (f) onFileSelected(f)
  }, [onFileSelected])

  const onImageLoad = () => {
    const img = imgRef.current
    if (!img) return
    setImgNaturalSize({ width: img.naturalWidth, height: img.naturalHeight })
    setImgRenderedSize({ width: img.clientWidth, height: img.clientHeight })
  }

  const handleAnalyze = async () => {
    if (!file) return
    setStatus('loading')
    setErrorMsg(null)
    setDetectResult(null)
    setCompareResult(null)
    setAnalysis(null)
    setReconstruction(null)

    if (mode === 'compare') {
      setStage('detecting')
      const { data, error } = await compareDetectors(file)
      if (error) {
        setStatus('error')
        setStage(null)
        setErrorMsg(describeError(error))
        return
      }
      setCompareResult(data)
      setStatus('success')
      setStage(null)
      return
    }

    setStage('detecting')
    const { data, error } = await detect(file, mode)
    if (error) {
      setStatus('error')
      setStage(null)
      setErrorMsg(describeError(error))
      return
    }
    setDetectResult(data)

    setStage('analyzing')
    const { data: analyzeData, error: analyzeError } = await analyze(file, mode)
    if (analyzeError) {
      // Detection succeeded but analysis failed -- still show the real
      // detection result rather than discarding it; report analysis
      // failure honestly instead of pretending nothing happened.
      setStatus('error')
      setStage(null)
      setErrorMsg(describeError(analyzeError))
      return
    }
    setAnalysis(analyzeData)

    setStage('reconstructing')
    const { data: reconstructData, error: reconstructError } = await reconstruct(file, mode)
    // Reconstruction is best-effort: an uploaded photo may not carry
    // enough structure to reconstruct even when detection/analysis
    // succeeded. Never fabricate a result -- an error or an explicit
    // "nothing to reconstruct" note is shown as-is, not hidden.
    if (reconstructData) setReconstruction(reconstructData)
    else if (reconstructError) setReconstruction({ error: describeError(reconstructError) })

    setStage(null)
    setStatus('success')
  }

  const scale = imgNaturalSize && imgRenderedSize ? imgRenderedSize.width / imgNaturalSize.width : 1

  return (
    <main id="main-content" className="detect-page">
      <header className="detect-header section section--bordered">
        <div className="container">
          <p className="eyebrow eyebrow--accent">Live Detection Workflow</p>
          <h1 className="heading-display heading-hero detect-title">Detect &amp; Analyze a Kolam</h1>
          <p className="body-text detect-sub">
            Upload a photograph of a Pulli Kolam. Choose the classical deterministic detector, the experimental
            ML detector (M4.2, 128&times;128), or run both side by side.
          </p>
        </div>
      </header>

      <section className="container section detect-body-section">
        <div className="detect-grid">
          {/* UPLOAD PANEL */}
          <div className="detect-upload-panel archival-frame">
            <div
              className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              {previewUrl ? (
                <div className="preview-wrapper">
                  <img
                    ref={imgRef}
                    src={previewUrl}
                    alt="Uploaded Kolam"
                    onLoad={onImageLoad}
                    className="preview-img"
                  />
                  <DotOverlay
                    mode={mode}
                    detectResult={detectResult}
                    compareResult={compareResult}
                    scale={scale}
                  />
                </div>
              ) : (
                <p className="dropzone-label label-tech">Drag &amp; drop an image, or click to browse</p>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/bmp"
              hidden
              onChange={(e) => onFileSelected(e.target.files?.[0])}
            />

            <div className="detector-selector">
              <span className="label-tech">DETECTOR:</span>
              <div className="detector-radios">
                {MODES.map((m) => (
                  <label key={m.id} className={`detector-radio ${mode === m.id ? 'detector-radio--active' : ''}`}>
                    <input
                      type="radio"
                      name="detector"
                      value={m.id}
                      checked={mode === m.id}
                      onChange={() => setMode(m.id)}
                    />
                    {m.label}
                  </label>
                ))}
              </div>
            </div>

            <p className="label-tech model-status-line">
              ML MODEL: {modelStatus === 'loading' && '…'}
              {modelStatus === 'available' && (
                <span className="text-valid">● Available{modelInfo?.ml_model_version ? ` — ${modelInfo.ml_model_version}` : ''} (CPU)</span>
              )}
              {modelStatus === 'unavailable' && <span>○ Unavailable</span>}
            </p>

            <button className="btn-primary analyze-btn" disabled={!file || status === 'loading'} onClick={handleAnalyze}>
              {status === 'loading' ? stageLabel(stage) : 'Analyze Kolam'}
            </button>

            {status === 'error' && (
              <p className="detect-error" role="alert">{errorMsg}</p>
            )}
          </div>

          {/* RESULT PANEL */}
          <div className="detect-result-panel">
            {status === 'idle' && (
              <p className="body-text body-text--sm detect-placeholder">
                Results will appear here after you upload an image and choose a detector.
              </p>
            )}

            {mode !== 'compare' && detectResult && (
              <div className="archival-frame result-card">
                <h2 className="heading-display heading-3">Detection Result</h2>
                <div className="step-table">
                  <div className="step-row"><span className="label-tech">Detected dots</span><strong>{detectResult.count}</strong></div>
                  <div className="step-row"><span className="label-tech">Processing</span><strong>{detectResult.processing_ms} ms</strong></div>
                  <div className="step-row"><span className="label-tech">Detector</span><strong>{detectResult.detector}</strong></div>
                  {detectResult.model && (
                    <>
                      <div className="step-row"><span className="label-tech">Model</span><strong>{detectResult.model.name}{detectResult.model.version ? ` (${detectResult.model.version})` : ''}</strong></div>
                      <div className="step-row"><span className="label-tech">Device</span><strong>{detectResult.model.device.toUpperCase()}</strong></div>
                    </>
                  )}
                </div>
              </div>
            )}

            {mode === 'compare' && compareResult && (
              <div className="archival-frame result-card">
                <h2 className="heading-display heading-3">Detector Comparison</h2>
                <div className="compare-columns">
                  <div className="compare-col">
                    <span className="label-tech">CLASSICAL</span>
                    <div className="step-row"><span>Dots</span><strong>{compareResult.classical.count}</strong></div>
                    <div className="step-row"><span>Time</span><strong>{compareResult.classical.processing_ms} ms</strong></div>
                    {compareResult.classical.error && <p className="detect-error">{compareResult.classical.error}</p>}
                  </div>
                  <div className="compare-col">
                    <span className="label-tech">ML</span>
                    <div className="step-row"><span>Dots</span><strong>{compareResult.ml.count}</strong></div>
                    <div className="step-row"><span>Time</span><strong>{compareResult.ml.processing_ms} ms</strong></div>
                    {compareResult.ml.error && <p className="detect-error">{compareResult.ml.error}</p>}
                  </div>
                </div>
                <div className="step-table">
                  <div className="step-row"><span className="label-tech">Agreeing dots</span><strong className="legend-agree">{compareResult.agreement.agreeing_dots ?? '—'}</strong></div>
                  <div className="step-row"><span className="label-tech">ML only</span><strong className="legend-ml">{compareResult.agreement.ml_only ?? '—'}</strong></div>
                  <div className="step-row"><span className="label-tech">Classical only</span><strong className="legend-classical">{compareResult.agreement.classical_only ?? '—'}</strong></div>
                </div>
                <div className="overlay-legend">
                  <span><i className="swatch legend-agree" /> Agreement</span>
                  <span><i className="swatch legend-ml" /> ML-only</span>
                  <span><i className="swatch legend-classical" /> Classical-only</span>
                </div>
              </div>
            )}

            {analysis && (
              <div className="archival-frame result-card">
                <h2 className="heading-display heading-3">Structural Analysis</h2>
                {analysis.dot_count > 0 && !analysis.validity.is_eulerian_circuit && !analysis.validity.has_eulerian_path && (
                  <p className="body-text body-text--sm detect-placeholder">
                    Detection succeeded — structural validation failed. The detected graph is not a valid
                    single-stroke (Eulerian) structure; this is a property of the detected structure, not a
                    request failure.
                  </p>
                )}
                <div className="step-table">
                  <div className="step-row"><span className="label-tech">Dot count</span><strong>{analysis.dot_count}</strong></div>
                  <div className="step-row"><span className="label-tech">Graph nodes</span><strong>{analysis.graph.nodes}</strong></div>
                  <div className="step-row"><span className="label-tech">Graph edges</span><strong>{analysis.graph.edges}</strong></div>
                  <div className="step-row"><span className="label-tech">Distinct edges</span><strong>{analysis.graph.distinct_edges}</strong></div>
                  <div className="step-row"><span className="label-tech">Motif count</span><strong>{analysis.motifs.motif_count}</strong></div>
                  <div className="step-row"><span className="label-tech">Eulerian circuit</span><strong>{analysis.validity.is_eulerian_circuit ? 'Valid' : 'No'}</strong></div>
                  <div className="step-row"><span className="label-tech">Connected</span><strong>{analysis.validity.largest_component_covers_all_nodes ? 'Yes' : 'No'}</strong></div>
                  {analysis.timing_ms && (
                    <div className="step-row"><span className="label-tech">Analysis time</span><strong>{analysis.timing_ms.total} ms</strong></div>
                  )}
                </div>
              </div>
            )}

            {reconstruction && (
              <div className="archival-frame result-card">
                <h2 className="heading-display heading-3">Reconstruction</h2>
                <p className="body-text body-text--sm detect-placeholder">
                  Checks whether the motif/residual decomposition of THIS pattern's own detected
                  structure reproduces a connected, valid graph. This is not novel-pattern
                  generation — that capability remains experimental and is not exposed here.
                </p>
                {reconstruction.error && (
                  <p className="detect-error" role="alert">{reconstruction.error}</p>
                )}
                {reconstruction.reconstruction?.note && (
                  <p className="detect-error" role="alert">{reconstruction.reconstruction.note}</p>
                )}
                {reconstruction.reconstruction && reconstruction.reconstruction.is_valid !== undefined && (
                  <>
                    {!reconstruction.reconstruction.is_valid && (
                      <p className="detect-error" role="status">
                        Detection succeeded — reconstruction validation failed (the motif/residual
                        decomposition does not reproduce a valid single-stroke structure).
                      </p>
                    )}
                    <div className="step-table">
                      <div className="step-row">
                        <span className="label-tech">Valid reconstruction</span>
                        <strong className={reconstruction.reconstruction.is_valid ? 'text-valid' : ''}>
                          {reconstruction.reconstruction.is_valid ? 'Yes' : 'No'}
                        </strong>
                      </div>
                      <div className="step-row"><span className="label-tech">Motif edges</span><strong>{reconstruction.reconstruction.motif_edges}</strong></div>
                      <div className="step-row"><span className="label-tech">Residual edges</span><strong>{reconstruction.reconstruction.residual_edges}</strong></div>
                      <div className="step-row"><span className="label-tech">Capped excess pairs</span><strong>{reconstruction.reconstruction.capped_excess_pairs}</strong></div>
                      <div className="step-row"><span className="label-tech">Connected</span><strong>{reconstruction.reconstruction.connectivity.largest_component_covers_all_nodes ? 'Yes' : 'No'}</strong></div>
                      {reconstruction.timing_ms && (
                        <div className="step-row"><span className="label-tech">Reconstruction time</span><strong>{reconstruction.timing_ms.total} ms</strong></div>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  )
}

function stageLabel(stage) {
  switch (stage) {
    case 'detecting': return 'Detecting…'
    case 'analyzing': return 'Building structure…'
    case 'reconstructing': return 'Reconstructing…'
    default: return 'Analyzing…'
  }
}

function DotOverlay({ mode, detectResult, compareResult, scale }) {
  if (mode !== 'compare' && detectResult) {
    return (
      <svg className="dot-overlay-svg">
        {detectResult.detections.map((d, i) => (
          <circle key={i} cx={d.x * scale} cy={d.y * scale} r={4} className="dot-marker dot-marker--single" />
        ))}
      </svg>
    )
  }
  if (mode === 'compare' && compareResult) {
    const { agree, mlOnly, classicalOnly } = categorizeCompareDots(compareResult)
    return (
      <svg className="dot-overlay-svg">
        {agree.map((d, i) => <circle key={`a${i}`} cx={d.x * scale} cy={d.y * scale} r={4} className="dot-marker legend-agree" />)}
        {mlOnly.map((d, i) => <circle key={`m${i}`} cx={d.x * scale} cy={d.y * scale} r={4} className="dot-marker legend-ml" />)}
        {classicalOnly.map((d, i) => <circle key={`c${i}`} cx={d.x * scale} cy={d.y * scale} r={4} className="dot-marker legend-classical" />)}
      </svg>
    )
  }
  return null
}

function describeError(error) {
  switch (error.kind) {
    case 'backend_unavailable':
      return 'Could not reach the PULLI backend. Make sure the API server is running.'
    case 'timeout':
      return 'The request timed out. Try a smaller image or try again.'
    case 'model_unavailable':
      return 'The ML detector is currently unavailable on the server.'
    case 'upload_too_large':
      return error.message || 'That image is too large. Please upload a smaller file (20MB limit).'
    case 'invalid_request':
      return error.message || 'That request could not be processed.'
    case 'invalid_image':
      return error.message || 'That file could not be processed as an image.'
    default:
      return error.message || 'Something went wrong.'
  }
}
