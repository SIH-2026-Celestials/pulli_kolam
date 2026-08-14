import { useRef, useState, useCallback } from 'react'
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

const CARD_WIDTH = 168 // px — card width + gap

export default function RecentKolams({ onSelectKolam }) {
  const { user, status, recentKolams } = useAuth()
  const isAuth = status === 'authenticated' && user

  const displayList = (recentKolams && recentKolams.length > 0) ? recentKolams : MOCK_KOLAM_ITEMS

  const trackRef = useRef(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(true)

  // Drag-to-scroll state
  const dragRef = useRef({ active: false, startX: 0, scrollLeft: 0 })

  const syncButtons = useCallback(() => {
    const el = trackRef.current
    if (!el) return
    setCanScrollLeft(el.scrollLeft > 4)
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4)
  }, [])

  const scrollBy = useCallback((dir) => {
    const el = trackRef.current
    if (!el) return
    el.scrollBy({ left: dir * CARD_WIDTH * 2, behavior: 'smooth' })
    setTimeout(syncButtons, 350)
  }, [syncButtons])

  const onMouseDown = (e) => {
    const el = trackRef.current
    if (!el) return
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
  }

  const getDistinctImageSrc = (item, idx) => {
    if (!item.image_url || item.image_url.includes('kolam19_1.jpg')) {
      return SYNTHETIC_PHOTOS[idx % SYNTHETIC_PHOTOS.length]
    }
    const isDuplicate = displayList.findIndex((k) => k.image_url === item.image_url) !== idx
    if (isDuplicate) {
      return SYNTHETIC_PHOTOS[idx % SYNTHETIC_PHOTOS.length]
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
              disabled={!canScrollLeft}
              onClick={() => scrollBy(-1)}
            >
              <ChevronLeft size={15} strokeWidth={2.5} />
            </button>
            <button
              className="carousel-btn"
              aria-label="Scroll right"
              disabled={!canScrollRight}
              onClick={() => scrollBy(1)}
            >
              <ChevronRight size={15} strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>

      {/* Horizontal carousel track */}
      <div className="recent-carousel-wrapper">
        <div
          className="recent-carousel-track"
          ref={trackRef}
          onScroll={syncButtons}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={stopDrag}
          onMouseLeave={stopDrag}
        >
          {displayList.map((item, idx) => (
            <div
              key={item.id || idx}
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
