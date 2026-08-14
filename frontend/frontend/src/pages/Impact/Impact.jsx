import { Link } from 'react-router-dom'
import { useLanguage } from '../../context/LanguageContext'
import './Impact.css'

export default function Impact() {
  const { t } = useLanguage()

  return (
    <main id="main-content" className="impact-page">
      <header className="impact-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">{t('impact.eyebrow')}</p>
          <h1 className="heading-display heading-2 impact-title">
            {t('impact.title')}
          </h1>
          <p className="body-text impact-sub">
            {t('impact.sub')}
          </p>
        </div>
      </header>

      <section className="container--narrow section section--bordered">
        <div className="impact-detail-grid">
          <div className="impact-detail-card archival-frame">
            <h3 className="eyebrow eyebrow--accent">CULTURAL HERITAGE</h3>
            <h4 className="heading-display heading-3">Digital Preservation</h4>
            <p className="body-text body-text--sm">
              Traditional Kolam patterns are typically transmitted by hand and observation rather
              than written specification. Representing patterns as coordinate traces and graph
              structures provides a documentation format that can be stored, indexed, and
              compared computationally - supporting archival efforts alongside the original
              artistic practice.
            </p>
          </div>

          <div className="impact-detail-card archival-frame">
            <h3 className="eyebrow eyebrow--accent">EDUCATION</h3>
            <h4 className="heading-display heading-3">STEM &amp; Ethnomathematics</h4>
            <p className="body-text body-text--sm">
              Kolam construction encodes geometry, symmetry groups, graph theory, and
              combinatorics inside a familiar cultural practice. A computational lens on these
              patterns offers a concrete way to introduce dihedral symmetry, Eulerian paths, and
              graph representations in a classroom setting.
            </p>
          </div>

          <div className="impact-detail-card archival-frame">
            <h3 className="eyebrow eyebrow--accent">RESEARCH &amp; INNOVATION</h3>
            <h4 className="heading-display heading-3">Pattern Systems</h4>
            <p className="body-text body-text--sm">
              The MultiGraph and multi-motif set-cover methods developed for Kolam analysis are
              not specific to this dataset - they generalize to other continuous, structured
              visual patterns with loop-around geometry, offering a reusable computational
              framework for studying similar traditional design systems.
            </p>
          </div>

          <div className="impact-detail-card archival-frame">
            <h3 className="eyebrow eyebrow--accent">DIGITAL HERITAGE</h3>
            <h4 className="heading-display heading-3">Searchable Repositories</h4>
            <p className="body-text body-text--sm">
              Structured, validated representations lay the groundwork for searchable digital
              archives of traditional artistic designs - allowing patterns to be queried by
              structural properties such as symmetry class or motif composition rather than
              by filename alone.
            </p>
          </div>
        </div>
      </section>

      <section className="container--narrow section impact-cta-section">
        <div className="impact-cta-card archival-frame">
          <div>
            <h3 className="heading-display heading-3">See the Current Evidence</h3>
            <p className="body-text body-text--sm">
              These are potential directions built on top of verified experimental results -
              not claims about deployed systems or measured adoption.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <Link to="/explore" className="btn btn--primary">
              Explore the Archive →
            </Link>
            <Link to="/project" className="btn btn--outline">
              Project Overview →
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}
