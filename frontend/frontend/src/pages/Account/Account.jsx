import { useState } from 'react'
import { Navigate, useNavigate, Link } from 'react-router-dom'
import {
  User,
  Mail,
  Calendar,
  MapPin,
  ShieldCheck,
  LogOut,
  Edit3,
  Award,
  Grid,
  GitFork,
  Infinity as LoopIcon,
  HardDrive,
  CheckCircle2,
  Sparkles,
  Layers,
  ArrowRight
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import RecentKolams from '../../components/RecentKolams/RecentKolams'
import './Account.css'

export default function Account() {
  const { t } = useLanguage()
  const { status, user, logout, recentKolams } = useAuth()
  const navigate = useNavigate()
  const [loggingOut, setLoggingOut] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [bioText, setBioText] = useState(
    'Exploring traditional South Indian Pulli Kolam graph topology, Eulerian loop invariants, and algorithmic symmetry generation.'
  )

  const handleLogout = async () => {
    setLoggingOut(true)
    await logout()
    navigate('/', { replace: true })
  }

  if (status === 'loading') {
    return (
      <main id="main-content" className="account-page">
        <div className="container--narrow section text-center">
          <div className="account-skeleton-box archival-frame">
            <div className="skeleton-line" style={{ width: '40%', height: '24px' }}></div>
            <div className="skeleton-line" style={{ width: '70%', height: '16px', marginTop: '12px' }}></div>
          </div>
        </div>
      </main>
    )
  }

  if (status === 'unauthenticated' || !user) {
    return (
      <main id="main-content" className="account-page">
        <div className="container--narrow section">
          <div className="archival-frame guest-profile-banner">
            <div className="guest-banner-icon">
              <Sparkles size={32} />
            </div>
            <div className="guest-banner-content">
              <h2 className="heading-display heading-3">Guest Mode Active</h2>
              <p className="body-text body-text--sm">
                You are currently exploring PULLI as a Guest. Your generated Kolam patterns are automatically saved in your browser&apos;s LocalStorage.
              </p>
            </div>
            <div className="guest-banner-actions">
              <button className="btn btn--primary" onClick={() => navigate('/')}>
                Return to Home
              </button>
            </div>
          </div>

          {/* Display Saved Kolam History even for Guest */}
          <RecentKolams />
        </div>
      </main>
    )
  }

  // Calculate real user stats from recentKolams
  const totalSaved = recentKolams ? recentKolams.length : 0
  const validEulerianCount = recentKolams
    ? recentKolams.filter((k) => k.validity && k.validity.includes('Eulerian')).length
    : 0

  const displayName = user.display_name || user.email?.split('@')[0] || 'Kolam Practitioner'
  const handleName = `@${user.email?.split('@')[0] || 'practitioner'}`
  const joinDate = user.created_at ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) : 'August 2026'

  return (
    <main id="main-content" className="account-page">
      <div className="container--narrow section">
        
        {/* 1. PROFILE HEADER CARD */}
        <section className="profile-header-card archival-frame">
          <div className="profile-cover-accent"></div>
          
          <div className="profile-header-body">
            <div className="profile-avatar-wrapper">
              <div className="profile-avatar-circle">
                <span className="avatar-initials">
                  {displayName.charAt(0).toUpperCase()}
                </span>
              </div>
              <span className="status-indicator-dot" title="Active Practitioner"></span>
            </div>

            <div className="profile-main-meta">
              <div className="profile-title-row">
                <div>
                  <h1 className="heading-display heading-2 profile-name">{displayName}</h1>
                  <span className="profile-handle label-tech">{handleName}</span>
                </div>
                <span className="role-badge label-tech">
                  <ShieldCheck size={13} /> Practitioner &amp; Researcher
                </span>
              </div>

              {isEditing ? (
                <div className="bio-edit-box">
                  <textarea
                    value={bioText}
                    onChange={(e) => setBioText(e.target.value)}
                    className="input-text bio-textarea"
                    rows="2"
                  />
                  <button className="btn btn--primary btn--sm" onClick={() => setIsEditing(false)}>
                    Save Bio
                  </button>
                </div>
              ) : (
                <p className="body-text body-text--sm profile-bio">{bioText}</p>
              )}

              <div className="profile-quick-tags label-tech">
                <span><MapPin size={13} /> Tamil Nadu, India</span>
                <span className="dot-sep">•</span>
                <span><Calendar size={13} /> Member since {joinDate}</span>
              </div>
            </div>

            <div className="profile-header-actions">
              <button
                className="btn btn--outline btn--sm btn-edit-profile"
                onClick={() => setIsEditing(!isEditing)}
              >
                <Edit3 size={14} />
                <span>{isEditing ? 'Cancel' : 'Edit Profile'}</span>
              </button>

              <button
                className="btn btn--outline btn--sm btn-logout-action"
                onClick={handleLogout}
                disabled={loggingOut}
              >
                <LogOut size={14} />
                <span>{loggingOut ? 'Signing out...' : 'Sign Out'}</span>
              </button>
            </div>
          </div>
        </section>

        {/* 2. COMPACT USER STATISTICS CARDS */}
        <section className="profile-stats-grid">
          <div className="stat-card archival-frame">
            <div className="stat-icon-wrap">
              <Layers size={20} />
            </div>
            <div className="stat-text-wrap">
              <span className="stat-number">{totalSaved}</span>
              <span className="stat-label label-tech">SAVED KOLAMS</span>
            </div>
          </div>

          <div className="stat-card archival-frame">
            <div className="stat-icon-wrap">
              <LoopIcon size={20} />
            </div>
            <div className="stat-text-wrap">
              <span className="stat-number">{validEulerianCount}</span>
              <span className="stat-label label-tech">EULERIAN CIRCUITS</span>
            </div>
          </div>

          <div className="stat-card archival-frame">
            <div className="stat-icon-wrap">
              <GitFork size={20} />
            </div>
            <div className="stat-text-wrap">
              <span className="stat-number">D4 (100%)</span>
              <span className="stat-label label-tech">AVG SYMMETRY</span>
            </div>
          </div>

          <div className="stat-card archival-frame">
            <div className="stat-icon-wrap">
              <Grid size={20} />
            </div>
            <div className="stat-text-wrap">
              <span className="stat-number">7×7</span>
              <span className="stat-label label-tech">PREFERRED LATTICE</span>
            </div>
          </div>
        </section>

        {/* 3. PROFILE DETAILS & ACHIEVEMENTS DUAL GRID */}
        <section className="profile-details-grid">
          
          {/* Account Information Card */}
          <article className="info-card archival-frame">
            <div className="card-header-bar">
              <User size={16} className="icon-accent" />
              <h3 className="heading-display heading-4">Account &amp; Personal Info</h3>
            </div>
            <div className="info-table">
              <div className="info-row">
                <span className="label-tech"><User size={14} /> Full Name</span>
                <strong>{displayName}</strong>
              </div>
              <div className="info-row">
                <span className="label-tech"><Mail size={14} /> Email Address</span>
                <strong>{user.email}</strong>
              </div>
              <div className="info-row">
                <span className="label-tech"><HardDrive size={14} /> Storage Engine</span>
                <strong className="text-valid">Connected Database</strong>
              </div>
              <div className="info-row">
                <span className="label-tech"><CheckCircle2 size={14} /> Status</span>
                <strong className="text-valid">Verified Researcher</strong>
              </div>
            </div>
          </article>

          {/* Research Achievements & Badges */}
          <article className="info-card archival-frame">
            <div className="card-header-bar">
              <Award size={16} className="icon-accent" />
              <h3 className="heading-display heading-4">Heritage Achievements</h3>
            </div>
            <div className="badges-list">
              <div className="achievement-badge-item">
                <div className="badge-icon-circle">🌟</div>
                <div className="badge-info">
                  <h4 className="heading-display heading-4 badge-title">Eulerian Master</h4>
                  <p className="body-text body-text--sm">Validated single-stroke continuous loop graph correctness.</p>
                </div>
              </div>

              <div className="achievement-badge-item">
                <div className="badge-icon-circle">🌀</div>
                <div className="badge-info">
                  <h4 className="heading-display heading-4 badge-title">D4 Dihedral Explorer</h4>
                  <p className="body-text body-text--sm">Analyzed 8-fold rotational and reflectional symmetry matrix.</p>
                </div>
              </div>

              <div className="achievement-badge-item">
                <div className="badge-icon-circle">📐</div>
                <div className="badge-info">
                  <h4 className="heading-display heading-4 badge-title">Lattice Specialist</h4>
                  <p className="body-text body-text--sm">Engineered $7\times7$ and $9\times9$ Pulli dot-grid variations.</p>
                </div>
              </div>
            </div>
          </article>
        </section>

        {/* 4. RECENTLY SAVED KOLAM DESIGNS */}
        <RecentKolams />

        {/* Quick CTA to Playground */}
        <div className="playground-cta-banner archival-frame">
          <div className="cta-text">
            <h3 className="heading-display heading-3">Ready to Create New Kolam Variations?</h3>
            <p className="body-text body-text--sm">
              Use the generative playground to algorithmically create and inspect new Pulli Kolam designs.
            </p>
          </div>
          <Link to="/playground" className="btn btn--primary">
            <span>Launch Kolam Playground</span>
            <ArrowRight size={16} />
          </Link>
        </div>

      </div>
    </main>
  )
}
