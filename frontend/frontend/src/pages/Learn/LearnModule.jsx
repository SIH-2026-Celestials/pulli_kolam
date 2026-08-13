import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import ConceptCard from '../../components/ConceptCard/ConceptCard'
import MathematicsFlow from './interactions/MathematicsFlow'
import SymmetryDemo from './interactions/SymmetryDemo'
import PulliGridDemo from './interactions/PulliGridDemo'
import StrokeDemo from './interactions/StrokeDemo'
import EnclosureDemo from './interactions/EnclosureDemo'
import SmoothnessDemo from './interactions/SmoothnessDemo'
import SymmetryBuildDemo from './interactions/SymmetryBuildDemo'
import { learnModules } from '../../data/learnData'
import './LearnModule.css'

// Typology image assets imported directly for Vite bundling pipeline
import PulliSikkuKolam from '../../assets/Pulli-Sikku-Kolam.png'
import KoduKambiKolam from '../../assets/Kodu-Kambi-Kolam.png'
import FreehandRangoli from '../../assets/Freehand-Rangoli.png'
import BramhaMudi from '../../assets/Bramha Mudi.png'

// Interactive component registry lookup map (no if-else branching chains)
const MODULE_VISUALS = {
  mathematics: MathematicsFlow,
  symmetry: SymmetryDemo
}

// Section-specific inline interactive visuals
const SECTION_VISUALS = {
  'rule-1-dot-grid': PulliGridDemo,
  'rule-2-continuous-loop': StrokeDemo,
  'rule-3-dot-enclosure': EnclosureDemo,
  'rule-4-smoothness': SmoothnessDemo,
  'rule-5-symmetry': SymmetryBuildDemo
}

function TypologyVisual({ visualId }) {
  if (!visualId) return null

  const imageMap = {
    sikku: PulliSikkuKolam,
    kambi: KoduKambiKolam,
    freehand: FreehandRangoli,
    bramhamudi: BramhaMudi
  }

  const src = imageMap[visualId]
  if (!src) return null

  return (
    <div className="typology-canvas">
      <img src={src} className="typology-img" alt={visualId} />
    </div>
  )
}

export default function LearnModule() {
  const { moduleSlug } = useParams()
  const moduleIndex = learnModules.findIndex(m => m.slug === moduleSlug)
  const currentModule = learnModules[moduleIndex] || learnModules[0]
  const prevModule = learnModules[moduleIndex - 1]
  const nextModule = learnModules[moduleIndex + 1]

  const [activeSectionId, setActiveSectionId] = useState(currentModule.sections?.[0]?.id || '')
  const [prevSlug, setPrevSlug] = useState(moduleSlug)

  if (moduleSlug !== prevSlug) {
    setPrevSlug(moduleSlug)
    setActiveSectionId(currentModule.sections?.[0]?.id || '')
  }

  const VisualComponent = MODULE_VISUALS[currentModule.slug] || null

  useEffect(() => {
    window.scrollTo(0, 0)

    const sections = document.querySelectorAll('.module-section')
    const observerOptions = {
      root: null,
      rootMargin: '-15% 0px -65% 0px',
      threshold: 0
    }

    const observerCallback = (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          setActiveSectionId(entry.target.id)
        }
      })
    }

    const observer = new IntersectionObserver(observerCallback, observerOptions)
    sections.forEach(sec => observer.observe(sec))

    return () => {
      observer.disconnect()
    }
  }, [moduleSlug, currentModule])

  return (
    <main id="main-content" className="module-page">
      {/* Header & Breadcrumb */}
      <header className="module-header section section--bordered">
        <div className="container--narrow">
          <nav className="breadcrumb label-tech" aria-label="Breadcrumb navigation">
            <Link to="/learn" className="breadcrumb__link">LEARN</Link>
            <span className="breadcrumb__sep">/</span>
            <span className="breadcrumb__current">MODULE {currentModule.numberStr}</span>
          </nav>

          <div className="module-title-group">
            <span className="eyebrow eyebrow--accent">MODULE {currentModule.numberStr} · {currentModule.difficulty}</span>
            <h1 className="heading-display heading-2 module-title">{currentModule.title}</h1>
            <p className="body-text module-sub">{currentModule.subtitle}</p>
          </div>
        </div>
      </header>

      {/* Main Content Layout (Sidebar ToC + Content) */}
      <section className="container--narrow section section--bordered">
        <div className="module-layout">
          {/* Sticky Sidebar ToC */}
          <aside className="module-sidebar">
            <div className="toc-frame archival-frame">
              <span className="eyebrow">TABLE OF CONTENTS</span>
              <ul className="toc-list label-tech">
                {currentModule.sections.map(section => (
                  <li key={section.id}>
                    <a
                      href={`#${section.id}`}
                      className={`toc-link ${activeSectionId === section.id ? 'toc-link--active' : ''}`}
                      onClick={() => setActiveSectionId(section.id)}
                    >
                      {section.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </aside>

          {/* Core Content Body */}
          <article className="module-body">
            {/* Embedded Visual Interactive Demo (Top or In-Context) */}
            {VisualComponent && (
              <section className="module-visual-wrap">
                <span className="eyebrow eyebrow--accent">INTERACTIVE DEMONSTRATION</span>
                <VisualComponent />
              </section>
            )}

            {/* Render Content Sections */}
            {currentModule.sections.map(sec => {
              const SectionVisual = SECTION_VISUALS[sec.id]
              return (
                <section key={sec.id} id={sec.id} className="module-section">
                  <h2 className="heading-display heading-3 sec-heading">{sec.title}</h2>
                  
                  {SectionVisual && (
                    <div className="section-inline-visual" style={{ marginTop: '1rem', marginBottom: '1.5rem' }}>
                      <SectionVisual />
                    </div>
                  )}

                  <p className="body-text sec-text" style={{ whiteSpace: 'pre-wrap' }}>{sec.content}</p>

                {/* Bullets */}
                {sec.bullets && (
                  <ul className="sec-bullets body-text body-text--sm">
                    {sec.bullets.map((b, idx) => (
                      <li key={idx} className="sec-bullet-item">{b}</li>
                    ))}
                  </ul>
                )}

                {sec.contentPost && (
                  <p className="body-text sec-text" style={{ marginTop: '1rem', whiteSpace: 'pre-wrap' }}>{sec.contentPost}</p>
                )}

                {/* Unified Explanatory Callout Card (Formula + Simple Terms) */}
                {(sec.formula || sec.simpleTerms) && (
                  <div className="sec-formula-box archival-frame" style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {sec.formula && (
                      <div className="formula-block">
                        <span className="eyebrow">MATHEMATICAL FORMULATION</span>
                        <div className="sec-formula-text label-tech" style={{ marginTop: '4px' }}>{sec.formula}</div>
                      </div>
                    )}
                    {sec.simpleTerms && (
                      <div className="simple-terms-block" style={{ borderTop: sec.formula ? '1px solid var(--color-card-border)' : 'none', paddingTop: sec.formula ? '16px' : '0' }}>
                        <div className="simple-terms-title label-tech" style={{ fontSize: '11px', fontWeight: '700', color: 'var(--color-maroon-main)', letterSpacing: '0.08em', marginBottom: '6px' }}>
                          IN SIMPLE TERMS
                        </div>
                        <p className="body-text body-text--sm" style={{ margin: 0, color: 'var(--color-text-body)', lineHeight: '1.6' }}>{sec.simpleTerms}</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Typologies List (Module 1) */}
                {sec.typologies && (
                  <div className="typologies-grid">
                    {sec.typologies.map((t, idx) => (
                      <div key={idx} className="typology-card archival-frame">
                        <div className="typology-header">
                          <span className="heading-display heading-4">{t.name}</span>
                          <span className="typology-tamil label-tech">{t.tamil}</span>
                        </div>
                        <p className="body-text body-text--sm">{t.desc}</p>
                        <TypologyVisual visualId={t.visualId} />
                      </div>
                    ))}
                  </div>
                )}

                {/* Regional Table (Module 1) */}
                {sec.table && (
                  <div className="table-frame archival-frame">
                    <table className="regional-table">
                      <thead>
                        <tr>
                          <th className="label-tech">REGION</th>
                          <th className="label-tech">LOCAL NAME</th>
                          <th className="label-tech">GRID TYPE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sec.table.map((r, idx) => (
                          <tr key={idx}>
                            <td>{r.region}</td>
                            <td style={{ color: 'var(--color-accent)', fontWeight: 600 }}>{r.name}</td>
                            <td>{r.gridType}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Key Concepts */}
                {sec.concepts && (
                  <div className="sec-concepts">
                    {sec.concepts.map((c, idx) => (
                      <ConceptCard key={idx} term={c.term} definition={c.definition} />
                    ))}
                  </div>
                )}
              </section>
            )})}


            {/* Bottom Module Navigation */}
            <nav className="module-nav-bar">
              {prevModule ? (
                <Link to={`/learn/${prevModule.slug}`} className="btn btn--outline">
                  ← Module {prevModule.numberStr}: {prevModule.title}
                </Link>
              ) : <div />}

              {nextModule ? (
                <Link to={`/learn/${nextModule.slug}`} className="btn btn--primary">
                  Module {nextModule.numberStr}: {nextModule.title} →
                </Link>
              ) : (
                <Link to="/learn" className="btn btn--primary">
                  ✓ Back to Module Overview
                </Link>
              )}
            </nav>
          </article>
        </div>
      </section>
    </main>
  )
}
