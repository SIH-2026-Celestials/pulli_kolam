import { useAuth } from '../../context/AuthContext'
import { Database, HardDrive } from 'lucide-react'
import './RecentKolams.css'

const MOCK_KOLAM_ITEMS = [
  {
    id: 'mock_1',
    title: 'Lotus Pulli Kolam (7×7)',
    image_url: 'data:image/svg+xml;utf8,<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><rect width="200" height="200" fill="%23111111"/><circle cx="100" cy="100" r="6" fill="%23E6B800"/><circle cx="60" cy="60" r="5" fill="%23E6B800"/><circle cx="140" cy="60" r="5" fill="%23E6B800"/><circle cx="60" cy="140" r="5" fill="%23E6B800"/><circle cx="140" cy="140" r="5" fill="%23E6B800"/><circle cx="100" cy="50" r="5" fill="%23E6B800"/><circle cx="100" cy="150" r="5" fill="%23E6B800"/><circle cx="50" cy="100" r="5" fill="%23E6B800"/><circle cx="150" cy="100" r="5" fill="%23E6B800"/><path d="M 100 30 C 130 30, 140 70, 100 70 C 60 70, 70 30, 100 30 Z" fill="none" stroke="%23E6B800" stroke-width="4"/><path d="M 100 170 C 130 170, 140 130, 100 130 C 60 130, 70 170, 100 170 Z" fill="none" stroke="%23E6B800" stroke-width="4"/><path d="M 30 100 C 30 130, 70 140, 70 100 C 70 60, 30 70, 30 100 Z" fill="none" stroke="%23E6B800" stroke-width="4"/><path d="M 170 100 C 170 130, 130 140, 130 100 C 130 60, 170 70, 170 100 Z" fill="none" stroke="%23E6B800" stroke-width="4"/><path d="M 60 60 C 100 20, 140 60, 140 100 C 140 140, 100 180, 60 140 C 20 100, 60 20, 60 60 Z" fill="none" stroke="%23E6B800" stroke-width="3"/></svg>',
    grid_size: '7×7 Lattice',
    symmetry: 'D4 Dihedral',
    validity: '✓ Eulerian Single-stroke',
  },
  {
    id: 'mock_2',
    title: 'Symmetrical Star Loop (5×5)',
    image_url: 'data:image/svg+xml;utf8,<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><rect width="200" height="200" fill="%23111111"/><circle cx="100" cy="100" r="7" fill="%23E6B800"/><circle cx="50" cy="100" r="5" fill="%23E6B800"/><circle cx="150" cy="100" r="5" fill="%23E6B800"/><circle cx="100" cy="50" r="5" fill="%23E6B800"/><circle cx="100" cy="150" r="5" fill="%23E6B800"/><path d="M 100 35 C 145 35, 165 80, 165 100 C 165 120, 145 165, 100 165 C 55 165, 35 120, 35 100 C 35 80, 55 35, 100 35 Z" fill="none" stroke="%23E6B800" stroke-width="4"/><path d="M 70 70 C 100 40, 130 70, 130 100 C 130 130, 100 160, 70 130 C 40 100, 70 70, 70 70 Z" fill="none" stroke="%23E6B800" stroke-width="3"/></svg>',
    grid_size: '5×5 Lattice',
    symmetry: 'C4 Rotational',
    validity: '✓ Eulerian Single-stroke',
  },
  {
    id: 'mock_3',
    title: 'Corner Petal Lattice (9×9)',
    image_url: 'data:image/svg+xml;utf8,<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><rect width="200" height="200" fill="%23111111"/><circle cx="100" cy="100" r="6" fill="%23E6B800"/><circle cx="50" cy="50" r="5" fill="%23E6B800"/><circle cx="150" cy="50" r="5" fill="%23E6B800"/><circle cx="50" cy="150" r="5" fill="%23E6B800"/><circle cx="150" cy="150" r="5" fill="%23E6B800"/><path d="M 50 50 L 150 50 L 150 150 L 50 150 Z" fill="none" stroke="%23E6B800" stroke-width="3"/><circle cx="100" cy="100" r="45" fill="none" stroke="%23E6B800" stroke-width="4"/></svg>',
    grid_size: '9×9 Lattice',
    symmetry: 'D4 Dihedral',
    validity: '✓ Eulerian Single-stroke',
  },
  {
    id: 'mock_4',
    title: 'Double-Strand Sikku Kolam (7×7)',
    image_url: 'data:image/svg+xml;utf8,<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg"><rect width="200" height="200" fill="%23111111"/><circle cx="100" cy="100" r="7" fill="%23E6B800"/><circle cx="70" cy="100" r="5" fill="%23E6B800"/><circle cx="130" cy="100" r="5" fill="%23E6B800"/><circle cx="100" cy="70" r="5" fill="%23E6B800"/><circle cx="100" cy="130" r="5" fill="%23E6B800"/><path d="M 100 45 C 135 45, 155 85, 155 100 C 155 115, 135 155, 100 155 C 65 155, 45 115, 45 100 C 45 85, 65 45, 100 45 Z" fill="none" stroke="%23E6B800" stroke-width="3"/><path d="M 100 55 C 125 55, 145 85, 145 100 C 145 115, 125 145, 100 145 C 75 145, 55 115, 55 100 C 55 85, 75 55, 100 55 Z" fill="none" stroke="%23E6B800" stroke-width="2"/></svg>',
    grid_size: '7×7 Lattice',
    symmetry: 'D2 Mirror',
    validity: '✓ Eulerian Single-stroke',
  }
]

export default function RecentKolams({ onSelectKolam }) {
  const { user, isGuest, recentKolams } = useAuth()

  const displayList = (recentKolams && recentKolams.length > 0) ? recentKolams : MOCK_KOLAM_ITEMS

  return (
    <section className="recent-kolams-section">
      <div className="recent-header">
        <div className="recent-title-group">
          <h3 className="heading-display heading-3">Recently Generated Kolams</h3>
        </div>

        <div className="storage-badge label-tech">
          {user ? (
            <>
              <Database size={12} />
              <span>Saved in Database ({user.email})</span>
            </>
          ) : (
            <>
              <HardDrive size={12} />
              <span>Browser Storage ({isGuest ? 'Guest Mode' : 'Unauthenticated'})</span>
            </>
          )}
        </div>
      </div>

      <div className="recent-kolams-grid">
        {displayList.map((item) => (
          <div
            key={item.id}
            className="recent-card archival-frame"
            onClick={() => onSelectKolam && onSelectKolam(item)}
          >
            <div className="recent-card-img">
              <img src={item.image_url} alt={item.title} />
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
