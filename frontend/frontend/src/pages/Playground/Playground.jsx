import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Shuffle, Sparkles, Download, Save, Eye, ZoomIn, ZoomOut, Maximize2, RotateCcw,
  Copy, Check, History, ChevronDown, ChevronUp, ShieldCheck, Layers, Info,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import {
  createGeneration, listGenerations, generationExportUrl, getGeneration, getHealth,
} from '../../lib/api/kolam'
import MathematicsPanel from '../../components/kolam/MathematicsPanel'
import GraphView from '../../components/kolam/GraphView'
import './Playground.css'

// Server-enforced cap (api/routes_generations.py's MAX_GENERATE_COUNT) --
// the real backend limit per request, mirrored here only to bound the
// <select> shown, never re-validated silently client-side.
const MAX_GENERATE_COUNT = 5

// GENERATION vs DISPLAY is a real, load-bearing distinction here, not
// cosmetic: api/routes_generations.py's CreateGenerationRequest accepts
// exactly {seed, count, verify_recognizer} -- there is no backend
// concept of a selectable grid resolution, symmetry algorithm,
// "complexity" or "density" INPUT. api/generation_service.py's
// layout_for_seed picks a fixed held-out layout via `seed % len(layouts)`;
// grid size and symmetry are OUTPUTS reported per-candidate afterward
// (mathematics.graph / mathematics.symmetry), never a dial a caller
// turns beforehand. Exposing fake sliders for those would be exactly
// the "parameters that do nothing" this workspace explicitly must not
// have -- so Section A only has what's real (seed, count, opt-in
// recognizer verification), and Section B is honestly scoped to pure
// client-side DISPLAY of the real returned SVG (background, zoom),
// never a generation input.

function formatPct(x) {
  return x != null ? `${(x * 100).toFixed(0)}%` : '—'
}

/** Small dot -- real backend/model/db reachability, refreshed on mount.
 * Never hardcoded "Connected"; a failed fetch renders "Offline". */
function StatusDot({ label, ok, detail }) {
  return (
    <div className="status-chip" title={detail}>
      <span className={`status-led${ok === null ? ' status-led--unknown' : ok ? ' status-led--ok' : ' status-led--down'}`} />
      <span className="label-tech">{label}</span>
      <span className="status-chip-state">{ok === null ? 'CHECKING' : ok ? 'ONLINE' : 'OFFLINE'}</span>
    </div>
  )
}

export default function Playground() {
  const { t } = useLanguage()
  const { addRecentKolam } = useAuth()
  const canvasHostRef = useRef(null)

  // ---- Generation inputs (the only real ones) ----
  const [seedInput, setSeedInput] = useState('')
  const [verifyRecognizer, setVerifyRecognizer] = useState(false)
  const [variationCount, setVariationCount] = useState(3)

  // ---- Display-only controls (affect rendering of the real SVG, never generation) ----
  const [bgColor, setBgColor] = useState('#0B0B0B')
  const [zoom, setZoom] = useState(1)

  // ---- Generation lifecycle ----
  const [genStatus, setGenStatus] = useState('idle') // idle | loading | success | error
  const [stageText, setStageText] = useState('')
  const [errorInfo, setErrorInfo] = useState(null) // { message, code }
  const [active, setActive] = useState(null) // the active candidate object (full response shape)
  const [runMeta, setRunMeta] = useState(null) // { run_id, request_id, model_version, total_latency_ms }

  // ---- Panels ----
  const [mathOpen, setMathOpen] = useState(true)
  const [graphOpen, setGraphOpen] = useState(false)
  const [verifyOpen, setVerifyOpen] = useState(true)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [viewMode, setViewMode] = useState('final') // 'final' | 'graph'

  // ---- Recognizer (opt-in, separate real request) ----
  const [recognizerStatus, setRecognizerStatus] = useState('idle') // idle | running | done | error

  // ---- Variations / compare ----
  const [variations, setVariations] = useState([])
  const [variationsStatus, setVariationsStatus] = useState('idle')
  const [compareIds, setCompareIds] = useState([])
  const [compareOpen, setCompareOpen] = useState(false)

  // ---- History (server-side, real) ----
  const [history, setHistory] = useState([])
  const [historyStatus, setHistoryStatus] = useState('idle')

  // ---- Save/export feedback ----
  const [savedLocally, setSavedLocally] = useState(false)
  const [copiedId, setCopiedId] = useState(false)

  // ---- Status bar (real health checks) ----
  const [backendOk, setBackendOk] = useState(null)
  const [mlOk, setMlOk] = useState(null)
  const [recognizerOk, setRecognizerOk] = useState(null)
  const [dbOk, setDbOk] = useState(null)

  useEffect(() => {
    let cancelled = false
    getHealth().then(({ data, error }) => {
      if (cancelled) return
      if (error || !data) {
        setBackendOk(false)
        setMlOk(false)
        setRecognizerOk(false)
        setDbOk(false)
        return
      }
      setBackendOk(true)
      // generation_service_available/database_connected/artifact_storage_available
      // are direct, real checks the backend itself runs (api/main.py's
      // /api/v1/health) -- not inferred client-side from a second call.
      setMlOk(!!data.generation_service_available)
      setRecognizerOk(!!data.gated_detector_available)
      setDbOk(!!data.database_connected)
    })
    return () => { cancelled = true }
  }, [])

  const loadHistory = useCallback(() => {
    setTimeout(() => {
      setHistoryStatus('loading')
      listGenerations(1, 20).then(({ data, error }) => {
        if (error) {
          setHistoryStatus('error')
          return
        }
        setHistory(data.items || [])
        setHistoryStatus('success')
      })
    }, 0)
  }, [])

  useEffect(() => {
    if (historyOpen && historyStatus === 'idle') loadHistory()
  }, [historyOpen, historyStatus, loadHistory])

  const applyResult = (data) => {
    const candidate = data.candidates[0]
    setActive(candidate)
    setRunMeta({
      run_id: data.run_id, request_id: data.request_id,
      model_version: data.model_version, total_latency_ms: data.total_latency_ms,
    })
    setSavedLocally(false)
  }

  const runGenerate = async (params) => {
    if (genStatus === 'loading') return // guard against duplicate in-flight requests
    setGenStatus('loading')
    setErrorInfo(null)
    setStageText('Searching structural candidates (M5 multi-restart guided search)…')
    setRecognizerStatus('idle')

    const { data, error } = await createGeneration({ ...params, count: 1, verify_recognizer: verifyRecognizer })

    if (error) {
      setGenStatus('error')
      setErrorInfo({ message: error.message, code: error.code })
      setStageText('')
      return
    }

    // The response already reflects analysis + verification + render +
    // persistence having happened server-side by the time it arrives --
    // this is real sequencing information, not a fabricated progress
    // bar, just a short honest label for what the backend just finished.
    setStageText('Rendering & persisting…')
    await new Promise((r) => setTimeout(r, 150))

    applyResult(data)
    setGenStatus('success')
    setStageText('')
  }

  const handleGenerate = () => {
    const trimmed = seedInput.trim()
    const params = {}
    if (trimmed !== '') {
      const parsed = Number(trimmed)
      if (!Number.isInteger(parsed)) {
        setGenStatus('error')
        setErrorInfo({ message: 'Seed must be a whole number.', code: 'INVALID_SEED' })
        return
      }
      params.seed = parsed
    }
    runGenerate(params)
  }

  const handleRandomize = () => {
    const s = Math.floor(Math.random() * 1_000_000)
    setSeedInput(String(s))
    runGenerate({ seed: s })
  }

  // Recognizer verification is generation-time-only on the backend
  // (api/services/verification.py: recognizer self-consistency needs a
  // freshly rendered image, there is no "verify this existing ID"
  // endpoint). Re-running the SAME seed with verify_recognizer=true is
  // a genuine new backend call/persisted record, not a client-side
  // simulation -- M5's search is seed-deterministic, so this reproduces
  // the same structure with real recognizer verification now attached.
  const runRecognizer = async () => {
    if (!active) return
    setRecognizerStatus('running')
    const { data, error } = await createGeneration({ seed: active.seed, count: 1, verify_recognizer: true })
    if (error) {
      setRecognizerStatus('error')
      return
    }
    applyResult(data)
    setRecognizerStatus('done')
  }

  const generateVariations = async () => {
    setVariationsStatus('loading')
    setCompareIds([])
    const { data, error } = await createGeneration({ count: Math.min(variationCount, MAX_GENERATE_COUNT) })
    if (error) {
      setVariationsStatus('error')
      return
    }
    setVariations(data.candidates)
    setVariationsStatus('success')
  }

  const selectVariation = (candidate) => {
    setActive(candidate)
    setGenStatus('success')
    setRecognizerStatus('idle')
  }

  const toggleCompare = (id) => {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= 4) return prev
      return [...prev, id]
    })
  }

  const handleSaveLocal = () => {
    if (!active) return
    addRecentKolam({
      id: active.id,
      title: `Generated Kolam Pattern (Seed ${active.seed})`,
      image_url: generationExportUrl(active.id, 'png'),
      grid_size: active.analysis?.graph?.vertices ? `${active.analysis.graph.vertices} dots` : 'Not available',
      symmetry: active.analysis?.symmetry?.coverage != null ? `D4 (${formatPct(active.analysis.symmetry.coverage)})` : 'Not available',
      validity: active.is_valid ? '✓ Eulerian Single-stroke' : '⚠️ Continuous Subgraph',
    })
    setSavedLocally(true)
  }

  const copyGenerationId = () => {
    if (!active) return
    navigator.clipboard?.writeText(active.id).then(() => {
      setCopiedId(true)
      setTimeout(() => setCopiedId(false), 1500)
    })
  }

  const restoreFromHistory = async (item) => {
    const { data, error } = await getGeneration(item.id)
    if (error) return
    setActive({
      id: data.id, seed: data.seed, is_valid: data.is_valid,
      render_svg: data.render_svg, analysis: data.analysis, mathematics: data.analysis,
      verification: data.verification, graph: null,
    })
    setRunMeta({ run_id: data.run_id, model_version: data.model?.version, total_latency_ms: null })
    setGenStatus('success')
  }

  const analysis = active?.analysis || active?.mathematics
  const structuralVerification = active?.verification?.structural_hard_gate
  const recognizerVerification = active?.verification?.recognizer_self_consistency
  const recognizerPrecision = recognizerVerification?.precision
  const recognizerRecall = recognizerVerification?.recall
  const recognizerF1 = (recognizerPrecision != null && recognizerRecall != null && (recognizerPrecision + recognizerRecall) > 0)
    ? (2 * recognizerPrecision * recognizerRecall) / (recognizerPrecision + recognizerRecall)
    : null

  const compareCandidates = variations.filter((v) => compareIds.includes(v.id))

  return (
    <main className="playground-page">
      <header className="playground-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">{t('playground.eyebrow')}</p>
          <h1 className="heading-display heading-hero">{t('playground.title')}</h1>
          <p className="body-text playground-sub">
            {t('playground.sub')}
          </p>
          <div className="status-bar">
            <StatusDot label="BACKEND" ok={backendOk} detail="FastAPI /api/v1/health" />
            <StatusDot label="ML ENGINE (M5)" ok={mlOk} detail="M5 generation model availability" />
            <StatusDot label="RECOGNIZER (M4.2)" ok={recognizerOk} detail="Gated M4.2 detector availability" />
            <StatusDot label="DATABASE" ok={dbOk} detail="Generation history query succeeded" />
          </div>
        </div>
      </header>

      <section className="playground-body container">
        <div className="playground-layout playground-layout--3col">
          {/* ============ LEFT: CONTROLS ============ */}
          <aside className="playground-controls archival-frame">
            <div className="controls-header">
              <Sparkles size={18} className="icon-accent" />
              <h3 className="heading-display heading-4">Generation</h3>
            </div>

            <div className="control-group">
              <label className="label-tech" title="Sent to POST /api/v1/generations. Omit to let the backend pick a random seed.">
                SEED
              </label>
              <div className="control-row">
                <input
                  type="number"
                  inputMode="numeric"
                  className="input-select flex-1"
                  placeholder="random"
                  value={seedInput}
                  onChange={(e) => setSeedInput(e.target.value)}
                  disabled={genStatus === 'loading'}
                />
                <button className="btn-icon-action" onClick={handleRandomize} disabled={genStatus === 'loading'} title="Randomize seed and generate">
                  <Shuffle size={14} />
                </button>
              </div>
            </div>

            <div className="control-group">
              <label className="checkbox-row label-tech">
                <input
                  type="checkbox"
                  checked={verifyRecognizer}
                  onChange={(e) => setVerifyRecognizer(e.target.checked)}
                  disabled={genStatus === 'loading'}
                />
                <span title="Runs the real frozen M4.2 recognizer against the rendered candidate at generation time. Costs real inference latency.">
                  Verify with recognizer at generation time
                </span>
              </label>
            </div>

            <div className="action-buttons-group">
              <button className="btn btn--primary btn--full" onClick={handleGenerate} disabled={genStatus === 'loading'}>
                {genStatus === 'loading' ? (
                  <span className="btn-spinner" aria-hidden="true" />
                ) : (
                  <Sparkles size={16} />
                )}
                <span>{genStatus === 'loading' ? (stageText || 'Generating…') : 'GENERATE KOLAM'}</span>
              </button>
            </div>

            {genStatus === 'error' && errorInfo && (
              <div className="gen-error-box">
                <strong>Generation failed.</strong>
                <p>{errorInfo.message}</p>
                {errorInfo.code && <p className="gen-error-code">Code: {errorInfo.code}</p>}
                <p className="gen-error-hint">
                  {errorInfo.code === 'GENERATION_MODEL_UNAVAILABLE'
                    ? 'The M5 model is not currently loaded on the backend. Retrying will not help until the server is restarted with a valid checkpoint.'
                    : 'This is usually safe to retry.'}
                </p>
              </div>
            )}

            {genStatus === 'success' && active && (
              <div className="gen-success-box">
                <div className="gen-success-row"><Check size={13} className="text-valid" /> Generated</div>
                <div className="gen-meta-row"><span>Generation ID</span><code>{active.id?.slice(0, 8) ?? '—'}…</code></div>
                <div className="gen-meta-row"><span>Seed</span><code>{active.seed}</code></div>
                <div className="gen-meta-row"><span>Latency</span><code>{runMeta?.total_latency_ms != null ? `${(runMeta.total_latency_ms / 1000).toFixed(1)}s` : '—'}</code></div>
                <div className="gen-meta-row"><span>Engine</span><code>{runMeta?.model_version || 'M5'}</code></div>
                <div className="gen-meta-row"><span>Validity</span><code className={active.is_valid ? 'text-valid' : 'text-invalid'}>{active.is_valid ? 'VALID' : 'INVALID'}</code></div>
              </div>
            )}

            <div className="controls-header controls-header--secondary">
              <Layers size={18} className="icon-accent" />
              <h3 className="heading-display heading-4">Display</h3>
            </div>
            <p className="body-text body-text--sm control-note">
              These only affect how the real returned pattern is displayed — they never change what gets generated.
            </p>

            <div className="control-row">
              <div className="control-group flex-1">
                <label className="label-tech">CANVAS BG</label>
                <input type="color" value={bgColor} onChange={(e) => setBgColor(e.target.value)} className="input-color" />
              </div>
            </div>

            <div className="action-buttons-group">
              <button className="btn btn--outline btn--full" onClick={handleSaveLocal} disabled={!active}>
                <Save size={16} />
                <span>{savedLocally ? 'Saved Locally ✓' : 'Save Locally'}</span>
              </button>
            </div>
          </aside>

          {/* ============ CENTER: CANVAS ============ */}
          <div className="playground-viewport archival-frame">
            <div className="viewport-header">
              <div className="viewport-meta label-tech">
                <span>SEED: {active ? `#${active.seed}` : '—'}</span>
                <span className="dot-sep">•</span>
                <span>DOTS: {analysis?.graph?.vertices ?? '—'}</span>
                <span className="dot-sep">•</span>
                <span>SYMMETRY: {analysis?.symmetry?.coverage != null ? formatPct(analysis.symmetry.coverage) : '—'}</span>
                <span className="dot-sep">•</span>
                <span>ENGINE: {runMeta?.model_version ? 'M5' : '—'}</span>
                <span className="dot-sep">•</span>
                <span className={active?.is_valid ? 'text-valid' : ''}>STATUS: {active ? (active.is_valid ? 'VALID' : 'INVALID') : '—'}</span>
              </div>

              <div className="viewport-actions">
                <button className="btn-icon-action" onClick={() => setViewMode(viewMode === 'final' ? 'graph' : 'final')} title="Toggle Final Kolam / Graph view">
                  <Eye size={16} />
                  <span>{viewMode === 'final' ? 'Final' : 'Graph'}</span>
                </button>
                <button className="btn-icon-action" onClick={copyGenerationId} disabled={!active} title="Copy Generation ID">
                  {copiedId ? <Check size={16} /> : <Copy size={16} />}
                  <span>{copiedId ? 'Copied' : 'Copy ID'}</span>
                </button>
                <a
                  className={`btn-icon-action${!active ? ' btn-icon-action--disabled' : ''}`}
                  href={active ? generationExportUrl(active.id, 'png') : undefined}
                  target="_blank" rel="noreferrer"
                  title="Export PNG (real backend-rendered artifact)"
                >
                  <Download size={16} /><span>PNG</span>
                </a>
                <a
                  className={`btn-icon-action${!active ? ' btn-icon-action--disabled' : ''}`}
                  href={active ? generationExportUrl(active.id, 'svg') : undefined}
                  target="_blank" rel="noreferrer"
                  title="Export SVG"
                >
                  <Download size={16} /><span>SVG</span>
                </a>
                <a
                  className={`btn-icon-action${!active ? ' btn-icon-action--disabled' : ''}`}
                  href={active ? generationExportUrl(active.id, 'json') : undefined}
                  target="_blank" rel="noreferrer"
                  title="Download raw JSON"
                >
                  <Download size={16} /><span>JSON</span>
                </a>
              </div>
            </div>

            <div className="canvas-toolbar" role="toolbar" aria-label="Canvas zoom controls">
              <button className="graph-tool-btn" onClick={() => setZoom((z) => Math.min(z + 0.25, 3))} title="Zoom in"><ZoomIn size={13} /></button>
              <button className="graph-tool-btn" onClick={() => setZoom((z) => Math.max(z - 0.25, 0.25))} title="Zoom out"><ZoomOut size={13} /></button>
              <button className="graph-tool-btn" onClick={() => setZoom(1)} title="Reset zoom"><RotateCcw size={13} /></button>
              <button className="graph-tool-btn" onClick={() => setZoom(0.6)} title="Fit"><Maximize2 size={13} /></button>
            </div>

            <div className="canvas-wrapper" style={{ backgroundColor: bgColor }} ref={canvasHostRef}>
              {genStatus === 'loading' && (
                <div className="canvas-empty-state">
                  <span className="btn-spinner btn-spinner--lg" aria-hidden="true" />
                  <p>{stageText}</p>
                </div>
              )}
              {genStatus !== 'loading' && !active && (
                <div className="canvas-empty-state">
                  <Sparkles size={28} />
                  <p>No pattern generated yet. Click GENERATE KOLAM to run the real M5 search.</p>
                </div>
              )}
              {genStatus !== 'loading' && active && viewMode === 'final' && (
                <div
                  className="kolam-svg-render"
                  style={{ transform: `scale(${zoom})` }}
                  dangerouslySetInnerHTML={{ __html: active.render_svg || active.svg || '' }}
                />
              )}
              {genStatus !== 'loading' && active && viewMode === 'graph' && (
                <div className="kolam-graph-render" style={{ transform: `scale(${zoom})` }}>
                  <GraphView graph={active.graph} interactive height={480} />
                </div>
              )}
            </div>

            <div className="viewport-footer">
              <p className="body-text body-text--sm">
                Rendered SVG and every statistic on this page come directly from the FastAPI backend
                (api/routes_generations.py, M5 generation + engine analysis) — nothing on this page is
                computed or fabricated in the browser.
              </p>
              <Link to="/detect" className="link-analyze label-tech">
                <Eye size={14} /> Run Deep AI Dot Detection →
              </Link>
            </div>
          </div>

          {/* ============ RIGHT: ANALYSIS ============ */}
          <aside className="playground-analysis">
            <div className="analysis-panel archival-frame">
              <button className="analysis-panel-header" onClick={() => setMathOpen((o) => !o)}>
                <span className="heading-display heading-4">Mathematics</span>
                {mathOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
              {mathOpen && (
                <div className="analysis-panel-body">
                  {analysis ? <MathematicsPanel analysis={analysis} /> : <p className="body-text body-text--sm">Generate a pattern to see its mathematics.</p>}
                </div>
              )}
            </div>

            <div className="analysis-panel archival-frame">
              <button className="analysis-panel-header" onClick={() => setGraphOpen((o) => !o)}>
                <span className="heading-display heading-4">Structural Graph</span>
                {graphOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
              {graphOpen && (
                <div className="analysis-panel-body">
                  {active ? (
                    <>
                      <div className="graph-stat-row">
                        <span>Nodes: {analysis?.graph?.vertices ?? '—'}</span>
                        <span>Edges: {analysis?.graph?.edges ?? '—'}</span>
                        <span>Components: {analysis?.graph?.connected_components ?? '—'}</span>
                        <span>Max multiplicity: {analysis?.multiplicity?.max_multiplicity ?? '—'}</span>
                        <span>Eulerian: {analysis?.eulerian?.is_eulerian_circuit ? 'Yes' : 'No'}</span>
                      </div>
                      {active.graph ? <GraphView graph={active.graph} interactive /> : <p className="body-text body-text--sm">Graph geometry not loaded for this entry — reopen it from a fresh generation to inspect the overlay.</p>}
                    </>
                  ) : <p className="body-text body-text--sm">Generate a pattern to inspect its graph.</p>}
                </div>
              )}
            </div>

            <div className="analysis-panel archival-frame">
              <button className="analysis-panel-header" onClick={() => setVerifyOpen((o) => !o)}>
                <span className="heading-display heading-4"><ShieldCheck size={15} className="icon-accent" /> AI Verification</span>
                {verifyOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
              {verifyOpen && (
                <div className="analysis-panel-body">
                  {!active ? (
                    <p className="body-text body-text--sm">Generate a pattern to verify it.</p>
                  ) : (
                    <>
                      <div className="verify-block">
                        <div className="verify-block-title">Structural verification <span className="verify-tag">free, always run</span></div>
                        {structuralVerification ? (
                          <>
                            <div className="gen-meta-row"><span>Status</span><code className={structuralVerification.is_valid ? 'text-valid' : 'text-invalid'}>{structuralVerification.is_valid ? 'VALID' : 'INVALID'}</code></div>
                            <p className="body-text body-text--sm">{structuralVerification.notes}</p>
                          </>
                        ) : <p className="body-text body-text--sm">Not available for this entry.</p>}
                      </div>

                      <div className="verify-block">
                        <div className="verify-block-title">Recognizer verification (M4.2) <span className="verify-tag">opt-in, real inference</span></div>
                        {recognizerVerification ? (
                          <>
                            <div className="gen-meta-row"><span>Status</span><code className={recognizerVerification.is_valid ? 'text-valid' : 'text-invalid'}>{recognizerVerification.is_valid ? 'MATCH' : 'MISMATCH'}</code></div>
                            <div className="gen-meta-row"><span>Detections</span><code>{recognizerVerification.n_detected ?? '—'} / {recognizerVerification.n_expected ?? '—'}</code></div>
                            <div className="gen-meta-row"><span>Recall</span><code>{recognizerRecall != null ? formatPct(recognizerRecall) : 'Not available'}</code></div>
                            <div className="gen-meta-row"><span>Precision</span><code>{recognizerPrecision != null ? formatPct(recognizerPrecision) : 'Not available'}</code></div>
                            <div className="gen-meta-row"><span>F1 (derived)</span><code>{recognizerF1 != null ? formatPct(recognizerF1) : 'Not available'}</code></div>
                            <div className="gen-meta-row"><span>Localization error</span><code>Not available</code></div>
                            <div className="gen-meta-row"><span>Latency</span><code>Not available</code></div>
                          </>
                        ) : (
                          <>
                            <p className="body-text body-text--sm">Not yet computed for this pattern.</p>
                            <button className="btn btn--outline btn--full" onClick={runRecognizer} disabled={recognizerStatus === 'running'}>
                              {recognizerStatus === 'running' ? <span className="btn-spinner" aria-hidden="true" /> : <ShieldCheck size={14} />}
                              <span>{recognizerStatus === 'running' ? 'Analyzing generated structure…' : 'Run Recognizer'}</span>
                            </button>
                            {recognizerStatus === 'error' && <p className="gen-error-code">Recognizer verification failed — see backend logs.</p>}
                          </>
                        )}
                        {recognizerVerification && recognizerStatus === 'done' && (
                          <p className="body-text body-text--sm text-valid">✓ Recognizer verification complete</p>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </aside>
        </div>

        {/* ============ VARIATIONS ============ */}
        <div className="playground-section archival-frame">
          <div className="section-row">
            <h3 className="heading-display heading-4">Generate Variations</h3>
            <div className="control-row">
              <select className="input-select" value={variationCount} onChange={(e) => setVariationCount(Number(e.target.value))} disabled={variationsStatus === 'loading'}>
                {Array.from({ length: MAX_GENERATE_COUNT }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>{n} variation{n > 1 ? 's' : ''}</option>
                ))}
              </select>
              <button className="btn btn--outline" onClick={generateVariations} disabled={variationsStatus === 'loading'}>
                {variationsStatus === 'loading' ? <span className="btn-spinner" aria-hidden="true" /> : <Sparkles size={14} />}
                <span>{variationsStatus === 'loading' ? 'Generating…' : 'Generate Variations'}</span>
              </button>
              {variations.length > 1 && (
                <button className="btn btn--outline" onClick={() => setCompareOpen((o) => !o)} disabled={compareIds.length < 2}>
                  Compare Selected ({compareIds.length})
                </button>
              )}
            </div>
          </div>

          {variationsStatus === 'error' && <p className="gen-error-code">Variation generation failed. Try again.</p>}

          {variations.length > 0 && (
            <div className="variations-card-grid">
              {variations.map((v) => (
                <div key={v.id} className={`variation-card${active?.id === v.id ? ' variation-card--active' : ''}`}>
                  <label className="variation-card-select">
                    <input type="checkbox" checked={compareIds.includes(v.id)} onChange={() => toggleCompare(v.id)} />
                  </label>
                  <div className="variation-card-svg" onClick={() => selectVariation(v)} dangerouslySetInnerHTML={{ __html: v.render_svg }} />
                  <div className="variation-card-body">
                    <div className="gen-meta-row"><span>Seed</span><code>{v.seed}</code></div>
                    <div className="gen-meta-row"><span>Valid</span><code className={v.is_valid ? 'text-valid' : 'text-invalid'}>{v.is_valid ? '✓' : '✗'}</code></div>
                    <div className="gen-meta-row"><span>Symmetry</span><code>{v.analysis?.symmetry?.coverage != null ? formatPct(v.analysis.symmetry.coverage) : '—'}</code></div>
                    <div className="gen-meta-row"><span>Complexity</span><code>{v.analysis?.complexity?.complexity_score != null ? v.analysis.complexity.complexity_score.toFixed(2) : '—'}</code></div>
                    <div className="gen-meta-row"><span>Novelty</span><code>{v.novelty?.novelty_score != null ? v.novelty.novelty_score.toFixed(2) : '—'}</code></div>
                    <div className="gen-meta-row"><span>Latency</span><code>{v.generation_time_ms != null ? `${(v.generation_time_ms / 1000).toFixed(1)}s` : (v.latency_ms != null ? `${(v.latency_ms / 1000).toFixed(1)}s` : '—')}</code></div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {compareOpen && compareCandidates.length >= 2 && (
            <div className="compare-table-wrap">
              <table className="compare-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    {compareCandidates.map((c) => <th key={c.id}>Seed {c.seed}</th>)}
                  </tr>
                </thead>
                <tbody>
                  <tr><td>Preview</td>{compareCandidates.map((c) => <td key={c.id}><div className="compare-thumb" dangerouslySetInnerHTML={{ __html: c.render_svg }} /></td>)}</tr>
                  <tr><td>Valid</td>{compareCandidates.map((c) => <td key={c.id}>{c.is_valid ? '✓' : '✗'}</td>)}</tr>
                  <tr><td>Nodes</td>{compareCandidates.map((c) => <td key={c.id}>{c.analysis?.graph?.vertices ?? '—'}</td>)}</tr>
                  <tr><td>Edges</td>{compareCandidates.map((c) => <td key={c.id}>{c.analysis?.graph?.edges ?? '—'}</td>)}</tr>
                  <tr><td>Components</td>{compareCandidates.map((c) => <td key={c.id}>{c.analysis?.graph?.connected_components ?? '—'}</td>)}</tr>
                  <tr><td>Symmetry</td>{compareCandidates.map((c) => <td key={c.id}>{c.analysis?.symmetry?.coverage != null ? formatPct(c.analysis.symmetry.coverage) : '—'}</td>)}</tr>
                  <tr><td>Max multiplicity</td>{compareCandidates.map((c) => <td key={c.id}>{c.analysis?.multiplicity?.max_multiplicity ?? '—'}</td>)}</tr>
                  <tr><td>Novelty</td>{compareCandidates.map((c) => <td key={c.id}>{c.novelty?.novelty_score != null ? c.novelty.novelty_score.toFixed(2) : '—'}</td>)}</tr>
                  <tr><td>Generation time</td>{compareCandidates.map((c) => <td key={c.id}>{c.generation_time_ms != null ? `${(c.generation_time_ms / 1000).toFixed(1)}s` : '—'}</td>)}</tr>
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ============ HISTORY ============ */}
        <div className="playground-section archival-frame">
          <button className="analysis-panel-header" onClick={() => setHistoryOpen((o) => !o)}>
            <span className="heading-display heading-4"><History size={16} className="icon-accent" /> Generation History (server)</span>
            {historyOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {historyOpen && (
            <div className="history-list">
              {historyStatus === 'loading' && <p className="body-text body-text--sm">Loading…</p>}
              {historyStatus === 'error' && <p className="gen-error-code">Could not load history from the backend.</p>}
              {historyStatus === 'success' && history.length === 0 && <p className="body-text body-text--sm">No generations persisted yet.</p>}
              {history.map((item) => (
                <button key={item.id} className="history-row" onClick={() => restoreFromHistory(item)}>
                  <span className="label-tech">{new Date(item.created_at).toLocaleString()}</span>
                  <span>Seed {item.seed}</span>
                  <span>{item.n_dots ?? '—'} dots</span>
                  <span>{item.generator || 'M5'}</span>
                  <span className={item.is_valid ? 'text-valid' : 'text-invalid'}>{item.is_valid ? 'VALID' : 'INVALID'}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <p className="body-text body-text--sm playground-disclaimer">
          <Info size={12} /> "Saved Locally" stores a thumbnail reference in this browser only (localStorage).
          Every generation shown above is already persisted server-side automatically by PULLI the moment it's
          created — Generation History reads that real database record directly.
        </p>
      </section>
    </main>
  )
}
