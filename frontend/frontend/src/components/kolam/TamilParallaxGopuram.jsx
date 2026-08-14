import React, { useEffect, useRef } from 'react'
import './kolam.css'

export default function TamilParallaxGopuram() {
  const leftRef = useRef(null)
  const rightRef = useRef(null)

  useEffect(() => {
    let ticking = false

    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const y = window.scrollY
          // Apply a gentle scroll parallax translateY shift (10% of scroll)
          if (leftRef.current) {
            leftRef.current.style.transform = `translateY(${y * 0.1}px)`
          }
          if (rightRef.current) {
            rightRef.current.style.transform = `translateY(${y * 0.1}px)`
          }
          ticking = false
        })
        ticking = true
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    // Run initial alignment
    handleScroll()

    return () => {
      window.removeEventListener('scroll', handleScroll)
    }
  }, [])

  return (
    <div className="gopuram-parallax-root" aria-hidden="true">
      {/* LEFT GOPURAM VIGNETTE */}
      <div className="gopuram-parallax-wrapper left" ref={leftRef}>
        <img 
          src="/assets/gopuram_sunset1.jpg" 
          alt="Dravidian temple gopuram sunset" 
          className="gopuram-motion-img" 
        />
      </div>

      {/* RIGHT GOPURAM VIGNETTE */}
      <div className="gopuram-parallax-wrapper right" ref={rightRef}>
        <img 
          src="/assets/gopuram_sunset2.jpg" 
          alt="Dravidian temple gopuram sunset" 
          className="gopuram-motion-img" 
        />
      </div>
    </div>
  )
}
