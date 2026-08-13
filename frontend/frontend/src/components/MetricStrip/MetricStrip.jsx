import './MetricStrip.css'

/**
 * MetricStrip - Restrained research metrics display.
 * 
 * NOT colorful SaaS cards. Research-table aesthetic with
 * thin rules, typographic number + label pairs, and context.
 */
export default function MetricStrip({ metrics, context }) {
  return (
    <div className="metric-strip">
      {context && (
        <p className="metric-strip__context eyebrow">{context}</p>
      )}
      <div className="metric-strip__grid">
        {metrics.map((m, i) => (
          <div key={i} className="metric-strip__item">
            <div className="metric-strip__value">{m.value}</div>
            <div className="metric-strip__label label-tech">{m.label}</div>
            {m.note && (
              <div className="metric-strip__note">{m.note}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
