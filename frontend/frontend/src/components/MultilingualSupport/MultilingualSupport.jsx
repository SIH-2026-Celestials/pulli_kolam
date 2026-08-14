import { useState } from 'react'
import { useLanguage } from '../../context/LanguageContext'
import { LANGUAGES, ALL_LANGUAGES } from '../../i18n/index'
import './MultilingualSupport.css'

export default function MultilingualSupport() {
  const { lang, setLanguage, t } = useLanguage()
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <section className="ml-section">
      {/* Section header */}
      <div className="ml-header">
        <span className="ml-badge" aria-hidden="true">12</span>
        <div>
          <h2 className="ml-title">{t('multilingual.title')}</h2>
          <p className="ml-subtitle">
            {t('multilingual.subtitle').split('\n').map((line, i) => (
              <span key={i}>{line}{i === 0 && <br />}</span>
            ))}
          </p>
        </div>
      </div>

      {/* Card */}
      <div className="ml-card">
        <p className="ml-card-heading">{t('multilingual.selectLanguage')}</p>

        {/* 3×2 Language Grid */}
        <div className="ml-grid" role="group" aria-label={t('multilingual.selectLanguage')}>
          {LANGUAGES.map((l) => {
            const isSelected = l.code === lang
            return (
              <button
                key={l.code}
                className={`ml-lang-btn${isSelected ? ' ml-lang-btn--selected' : ''}`}
                onClick={() => setLanguage(l.code)}
                aria-pressed={isSelected}
                aria-label={`${l.label} - ${l.nativeName}`}
              >
                <span className="ml-lang-icon" aria-hidden="true">{l.script}</span>
                <span className="ml-lang-name">
                  {l.code === 'en' ? l.nativeName : `${l.nativeName} (${l.label})`}
                </span>
                {isSelected && (
                  <span className="ml-lang-check" aria-hidden="true">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M2.5 7L5.5 10L11.5 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {/* View All */}
        <button
          className="ml-view-all"
          onClick={() => setModalOpen(true)}
          aria-label="View all supported languages"
        >
          {t('multilingual.viewAll')}
        </button>
      </div>

      {/* "View All Languages" Modal */}
      {modalOpen && (
        <div
          className="ml-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="All supported languages"
          onClick={(e) => e.target === e.currentTarget && setModalOpen(false)}
        >
          <div className="ml-modal">
            <div className="ml-modal-header">
              <h3 className="ml-modal-title">All Supported Languages</h3>
              <button
                className="ml-modal-close"
                onClick={() => setModalOpen(false)}
                aria-label="Close language modal"
              >
                ✕
              </button>
            </div>
            <p className="ml-modal-note">Additional languages are in preview. More coming soon.</p>
            <div className="ml-modal-grid">
              {ALL_LANGUAGES.map((l) => {
                const isSelected = l.code === lang
                const isPreview = !LANGUAGES.find(x => x.code === l.code)
                return (
                  <button
                    key={l.code}
                    className={`ml-lang-btn${isSelected ? ' ml-lang-btn--selected' : ''}${isPreview ? ' ml-lang-btn--preview' : ''}`}
                    onClick={() => { if (!isPreview) { setLanguage(l.code); setModalOpen(false) } }}
                    aria-pressed={isSelected}
                    aria-label={`${l.label} - ${l.nativeName}${isPreview ? ' (coming soon)' : ''}`}
                    disabled={isPreview}
                  >
                    <span className="ml-lang-icon" aria-hidden="true">{l.script}</span>
                    <span className="ml-lang-name">
                      {l.code === 'en' ? l.nativeName : `${l.nativeName} (${l.label})`}
                      {isPreview && <span className="ml-preview-tag">soon</span>}
                    </span>
                    {isSelected && (
                      <span className="ml-lang-check" aria-hidden="true">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path d="M2.5 7L5.5 10L11.5 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
