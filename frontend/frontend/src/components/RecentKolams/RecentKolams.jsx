import { useRef, useState, useCallback, useEffect } from 'react'
import { useAuth } from '../../context/AuthContext'
import { Database, HardDrive, ChevronLeft, ChevronRight } from 'lucide-react'
import './RecentKolams.css'

const SYNTHETIC_PHOTOS = [
  '/synthetic/kolam19_k1.jpg',
  '/synthetic/kolam19_k2.jpg',
  '/synthetic/kolam19_k3.jpg',
  '/synthetic/kolam19_k27.jpg',
  '/synthetic/kolam19_k50.jpg',
  '/synthetic/kolam29_k1.jpg',
  '/synthetic/kolam29_k2.jpg'
]

const MOCK_KOLAM_ITEMS = [
  {
    id: 'mock_1',
    title: 'Lotus Pulli Kolam (7×7)',
    image_url: '/synthetic/kolam19_k1.jpg',
    grid_size: '7×7 Lattice',
    symmetry: 'D4 Dihedral',
    validity: '✓ Eulerian Single-stroke',
  },
  {
    id: 'mock_2',
    title: 'Symmetrical Star Loop (5×5)',
    image_url: '/synthetic/kolam19_k2.jpg',
    grid_size: '5×5 Lattice',
    symmetry: 'C4 Rotational',
    validity: '✓ Eulerian Single-stroke',
  },
  {
    id: 'mock_3',
    title: 'Corner Petal Lattice (9×9)',
    image_url: '/synthetic/kolam19_k3.jpg',
    grid_size: '9×9 Lattice',
    symmetry: 'D4 Dihedral',
    validity: '✓ Eulerian Single-stroke',
  },
  {
    id: 'mock_4',
    title: 'Double-Strand Sikku Kolam (7×7)',
    image_url: '/synthetic/kolam19_k27.jpg',
    grid_size: '7×7 Lattice',
    symmetry: 'D2 Mirror',
    validity: '✓ Eulerian Single-stroke',
  },
  {
    id: 'mock_5',
    title: 'Radial Lattice Kolam (9×9)',
    image_url: '/synthetic/kolam19_k50.jpg',
    grid_size: '9×9 Lattice',
    symmetry: 'D4 Dihedral',
    validity: '✓ Eulerian Single-stroke',
  },
  {
    id: 'mock_6',
    title: 'Dense Interlocking Loop (11×11)',
    image_url: '/synthetic/kolam29_k1.jpg',
    grid_size: '11×11 Lattice',
    symmetry: 'D4 Dihedral',
    validity: '✓ Eulerian Single-stroke',
  }
]

// Auto-scroll speed: pixels per frame (at ~60 fps ≈ 0.5px/frame = 30px/s)
const SCROLL_SPEED = 0.5

export default function RecentKolams({ onSelectKolam }) {
  const { user, status, recentKolams } = useAuth()
  const isAuth = status === 'authenticated' && user

  const baseList = (recentKolams && recentKolams.length > 0) ? recentKolams : MOCK_KOLAM_ITEMS
  // Duplicate list for seamless infinite-loop illusion
  const displayList = [...baseList, ...baseList, ...baseList]

  const trackRef = useRef(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(true)

  // Auto-scroll state refs (no re-renders needed)
  const pausedRef = useRef(false)   // true when mouse is hovering
  const rafRef    = useRef(null)    // the current requestAnimationFrame id
  const dragRef   = useRef({ active: false, startX: 0, scrollLeft: 0 })

  // ── Auto-scroll loop ────────────────────────────────────────────────
  useEffect(() => {
    const el = trackRef.current
    if (!el) return

    // Kick off at the midpoint of the tripled list so there's room to
    // scroll in both directions before hitting a boundary.
    const setMidpoint = () => {
      el.scrollLeft = el.scrollWidth / 3
    }
    setMidpoint()

    const tick = () => {
      if (!pausedRef.current && el) {
        el.scrollLeft += SCROLL_SPEED

        // When we reach the end of the second copy, silently jump back
        // to the matching position in the first copy — the user sees
        // nothing because the content is identical.
        const third = el.scrollWidth / 3
        if (el.scrollLeft >= third * 2) {
          el.scrollLeft -= third
        }
        // Guard against scrolling too far left
        if (el.scrollLeft <= 0) {
          el.scrollLeft += third
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [baseList.length]) // restart if the list length changes

  // ── Manual scroll buttons (pause auto-scroll briefly) ─────────────
  const syncButtons = useCallback(() => {
    const el = trackRef.current
    if (!el) return
    setCanScrollLeft(el.scrollLeft > 4)
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4)
  }, [])

  const scrollBy = useCallback((dir) => {
    const el = trackRef.current
    if (!el) return
    // Briefly pause auto-scroll while the button scroll animates
    pausedRef.current = true
    el.scrollBy({ left: dir * 212 * 2, behavior: 'smooth' })
    setTimeout(() => {
      syncButtons()
      pausedRef.current = false
    }, 500)
  }, [syncButtons])

  // ── Hover: pause / resume ──────────────────────────────────────────
  const onMouseEnterTrack = () => { pausedRef.current = true  }
  const onMouseLeaveTrack = () => {
    // Only resume if not dragging
    if (!dragRef.current.active) pausedRef.current = false
  }

  // ── Drag-to-scroll ─────────────────────────────────────────────────
  const onMouseDown = (e) => {
    const el = trackRef.current
    if (!el) return
    pausedRef.current = true
    dragRef.current = { active: true, startX: e.pageX - el.offsetLeft, scrollLeft: el.scrollLeft }
    el.style.cursor = 'grabbing'
    el.style.userSelect = 'none'
  }

  const onMouseMove = (e) => {
    if (!dragRef.current.active) return
    const el = trackRef.current
    if (!el) return
    const x = e.pageX - el.offsetLeft
    const walk = x - dragRef.current.startX
    el.scrollLeft = dragRef.current.scrollLeft - walk
    syncButtons()
  }

  const stopDrag = () => {
    if (!dragRef.current.active) return
    dragRef.current.active = false
    const el = trackRef.current
    if (el) {
      el.style.cursor = 'grab'
      el.style.userSelect = ''
    }
    // Resume auto-scroll only if mouse is not hovering
    // (onMouseLeaveTrack handles that case separately)
  }

  const getDistinctImageSrc = (item, idx) => {
    const baseLen = baseList.length
    const baseIdx = idx % baseLen
    if (!item.image_url || item.image_url.includes('kolam19_1.jpg')) {
      return SYNTHETIC_PHOTOS[baseIdx % SYNTHETIC_PHOTOS.length]
    }
    const isDuplicate = baseList.findIndex((k) => k.image_url === item.image_url) !== baseIdx
    if (isDuplicate) {
      return SYNTHETIC_PHOTOS[baseIdx % SYNTHETIC_PHOTOS.length]
    }
    return item.image_url
  }

  const handleImageError = (e, index) => {
    e.target.onerror = null
    e.target.src = SYNTHETIC_PHOTOS[index % SYNTHETIC_PHOTOS.length]
  }

  return (
    <section className="recent-kolams-section">
      <div className="recent-header">
        <div className="recent-title-group">
          <h3 className="heading-display heading-3">Recently Generated Kolams</h3>
        </div>

        <div className="recent-header-right">
          <div className="storage-badge label-tech">
            {isAuth ? (
              <>
                <Database size={12} />
                <span>Saved in Database</span>
              </>
            ) : (
              <>
                <HardDrive size={12} />
                <span>Browser Storage (Local)</span>
              </>
            )}
          </div>

          {/* Carousel navigation arrows */}
          <div className="carousel-nav">
            <button
              className="carousel-btn"
              aria-label="Scroll left"
              onClick={() => scrollBy(-1)}
            >
              <ChevronLeft size={15} strokeWidth={2.5} />
            </button>
            <button
              className="carousel-btn"
              aria-label="Scroll right"
              onClick={() => scrollBy(1)}
            >
              <ChevronRight size={15} strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>

      {/* Horizontal auto-scrolling carousel track */}
      <div className="recent-carousel-wrapper">
        <div
          className="recent-carousel-track"
          ref={trackRef}
          onScroll={syncButtons}
          onMouseEnter={onMouseEnterTrack}
          onMouseLeave={onMouseLeaveTrack}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={stopDrag}
        >
          {displayList.map((item, idx) => (
            <div
              key={`${item.id || idx}-${idx}`}
              className="recent-card archival-frame"
              onClick={() => onSelectKolam && onSelectKolam(item)}
            >
              <div className="recent-card-img">
                <img
                  src={getDistinctImageSrc(item, idx)}
                  alt={item.title}
                  onError={(e) => handleImageError(e, idx)}
                  draggable="false"
                />
              </div>
              <div className="recent-card-body">
                <h4 className="heading-display heading-4 recent-card-title">{item.title}</h4>
                <div className="recent-card-meta label-tech">
                  <span>{item.grid_size}</span>
                  <span className="dot-sep">•</span>
                  <span>{item.symmetry}</span>
                </div>
                <span className="recent-badge text-valid">{item.validity}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
