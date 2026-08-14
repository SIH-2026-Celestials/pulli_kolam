import { useEffect, useState } from 'react'
import { RotateCw, Grid, GitFork, Infinity as LoopIcon, Flower2, BarChart2 } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { useAuth } from '../../context/AuthContext'
import { generate } from '../../lib/api/kolam'
import RecentKolams from '../RecentKolams/RecentKolams'
import './GeneratedVariations.css'

export default function GeneratedVariations() {
  const { t } = useLanguage()
  const { addRecentKolam } = useAuth()
  const [status, setStatus] = useState('loading') // idle | loading | success | error
  const [candidates, setCandidates] = useState([])
  const [constraints, setConstraints] = useState(null)
  const [model, setModel] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)

  const saveCandidatesToHistory = (candList, constr) => {
    if (candList && candList.length > 0) {
      candList.forEach((c, idx) => {
        addRecentKolam({
          id: `gen_${c.seed}_${idx}`,
          title: `Generated Kolam Pattern (Seed ${c.seed})`,
          image_url: `/static/synthetic/kolam19_${(c.seed % 8) + 1}.jpg`,
          grid_size: constr ? `${constr.lattice_width}×${constr.lattice_height}` : '7×7',
          symmetry: c.symmetry_coverage ? `D4 (${(c.symmetry_coverage * 100).toFixed(0)}%)` : 'D4 Dihedral',
          validity: c.is_valid ? '✓ Eulerian Single-stroke' : '⚠️ Continuous Subgraph',
        })
      })
    }
  }

  const runGenerate = async () => {
    setStatus('loading')
    setErrorMsg(null)
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

    saveCandidatesToHistory(data.candidates, data.constraints)
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

      saveCandidatesToHistory(data.candidates, data.constraints)
    })
    return () => { cancelled = true }
  }, [])

  const nValid = candidates.filter((c) => c.is_valid).length
  const avgSymmetry = candidates.length
    ? candidates.reduce((sum, c) => sum + (c.symmetry_coverage ?? 0), 0) / candidates.length
    : null

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

            {/* DESIGN RULE SUMMARY */}
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

      {/* RECENT KOLAMS STORAGE HISTORY DISPLAY */}
      <RecentKolams />
    </div>
  )
}
