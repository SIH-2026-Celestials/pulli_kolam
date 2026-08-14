
export default function KolamHeroSvg() {
  return (
    <div className="hero-kolam-container">
      <svg
        width="480"
        height="480"
        viewBox="-240 -240 480 480"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="hero-kolam-svg"
      >
        {/* Subtle background radial guide ring */}
        <circle cx="0" cy="0" r="225" stroke="#E6DEC9" strokeWidth="0.8" strokeDasharray="4 6" opacity="0.4" />
        <circle cx="0" cy="0" r="175" stroke="#E6DEC9" strokeWidth="0.5" opacity="0.3" />

        {/* --- PULLI (DOTS) --- */}
        {/* Vertical Axis (9 dots) */}
        {[-160, -120, -80, -40, 0, 40, 80, 120, 160].map((y, i) => (
          <circle key={`v-${i}`} cx="0" cy={y} r="3.2" fill="var(--color-text-dark)" />
        ))}

        {/* Horizontal Axis (8 non-center dots) */}
        {[-160, -120, -80, -40, 40, 80, 120, 160].map((x, i) => (
          <circle key={`h-${i}`} cx={x} cy="0" r="3.2" fill="var(--color-text-dark)" />
        ))}

        {/* Inner Grid Dots (y = ±40) */}
        <circle cx="-40" cy="-40" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="40" cy="-40" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="-40" cy="40" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="40" cy="40" r="3.2" fill="var(--color-text-dark)" />

        {/* Mid Grid Dots (y = ±80, ±120) */}
        <circle cx="-40" cy="-80" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="40" cy="-80" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="-40" cy="80" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="40" cy="80" r="3.2" fill="var(--color-text-dark)" />

        <circle cx="-80" cy="-40" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="80" cy="-40" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="-80" cy="40" r="3.2" fill="var(--color-text-dark)" />
        <circle cx="80" cy="40" r="3.2" fill="var(--color-text-dark)" />

        {/* Outer Accent Dots (Symmetrical outer vertices matching screenshot) */}
        <circle cx="-80" cy="-120" r="2.8" fill="var(--color-text-dark)" />
        <circle cx="80" cy="-120" r="2.8" fill="var(--color-text-dark)" />
        <circle cx="-80" cy="120" r="2.8" fill="var(--color-text-dark)" />
        <circle cx="80" cy="120" r="2.8" fill="var(--color-text-dark)" />

        <circle cx="-120" cy="-80" r="2.8" fill="var(--color-text-dark)" />
        <circle cx="120" cy="-80" r="2.8" fill="var(--color-text-dark)" />
        <circle cx="-120" cy="80" r="2.8" fill="var(--color-text-dark)" />
        <circle cx="120" cy="80" r="2.8" fill="var(--color-text-dark)" />

        {/* --- CONTINUOUS SIKKU LINES (Red-Maroon with Gold Reflection) --- */}
        <defs>
          <linearGradient id="hero-kambi-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#8C1B20" />
            <stop offset="35%" stopColor="#9C2025" />
            <stop offset="50%" stopColor="#FFE082" /> {/* Golden highlight reflection */}
            <stop offset="65%" stopColor="#9C2025" />
            <stop offset="100%" stopColor="#8C1B20" />
          </linearGradient>
          <filter id="hero-shadow" x="-15%" y="-15%" width="130%" height="130%">
            <feDropShadow dx="0" dy="2.5" stdDeviation="2.8" floodColor="#000000" floodOpacity="0.45" />
          </filter>
        </defs>

        <g
          stroke="url(#hero-kambi-grad)"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
          filter="url(#hero-shadow)"
          className="kolam-lines-group"
        >
          {/* Top Outer Tip Loop */}
          <path d="M 0 -195 C -20 -195 -20 -145 0 -145 C 20 -145 20 -195 0 -195 Z" />

          {/* Bottom Outer Tip Loop */}
          <path d="M 0 195 C -20 195 -20 145 0 145 C 20 145 20 195 0 195 Z" />

          {/* Left Outer Tip Loop */}
          <path d="M -195 0 C -195 -20 -145 -20 -145 0 C -145 20 -195 20 -195 0 Z" />

          {/* Right Outer Tip Loop */}
          <path d="M 195 0 C 195 -20 145 -20 145 0 C 145 20 195 20 195 0 Z" />

          {/* Vertical Central Sinusoidal Loops */}
          <path d="
            M 0 -145
            C -50 -145 -70 -105 -45 -60
            C -25 -20 0 -35 0 0
            C 0 35 -25 20 -45 60
            C -70 105 -50 145 0 145
            C 50 145 70 105 45 60
            C 25 20 0 35 0 0
            C 0 -35 25 -20 45 -60
            C 70 -105 50 -145 0 -145 Z
          " />

          {/* Horizontal Central Sinusoidal Loops */}
          <path d="
            M -145 0
            C -145 -50 -105 -70 -60 -45
            C -20 -25 -35 0 0 0
            C 35 0 20 -25 60 -45
            C 105 -70 145 -50 145 0
            C 145 50 105 70 60 45
            C 20 25 35 0 0 0
            C -35 0 -20 25 -60 45
            C -105 70 -145 50 -145 0 Z
          " />

          {/* Diagonal Loop Wings (4 Corner Quadrants) */}
          <path d="M -40 -90 C -80 -130 -110 -80 -70 -45 C -45 -20 -15 -60 -40 -90 Z" />
          <path d="M 40 -90 C 80 -130 110 -80 70 -45 C 45 -20 15 -60 40 -90 Z" />
          <path d="M -40 90 C -80 130 -110 80 -70 45 C -45 20 -15 60 -40 90 Z" />
          <path d="M 40 90 C 80 130 110 80 70 45 C 45 20 15 60 40 90 Z" />

          {/* Secondary Outer Loops */}
          <path d="M 0 -105 C -30 -105 -30 -60 0 -60 C 30 -60 30 -105 0 -105 Z" />
          <path d="M 0 105 C -30 105 -30 60 0 60 C 30 60 30 105 0 105 Z" />
          <path d="M -105 0 C -105 -30 -60 -30 -60 0 C -60 30 -105 30 -105 0 Z" />
          <path d="M 105 0 C 105 -30 60 -30 60 0 C 60 30 105 30 105 0 Z" />

          {/* Inner Ring around center dot */}
          <circle cx="0" cy="0" r="16" strokeWidth="1.8" />
        </g>
      </svg>
    </div>
  )
}
