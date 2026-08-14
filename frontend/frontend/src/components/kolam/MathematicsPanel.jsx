/**
 * Shared "Mathematics" panel — renders the real PatternAnalysis payload
 * returned by the backend (candidate.analysis / candidate.mathematics,
 * GET /api/v1/generations/{id}/mathematics). Used by both
 * GeneratedVariations (compact, per-card) and Playground (full-size,
 * collapsible). Every value rendered here comes directly from the
 * backend response object passed in via `analysis` -- this file never
 * invents a number; a missing field renders as "—", never a guess.
 */
import './MathematicsPanel.css'

const EXPLAIN = {
  graph: 'Real vertex/edge counts from the persisted structural representation (engine.generation_contract).',
  eulerian: 'Whether the stroke graph admits a single continuous pass (engine.validity), the core one-stroke constraint.',
  multiplicity: 'How many times the same dot-to-dot edge repeats in the trace; PULLI patterns can legitimately retrace a strand.',
  symmetry: 'Fraction of the structure explained by a D4 (8-fold dihedral) symmetry match (engine.symmetry).',
  complexity: 'A derived structural-complexity / density score (engine analysis), not a subjective quality rating.',
  novelty: 'Distance from the nearest known source pattern in the training/reference set (engine.novelty).',
}

function Row({ label, value }) {
  return (
    <div className="math-row">
      <span>{label}</span>
      <span>{value ?? '—'}</span>
    </div>
  )
}

export default function MathematicsPanel({ analysis, compact = false }) {
  if (!analysis) {
    return <p className="math-empty">Mathematics not available for this pattern.</p>
  }
  const { graph, eulerian, multiplicity, symmetry, complexity, novelty } = analysis

  return (
    <div className={`math-grid${compact ? ' math-grid--compact' : ''}`}>
      {graph && (
        <div className="math-group" title={EXPLAIN.graph}>
          <div className="math-group-title">Graph</div>
          <Row label="Vertices" value={graph.vertices} />
          <Row label="Edges (instances)" value={graph.edges} />
          <Row label="Distinct edges" value={graph.distinct_edges} />
          <Row label="Components" value={graph.connected_components} />
          {!compact && <Row label="Density" value={graph.density != null ? graph.density.toFixed(3) : null} />}
        </div>
      )}
      {eulerian && (
        <div className="math-group" title={EXPLAIN.eulerian}>
          <div className="math-group-title">Eulerian structure</div>
          <Row label="Odd-degree vertices" value={eulerian.odd_degree_vertex_count} />
          <Row label="Circuit" value={eulerian.is_eulerian_circuit ? 'Yes' : 'No'} />
          <Row label="Open path" value={eulerian.has_eulerian_path ? 'Yes' : 'No'} />
        </div>
      )}
      {multiplicity && (
        <div className="math-group" title={EXPLAIN.multiplicity}>
          <div className="math-group-title">Multiplicity</div>
          <Row label="Max strand count" value={multiplicity.max_multiplicity} />
          <Row label="Violations (>2)" value={multiplicity.violations} />
        </div>
      )}
      {symmetry && (
        <div className="math-group" title={EXPLAIN.symmetry}>
          <div className="math-group-title">Symmetry</div>
          <Row label="D4 coverage" value={symmetry.coverage != null ? `${(symmetry.coverage * 100).toFixed(0)}%` : null} />
        </div>
      )}
      {complexity && (
        <div className="math-group" title={EXPLAIN.complexity}>
          <div className="math-group-title">Complexity</div>
          <Row label="Complexity score" value={complexity.complexity_score != null ? complexity.complexity_score.toFixed(3) : null} />
          <Row label="Density score" value={complexity.density_score != null ? complexity.density_score.toFixed(3) : null} />
        </div>
      )}
      {novelty && (
        <div className="math-group" title={EXPLAIN.novelty}>
          <div className="math-group-title">Novelty</div>
          <Row label="Novelty score" value={novelty.novelty_score != null ? novelty.novelty_score.toFixed(3) : null} />
          <Row label="Nearest source" value={novelty.nearest_source_id ?? 'Not available'} />
        </div>
      )}
    </div>
  )
}
