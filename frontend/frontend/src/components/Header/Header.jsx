import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { ChevronDown, Sun, User } from 'lucide-react'
import './Header.css'

export default function Header() {
  const [langOpen, setLangOpen] = useState(false)

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
              {/* Kolam interlocking loops */}
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
            Home
          </NavLink>
          <NavLink to="/analyze" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            Analyze
          </NavLink>
          <NavLink to="/generate" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            Generate
          </NavLink>
          <NavLink to="/explore" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            Gallery
          </NavLink>
          <NavLink to="/about" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            About
          </NavLink>
          <NavLink to="/how-it-works" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            How it Works
          </NavLink>
        </nav>

        {/* Right: Controls */}
        <div className="navbar-controls">
          <div className="lang-dropdown">
            <button className="btn-lang" onClick={() => setLangOpen(!langOpen)}>
              <span>English</span>
              <ChevronDown size={14} />
            </button>
          </div>

          <button className="btn-theme" aria-label="Toggle Theme">
            <Sun size={18} />
          </button>

          <button className="btn-login">
            <User size={16} />
            <span>Login</span>
          </button>
        </div>
      </div>
    </header>
  )
}
