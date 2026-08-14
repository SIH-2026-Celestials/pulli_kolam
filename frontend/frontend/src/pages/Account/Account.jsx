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
  ArrowRight,
  Compass,
  Check
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
            <div className="skeleton-line" style={{ width: '40%', height: '24px', margin: '0 auto' }}></div>
            <div className="skeleton-line" style={{ width: '70%', height: '16px', margin: '16px auto 0' }}></div>
          </div>
        </div>
      </main>
    )
  }

  if (status === 'unauthenticated' || !user) {
    return (
      <main id="main-content" className="account-page">
        <div className="container--narrow section">
          {/* Guest Mode Hero Banner */}
          <div className="archival-frame guest-profile-banner">
            <div className="guest-banner-decor-dots" aria-hidden="true"></div>
            <div className="guest-banner-body">
              <div className="guest-banner-icon">
                <Sparkles size={28} />
              </div>
              <div className="guest-banner-content">
                <span className="section-eyebrow label-tech">SESSION MODE · GUEST EXPLORER</span>
                <h2 className="heading-display heading-3 guest-title">Guest Exploration Mode</h2>
                <p className="body-text body-text--sm guest-desc">
                  You are currently exploring PULLI as a Guest. Generated Kolam patterns and analysis sessions are automatically cached in your browser&apos;s LocalStorage.
                </p>
              </div>
              <div className="guest-banner-actions">
                <button className="btn btn--primary" onClick={() => navigate('/')}>
                  <span>Return to Home</span>
                  <ArrowRight size={15} />
                </button>
              </div>
            </div>
          </div>

          {/* Display Saved Kolam History even for Guest */}
          <div className="recent-work-wrapper">
            <RecentKolams />
          </div>
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

        {/* 1. ARCHIVAL PROFILE HERO */}
        <section className="profile-hero-card archival-frame">
          {/* Decorative Top Accent Cover */}
          <div className="profile-cover-banner">
            <div className="cover-grid-overlay" aria-hidden="true"></div>
            <div className="cover-geometric-ornament" aria-hidden="true">
              <svg width="240" height="90" viewBox="0 0 240 90" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="120" cy="45" r="35" stroke="rgba(255,255,255,0.08)" strokeWidth="1" strokeDasharray="3 3"/>
                <circle cx="120" cy="45" r="20" stroke="rgba(255,255,255,0.12)" strokeWidth="1"/>
                <circle cx="120" cy="45" r="4" fill="rgba(184,135,53,0.4)"/>
                <path d="M40 45H200" stroke="rgba(255,255,255,0.06)" strokeWidth="1"/>
                <path d="M120 -35V125" stroke="rgba(255,255,255,0.06)" strokeWidth="1"/>
              </svg>
            </div>
          </div>

          <div className="profile-hero-body">
            {/* Top Bar: Avatar overlapping cover on left, Actions on right */}
            <div className="profile-top-row">
              <div className="profile-avatar-container">
                <div className="profile-avatar-ring">
                  <div className="profile-avatar-circle">
                    <span className="avatar-initials">
                      {displayName.charAt(0).toUpperCase()}
                    </span>
                  </div>
                </div>
                <span className="status-indicator-dot" title="Active Kolam Practitioner">
                  <span className="status-pulse"></span>
                </span>
              </div>

              <div className="profile-hero-actions">
                <button
                  className="btn btn--outline btn--sm btn-edit-profile"
                  onClick={() => setIsEditing(!isEditing)}
                >
                  <Edit3 size={14} />
                  <span>{isEditing ? 'Cancel' : 'Edit Bio'}</span>
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

            {/* Main Information below top bar */}
            <div className="profile-main-meta">
              <div className="profile-identity-header">
                <div className="profile-name-group">
                  <div className="profile-name-row">
                    <h1 className="heading-display profile-name">{displayName}</h1>
                    <span className="role-badge label-tech">
                      <ShieldCheck size={12} /> PRACTITIONER &amp; RESEARCHER
                    </span>
                  </div>
                  <span className="profile-handle label-tech">{handleName}</span>
                </div>
              </div>

              {/* Bio Section */}
              {isEditing ? (
                <div className="bio-edit-box">
                  <textarea
                    value={bioText}
                    onChange={(e) => setBioText(e.target.value)}
                    className="input-text bio-textarea"
                    rows="2"
                    placeholder="Share your Kolam research interests or background..."
                  />
                  <div className="bio-edit-actions">
                    <button className="btn btn--primary btn--sm" onClick={() => setIsEditing(false)}>
                      <Check size={13} />
                      <span>Save Bio</span>
                    </button>
                  </div>
                </div>
              ) : (
                <p className="body-text body-text--sm profile-bio">{bioText}</p>
              )}

              {/* Meta Tags Footer */}
              <div className="profile-quick-tags label-tech">
                <span className="tag-item"><MapPin size={13} className="tag-icon" /> Tamil Nadu, India</span>
                <span className="dot-sep">•</span>
                <span className="tag-item"><Calendar size={13} className="tag-icon" /> Member since {joinDate}</span>
                <span className="dot-sep">•</span>
                <span className="tag-item"><Compass size={13} className="tag-icon" /> Kolam Mathematics Engine v1.0</span>
              </div>
            </div>
          </div>
        </section>

        {/* 2. COHESIVE RESEARCH STATISTICS SECTION */}
        <section className="stats-section-container">
          <div className="section-header-bar">
            <span className="section-eyebrow label-tech">RESEARCH METRICS</span>
            <h2 className="section-title heading-display">Quantitative Exploration</h2>
            <div className="section-divider-line"></div>
          </div>

          <div className="profile-stats-panel archival-frame">
            <div className="stat-col">
              <div className="stat-header">
                <Layers size={16} className="stat-icon" />
                <span className="stat-label label-tech">SAVED KOLAMS</span>
              </div>
              <span className="stat-number">{totalSaved}</span>
              <span className="stat-subtext">Archived in research log</span>
            </div>

            <div className="stat-col">
              <div className="stat-header">
                <LoopIcon size={16} className="stat-icon" />
                <span className="stat-label label-tech">EULERIAN CIRCUITS</span>
              </div>
              <span className="stat-number">{validEulerianCount}</span>
              <span className="stat-subtext">Single-stroke valid graphs</span>
            </div>

            <div className="stat-col">
              <div className="stat-header">
                <GitFork size={16} className="stat-icon" />
                <span className="stat-label label-tech">AVG SYMMETRY</span>
              </div>
              <span className="stat-number">D4 (100%)</span>
              <span className="stat-subtext">Dihedral 8-fold invariance</span>
            </div>

            <div className="stat-col">
              <div className="stat-header">
                <Grid size={16} className="stat-icon" />
                <span className="stat-label label-tech">PREFERRED LATTICE</span>
              </div>
              <span className="stat-number">7×7</span>
              <span className="stat-subtext">Standard Pulli dot matrix</span>
            </div>
          </div>
        </section>

        {/* 3. PROFILE DETAILS & ACHIEVEMENTS DUAL GRID */}
        <section className="profile-details-grid">

          {/* Account Information Card */}
          <article className="info-card archival-frame">
            <div className="card-header-bar">
              <div className="card-header-text">
                <span className="card-eyebrow label-tech">ACCOUNT DETAILS</span>
                <h3 className="heading-display heading-4 card-title">Account &amp; Personal Info</h3>
              </div>
              <User size={18} className="icon-accent" />
            </div>

            <div className="info-table">
              <div className="info-row">
                <span className="info-label label-tech"><User size={13} /> Full Name</span>
                <strong className="info-value">{displayName}</strong>
              </div>

              <div className="info-row">
                <span className="info-label label-tech"><Mail size={13} /> Email Address</span>
                <strong className="info-value info-value--email">{user.email}</strong>
              </div>

              <div className="info-row">
                <span className="info-label label-tech"><HardDrive size={13} /> Storage Engine</span>
                <span className="status-pill status-pill--valid">
                  <CheckCircle2 size={12} />
                  <span>Connected Database</span>
                </span>
              </div>

              <div className="info-row">
                <span className="info-label label-tech"><ShieldCheck size={13} /> Researcher Status</span>
                <span className="status-pill status-pill--gold">
                  <Award size={12} />
                  <span>Verified Researcher</span>
                </span>
              </div>
            </div>
          </article>

          {/* Research Achievements & Badges */}
          <article className="info-card archival-frame">
            <div className="card-header-bar">
              <div className="card-header-text">
                <span className="card-eyebrow label-tech">HERITAGE MILESTONES</span>
                <h3 className="heading-display heading-4 card-title">Heritage Achievements</h3>
              </div>
              <Award size={18} className="icon-accent" />
            </div>

            <div className="badges-list">
              <div className="achievement-badge-item">
                <div className="badge-emblem-wrap">
                  <LoopIcon size={18} />
                </div>
                <div className="badge-info">
                  <div className="badge-header-row">
                    <h4 className="heading-display badge-title">Eulerian Master</h4>
                    <span className="badge-tag label-tech">GRAPH TOPOLOGY</span>
                  </div>
                  <p className="body-text body-text--sm badge-desc">
                    Validated single-stroke continuous loop graph correctness with zero vertex degree violations.
                  </p>
                </div>
              </div>

              <div className="achievement-badge-item">
                <div className="badge-emblem-wrap">
                  <GitFork size={18} />
                </div>
                <div className="badge-info">
                  <div className="badge-header-row">
                    <h4 className="heading-display badge-title">D4 Dihedral Explorer</h4>
                    <span className="badge-tag label-tech">SYMMETRY MATRIX</span>
                  </div>
                  <p className="body-text body-text--sm badge-desc">
                    Analyzed 8-fold rotational and reflectional symmetry matrix across complex pattern variations.
                  </p>
                </div>
              </div>

              <div className="achievement-badge-item">
                <div className="badge-emblem-wrap">
                  <Grid size={18} />
                </div>
                <div className="badge-info">
                  <div className="badge-header-row">
                    <h4 className="heading-display badge-title">Lattice Specialist</h4>
                    <span className="badge-tag label-tech">PULLI LATTICE</span>
                  </div>
                  <p className="body-text body-text--sm badge-desc">
                    Engineered 7×7 and 9×9 Pulli dot-grid variations using mathematical motif placement.
                  </p>
                </div>
              </div>
            </div>
          </article>
        </section>

        {/* 4. RECENTLY SAVED KOLAM DESIGNS */}
        <section className="recent-work-section">
          <div className="section-header-bar">
            <span className="section-eyebrow label-tech">ARCHIVAL LOG</span>
            <h2 className="section-title heading-display">Recent Kolam Explorations</h2>
            <p className="section-subtitle body-text body-text--sm">
              Your saved patterns and recent generative explorations stored in your archive.
            </p>
          </div>

          <div className="recent-work-wrapper">
            <RecentKolams />
          </div>
        </section>

        {/* 5. EDITORIAL PLAYGROUND CTA BANNER */}
        <section className="playground-cta-section">
          <div className="playground-cta-banner archival-frame">
            <div className="cta-pattern-overlay" aria-hidden="true"></div>
            <div className="cta-content">
              <span className="section-eyebrow label-tech">GENERATIVE ENGINE</span>
              <h3 className="heading-display heading-3 cta-title">Ready to Create Your Next Kolam?</h3>
              <p className="body-text body-text--sm cta-desc">
                Explore new Pulli Kolam variations, Eulerian loop constraints, and symmetry groups through the interactive generative playground.
              </p>
            </div>
            <div className="cta-action">
              <Link to="/playground" className="btn btn--primary cta-btn">
                <span>Launch Kolam Playground</span>
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </section>

      </div>
    </main>
  )
}
