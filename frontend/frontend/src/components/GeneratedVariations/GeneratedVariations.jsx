import { useEffect, useState } from 'react'
import { RotateCw, Grid, GitFork, Infinity as LoopIcon, Flower2, BarChart2 } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { generate } from '../../lib/api/kolam'
import './GeneratedVariations.css'

export default function GeneratedVariations() {
  const { t } = useLanguage()
  const [status, setStatus] = useState('loading') // idle | loading | success | error
  const [candidates, setCandidates] = useState([])
  const [constraints, setConstraints] = useState(null)
  const [model, setModel] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)

  const runGenerate = async () => {
    setStatus('loading')
    setErrorMsg(null)
    // count kept small (2, not 4): each candidate is a real ~10-55s
    // structural search (engine.learned_generation), not a cheap lookup
    // -- see client.js's GENERATE_TIMEOUT_MS for the latency this implies.
    const { data, error } = await generate({ count: 2 })
    if (error) {
      setStatus('error')
      setErrorMsg(error.message)
      return
    }
    setCandidates(data.candidates)
    setConstraints(data.constraints)
    setModel(data.model)
    setStatus('success')
  }

  useEffect(() => {
    let cancelled = false
    generate({ count: 2 }).then(({ data, error }) => {
      if (cancelled) return
      if (error) {
        setStatus('error')
        setErrorMsg(error.message)
        return
      }
      setCandidates(data.candidates)
      setConstraints(data.constraints)
      setModel(data.model)
      setStatus('success')
    })
    return () => { cancelled = true }
  }, [])

  const nValid = candidates.filter((c) => c.is_valid).length
  const avgSymmetry = candidates.length
    ? candidates.reduce((sum, c) => sum + (c.symmetry_coverage ?? 0), 0) / candidates.length
    : null

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

        <button className="btn-generate-more" onClick={runGenerate} disabled={status === 'loading'}>
          <RotateCw size={14} className={`refresh-icon${status === 'loading' ? ' spinning' : ''}`} />
          <span>{status === 'loading' ? t('variations.generating') : t('variations.generateMore')}</span>
        </button>
      </div>

      {status === 'error' && (
        <div className="generated-error">
          {t('variations.errorPrefix')} {errorMsg}
        </div>
      )}

      {status === 'loading' && candidates.length === 0 && (
        <div className="generated-loading">{t('variations.generating')}</div>
      )}

      {candidates.length > 0 && (
        <>
          {/* CANDIDATE GRID */}
          <div className="variations-grid">
            {candidates.map((c) => (
              <div key={c.seed} className="variation-thumb-box" title={`seed=${c.seed}, valid=${c.is_valid}`}>
                <div
                  className="variation-svg-wrap"
                  dangerouslySetInnerHTML={{ __html: c.render_svg }}
                />
                {!c.is_valid && <span className="variation-invalid-badge">invalid</span>}
              </div>
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
                  <span className="metric-val">
                    {constraints ? `${constraints.lattice_width} × ${constraints.lattice_height}` : '—'}
                  </span>
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
                  <span className="metric-val">{constraints ? constraints.motif_library_size : '—'}</span>
                </div>
              </div>

              <div className="metric-col">
                <BarChart2 size={18} className="metric-icon" />
                <div className="metric-text-box">
                  <span className="metric-label">{t('variations.complexity')}</span>
                  <span className="metric-val">{constraints ? `${constraints.n_dots} dots` : '—'}</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
