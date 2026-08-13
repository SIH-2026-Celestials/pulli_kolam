import { Link } from 'react-router-dom'
import './Project.css'

export default function Project() {
  return (
    <main id="main-content" className="project-page">
      <header className="project-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">Project Background &amp; Scope</p>
          <h1 className="heading-display heading-2 project-title">
            Project Overview: PULLI
          </h1>
          <p className="body-text project-sub">
            A computational platform for studying, representing and analysing traditional one-stroke dotted Kolam patterns using geometric traces, graph structures and pattern-based methods.
          </p>
        </div>
      </header>

      {/* Problem Statement */}
      <section className="container--narrow section section--bordered">
        <div className="project-section-grid">
          <div className="grid-col-left">
            <h2 className="eyebrow">BACKGROUND</h2>
            <h3 className="heading-display heading-3">The Mathematical Structure of Traditional Kolam</h3>
          </div>
          <div className="grid-col-right body-text">
            <p>
              Pulli Kolam is a traditional South Indian form of geometric drawing constructed around a matrix field of dots (Pulli). A single continuous line loops around dots without crossing itself incorrectly, creating intricate symmetrical figures.
            </p>
            <p>
              While resulting patterns appear artistic and intuitive, many designs exhibit recurring underlying structure involving symmetry, loop continuity, strand multiplicity, and strict spatial relationships. PULLI explores how these characteristics can be represented digitally and analysed computationally.
            </p>
          </div>
        </div>
      </section>

      {/* Three Pillars */}
      <section className="container--narrow section section--bordered">
        <h2 className="eyebrow eyebrow--accent" style={{ marginBottom: '2rem' }}>THREE CORE PILLARS</h2>
        <div className="pillars-detail-grid">
          <div className="pillar-detail-card archival-frame">
            <span className="eyebrow">PILLAR 01</span>
            <h3 className="heading-display heading-4">DIGITAL PRESERVATION</h3>
            <p className="body-text body-text--sm">
              Digitally represent traditional Kolam patterns and their geometric traces from authentic datasets into standardized vector polylines, capturing coordinate order and bounding geometry.
            </p>
          </div>

          <div className="pillar-detail-card archival-frame">
            <span className="eyebrow">PILLAR 02</span>
            <h3 className="heading-display heading-4">COMPUTATIONAL ANALYSIS</h3>
            <p className="body-text body-text--sm">
              Study drawing paths, graph structures using NetworkX MultiGraph to preserve strand multiplicity, analyze dihedral D4 group symmetry, and induce multi-motif local subgraphs.
            </p>
          </div>

          <div className="pillar-detail-card archival-frame">
            <span className="eyebrow">PILLAR 03</span>
            <h3 className="heading-display heading-4">GENERATIVE POTENTIAL</h3>
            <p className="body-text body-text--sm">
              Build a foundation for computational reconstruction and future generation of valid patterns by evaluating candidates against automated Eulerian trail constraint filters.
            </p>
          </div>
        </div>
      </section>

      {/* Call to action */}
      <section className="container--narrow section">
        <div className="project-cta-card archival-frame">
          <div>
            <h3 className="heading-display heading-3">Explore the Technology &amp; Pipeline</h3>
            <p className="body-text body-text--sm">
              Learn how PULLI parses polylines into MultiGraph edge multiplicity and checks Eulerian path constraints.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <Link to="/how-it-works" className="btn btn--primary">
              How It Works →
            </Link>
            <Link to="/technology" className="btn btn--outline">
              System Architecture →
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}
