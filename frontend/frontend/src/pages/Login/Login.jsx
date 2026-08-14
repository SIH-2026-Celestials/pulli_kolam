import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import './Login.css'

export default function Login() {
  const { t } = useLanguage()
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    const { error: err } = await login(email, password)
    setSubmitting(false)
    if (err) {
      setError(err.kind === 'unauthorized' ? t('auth.errorInvalidCredentials') : err.message)
      return
    }
    const redirectTo = location.state?.from || '/account'
    navigate(redirectTo, { replace: true })
  }

  return (
    <main id="main-content" className="auth-page">
      <div className="container auth-container">
        <form className="archival-frame auth-card" onSubmit={handleSubmit}>
          <p className="eyebrow eyebrow--accent">{t('auth.loginEyebrow')}</p>
          <h1 className="heading-display heading-2">{t('auth.loginTitle')}</h1>

          <label className="auth-field">
            <span className="label-tech">{t('auth.email')}</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="auth-input"
            />
          </label>

          <label className="auth-field">
            <span className="label-tech">{t('auth.password')}</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="auth-input"
            />
          </label>

          {error && <p className="auth-error" role="alert">{error}</p>}

          <button type="submit" className="btn btn--primary auth-submit" disabled={submitting}>
            {submitting ? t('auth.loggingIn') : t('auth.loginSubmit')}
          </button>

          <p className="body-text body-text--sm auth-switch">
            {t('auth.noAccount')} <Link to="/register">{t('auth.registerLink')}</Link>
          </p>
        </form>
      </div>
    </main>
  )
}
