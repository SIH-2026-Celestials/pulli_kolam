import { useState } from 'react'
import { X, Lock, Mail, Sparkles, ShieldCheck } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import './AuthModal.css'

export default function AuthModal() {
  const { isAuthModalOpen, setIsAuthModalOpen, login, signup, bypassLogin } = useAuth()
  const [tab, setTab] = useState('login') // 'login' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  if (!isAuthModalOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      if (tab === 'login') {
        await login(email, password)
      } else {
        await signup(email, password)
      }
    } catch (err) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-modal-overlay" onClick={() => setIsAuthModalOpen(false)}>
      <div className="auth-modal-card archival-frame" onClick={(e) => e.stopPropagation()}>
        <button
          className="auth-modal-close"
          onClick={() => setIsAuthModalOpen(false)}
          aria-label="Close modal"
        >
          <X size={20} />
        </button>

        <div className="auth-modal-header">
          <span className="eyebrow eyebrow--accent">PULLI AUTHENTICATION &amp; STORAGE</span>
          <h2 className="heading-display heading-3">Sign In or Explore as Guest</h2>
          <p className="body-text body-text--sm">
            Access your saved Kolam generations stored in Supabase DB, or bypass login to try the live MVP immediately using browser local storage.
          </p>
        </div>

        {/* Tab switcher */}
        <div className="auth-tab-bar">
          <button
            className={`auth-tab ${tab === 'login' ? 'active' : ''}`}
            onClick={() => { setTab('login'); setError(null) }}
          >
            Sign In
          </button>
          <button
            className={`auth-tab ${tab === 'signup' ? 'active' : ''}`}
            onClick={() => { setTab('signup'); setError(null) }}
          >
            Create Account
          </button>
        </div>

        {error && (
          <div className="auth-error-box label-tech">
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="auth-field">
            <label className="label-tech">EMAIL ADDRESS</label>
            <div className="auth-input-wrapper">
              <Mail size={16} className="auth-input-icon" />
              <input
                type="email"
                required
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-text auth-input"
              />
            </div>
          </div>

          <div className="auth-field">
            <label className="label-tech">PASSWORD</label>
            <div className="auth-input-wrapper">
              <Lock size={16} className="auth-input-icon" />
              <input
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-text auth-input"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn--primary btn--full"
          >
            {loading ? 'Processing...' : tab === 'login' ? 'Sign In to Account' : 'Register Account'}
          </button>
        </form>

        <div className="auth-divider">
          <span>OR</span>
        </div>

        {/* GUEST MODE BYPASS BUTTON */}
        <div className="auth-guest-section">
          <button
            type="button"
            onClick={bypassLogin}
            className="btn btn--outline btn--full btn--guest-bypass"
          >
            <Sparkles size={16} />
            <span>Bypass Login &amp; Try Live MVP as Guest →</span>
          </button>

          <p className="guest-note label-tech">
            <ShieldCheck size={14} inline /> Guest Mode stores your recent Kolam generations in LocalStorage automatically.
          </p>
        </div>
      </div>
    </div>
  )
}
