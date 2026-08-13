import { Link } from 'react-router-dom'
import { kolam19 } from '../../data/kolams'
import './ArchiveWall.css'

// Selected real items from kolam19 dataset to exhibit
const featuredExhibits = [
  { id: 26, label: 'EXHIBIT 01 · PATTERN TRACE', caption: 'Kolam 26 - 725 dense polyline points, 816.8u path length' },
  { id: 1,  label: 'EXHIBIT 02 · EULERIAN PATH', caption: 'Kolam 1 - 100% closed one-stroke continuity verified' },
  { id: 55, label: 'EXHIBIT 03 · D4 SYMMETRY', caption: 'Kolam 55 - Dual vertical & 180° rotational invariance' },
  { id: 118,label: 'EXHIBIT 04 · MULTIGRAPH', caption: 'Kolam 118 - Complex strand multiplicity at lattice nodes' },
  { id: 232,label: 'EXHIBIT 05 · MOTIF SUBGRAPH', caption: 'Kolam 232 - Dihedral canonicalized recurring window' },
]

export default function ArchiveWall() {
  return (
    <div className="archive-wall">
      <div className="archive-wall__grid">
        {/* Large featured exhibition item */}
        <div className="archive-wall__item archive-wall__item--large">
          <Link to={`/explore/${featuredExhibits[0].id}`} className="archive-wall__frame">
            <img
              src={kolam19.find(k => k.id === featuredExhibits[0].id)?.imagePath}
              alt="Featured Kolam pattern"
              className="archive-wall__img"
            />
            <div className="archive-wall__overlay">
              <span className="eyebrow">{featuredExhibits[0].label}</span>
              <p className="archive-wall__caption">{featuredExhibits[0].caption}</p>
            </div>
          </Link>
        </div>

        {/* 4 smaller exhibition items */}
        {featuredExhibits.slice(1).map((item) => {
          const kData = kolam19.find(k => k.id === item.id)
          return (
            <div key={item.id} className="archive-wall__item">
              <Link to={`/explore/${item.id}`} className="archive-wall__frame">
                <img
                  src={kData?.imagePath}
                  alt={`Kolam pattern ${item.id}`}
                  className="archive-wall__img"
                />
                <div className="archive-wall__overlay">
                  <span className="eyebrow">{item.label}</span>
                  <p className="archive-wall__caption">{item.caption}</p>
                </div>
              </Link>
            </div>
          )
        })}
      </div>
    </div>
  )
}
