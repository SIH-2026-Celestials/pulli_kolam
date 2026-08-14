import ModuleCard from '../../components/ModuleCard/ModuleCard'
import { learnModules } from '../../data/learnData'
import './Learn.css'

export default function Learn() {
  return (
    <main id="main-content" className="learn-page">
      {/* ── 1. HERO SECTION ────────────────────────────────────────────── */}
      <header className="learn-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">INDIAN KNOWLEDGE SYSTEMS (IKS)</p>
          <h1 className="heading-display heading-2 learn-title">
            LEARNING &amp; EDUCATION
          </h1>
          <p className="body-text learn-sub">
            Explore the ethnomathematics, graph theory, D₄ symmetry groups, and cultural history behind South Indian one-stroke <em>Pulli Kolam</em> patterns.
          </p>
        </div>
      </header>

      {/* ── 2. MODULE CARDS GRID ───────────────────────────────────────── */}
      <section className="container--narrow section section--bordered">
        <div className="section-title-block">
          <p className="eyebrow">Interactive Curriculum</p>
          <h2 className="heading-display heading-3">FOUR LEARNING MODULES</h2>
          <p className="body-text body-text--sm">
            Select a module below to study its mathematical theory and interact with live visual demonstrations.
          </p>
        </div>

        <div className="learn-modules-grid">
          {learnModules.map(module => (
            <ModuleCard key={module.id} module={module} />
          ))}
        </div>
      </section>

      {/* ── 3. WHY STUDY KOLAM? (3 VALUE PILLARS) ──────────────────────── */}
      <section className="section section--bordered learn-why-section">
        <div className="container--narrow">
          <div className="section-title-block">
            <p className="eyebrow eyebrow--accent">Pedagogical Value</p>
            <h2 className="heading-display heading-3">WHY STUDY KOLAM MATHEMATICS?</h2>
            <p className="body-text body-text--sm">
              How traditional South Indian ritual floor drawings bridge ancient cultural practice with modern computer science.
            </p>
          </div>

          <div className="why-grid">
            <div className="why-card archival-frame">
              <span className="eyebrow eyebrow--accent">PILLAR 01</span>
              <h3 className="heading-display heading-4">Ethnomathematics</h3>
              <p className="body-text body-text--sm">
                Demonstrates how complex topological ideas (Eulerian circuits, array grammars, knot theory) were practiced intuitively for centuries prior to modern formal graph notation.
              </p>
            </div>

            <div className="why-card archival-frame">
              <span className="eyebrow eyebrow--accent">PILLAR 02</span>
              <h3 className="heading-display heading-4">STEM &amp; Computer Science</h3>
              <p className="body-text body-text--sm">
                Provides a visual, interactive medium for teaching graph theory, edge multiplicity, array expansion, and D₄ dihedral group transformations to students.
              </p>
            </div>

            <div className="why-card archival-frame">
              <span className="eyebrow eyebrow--accent">PILLAR 03</span>
              <h3 className="heading-display heading-4">Cultural Heritage</h3>
              <p className="body-text body-text--sm">
                Supports AICTE's Indian Knowledge Systems (IKS) initiative by preserving sacred oral and floor art traditions in machine-readable computational formats.
              </p>
            </div>
          </div>
        </div>
      </section>


    </main>
  )
}
