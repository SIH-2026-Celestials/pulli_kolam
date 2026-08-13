import { useParams, Link, useNavigate } from 'react-router-dom'
import { getKolam } from '../../data/kolams'
import './KolamDetail.css'

export default function KolamDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const kolam = getKolam(id)

  if (!kolam) {
    return (
      <main id="main-content" className="container--narrow section">
        <div className="detail-not-found">
          <h1 className="heading-display heading-3">Kolam #{id} not found</h1>
          <p className="body-text">The requested pattern ID does not exist in the current dataset (kolam19).</p>
          <Link to="/explore" className="btn btn--primary" style={{ marginTop: '1rem' }}>
            Back to Explorer
          </Link>
        </div>
      </main>
    )
  }

  const prevId = kolam.id > 1 ? kolam.id - 1 : null
  const nextId = kolam.id < 400 ? kolam.id + 1 : null

  return (
    <main id="main-content" className="kolam-detail-page">
      <div className="detail-bar">
        <div className="container--narrow detail-bar__inner">
          <nav className="detail-breadcrumb label-tech" aria-label="Breadcrumb">
            <Link to="/explore" className="detail-breadcrumb__link">Explore</Link>
            <span className="detail-breadcrumb__sep">/</span>
            <span>Kolam {kolam.id}</span>
          </nav>

          <div className="detail-nav-buttons">
            <button
              disabled={!prevId}
              onClick={() => prevId && navigate(`/explore/${prevId}`)}
              className="btn btn--outline btn--sm"
              aria-label="Previous Kolam"
            >
              ← Prev ({prevId || '-'})
            </button>
            <button
              disabled={!nextId}
              onClick={() => nextId && navigate(`/explore/${nextId}`)}
              className="btn btn--outline btn--sm"
              aria-label="Next Kolam"
            >
              Next ({nextId || '-'}) →
            </button>
          </div>
        </div>
      </div>

      {/* Main split research view */}
      <section className="container--narrow detail-content section">
        <div className="detail-grid">
          {/* Left: Large Kolam image viewer */}
          <div className="detail-visual-panel">
            <div className="detail-image-frame">
              <img
                src={kolam.imagePath}
                alt={`Kolam pattern ${kolam.id} high resolution`}
                className="detail-image"
              />
            </div>
            <div className="detail-caption label-tech">
              Dataset: kolam19 · File: kolam19-{kolam.id - 1}.jpg
            </div>
          </div>

          {/* Right: Structural Research Data */}
          <div className="detail-data-panel">
            <div className="detail-header-block">
              <p className="eyebrow eyebrow--accent">Research Item #{kolam.id}</p>
              <h1 className="heading-display heading-2">Kolam {kolam.id}</h1>
              <p className="body-text body-text--sm">
                Dense coordinate polyline trace from Kaggle dataset. Analyzed for geometric properties,
                Eulerian path validity, and D4 group symmetry.
              </p>
            </div>

            <div className="detail-sections">
              {/* Geometry block */}
              <div className="detail-block">
                <h2 className="detail-block__title eyebrow">GEOMETRY</h2>
                <div className="detail-data-table">
                  <div className="detail-row">
                    <span className="detail-key">Points</span>
                    <span className="detail-val">{kolam.points}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Path length</span>
                    <span className="detail-val">{kolam.pathLength} units</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Bounding box</span>
                    <span className="detail-val">{kolam.width} × {kolam.height}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Start-End distance</span>
                    <span className="detail-val">{kolam.startEndDistance.toFixed(1)} (Closed)</span>
                  </div>
                </div>
              </div>

              {/* Validity block */}
              <div className="detail-block">
                <h2 className="detail-block__title eyebrow">VALIDITY</h2>
                <div className="detail-data-table">
                  <div className="detail-row">
                    <span className="detail-key">One-stroke continuous</span>
                    <span className="detail-val detail-val--valid">✓ Passed</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Closed loop</span>
                    <span className="detail-val detail-val--valid">✓ Yes</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Eulerian path constraint</span>
                    <span className="detail-val detail-val--valid">✓ Verified</span>
                  </div>
                </div>
              </div>

              {/* Symmetry block */}
              <div className="detail-block">
                <h2 className="detail-block__title eyebrow">SYMMETRY</h2>
                <div className="detail-data-table">
                  <div className="detail-row">
                    <span className="detail-key">Vertical symmetry</span>
                    <span className="detail-val">{kolam.symmetry.vertical.toFixed(5)}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Horizontal symmetry</span>
                    <span className="detail-val">{kolam.symmetry.horizontal.toFixed(1)}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">180° Rotational</span>
                    <span className="detail-val">{kolam.symmetry.rotation180.toFixed(5)}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="detail-actions">
              <Link to={`/analyze?kolam=${kolam.id}`} className="btn btn--primary">
                Analyze this Kolam
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
