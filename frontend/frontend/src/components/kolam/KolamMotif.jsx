import './kolam.css'

export default function KolamMotif({ size = 24, opacity = 0.3 }) {
  // A small classic 4-fold symmetric loop motif (flower style)
  return (
    <span className="kolam-motif-inline" style={{ width: size, height: size, opacity }} aria-hidden="true">
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M 12 12 Q 12 4, 16 4 Q 20 4, 20 8 Q 20 12, 12 12 Z"
          stroke="var(--color-gold)"
          strokeWidth="0.8"
        />
        <path
          d="M 12 12 Q 20 12, 20 16 Q 20 20, 16 20 Q 12 20, 12 12 Z"
          stroke="var(--color-gold)"
          strokeWidth="0.8"
        />
        <path
          d="M 12 12 Q 12 20, 8 20 Q 4 20, 4 16 Q 4 12, 12 12 Z"
          stroke="var(--color-gold)"
          strokeWidth="0.8"
        />
        <path
          d="M 12 12 Q 4 12, 4 8 Q 4 4, 8 4 Q 12 4, 12 12 Z"
          stroke="var(--color-gold)"
          strokeWidth="0.8"
        />
        <circle cx="12" cy="12" r="1" fill="var(--color-gold)" />
      </svg>
    </span>
  )
}
