import { useState, useEffect } from 'react'
import { Eye, EyeOff, X, Loader2 } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useAuthModal } from '../../context/AuthModalContext'
import { useLanguage } from '../../context/LanguageContext'
import './AuthModal.css'

const MIN_PASSWORD_LENGTH = 8

const CornerSVG = () => (
  <svg className="corner-decor-svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-gold)" strokeWidth="1.2" xmlns="http://www.w3.org/2000/svg">
    <path d="M 2 22 V 2 H 22" />
    <path d="M 6 22 V 6 H 22" strokeWidth="0.6" strokeDasharray="1.5 1.5" />
    <circle cx="2" cy="2" r="1.8" fill="var(--color-gold)" />
  </svg>
)

export default function AuthModal() {
  const { t } = useLanguage()
  const { login, register } = useAuth()
  const { isOpen, mode, closeModal, toggleMode } = useAuthModal()
  
  // Login Form States
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [showLoginPassword, setShowLoginPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [loginError, setLoginError] = useState(null)
  const [loginSubmitting, setLoginSubmitting] = useState(false)

  // Register Form States
  const [regName, setRegName] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirmPassword, setRegConfirmPassword] = useState('')
  const [showRegPassword, setShowRegPassword] = useState(false)
  const [showRegConfirmPassword, setShowRegConfirmPassword] = useState(false)
  const [acceptTerms, setAcceptTerms] = useState(false)
  const [regError, setRegError] = useState(null)
  const [regSubmitting, setRegSubmitting] = useState(false)

  // Manage body scroll when modal opens
  useEffect(() => {
    if (isOpen) {
      document.body.classList.add('auth-modal-open')
    } else {
      document.body.classList.remove('auth-modal-open')
    }
    return () => {
      document.body.classList.remove('auth-modal-open')
    }
  }, [isOpen])

  // Handle ESC key press
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        closeModal()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, closeModal])

  const handleLoginSubmit = async (e) => {
    e.preventDefault()
    setLoginError(null)
    setLoginSubmitting(true)
    
    const { error: err } = await login(loginEmail, loginPassword)
    setLoginSubmitting(false)
    
    if (err) {
      setLoginError(err.kind === 'unauthorized' ? t('auth.errorInvalidCredentials') : err.message)
      return
    }
    
    closeModal()
  }

  const handleRegisterSubmit = async (e) => {
    e.preventDefault()
    setRegError(null)

    if (regPassword.length < MIN_PASSWORD_LENGTH) {
      setRegError(t('auth.errorPasswordLength', { n: MIN_PASSWORD_LENGTH }))
      return
    }
    if (regPassword !== regConfirmPassword) {
      setRegError(t('auth.errorPasswordMismatch'))
      return
    }
    if (!acceptTerms) {
      setRegError('Please accept the Terms & Conditions to continue.')
      return
    }

    setRegSubmitting(true)
    const { error: err } = await register(regEmail, regPassword, regName)
    setRegSubmitting(false)

    if (err) {
      setRegError(err.kind === 'conflict' ? t('auth.errorEmailTaken') : err.message)
      return
    }

    closeModal()
  }

  if (!isOpen) return null

  // Inputs micro-interactions helper styles
  const isEmailValid = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  const isNameValid = (name) => name.trim().length >= 2
  const isPasswordValid = (pw) => pw.length >= MIN_PASSWORD_LENGTH

  return (
    <div 
      className={`auth-backdrop active`} 
      onClick={closeModal}
      role="dialog"
      aria-modal="true"
    >
      <div 
        className="auth-3d-scene" 
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`auth-card-flipper ${mode === 'register' ? 'flipped' : ''}`}>
          
          {/* FRONT CARD: LOGIN FORM */}
          <div className="auth-card-face auth-card-front">
            {/* Traditional Corner Ornaments */}
            <div className="auth-card-corners">
              <span className="corner-decor tl"><CornerSVG /></span>
              <span className="corner-decor tr"><CornerSVG /></span>
              <span className="corner-decor bl"><CornerSVG /></span>
              <span className="corner-decor br"><CornerSVG /></span>
            </div>

            <button 
              className="auth-close-btn" 
              onClick={closeModal} 
              aria-label="Close modal"
            >
              <X size={20} />
            </button>

            <div className="auth-header">
              <h2>{t('auth.loginTitle') || 'Welcome back'}</h2>
              <p>Sign in to continue to your account</p>
            </div>

            {/* Traditional Kolam Divider */}
            <div className="auth-divider-kolam">
              <svg width="60" height="24" viewBox="0 0 60 24" fill="none" stroke="var(--color-gold)" strokeWidth="1.2">
                <path d="M 20 12 Q 30 2 40 12 Q 30 22 20 12" />
                <path d="M 30 7 Q 40 17 30 17 Q 20 7 30 7" />
                <line x1="5" y1="12" x2="15" y2="12" strokeDasharray="2 2" />
                <line x1="45" y1="12" x2="55" y2="12" strokeDasharray="2 2" />
              </svg>
            </div>

            <form onSubmit={handleLoginSubmit} className="auth-form-body">
              <div className="auth-input-group">
                <label className="auth-input-label">{t('auth.email')}</label>
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  className={`auth-input-field ${isEmailValid(loginEmail) ? 'is-valid' : ''}`}
                />
              </div>

              <div className="auth-input-group">
                <label className="auth-input-label">{t('auth.password')}</label>
                <div className="auth-input-wrapper">
                  <input
                    type={showLoginPassword ? 'text' : 'password'}
                    required
                    autoComplete="current-password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    className={`auth-input-field ${isPasswordValid(loginPassword) ? 'is-valid' : ''}`}
                  />
                  <button
                    type="button"
                    className="auth-password-toggle"
                    onClick={() => setShowLoginPassword(p => !p)}
                    aria-label={showLoginPassword ? 'Hide password' : 'Show password'}
                  >
                    {showLoginPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="auth-helpers-row">
                <label className="auth-checkbox-label">
                  <input 
                    type="checkbox" 
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                  />
                  <span>Remember me</span>
                </label>
                <a href="#forgot" className="auth-forgot-link" onClick={(e) => e.preventDefault()}>
                  Forgot password?
                </a>
              </div>

              {loginError && (
                <p className="auth-error-message" role="alert">
                  {loginError}
                </p>
              )}

              <button 
                type="submit" 
                className="auth-btn-primary" 
                disabled={loginSubmitting}
              >
                {loginSubmitting && <Loader2 size={16} className="auth-spinner" />}
                <span>{loginSubmitting ? t('auth.loggingIn') : t('auth.loginSubmit')}</span>
              </button>
            </form>

            <p className="auth-footer-switch">
              Don't have an account? 
              <button className="auth-switch-btn" onClick={toggleMode}>
                Register
              </button>
            </p>
          </div>

          {/* BACK CARD: REGISTER FORM */}
          <div className="auth-card-face auth-card-back">
            {/* Traditional Corner Ornaments */}
            <div className="auth-card-corners">
              <span className="corner-decor tl"><CornerSVG /></span>
              <span className="corner-decor tr"><CornerSVG /></span>
              <span className="corner-decor bl"><CornerSVG /></span>
              <span className="corner-decor br"><CornerSVG /></span>
            </div>

            <button 
              className="auth-close-btn" 
              onClick={closeModal} 
              aria-label="Close modal"
            >
              <X size={20} />
            </button>

            <div className="auth-header">
              <h2>{t('auth.registerTitle') || 'Create your account'}</h2>
              <p>Join us and get started today</p>
            </div>

            {/* Traditional Kolam Divider */}
            <div className="auth-divider-kolam">
              <svg width="60" height="24" viewBox="0 0 60 24" fill="none" stroke="var(--color-gold)" strokeWidth="1.2">
                <path d="M 20 12 Q 30 2 40 12 Q 30 22 20 12" />
                <path d="M 30 7 Q 40 17 30 17 Q 20 7 30 7" />
                <line x1="5" y1="12" x2="15" y2="12" strokeDasharray="2 2" />
                <line x1="45" y1="12" x2="55" y2="12" strokeDasharray="2 2" />
              </svg>
            </div>

            <form onSubmit={handleRegisterSubmit} className="auth-form-body">
              <div className="auth-input-group">
                <label className="auth-input-label">{t('auth.displayName')}</label>
                <input
                  type="text"
                  required
                  maxLength={100}
                  autoComplete="name"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  className={`auth-input-field ${isNameValid(regName) ? 'is-valid' : ''}`}
                />
              </div>

              <div className="auth-input-group">
                <label className="auth-input-label">{t('auth.email')}</label>
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  className={`auth-input-field ${isEmailValid(regEmail) ? 'is-valid' : ''}`}
                />
              </div>

              <div className="auth-input-group">
                <label className="auth-input-label">{t('auth.password')}</label>
                <div className="auth-input-wrapper">
                  <input
                    type={showRegPassword ? 'text' : 'password'}
                    required
                    autoComplete="new-password"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    className={`auth-input-field ${isPasswordValid(regPassword) ? 'is-valid' : ''}`}
                  />
                  <button
                    type="button"
                    className="auth-password-toggle"
                    onClick={() => setShowRegPassword(p => !p)}
                    aria-label={showRegPassword ? 'Hide password' : 'Show password'}
                  >
                    {showRegPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="auth-input-group">
                <label className="auth-input-label">{t('auth.confirmPassword')}</label>
                <div className="auth-input-wrapper">
                  <input
                    type={showRegConfirmPassword ? 'text' : 'password'}
                    required
                    autoComplete="new-password"
                    value={regConfirmPassword}
                    onChange={(e) => setRegConfirmPassword(e.target.value)}
                    className={`auth-input-field ${regConfirmPassword && regPassword === regConfirmPassword ? 'is-valid' : ''}`}
                  />
                  <button
                    type="button"
                    className="auth-password-toggle"
                    onClick={() => setShowRegConfirmPassword(p => !p)}
                    aria-label={showRegConfirmPassword ? 'Hide password' : 'Show password'}
                  >
                    {showRegConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="auth-helpers-row">
                <label className="auth-checkbox-label auth-terms-checkbox">
                  <input 
                    type="checkbox" 
                    required
                    checked={acceptTerms}
                    onChange={(e) => setAcceptTerms(e.target.checked)}
                  />
                  <span>I agree to the Terms &amp; Conditions</span>
                </label>
              </div>

              {regError && (
                <p className="auth-error-message" role="alert">
                  {regError}
                </p>
              )}

              <button 
                type="submit" 
                className="auth-btn-primary" 
                disabled={regSubmitting}
              >
                {regSubmitting && <Loader2 size={16} className="auth-spinner" />}
                <span>{regSubmitting ? t('auth.registering') : t('auth.registerSubmit')}</span>
              </button>
            </form>

            <p className="auth-footer-switch">
              Already have an account? 
              <button className="auth-switch-btn" onClick={toggleMode}>
                Login
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
