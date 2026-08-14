import './kolam.css'

export default function KolamCornerDecoration({ position = 'top-left' }) {
  // SVG drawing of a traditional corner kolam motif (very subtle, low opacity, antique gold color)
  return (
    <div className={`kolam-corner-decor ${position}`} aria-hidden="true">
      <svg width="120" height="120" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M 10 10 Q 30 10 30 30 Q 10 30 10 10 Z"
          stroke="var(--color-gold)"
          strokeWidth="0.8"
          strokeOpacity="0.25"
        />
        <path
          d="M 10 10 Q 50 10 50 50 Q 10 50 10 10 Z"
          stroke="var(--color-gold)"
          strokeWidth="0.5"
          strokeOpacity="0.15"
          strokeDasharray="2 2"
        />
        <circle cx="30" cy="30" r="1.5" fill="var(--color-gold)" opacity="0.25" />
        <circle cx="50" cy="50" r="1" fill="var(--color-gold)" opacity="0.15" />
        <path
          d="M 30 10 C 35 15, 35 25, 30 30 C 25 35, 15 35, 10 30"
          stroke="var(--color-gold)"
          strokeWidth="0.8"
          strokeOpacity="0.2"
        />
      </svg>
    </div>
  )
}
