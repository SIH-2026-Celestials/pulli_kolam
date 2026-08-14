import { useSearchParams } from 'react-router-dom'
import { useLanguage } from '../../context/LanguageContext'
import { kolam19, getKolam } from '../../data/kolams'
import './Analyze.css'

export default function Analyze() {
  const { t } = useLanguage()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get('kolam') || '26'
  const currentKolam = getKolam(selectedId) || kolam19[0]

  const handleSelect = (id) => {
    setSearchParams({ kolam: id })
  }

  return (
    <main id="main-content" className="analyze-page">
      <header className="analyze-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">{t('pages.analyze.eyebrow')}</p>
          <h1 className="heading-display heading-hero analyze-title">
            {t('pages.analyze.titlePrefix', { id: currentKolam.id })}
          </h1>
          <p className="body-text analyze-sub">
            {t('pages.analyze.sub')}
          </p>

          {/* Pattern selector strip */}
          <div className="pattern-selector-bar archival-frame">
            <span className="label-tech">{t('pages.analyze.selectItem')}</span>
            <div className="selector-pills">
              {[1, 15, 26, 55, 100, 118, 179, 232, 331, 400].map(id => (
                <button
                  key={id}
                  className={`pill-btn ${Number(selectedId) === id ? 'pill-btn--active' : ''}`}
                  onClick={() => handleSelect(id.toString())}
                >
                  Kolam {id}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* Linear Scientific Breakdown: TRACE -> GRAPH -> MOTIF -> VALIDITY -> GENERATION */}
      <section className="container--narrow section analyze-pipeline-section">
        <div className="pipeline-walkthrough">
          {/* STEP 1: TRACE */}
          <article className="step-block archival-frame">
            <div className="step-header">
              <span className="step-num label-tech">{t('pages.analyze.stage01')}</span>
              <h2 className="heading-display heading-3">{t('pages.analyze.traceTitle')}</h2>
            </div>
            <div className="step-body">
              <div className="step-text body-text body-text--sm">
                <p>
                  {t('pages.analyze.traceDesc')}
                </p>
                <div className="step-table">
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.totalPoints')}</span><strong>{currentKolam.points}</strong></div>
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.pathLength')}</span><strong>{currentKolam.pathLength} units</strong></div>
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.gridResolution')}</span><strong>37.0 × 37.0</strong></div>
                </div>
              </div>
              <div className="step-img-frame">
                <img src={currentKolam.imagePath} alt={`Raw Kolam ${currentKolam.id} trace`} />
                <span className="label-tech">{t('pages.analyze.datasetFile', { file: `kolam19-${currentKolam.id - 1}.jpg` })}</span>
              </div>
            </div>
          </article>

          {/* STEP 2: GRAPH */}
          <article className="step-block archival-frame">
            <div className="step-header">
              <span className="step-num label-tech">{t('pages.analyze.stage02')}</span>
              <h2 className="heading-display heading-3">{t('pages.analyze.graphTitle')}</h2>
            </div>
            <div className="step-body">
              <div className="step-text body-text body-text--sm">
                <p>
                  {t('pages.analyze.graphDesc')}
                </p>
                <div className="step-table">
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.dataStructure')}</span><strong>NetworkX MultiGraph</strong></div>
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.dotVertexRep')}</span><strong>Integer (x, y)</strong></div>
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.loopVertexRep')}</span><strong>Half-Integer (x+0.5, y+0.5)</strong></div>
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.edgeMultiplicity')}</span><strong>{t('pages.analyze.preserved')}</strong></div>
                </div>
              </div>
              <div className="step-diagram-box">
                <pre className="ascii-diagram label-tech">
{`  (x, y) ─────────── (x+1, y)
    │     \\  Multi  /     │
    │      \\ Strand/      │
    │       (x+0.5, y+0.5)│
    │      /        \\     │
  (x, y+1) ───────── (x+1, y+1)`}
                </pre>
              </div>
            </div>
          </article>

          {/* STEP 3: MOTIF */}
          <article className="step-block archival-frame">
            <div className="step-header">
              <span className="step-num label-tech">{t('pages.analyze.stage03')}</span>
              <h2 className="heading-display heading-3">{t('pages.analyze.motifTitle')}</h2>
            </div>
            <div className="step-body">
              <div className="step-text body-text body-text--sm">
                <p>
                  {t('pages.analyze.motifDesc')}
                </p>
                <div className="step-table">
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.vertSym')}</span><strong>{currentKolam.symmetry.vertical.toFixed(5)}</strong></div>
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.horizSym')}</span><strong>{currentKolam.symmetry.horizontal.toFixed(1)}</strong></div>
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.rot180')}</span><strong>{currentKolam.symmetry.rotation180.toFixed(5)}</strong></div>
                </div>
              </div>
            </div>
          </article>

          {/* STEP 4: VALIDITY */}
          <article className="step-block archival-frame">
            <div className="step-header">
              <span className="step-num label-tech">{t('pages.analyze.stage04')}</span>
              <h2 className="heading-display heading-3">{t('pages.analyze.validityTitle')}</h2>
            </div>
            <div className="step-body">
              <div className="step-text body-text body-text--sm">
                <p>
                  {t('pages.analyze.validityDesc')}
                </p>
                <div className="step-table">
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.oneStroke')}</span><strong className="text-valid">{t('pages.analyze.validCircuit')}</strong></div>
                  <div className="step-row"><span className="label-tech">{t('pages.analyze.closedLoop')}</span><strong className="text-valid">{t('pages.analyze.startEnd')}</strong></div>
                </div>
              </div>
            </div>
          </article>

          {/* STEP 5: GENERATION */}
          <article className="step-block archival-frame step-block--future">
            <div className="step-header">
              <span className="step-num label-tech">{t('pages.analyze.stage05')}</span>
              <h2 className="heading-display heading-3">{t('pages.analyze.generationTitle')}</h2>
            </div>
            <div className="step-body">
              <p className="body-text body-text--sm">
                {t('pages.analyze.generationDesc')}
              </p>
            </div>
          </article>
        </div>
      </section>
    </main>
  )
}
