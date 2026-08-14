import { useAuth } from '../../context/AuthContext'
import { History, Database, HardDrive, Sparkles } from 'lucide-react'
import './RecentKolams.css'

export default function RecentKolams({ onSelectKolam }) {
  const { user, isGuest, recentKolams } = useAuth()

  if (!recentKolams || recentKolams.length === 0) {
    return (
      <div className="recent-kolams-empty archival-frame">
        <div className="empty-icon-wrap">
          <History size={24} />
        </div>
        <div className="empty-text">
          <h4 className="heading-display heading-4">No Recently Generated Kolams</h4>
          <p className="body-text body-text--sm">
            {user
              ? 'Your generated Kolam images will be saved automatically to your Supabase database.'
              : 'Try analyzing or generating a Kolam above — your history is saved locally in your browser!'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <section className="recent-kolams-section">
      <div className="recent-header">
        <div className="recent-title-group">
          <History size={18} className="icon-accent" />
          <h3 className="heading-display heading-3">Recently Generated Kolams</h3>
        </div>

        <div className="storage-badge label-tech">
          {user ? (
            <>
              <Database size={12} />
              <span>Saved in Supabase DB ({user.email})</span>
            </>
          ) : (
            <>
              <HardDrive size={12} />
              <span>Browser LocalStorage ({isGuest ? 'Guest Mode' : 'Unauthenticated'})</span>
            </>
          )}
        </div>
      </div>

      <div className="recent-kolams-grid">
        {recentKolams.map((item) => (
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
