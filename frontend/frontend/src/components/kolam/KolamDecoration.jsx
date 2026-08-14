import './kolam.css'

export default function KolamDecoration({ variant = 'horizontal', width = '100%', height = '16px' }) {
  // Renders a beautiful line divider utilizing continuous loop style geometry (like a running border)
  if (variant === 'vertical') {
    return (
      <div className="kolam-decor-wrapper vertical" style={{ width, height }} aria-hidden="true">
        <svg width="10" height="100%" viewBox="0 0 10 100" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
          <line x1="5" y1="0" x2="5" y2="100" stroke="var(--color-card-border)" strokeWidth="0.8" strokeDasharray="3 6" />
          <circle cx="5" cy="25" r="1.5" fill="var(--color-gold)" opacity="0.3" />
          <circle cx="5" cy="50" r="1.5" fill="var(--color-gold)" opacity="0.3" />
          <circle cx="5" cy="75" r="1.5" fill="var(--color-gold)" opacity="0.3" />
        </svg>
      </div>
    )
  }

  return (
    <div className="kolam-decor-wrapper horizontal" style={{ width, height }} aria-hidden="true">
      <svg width="100%" height="16" viewBox="0 0 400 16" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M 0 8 Q 20 2, 40 8 T 80 8 T 120 8 T 160 8 T 200 8 T 240 8 T 280 8 T 320 8 T 360 8 T 400 8"
          stroke="var(--color-gold)"
          strokeWidth="0.7"
          strokeOpacity="0.25"
          fill="none"
        />
        <path
          d="M 0 8 Q 20 14, 40 8 T 80 8 T 120 8 T 160 8 T 200 8 T 240 8 T 280 8 T 320 8 T 360 8 T 400 8"
          stroke="var(--color-gold)"
          strokeWidth="0.7"
          strokeOpacity="0.25"
          fill="none"
        />
        <circle cx="40" cy="8" r="1.2" fill="var(--color-gold)" opacity="0.25" />
        <circle cx="120" cy="8" r="1.2" fill="var(--color-gold)" opacity="0.25" />
        <circle cx="200" cy="8" r="1.2" fill="var(--color-gold)" opacity="0.25" />
        <circle cx="280" cy="8" r="1.2" fill="var(--color-gold)" opacity="0.25" />
        <circle cx="360" cy="8" r="1.2" fill="var(--color-gold)" opacity="0.25" />
      </svg>
    </div>
  )
}
