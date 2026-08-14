import './ConceptCard.css'

export default function ConceptCard({ term, definition, formula }) {
  return (
    <div className="concept-card">
      <span className="concept-card__term eyebrow eyebrow--accent">{term}</span>
      <p className="concept-card__def body-text body-text--sm">{definition}</p>
      {formula && (
        <div className="concept-card__formula label-tech">
          {formula}
        </div>
      )}
    </div>
  )
}
