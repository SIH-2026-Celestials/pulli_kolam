import { Link } from 'react-router-dom'
import './Technology.css'

export default function Technology() {
  return (
    <main id="main-content" className="technology-page">
      <header className="technology-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">System Architecture</p>
          <h1 className="heading-display heading-2 technology-title">
            Technology
          </h1>
          <p className="body-text technology-sub">
            The data pipeline and technology stack behind PULLI's computational analysis of traditional Kolam patterns.
          </p>
        </div>
      </header>

      {/* Architecture diagram */}
      <section className="container--narrow section section--bordered">
        <div className="technology-grid">
          <div className="technology-col-left">
            <p className="eyebrow">Data &amp; Analysis Pipeline</p>
            <h2 className="heading-display heading-3">From Dataset to Validated Structure</h2>
            <p className="body-text">
              Raw Kolam traces move through a fixed sequence of stages: parsing, canonical
              representation, graph construction, symmetry/motif analysis, and structural
              validation. Each stage is implemented as an independent Python module so
              intermediate results can be inspected and tested in isolation.
            </p>
          </div>

          <div className="technology-col-right">
            <div className="technology-card diagram-card">
              <h3 className="eyebrow">System Architecture</h3>
              <div className="architecture-flow label-tech">
                <div className="arch-node">Dataset (Kaggle - kolam19 / kolam29 / kolam109)</div>
                <div className="arch-arrow">↓</div>
                <div className="arch-node">Parser (CSV Coordinate Polyline Trace)</div>
                <div className="arch-arrow">↓</div>
                <div className="arch-node">Canonical Representation (Normalized ~0.5u Resolution)</div>
                <div className="arch-arrow">↓</div>
                <div className="arch-node arch-node--highlight">Graph Engine (NetworkX MultiGraph)</div>
                <div className="arch-arrow">↓</div>
                <div className="arch-node">Symmetry / Motif Analysis (D4 + Set-Cover Induction)</div>
                <div className="arch-arrow">↓</div>
                <div className="arch-node arch-node--valid">Validation (Eulerian Trail Constraint Check)</div>
                <div className="arch-arrow">↓</div>
                <div className="arch-node">Visualization (React + Canvas/SVG)</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Tech stack */}
      <section className="section technology-stack-section">
        <div className="container--narrow">
          <div className="section-title-block">
            <p className="eyebrow eyebrow--accent">Stack Specification</p>
            <h2 className="heading-display heading-2">TECHNOLOGY STACK</h2>
            <p className="body-text body-text--sm">
              Only technologies actually used in the current implementation are listed below.
            </p>
          </div>

          <div className="stack-grid">
            <div className="stack-card archival-frame">
              <h3 className="eyebrow">Research Engine</h3>
              <ul className="stack-list label-tech">
                <li><span>Language</span> Python 3.10+</li>
                <li><span>Graph Core</span> NetworkX (MultiGraph)</li>
                <li><span>Data Processing</span> Pandas, NumPy</li>
                <li><span>Visualization</span> Matplotlib</li>
              </ul>
            </div>

            <div className="stack-card archival-frame">
              <h3 className="eyebrow">Frontend</h3>
              <ul className="stack-list label-tech">
                <li><span>Framework</span> React 19</li>
                <li><span>Build Tool</span> Vite</li>
                <li><span>Routing</span> React Router</li>
                <li><span>Styling</span> Plain CSS (design tokens)</li>
              </ul>
            </div>

            <div className="stack-card archival-frame">
              <h3 className="eyebrow">Backend</h3>
              <ul className="stack-list label-tech">
                <li><span>API Layer</span> FastAPI</li>
                <li><span>Endpoints</span> Detect, Analyze, Reconstruct, Compare Detectors</li>
                <li><span>Status</span> Live -- powers the /detect page</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Technical notes */}
      <section className="section technology-details-section">
        <div className="container--narrow">
          <h2 className="heading-display heading-3 section-title">Key Implementation Principles</h2>

          <div className="technology-cards-grid">
            <div className="technology-card">
              <h3 className="eyebrow eyebrow--accent">01 · Dense Polyline Resolution</h3>
              <p className="body-text body-text--sm">
                CSV traces are not clean discrete dot indices; they consist of dense continuous
                polylines sampled at approximately 0.5-unit resolution. Integer-coordinate points
                represent visited Pulli dots, while half-integer coordinates correspond to
                loop-around geometry.
              </p>
            </div>

            <div className="technology-card">
              <h3 className="eyebrow eyebrow--accent">02 · MultiGraph &amp; Multiplicity</h3>
              <p className="body-text body-text--sm">
                Standard simple graphs fail because consecutive dot edges frequently occur with
                multiplicity in complex Kolam motifs. PULLI uses NetworkX <code>MultiGraph</code> to
                preserve edge multiplicity and path topology.
              </p>
            </div>

            <div className="technology-card">
              <h3 className="eyebrow eyebrow--accent">03 · D4 Group Symmetry</h3>
              <p className="body-text body-text--sm">
                Motif comparison requires invariance under Dihedral Group D4 transformations
                (4 rotations, 4 reflections). Local subgraphs are canonicalized into a standard
                orientation before computing motif coverage.
              </p>
            </div>

            <div className="technology-card">
              <h3 className="eyebrow eyebrow--accent">04 · Multi-Motif Set Cover</h3>
              <p className="body-text body-text--sm">
                A single motif model explains only a fraction of a real pattern. PULLI uses a
                greedy set-cover strategy to induce multi-motif vocabularies, reaching ~89.7%
                average edge recall with a fixed radius, and ~99.5% with an adaptive radius.
              </p>
            </div>
          </div>

          <div className="technology-cta">
            <Link to="/how-it-works" className="btn btn--outline">
              ← Back to Pipeline Walkthrough
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}
