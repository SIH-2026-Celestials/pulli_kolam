import { Link } from 'react-router-dom'
import './KolamCard.css'

/**
 * KolamCard - Gallery card for a single Kolam.
 * Shows the actual image with number label.
 * Hover reveals basic metadata.
 */
export default function KolamCard({ kolam, compact = false }) {
  const { id, points, pathLength, width, height, validity } = kolam

  return (
    <Link
      to={`/explore/${id}`}
      className={`kolam-card${compact ? ' kolam-card--compact' : ''}`}
      aria-label={`View Kolam ${id}`}
    >
      {/* Image */}
      <div className="kolam-card__image-wrap">
        <img
          src={kolam.imagePath}
          alt={`Kolam pattern ${id}`}
          className="kolam-card__image"
          loading="lazy"
          decoding="async"
        />
        {/* Hover overlay */}
        <div className="kolam-card__overlay" aria-hidden="true">
          <div className="kolam-card__overlay-content">
            <span className="label-tech">Points: {points}</span>
            <span className="label-tech">Path: {pathLength.toFixed(0)}</span>
            <span className="label-tech">{width}×{height}</span>
          </div>
        </div>
      </div>

      {/* Label */}
      <div className="kolam-card__label">
        <span className="kolam-card__number">Kolam {id}</span>
        {validity?.isValid && (
          <span className="kolam-card__valid" aria-label="Valid one-stroke">✓</span>
        )}
      </div>
    </Link>
  )
}
