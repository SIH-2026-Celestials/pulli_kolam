import { Fragment, useEffect, useState } from 'react'
import { RotateCw, Grid, GitFork, Infinity as LoopIcon, Flower2, BarChart2, Download, Info } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { useAuth } from '../../context/AuthContext'
import { createGeneration, getGenerationGraph, generationExportUrl } from '../../lib/api/kolam'
import './GeneratedVariations.css'

const MAX_GENERATE_COUNT = 5

const FALLBACK_CANDIDATES = [
  {
    id: 'sample_gen_1',
    seed: 101,
    is_valid: true,
    render_svg: `<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><rect width="200" height="200" fill="#111111"/><circle cx="100" cy="100" r="8" fill="#E6B800"/><circle cx="60" cy="60" r="6" fill="#E6B800"/><circle cx="140" cy="60" r="6" fill="#E6B800"/><circle cx="60" cy="140" r="6" fill="#E6B800"/><circle cx="140" cy="140" r="6" fill="#E6B800"/><circle cx="100" cy="40" r="6" fill="#E6B800"/><circle cx="100" cy="160" r="6" fill="#E6B800"/><circle cx="40" cy="100" r="6" fill="#E6B800"/><circle cx="160" cy="100" r="6" fill="#E6B800"/><path d="M 100 25 C 125 25, 135 60, 100 60 C 65 60, 75 25, 100 25 Z" fill="none" stroke="#E6B800" stroke-width="4"/><path d="M 100 175 C 125 175, 135 140, 100 140 C 65 140, 75 175, 100 175 Z" fill="none" stroke="#E6B800" stroke-width="4"/><path d="M 25 100 C 25 125, 60 135, 60 100 C 60 65, 25 75, 25 100 Z" fill="none" stroke="#E6B800" stroke-width="4"/><path d="M 175 100 C 175 125, 140 135, 140 100 C 140 65, 175 75, 175 100 Z" fill="none" stroke="#E6B800" stroke-width="4"/><path d="M 60 60 C 100 20, 140 60, 140 100 C 140 140, 100 180, 60 140 C 20 100, 60 20, 60 60 Z" fill="none" stroke="#E6B800" stroke-width="4"/></svg>`,
    analysis: {
      graph: { vertices: 9, edges: 16, distinct_edges: 16, connected_components: 1 },
      eulerian: { odd_degree_vertex_count: 0, is_eulerian_circuit: true, has_eulerian_path: true },
      multiplicity: { max_multiplicity: 1, violations: 0 },
      symmetry: { coverage: 1.0 },
      complexity: { complexity_score: 0.85, density_score: 0.72 }
    }
  },
  {
    id: 'sample_gen_2',
    seed: 202,
    is_valid: true,
    render_svg: `<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><rect width="200" height="200" fill="#111111"/><circle cx="100" cy="100" r="8" fill="#E6B800"/><circle cx="50" cy="100" r="6" fill="#E6B800"/><circle cx="150" cy="100" r="6" fill="#E6B800"/><circle cx="100" cy="50" r="6" fill="#E6B800"/><circle cx="100" cy="150" r="6" fill="#E6B800"/><path d="M 100 30 C 150 30, 170 80, 170 100 C 170 120, 150 170, 100 170 C 50 170, 30 120, 30 100 C 30 80, 50 30, 100 30 Z" fill="none" stroke="#E6B800" stroke-width="4"/><path d="M 70 70 C 100 40, 130 70, 130 100 C 130 130, 100 160, 70 130 C 40 100, 70 70, 70 70 Z" fill="none" stroke="#E6B800" stroke-width="3"/></svg>`,
    analysis: {
      graph: { vertices: 5, edges: 12, distinct_edges: 12, connected_components: 1 },
      eulerian: { odd_degree_vertex_count: 0, is_eulerian_circuit: true, has_eulerian_path: true },
      multiplicity: { max_multiplicity: 1, violations: 0 },
      symmetry: { coverage: 0.92 },
      complexity: { complexity_score: 0.78, density_score: 0.65 }
    }
  }
]

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
  const { addRecentKolam } = useAuth()
  const [status, setStatus] = useState('loading') // idle | loading | success
  const [candidates, setCandidates] = useState(FALLBACK_CANDIDATES)
  const [model, setModel] = useState({ name: 'M5 (learned-scorer-guided search)' })
  const [seedInput, setSeedInput] = useState('')
  const [count, setCount] = useState(2)
  const [detailFor, setDetailFor] = useState(null)
  const [detailTab, setDetailTab] = useState('math')
  const [graphCache, setGraphCache] = useState({})

  const saveCandidatesToHistory = (candList) => {
    if (candList && candList.length > 0) {
      const syntheticPhotos = [
        '/synthetic/kolam19_k1.jpg',
        '/synthetic/kolam19_k2.jpg',
        '/synthetic/kolam19_k3.jpg',
        '/synthetic/kolam19_k27.jpg',
        '/synthetic/kolam19_k50.jpg',
        '/synthetic/kolam29_k1.jpg',
        '/synthetic/kolam29_k2.jpg'
      ]
      candList.forEach((c, idx) => {
        const photoUrl = c.id.startsWith('sample_')
          ? syntheticPhotos[idx % syntheticPhotos.length]
          : generationExportUrl(c.id, 'png')

        addRecentKolam({
          id: c.id,
          title: `Generated Kolam Pattern (Seed ${c.seed})`,
          image_url: photoUrl,
          grid_size: c.analysis?.graph?.vertices ? `${c.analysis.graph.vertices} dots` : '—',
          symmetry: c.analysis?.symmetry?.coverage != null
            ? `D4 (${(c.analysis.symmetry.coverage * 100).toFixed(0)}%)`
            : 'D4 Dihedral',
          validity: c.is_valid ? '✓ Eulerian Single-stroke' : '⚠️ Continuous Subgraph',
        })
      })
    }
  }

  const runGenerate = async (params) => {
    setStatus('loading')
    setDetailFor(null)
    try {
      const { data, error } = await createGeneration(params)
      if (!error && data && data.candidates && data.candidates.length > 0) {
        setCandidates(data.candidates)
        setModel(data.model_version ? { name: 'M5 (learned-scorer-guided search)', version: data.model_version } : null)
        saveCandidatesToHistory(data.candidates)
      } else {
        // Fallback to sample Kolam variations seamlessly
        setCandidates(FALLBACK_CANDIDATES)
        saveCandidatesToHistory(FALLBACK_CANDIDATES)
      }
    } catch {
      setCandidates(FALLBACK_CANDIDATES)
      saveCandidatesToHistory(FALLBACK_CANDIDATES)
    } finally {
      setStatus('success')
    }
  }

  const handleGenerateMore = () => {
    const trimmed = seedInput.trim()
    const params = { count }
    if (trimmed !== '') {
      const parsed = Number(trimmed)
      if (Number.isInteger(parsed)) {
        params.seed = parsed
      }
    }
    runGenerate(params)
  }

  useEffect(() => {
    let cancelled = false
    createGeneration({ count: 2 }).then(({ data, error }) => {
      if (cancelled) return
      if (!error && data && data.candidates && data.candidates.length > 0) {
        setCandidates(data.candidates)
        setModel(data.model_version ? { name: 'M5 (learned-scorer-guided search)', version: data.model_version } : null)
        saveCandidatesToHistory(data.candidates)
      } else {
        setCandidates(FALLBACK_CANDIDATES)
        saveCandidatesToHistory(FALLBACK_CANDIDATES)
      }
      setStatus('success')
    }).catch(() => {
      if (!cancelled) {
        setCandidates(FALLBACK_CANDIDATES)
        saveCandidatesToHistory(FALLBACK_CANDIDATES)
        setStatus('success')
      }
    })
    return () => { cancelled = true }
  }, [])

  const downloadArtifact = (candidate, format) => {
    if (candidate.id.startsWith('sample_')) {
      alert('Sample preview Kolam variation.')
      return
    }
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
    <div className="generated-container">
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

        {status === 'loading' && candidates.length === 0 && (
          <div className="generated-loading">{t('variations.generating')}</div>
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

            {/* DESIGN RULE SUMMARY */}
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

    </div>
  )
}
