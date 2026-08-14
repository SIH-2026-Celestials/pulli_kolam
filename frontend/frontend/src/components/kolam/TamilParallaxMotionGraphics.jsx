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
      {/* Left side motion graphic - Temple Gopuram at sunset */}
      <div className="tamil-motion-wrapper left" ref={leftRef}>
        <img
          src="/assets/gopuram_sunset1.jpg"
          alt=""
          className="tamil-motion-img"
          loading="eager"
        />
      </div>

      {/* Right side motion graphic - Gopuram with setting sun */}
      <div className="tamil-motion-wrapper right" ref={rightRef}>
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
