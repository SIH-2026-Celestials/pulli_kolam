import { Link } from 'react-router-dom'
import './ModuleCard.css'

export default function ModuleCard({ module }) {
  return (
    <Link to={`/learn/${module.slug}`} className="module-card archival-frame">
      <div className="module-card__header">
        <div className="module-card__tag label-tech">
          <svg className="module-card__icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="1" width="9.8" height="9.8" transform="rotate(45 8 1)" stroke="currentColor" strokeWidth="1.2"/>
          </svg>
          <span>MODULE {module.numberStr}</span>
        </div>
        <span className="module-card__badge label-tech">{module.difficulty}</span>
      </div>

      <div className="module-card__body">
        <h3 className="heading-display heading-4 module-card__title">{module.title}</h3>
        <p className="body-text body-text--sm module-card__sub">{module.subtitle}</p>
      </div>

      <div className="module-card__footer label-tech">
        <span>~{module.estimatedMinutes} MIN READ</span>
        <span className="module-card__arrow">START MODULE →</span>
      </div>
    </Link>
  )
}
