import { useState, useRef, useEffect } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { ChevronDown, Sun, User, LogOut, Sparkles } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { useAuth } from '../../context/AuthContext'
import { LANGUAGES } from '../../i18n/index'
import './Header.css'

export default function Header() {
  const { lang, setLanguage, t } = useLanguage()
  const { user, isGuest, setIsAuthModalOpen, logout } = useAuth()
  const [langOpen, setLangOpen] = useState(false)
  const dropdownRef = useRef(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handle(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setLangOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const currentLang = LANGUAGES.find(l => l.code === lang) || LANGUAGES[0]

  return (
    <header className="navbar-clone">
      <div className="navbar-inner">
        {/* Left: Brand Logo & Title */}
        <Link to="/" className="navbar-brand">
          <div className="brand-icon-wrapper">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="20" cy="8" r="1.5" fill="#B88735" />
              <circle cx="20" cy="32" r="1.5" fill="#B88735" />
              <circle cx="8" cy="20" r="1.5" fill="#B88735" />
              <circle cx="32" cy="20" r="1.5" fill="#B88735" />
              <circle cx="14" cy="14" r="1.5" fill="#B88735" />
              <circle cx="26" cy="14" r="1.5" fill="#B88735" />
              <circle cx="14" cy="26" r="1.5" fill="#B88735" />
              <circle cx="26" cy="26" r="1.5" fill="#B88735" />
              <circle cx="20" cy="20" r="2" fill="#B88735" />
              <path d="M 20 8 C 28 8, 32 12, 32 20 C 32 28, 28 32, 20 32 C 12 32, 8 28, 8 20 C 8 12, 12 8, 20 8 Z" stroke="#B88735" strokeWidth="1.5" fill="none"/>
              <path d="M 14 14 C 20 8, 26 8, 26 14 C 32 20, 32 26, 26 26 C 20 32, 14 32, 14 26 C 8 20, 8 14, 14 14 Z" stroke="#B88735" strokeWidth="1.2" strokeDasharray="60 0" fill="none"/>
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-title">PULLI</span>
            <span className="brand-subtitle">Kolam Design-Principle Engine</span>
          </div>
        </Link>

        {/* Center: Navigation Links */}
        <nav className="navbar-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.home')}
          </NavLink>
          <NavLink to="/analyze" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.analyze')}
          </NavLink>
          <NavLink to="/detect" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.detect')}
          </NavLink>
          <NavLink to="/explore" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.gallery')}
          </NavLink>
          <NavLink to="/learn" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            Learn
          </NavLink>
          <NavLink to="/about" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.about')}
          </NavLink>
          <NavLink to="/how-it-works" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.howItWorks')}
          </NavLink>
        </nav>

        {/* Right: Controls */}
        <div className="navbar-controls">
          <div className="lang-dropdown" ref={dropdownRef}>
            <button
              className="btn-lang"
              onClick={() => setLangOpen(o => !o)}
              aria-haspopup="listbox"
              aria-expanded={langOpen}
            >
              <span>{currentLang.nativeName}</span>
              <ChevronDown size={14} className={langOpen ? 'chevron-open' : ''} />
            </button>
            {langOpen && (
              <ul className="lang-menu" role="listbox" aria-label="Select language">
                {LANGUAGES.map(l => (
                  <li
                    key={l.code}
                    role="option"
                    aria-selected={l.code === lang}
                    className={`lang-option${l.code === lang ? ' selected' : ''}`}
                    onClick={() => { setLanguage(l.code); setLangOpen(false) }}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { setLanguage(l.code); setLangOpen(false) } }}
                    tabIndex={0}
                  >
                    <span className="lang-script">{l.script}</span>
                    <span>{l.nativeName}</span>
                    {l.code === lang && <span className="lang-check">✓</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <button className="btn-theme" aria-label="Toggle Theme">
            <Sun size={18} />
          </button>

          {/* User Auth / Guest Status Controls */}
          {user ? (
            <div className="user-auth-badge">
              <span className="user-email" title={user.email}>
                <User size={14} />
                {user.email.split('@')[0]}
              </span>
              <button className="btn-logout" onClick={logout} title="Sign Out">
                <LogOut size={14} />
              </button>
            </div>
          ) : isGuest ? (
            <div className="guest-badge-group">
              <span className="guest-mode-tag label-tech">
                <Sparkles size={12} /> Guest Mode
              </span>
              <button className="btn-login" onClick={() => setIsAuthModalOpen(true)}>
                <User size={14} />
                <span>Account</span>
              </button>
            </div>
          ) : (
            <button className="btn-login" onClick={() => setIsAuthModalOpen(true)}>
              <User size={16} />
              <span>Login / Guest</span>
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
