import './kolam.css'

export default function TamilCultureBackground() {
  return (
    <div className="tamil-background-root" aria-hidden="true">
      {/* 1. LEFT TEMPLE PILLAR COLUMN */}
      <div className="tamil-pillar-left">
        <svg width="80" height="100%" viewBox="0 0 80 800" preserveAspectRatio="none" fill="none" stroke="var(--color-gold)" strokeWidth="0.8">
          {/* Capital Bodegai Bracket */}
          <path d="M 10 40 Q 20 20 40 20 Q 60 20 70 40" />
          <path d="M 5 50 Q 20 30 40 30 Q 60 30 75 50" strokeWidth="0.5" />
          <rect x="15" y="50" width="50" height="12" rx="1" />
          <path d="M 15 62 L 5 75 H 75 L 65 62 Z" />
          
          {/* Shaft Column with rings and carvings */}
          <line x1="25" y1="75" x2="25" y2="720" />
          <line x1="55" y1="75" x2="55" y2="720" />
          <line x1="30" y1="75" x2="30" y2="720" strokeWidth="0.4" strokeDasharray="4 4" />
          <line x1="50" y1="75" x2="50" y2="720" strokeWidth="0.4" strokeDasharray="4 4" />
          
          {/* Decorative Shaft Rings */}
          {[120, 200, 280, 360, 440, 520, 600].map((y) => (
            <g key={`ring-${y}`}>
              <rect x="20" y={y} width="40" height="8" fill="none" stroke="var(--color-gold)" strokeWidth="0.8" />
              <line x1="20" y1={y + 4} x2="60" y2={y + 4} strokeWidth="0.4" />
            </g>
          ))}
          
          {/* Column Pedestal Base */}
          <path d="M 25 720 L 15 735 H 65 L 55 720 Z" />
          <rect x="10" y="735" width="60" height="15" rx="1" />
          <rect x="5" y="750" width="70" height="40" rx="2" />
          <line x1="5" y1="770" x2="75" y2="770" strokeWidth="0.5" />
        </svg>
      </div>

      {/* 2. RIGHT TEMPLE PILLAR COLUMN */}
      <div className="tamil-pillar-right">
        <svg width="80" height="100%" viewBox="0 0 80 800" preserveAspectRatio="none" fill="none" stroke="var(--color-gold)" strokeWidth="0.8">
          <path d="M 10 40 Q 20 20 40 20 Q 60 20 70 40" />
          <path d="M 5 50 Q 20 30 40 30 Q 60 30 75 50" strokeWidth="0.5" />
          <rect x="15" y="50" width="50" height="12" rx="1" />
          <path d="M 15 62 L 5 75 H 75 L 65 62 Z" />
          
          <line x1="25" y1="75" x2="25" y2="720" />
          <line x1="55" y1="75" x2="55" y2="720" />
          <line x1="30" y1="75" x2="30" y2="720" strokeWidth="0.4" strokeDasharray="4 4" />
          <line x1="50" y1="75" x2="50" y2="720" strokeWidth="0.4" strokeDasharray="4 4" />
          
          {[120, 200, 280, 360, 440, 520, 600].map((y) => (
            <g key={`ring-r-${y}`}>
              <rect x="20" y={y} width="40" height="8" fill="none" stroke="var(--color-gold)" strokeWidth="0.8" />
              <line x1="20" y1={y + 4} x2="60" y2={y + 4} strokeWidth="0.4" />
            </g>
          ))}
          
          <path d="M 25 720 L 15 735 H 65 L 55 720 Z" />
          <rect x="10" y="735" width="60" height="15" rx="1" />
          <rect x="5" y="750" width="70" height="40" rx="2" />
          <line x1="5" y1="770" x2="75" y2="770" strokeWidth="0.5" />
        </svg>
      </div>

      {/* 3. CENTER TEMPLE GOPURAM SILHOUETTES */}
      <div className="tamil-gopuram-box">
        <svg width="360" height="500" viewBox="0 0 360 500" fill="none" stroke="var(--color-gold)" strokeWidth="0.8">
          {/* Gopuram tiered pyarmidal layers */}
          {/* Base Tier 1 */}
          <path d="M 40 450 H 320 V 410 H 40 Z" />
          <path d="M 140 450 V 420 C 140 415 220 415 220 420 V 450" strokeWidth="1.2" /> {/* Entrance arch */}
          
          {/* Tier 2 */}
          <path d="M 60 410 H 300 V 360 H 60 Z" strokeDasharray="3 2" />
          <line x1="60" y1="385" x2="300" y2="385" strokeWidth="0.5" />

          {/* Tier 3 */}
          <path d="M 80 360 H 280 V 315 H 80 Z" />
          <line x1="80" y1="337" x2="280" y2="337" strokeWidth="0.5" />

          {/* Tier 4 */}
          <path d="M 100 315 H 260 V 275 H 100 Z" strokeDasharray="3 2" />
          <line x1="100" y1="295" x2="260" y2="295" strokeWidth="0.5" />

          {/* Tier 5 */}
          <path d="M 120 275 H 240 V 240 H 120 Z" />

          {/* Tier 6 */}
          <path d="M 140 240 H 220 V 210 H 140 Z" strokeDasharray="2 2" />

          {/* Shikhara / Rounded Crown */}
          <path d="M 150 210 Q 150 170 180 170 Q 210 170 210 210 Z" strokeWidth="1.2" />
          
          {/* Kalasams (Finials) on crown */}
          <line x1="180" y1="145" x2="180" y2="170" strokeWidth="1.2" />
          <circle cx="180" cy="145" r="3" />
          <circle cx="180" cy="138" r="1.5" />

          <line x1="165" y1="152" x2="165" y2="175" />
          <circle cx="165" cy="152" r="2" />

          <line x1="195" y1="152" x2="195" y2="175" />
          <circle cx="195" cy="152" r="2" />

          {/* Decorative side extensions (Wing-like curves on Gopuram edges) */}
          <path d="M 40 410 C 20 410 20 450 40 450" />
          <path d="M 320 410 C 340 410 340 450 320 450" />
          <path d="M 60 360 C 45 360 45 410 60 410" />
          <path d="M 300 360 C 315 360 315 410 300 410" />
          <path d="M 80 315 C 70 315 70 360 80 360" />
          <path d="M 280 315 C 290 315 290 360 280 360" />
        </svg>
      </div>

      {/* 4. DELICATE TRADITIONAL SIKKU KOLAMS FLOATING IN BACKGROUND */}
      <div className="tamil-kolam-float tk-1">
        <svg width="200" height="200" viewBox="0 0 200 200" fill="none" stroke="var(--color-gold)" strokeWidth="0.8">
          {/* Pulli Dots Grid (Diamond shape 5-dot configuration) */}
          {[60, 80, 100, 120, 140].map((y) =>
            [60, 80, 100, 120, 140].map((x) => (
              <circle key={`dp-${x}-${y}`} cx={x} cy={y} r="1" fill="var(--color-gold)" opacity="0.6" />
            ))
          )}
          {/* Loops wrapping around the dots (4-fold Sikku Kolam) */}
          <path d="M 100 40 C 60 40 60 90 100 90 C 140 90 140 40 100 40 Z" />
          <path d="M 100 160 C 60 160 60 110 100 110 C 140 110 140 160 100 160 Z" />
          <path d="M 40 100 C 40 60 90 60 90 100 C 90 140 40 140 40 100 Z" />
          <path d="M 160 100 C 160 60 110 60 110 100 C 110 140 160 140 160 100 Z" />
          <path d="M 60 60 C 100 40 160 100 100 160 C 40 100 100 40 60 60 Z" />
          <circle cx="100" cy="100" r="14" />
        </svg>
      </div>

      <div className="tamil-kolam-float tk-2">
        <svg width="160" height="160" viewBox="0 0 200 200" fill="none" stroke="var(--color-gold)" strokeWidth="0.8">
          {[60, 80, 100, 120, 140].map((y) =>
            [60, 80, 100, 120, 140].map((x) => (
              <circle key={`dp2-${x}-${y}`} cx={x} cy={y} r="1" fill="var(--color-gold)" opacity="0.6" />
            ))
          )}
          <path d="M 100 40 C 60 40 60 90 100 90 C 140 90 140 40 100 40 Z" />
          <path d="M 100 160 C 60 160 60 110 100 110 C 140 110 140 160 100 160 Z" />
          <path d="M 40 100 C 40 60 90 60 90 100 C 90 140 40 140 40 100 Z" />
          <path d="M 160 100 C 160 60 110 60 110 100 C 110 140 160 140 160 100 Z" />
          <path d="M 60 60 C 100 40 160 100 100 160 C 40 100 100 40 60 60 Z" />
          <circle cx="100" cy="100" r="14" />
        </svg>
      </div>
    </div>
  )
}
