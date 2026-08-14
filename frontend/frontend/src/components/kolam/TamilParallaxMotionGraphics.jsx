import React, { useEffect, useRef } from 'react'
import './kolam.css'

export default function TamilParallaxMotionGraphics() {
  const leftRef = useRef(null)
  const rightRef = useRef(null)

  useEffect(() => {
    let ticking = false

    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const y = window.scrollY || window.pageYOffset || 0
          // Smooth parallax translation at 10% scroll speed
          if (leftRef.current) {
            leftRef.current.style.transform = `translate3d(0, ${y * 0.1}px, 0)`
          }
          if (rightRef.current) {
            rightRef.current.style.transform = `translate3d(0, ${y * 0.12}px, 0)`
          }
          ticking = false
        })
        ticking = true
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()

    return () => {
      window.removeEventListener('scroll', handleScroll)
    }
  }, [])

  return (
    <div className="tamil-motion-root" aria-hidden="true">
      {/* ── LEFT MARGIN MOTION GRAPHIC ── */}
      <div className="tamil-motion-wrapper left" ref={leftRef}>
        {/* Breathing Sunset Backlight Halo */}
        <div className="tamil-sunset-glow left-glow" />

        {/* Ambient Diya Gold Spark Particles */}
        <div className="tamil-spark-particle spark-1" />
        <div className="tamil-spark-particle spark-2" />

        {/* Slowly Rotating Gold Sikku Kolam Motif */}
        <div className="tamil-floating-kolam left-kolam">
          <svg width="120" height="120" viewBox="0 0 120 120" fill="none" stroke="var(--color-gold)" strokeWidth="0.8" opacity="0.35">
            <circle cx="60" cy="60" r="48" strokeDasharray="3 3" strokeWidth="0.5" />
            <path d="M 60 20 Q 80 40 100 60 Q 80 80 60 100 Q 40 80 20 60 Q 40 40 60 20" />
            <path d="M 60 35 Q 75 50 85 60 Q 75 70 60 85 Q 45 70 35 60 Q 45 50 60 35" strokeWidth="0.6" />
            <circle cx="60" cy="60" r="3" fill="var(--color-gold)" />
          </svg>
        </div>

        <img
          src="/assets/gopuram_sunset1.jpg"
          alt=""
          className="tamil-motion-img"
          loading="eager"
        />
      </div>

      {/* ── RIGHT MARGIN MOTION GRAPHIC ── */}
      <div className="tamil-motion-wrapper right" ref={rightRef}>
        {/* Breathing Sunset Backlight Halo */}
        <div className="tamil-sunset-glow right-glow" />

        {/* Ambient Diya Gold Spark Particles */}
        <div className="tamil-spark-particle spark-3" />
        <div className="tamil-spark-particle spark-4" />

        {/* Slowly Rotating Gold Sikku Kolam Motif */}
        <div className="tamil-floating-kolam right-kolam">
          <svg width="120" height="120" viewBox="0 0 120 120" fill="none" stroke="var(--color-gold)" strokeWidth="0.8" opacity="0.35">
            <circle cx="60" cy="60" r="48" strokeDasharray="3 3" strokeWidth="0.5" />
            <path d="M 60 20 Q 80 40 100 60 Q 80 80 60 100 Q 40 80 20 60 Q 40 40 60 20" />
            <path d="M 60 35 Q 75 50 85 60 Q 75 70 60 85 Q 45 70 35 60 Q 45 50 60 35" strokeWidth="0.6" />
            <circle cx="60" cy="60" r="3" fill="var(--color-gold)" />
          </svg>
        </div>

        <img
          src="/assets/gopuram_sunset2.jpg"
          alt=""
          className="tamil-motion-img"
          loading="eager"
        />
      </div>
    </div>
  )
}
