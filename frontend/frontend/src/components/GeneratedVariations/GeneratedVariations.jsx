import { Fragment, useEffect, useState } from 'react'
import { RotateCw, Grid, GitFork, Infinity as LoopIcon, Flower2, BarChart2, Download, Info } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { createGeneration, getGenerationGraph, generationExportUrl } from '../../lib/api/kolam'
import './GeneratedVariations.css'

// Server-enforced cap (api/routes_generations.py's MAX_GENERATE_COUNT) --
// mirrored here only to bound the <select> options shown, not
// re-validated client-side (the backend is still the source of truth;
// an out-of-range value would simply come back as a 422 INVALID_REQUEST,
// handled like any other error).
const MAX_GENERATE_COUNT = 5

/** Small dots+edges SVG built from /generations/{id}/graph -- a
 * DIFFERENT visualization from the main render_svg (which draws the
 * kolam's stroke trace): this shows raw topology (every edge as a
 * straight line, no stroke-order curve), useful for inspecting graph
 * structure directly. Built client-side from data the backend already
 * computed (dot_points/edges) -- no client-side graph math beyond
 * layout scaling. */
function GraphViewSvg({ graph }) {
  if (!graph || !graph.dot_points || graph.dot_points.length === 0) return null
  const scale = 14
  const margin = 16
  const xs = graph.dot_points.map((p) => p[0])
  const ys = graph.dot_points.map((p) => p[1])
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  const width = (Math.max(...xs) - minX) * scale + margin * 2
  const height = (Math.max(...ys) - minY) * scale + margin * 2
  const toPx = ([x, y]) => [margin + (x - minX) * scale, margin + (y - minY) * scale]

  return (
    <svg width={Math.min(width, 600)} height={Math.min(height, 420)} viewBox={`0 0 ${width} ${height}`}>
      <rect x="0" y="0" width={width} height={height} fill="#FFFFFF" />
      {(graph.edges || []).map(([a, b], i) => {
        const [ax, ay] = toPx(a)
        const [bx, by] = toPx(b)
        return <line key={i} x1={ax} y1={ay} x2={bx} y2={by} stroke="#CFC5B8" strokeWidth="1.5" />
      })}
      {graph.dot_points.map((p, i) => {
        const [px, py] = toPx(p)
        return <circle key={i} cx={px} cy={py} r="2.5" fill="#8A3324" />
      })}
    </svg>
  )
}

/** Mathematics panel content -- purely a display of `analysis`, the
 * exact object POST /api/v1/generations already returned inline (no
 * extra request needed to show this tab; the backend is the source of
 * truth for every number shown here, nothing is computed client-side). */
function MathematicsPanel({ analysis }) {
  if (!analysis) return null
  const { graph, eulerian, multiplicity, symmetry, complexity } = analysis
  return (
    <div className="math-grid">
      <div>
        <div className="math-group-title">Graph</div>
        <div className="math-row"><span>Vertices</span><span>{graph.vertices}</span></div>
        <div className="math-row"><span>Edges (instances)</span><span>{graph.edges}</span></div>
        <div className="math-row"><span>Distinct edges</span><span>{graph.distinct_edges}</span></div>
        <div className="math-row"><span>Components</span><span>{graph.connected_components}</span></div>
      </div>
      <div>
        <div className="math-group-title">Eulerian</div>
        <div className="math-row"><span>Odd-degree vertices</span><span>{eulerian.odd_degree_vertex_count}</span></div>
        <div className="math-row"><span>Circuit</span><span>{eulerian.is_eulerian_circuit ? 'Yes' : 'No'}</span></div>
        <div className="math-row"><span>Open path</span><span>{eulerian.has_eulerian_path ? 'Yes' : 'No'}</span></div>
      </div>
      <div>
        <div className="math-group-title">Multiplicity</div>
        <div className="math-row"><span>Max strand count</span><span>{multiplicity.max_multiplicity}</span></div>
        <div className="math-row"><span>Violations (&gt;2)</span><span>{multiplicity.violations}</span></div>
      </div>
      <div>
        <div className="math-group-title">Symmetry &amp; Complexity</div>
        <div className="math-row"><span>D4 coverage</span><span>{symmetry.coverage != null ? `${(symmetry.coverage * 100).toFixed(0)}%` : '—'}</span></div>
        <div className="math-row"><span>Complexity score</span><span>{complexity.complexity_score != null ? complexity.complexity_score.toFixed(3) : '—'}</span></div>
        <div className="math-row"><span>Density score</span><span>{complexity.density_score != null ? complexity.density_score.toFixed(3) : '—'}</span></div>
      </div>
    </div>
  )
}

export default function GeneratedVariations() {
  const { t } = useLanguage()
  const [status, setStatus] = useState('loading') // idle | loading | success | error
  const [candidates, setCandidates] = useState([])
  const [model, setModel] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)
  const [seedInput, setSeedInput] = useState('')
  const [count, setCount] = useState(2)
  const [detailFor, setDetailFor] = useState(null) // candidate id currently expanded, or null
  const [detailTab, setDetailTab] = useState('math') // 'math' | 'graph'
  const [graphCache, setGraphCache] = useState({}) // candidate id -> graph payload

  const runGenerate = async (params) => {
    setStatus('loading')
    setErrorMsg(null)
    setDetailFor(null)
    // Persisted generation (api/services/generation.py) -- same
    // ~10-55s/candidate M5 search as before, plus DB persistence so
    // each candidate is individually retrievable afterward.
    const { data, error } = await createGeneration(params)
    if (error) {
      setStatus('error')
      setErrorMsg(error.message)
      return
    }
    setCandidates(data.candidates)
    setModel(data.model_version ? { name: 'M5 (learned-scorer-guided search)', version: data.model_version } : null)
    setStatus('success')
  }

  const handleGenerateMore = () => {
    const trimmed = seedInput.trim()
    const params = { count }
    if (trimmed !== '') {
      const parsed = Number(trimmed)
      if (!Number.isInteger(parsed)) {
        setStatus('error')
        setErrorMsg('Seed must be a whole number.')
        return
      }
      params.seed = parsed
    }
    runGenerate(params)
  }

  useEffect(() => {
    let cancelled = false
    createGeneration({ count: 2 }).then(({ data, error }) => {
      if (cancelled) return
      if (error) {
        setStatus('error')
        setErrorMsg(error.message)
        return
      }
      setCandidates(data.candidates)
      setModel(data.model_version ? { name: 'M5 (learned-scorer-guided search)', version: data.model_version } : null)
      setStatus('success')
    })
    return () => { cancelled = true }
  }, [])

  // Downloads go through the backend export endpoint (real persisted
  // artifacts -- api/routes_generations.py's export_generation), not a
  // client-side blob of the already-rendered SVG string: this is what
  // makes PNG/JSON export possible (the frontend never rasterizes SVG
  // itself, the backend already rendered a real PNG via engine.render
  // at generation time). window.open triggers the browser's native
  // download via the response's Content-Disposition header.
  const downloadArtifact = (candidate, format) => {
    window.open(generationExportUrl(candidate.id, format), '_blank')
  }

  const toggleDetail = async (candidate) => {
    if (detailFor === candidate.id) {
      setDetailFor(null)
      return
    }
    setDetailFor(candidate.id)
    setDetailTab('math')
    if (detailTab === 'graph' && !graphCache[candidate.id]) {
      const { data } = await getGenerationGraph(candidate.id)
      if (data) setGraphCache((prev) => ({ ...prev, [candidate.id]: data.graph }))
    }
  }

  const selectTab = async (candidate, tab) => {
    setDetailTab(tab)
    if (tab === 'graph' && !graphCache[candidate.id]) {
      const { data } = await getGenerationGraph(candidate.id)
      if (data) setGraphCache((prev) => ({ ...prev, [candidate.id]: data.graph }))
    }
  }

  const nValid = candidates.filter((c) => c.is_valid).length
  const avgSymmetry = candidates.length
    ? candidates.reduce((sum, c) => sum + (c.analysis?.symmetry?.coverage ?? 0), 0) / candidates.length
    : null
  const firstDots = candidates[0]?.analysis?.graph?.vertices

  return (
    <div className="generated-card">
      {/* HEADER ROW */}
      <div className="generated-header-row">
        <div className="generated-title-group">
          <h2 className="generated-title">{t('variations.title')}</h2>
          <p className="generated-subtitle">
            {t('variations.subtitle')}
            {model && <> &mdash; {model.name}</>}
          </p>
        </div>

        <div className="generated-controls">
          <label className="generated-control-field">
            <span className="generated-control-label">{t('variations.seedLabel')}</span>
            <input
              type="number"
              inputMode="numeric"
              className="generated-control-input"
              placeholder={t('variations.seedPlaceholder')}
              value={seedInput}
              onChange={(e) => setSeedInput(e.target.value)}
              disabled={status === 'loading'}
            />
          </label>
          <label className="generated-control-field">
            <span className="generated-control-label">{t('variations.countLabel')}</span>
            <select
              className="generated-control-input"
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              disabled={status === 'loading'}
            >
              {Array.from({ length: MAX_GENERATE_COUNT }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
          <button className="btn-generate-more" onClick={handleGenerateMore} disabled={status === 'loading'}>
            <RotateCw size={14} className={`refresh-icon${status === 'loading' ? ' spinning' : ''}`} />
            <span>{status === 'loading' ? t('variations.generating') : t('variations.generateMore')}</span>
          </button>
        </div>
      </div>

      {status === 'error' && (
        <div className="generated-error">
          {t('variations.errorPrefix')} {errorMsg}
        </div>
      )}

      {status === 'loading' && candidates.length === 0 && (
        <div className="generated-loading">{t('variations.generating')}</div>
      )}

      {status === 'success' && candidates.length === 0 && (
        <div className="generated-loading">{t('variations.empty')}</div>
      )}

      {candidates.length > 0 && (
        <>
          {/* CANDIDATE GRID */}
          <div className="variations-grid">
            {candidates.map((c) => (
              <Fragment key={c.id}>
                <div className="variation-thumb-box" title={`seed=${c.seed}, valid=${c.is_valid}`}>
                  <div className="variation-svg-wrap" dangerouslySetInnerHTML={{ __html: c.render_svg }} />
                  {!c.is_valid && <span className="variation-invalid-badge">invalid</span>}
                  <button
                    type="button"
                    className={`variation-detail-btn${detailFor === c.id ? ' active' : ''}`}
                    title="View mathematics / graph"
                    aria-label={`View mathematics for seed ${c.seed}`}
                    onClick={() => toggleDetail(c)}
                  >
                    <Info size={13} />
                  </button>
                  <div className="variation-export-group" role="group" aria-label={t('variations.download')}>
                    {['svg', 'png', 'json'].map((format) => (
                      <button
                        key={format}
                        type="button"
                        className="variation-export-btn"
                        title={`${t('variations.download')} (${format.toUpperCase()})`}
                        aria-label={`${t('variations.download')} ${format.toUpperCase()} (seed ${c.seed})`}
                        onClick={() => downloadArtifact(c, format)}
                      >
                        {format === 'svg' ? <Download size={13} /> : format.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                {detailFor === c.id && (
                  <div className="detail-panel">
                    <div className="detail-panel-tabs">
                      <button
                        type="button"
                        className={`detail-panel-tab${detailTab === 'math' ? ' active' : ''}`}
                        onClick={() => selectTab(c, 'math')}
                      >
                        Mathematics
                      </button>
                      <button
                        type="button"
                        className={`detail-panel-tab${detailTab === 'graph' ? ' active' : ''}`}
                        onClick={() => selectTab(c, 'graph')}
                      >
                        Graph
                      </button>
                    </div>
                    {detailTab === 'math' && <MathematicsPanel analysis={c.analysis} />}
                    {detailTab === 'graph' && (
                      <div className="graph-view-svg-wrap">
                        {graphCache[c.id] ? <GraphViewSvg graph={graphCache[c.id]} /> : <span>Loading graph…</span>}
                      </div>
                    )}
                  </div>
                )}
              </Fragment>
            ))}
          </div>

          {/* DESIGN RULE SUMMARY -- real values only, from the actual API response */}
          <div className="rule-summary-container">
            <h3 className="rule-summary-title">{t('variations.ruleSummary')}</h3>

            <div className="rule-metrics-row">
              <div className="metric-col">
                <Grid size={18} className="metric-icon" />
                <div className="metric-text-box">
                  <span className="metric-label">{t('variations.grid')}</span>
                  <span className="metric-val">{firstDots ? `${firstDots} dots` : '—'}</span>
                </div>
              </div>

              <div className="metric-col">
                <GitFork size={18} className="metric-icon" />
                <div className="metric-text-box">
                  <span className="metric-label">{t('variations.symmetry')}</span>
                  <span className="metric-val">
                    {avgSymmetry !== null ? `${(avgSymmetry * 100).toFixed(0)}% coverage` : 'Not yet evaluated'}
                  </span>
                </div>
              </div>

              <div className="metric-col">
                <LoopIcon size={18} className="metric-icon" />
                <div className="metric-text-box">
                  <span className="metric-label">{t('variations.stroke')}</span>
                  <span className="metric-val">
                    {candidates.length ? `${nValid} / ${candidates.length} valid` : '—'}
                  </span>
                </div>
              </div>

              <div className="metric-col">
                <Flower2 size={18} className="metric-icon" />
                <div className="metric-text-box">
                  <span className="metric-label">{t('variations.motifFamilies')}</span>
                  <span className="metric-val">
                    {candidates[0]?.analysis?.multiplicity?.max_multiplicity != null
                      ? `max ×${candidates[0].analysis.multiplicity.max_multiplicity}`
                      : '—'}
                  </span>
                </div>
              </div>

              <div className="metric-col">
                <BarChart2 size={18} className="metric-icon" />
                <div className="metric-text-box">
                  <span className="metric-label">{t('variations.complexity')}</span>
                  <span className="metric-val">
                    {candidates[0]?.analysis?.complexity?.complexity_score != null
                      ? candidates[0].analysis.complexity.complexity_score.toFixed(2)
                      : '—'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
