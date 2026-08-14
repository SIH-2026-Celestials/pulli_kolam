import { useAuth } from '../../context/AuthContext'
import { Database, HardDrive } from 'lucide-react'
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

export default function RecentKolams({ onSelectKolam }) {
  const { user, status, recentKolams } = useAuth()
  const isAuth = status === 'authenticated' && user

  const displayList = (recentKolams && recentKolams.length > 0) ? recentKolams : MOCK_KOLAM_ITEMS

  const getDistinctImageSrc = (item, idx) => {
    if (!item.image_url || item.image_url.includes('kolam19_1.jpg')) {
      return SYNTHETIC_PHOTOS[idx % SYNTHETIC_PHOTOS.length]
    }
    // If multiple items in recent storage have identical image_url, map distinct photos by index
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

        <div className="storage-badge label-tech">
          {isAuth ? (
            <>
              <Database size={12} />
              <span>Saved in Database ({user.email})</span>
            </>
          ) : (
            <>
              <HardDrive size={12} />
              <span>Browser Storage (Local)</span>
            </>
          )}
        </div>
      </div>

      <div className="recent-kolams-grid">
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
    </section>
  )
}
