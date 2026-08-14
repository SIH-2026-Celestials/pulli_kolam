import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import './Account.css'

export default function Account() {
  const { t } = useLanguage()
  const { status, user, logout } = useAuth()
  const navigate = useNavigate()
  const [loggingOut, setLoggingOut] = useState(false)

  const handleLogout = async () => {
    setLoggingOut(true)
    await logout()
    navigate('/', { replace: true })
  }

  if (status === 'loading') {
    return (
      <main id="main-content" className="account-page">
        <div className="container">
          <p className="body-text body-text--sm">{t('auth.loadingAccount')}</p>
        </div>
      </main>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" state={{ from: '/account' }} replace />
  }

  if (status === 'error') {
    return (
      <main id="main-content" className="account-page">
        <div className="container">
          <p className="detect-error" role="alert">{t('auth.errorLoadingAccount')}</p>
        </div>
      </main>
    )
  }

  return (
    <main id="main-content" className="account-page">
      <header className="account-header section section--bordered">
        <div className="container">
          <p className="eyebrow eyebrow--accent">{t('auth.accountEyebrow')}</p>
          <h1 className="heading-display heading-2">{t('auth.accountTitle')}</h1>
        </div>
      </header>

      <section className="container section">
        <div className="archival-frame account-card">
          <div className="step-table">
            <div className="step-row"><span className="label-tech">{t('auth.displayName')}</span><strong>{user.display_name}</strong></div>
            <div className="step-row"><span className="label-tech">{t('auth.email')}</span><strong>{user.email}</strong></div>
            <div className="step-row">
              <span className="label-tech">{t('auth.memberSince')}</span>
              <strong>{new Date(user.created_at).toLocaleDateString()}</strong>
            </div>
          </div>

          <button className="btn btn--outline account-logout-btn" onClick={handleLogout} disabled={loggingOut}>
            {loggingOut ? t('auth.loggingOut') : t('auth.logout')}
          </button>
        </div>
      </section>
    </main>
  )
}
