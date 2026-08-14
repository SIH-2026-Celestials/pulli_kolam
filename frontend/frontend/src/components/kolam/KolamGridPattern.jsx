import './kolam.css'

export default function KolamGridPattern({ opacity = 0.04 }) {
  // Renders a repeating dot lattice grid background using CSS/SVG patterns
  return (
    <div className="kolam-grid-pattern" style={{ opacity }} aria-hidden="true">
      <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="kolam-dots" width="40" height="40" patternUnits="userSpaceOnUse">
            <circle cx="20" cy="20" r="1.2" fill="var(--color-gold)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#kolam-dots)" />
      </svg>
    </div>
  )
}
