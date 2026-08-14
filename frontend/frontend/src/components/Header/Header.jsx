import { useState, useRef, useEffect } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { ChevronDown, Sun, Moon, User } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { useAuth } from '../../context/AuthContext'
import { useAuthModal } from '../../context/AuthModalContext'
import { LANGUAGES } from '../../i18n/index'
import PulliLogo from '../../assets/PULLI-LOGO.svg'
import './Header.css'

export default function Header() {
  const { lang, setLanguage, t } = useLanguage()
  const { status, user, logout, bypassAuth } = useAuth()
  const { openLogin, openRegister } = useAuthModal()
  const navigate = useNavigate()
  const [langOpen, setLangOpen] = useState(false)
  const dropdownRef = useRef(null)

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('pulli-theme')
      if (saved === 'dark') {
        document.documentElement.classList.add('dark-theme')
        return 'dark'
      }
    } catch {
      /* ignore */
    }
    document.documentElement.classList.remove('dark-theme')
    return 'light'
  })

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(nextTheme)
    try {
      localStorage.setItem('pulli-theme', nextTheme)
    } catch {
      /* ignore */
    }
    if (nextTheme === 'dark') {
      document.documentElement.classList.add('dark-theme')
    } else {
      document.documentElement.classList.remove('dark-theme')
    }
  }

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

  const userName = user?.displayName || user?.display_name || 'Guest Explorer'

  return (
    <header className="navbar-clone">
      <div className="navbar-inner">
        {/* Left: Brand Logo & Title */}
        <Link to="/" className="navbar-brand">
          <div className="brand-icon-wrapper">
            <img src={PulliLogo} alt="PULLI Logo" className="brand-logo-img" />
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
          <NavLink to="/detect" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.detect')}
          </NavLink>
          <NavLink to="/playground" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.playground')}
          </NavLink>
          <NavLink to="/explore" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.gallery')}
          </NavLink>
          <NavLink to="/learn" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            {t('nav.learn')}
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

          <button className="btn-theme" onClick={toggleTheme} aria-label="Toggle Theme">
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>

          {status === 'authenticated' && user ? (
            <div className="auth-controls">
              <Link to="/account" className="auth-user-chip">
                <span className="auth-user-avatar">{userName.charAt(0).toUpperCase()}</span>
                <span className="auth-user-name">{userName}</span>
              </Link>
              <button className="btn-login" onClick={handleLogout}>
                {t('nav.logout')}
              </button>
            </div>
          ) : (
            <div className="auth-controls">
              <button
                type="button"
                className="btn-bypass navbar-btn-action"
                style={{
                  padding: '6px 12px',
                  background: 'rgba(212, 175, 55, 0.12)',
                  border: '1px solid var(--color-gold, #d4af37)',
                  color: 'var(--color-gold, #d4af37)',
                  borderRadius: '4px',
                  fontSize: '0.8rem',
                  fontWeight: '600',
                  cursor: 'pointer'
                }}
                onClick={() => {
                  bypassAuth()
                  navigate('/account')
                }}
              >
                ⚡ {t('nav.bypassAuth')}
              </button>
              <button
                type="button"
                className="auth-login-link navbar-btn-action"
                onClick={openLogin}
              >
                {t('nav.login')}
              </button>
              <button
                type="button"
                className="btn-login navbar-btn-action"
                onClick={openRegister}
              >
                <User size={16} />
                <span>{t('nav.register')}</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
