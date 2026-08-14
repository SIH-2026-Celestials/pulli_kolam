import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import '../Login/Login.css'

const MIN_PASSWORD_LENGTH = 8

export default function Register() {
  const { t } = useLanguage()
  const { register } = useAuth()
  const navigate = useNavigate()
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(t('auth.errorPasswordLength', { n: MIN_PASSWORD_LENGTH }))
      return
    }
    if (password !== confirmPassword) {
      setError(t('auth.errorPasswordMismatch'))
      return
    }

    setSubmitting(true)
    const { error: err } = await register(email, password, displayName)
    setSubmitting(false)
    if (err) {
      setError(err.kind === 'conflict' ? t('auth.errorEmailTaken') : err.message)
      return
    }
    navigate('/account', { replace: true })
  }

  return (
    <main id="main-content" className="auth-page">
      <div className="container auth-container">
        <form className="archival-frame auth-card" onSubmit={handleSubmit}>
          <p className="eyebrow eyebrow--accent">{t('auth.registerEyebrow')}</p>
          <h1 className="heading-display heading-2">{t('auth.registerTitle')}</h1>

          <label className="auth-field">
            <span className="label-tech">{t('auth.displayName')}</span>
            <input
              type="text"
              required
              maxLength={100}
              autoComplete="name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="auth-input"
            />
          </label>

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
              minLength={MIN_PASSWORD_LENGTH}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="auth-input"
            />
            <span className="auth-hint">{t('auth.passwordHint', { n: MIN_PASSWORD_LENGTH })}</span>
          </label>

          <label className="auth-field">
            <span className="label-tech">{t('auth.confirmPassword')}</span>
            <input
              type="password"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="auth-input"
            />
          </label>

          {error && <p className="auth-error" role="alert">{error}</p>}

          <button type="submit" className="btn btn--primary auth-submit" disabled={submitting}>
            {submitting ? t('auth.registering') : t('auth.registerSubmit')}
          </button>

          <p className="body-text body-text--sm auth-switch">
            {t('auth.haveAccount')} <Link to="/login">{t('auth.loginLink')}</Link>
          </p>
        </form>
      </div>
    </main>
  )
}
