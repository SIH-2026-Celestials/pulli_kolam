import { useLanguage } from '../../context/LanguageContext'
import '../../styles/legal.css'

const CONTACT_EMAIL = import.meta.env.VITE_CONTACT_EMAIL?.trim()

export default function Contact() {
  const { t } = useLanguage()

  return (
    <main id="main-content" className="legal-page">
      <header className="legal-header section section--bordered">
        <div className="container">
          <p className="eyebrow eyebrow--accent">{t('legal.contactEyebrow')}</p>
          <h1 className="heading-display heading-2">{t('legal.contactTitle')}</h1>
        </div>
      </header>

      <section className="container section legal-content">
        {CONTACT_EMAIL ? (
          <div className="archival-frame legal-contact-card">
            <p className="body-text">{t('legal.contactBody')}</p>
            <a href={`mailto:${CONTACT_EMAIL}`} className="legal-contact-email">{CONTACT_EMAIL}</a>
          </div>
        ) : (
          <div className="archival-frame legal-contact-card">
            <p className="body-text">
              A contact address has not been configured for this deployment yet
              (<code>VITE_CONTACT_EMAIL</code> is unset). This is not an oversight in the
              text below -- it reflects the current deployment configuration honestly rather
              than inventing an address.
            </p>
          </div>
        )}

        <p className="body-text body-text--sm legal-form-note">
          There is no contact form on this page -- PULLI has no backend endpoint to receive
          form submissions, and adding one that doesn't actually deliver anywhere would be
          worse than not having a form at all.
        </p>
      </section>
    </main>
  )
}
