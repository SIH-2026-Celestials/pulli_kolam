import { Link } from 'react-router-dom'
import { useLanguage } from '../../context/LanguageContext'
import '../../styles/legal.css'

const EFFECTIVE_DATE = '2026-08-14'

export default function Privacy() {
  const { t } = useLanguage()

  return (
    <main id="main-content" className="legal-page">
      <header className="legal-header section section--bordered">
        <div className="container">
          <p className="eyebrow eyebrow--accent">{t('legal.privacyEyebrow')}</p>
          <h1 className="heading-display heading-2">{t('legal.privacyTitle')}</h1>
        </div>
      </header>

      <section className="container section legal-content">
        <p className="legal-effective-date label-tech">Effective date: {EFFECTIVE_DATE}</p>
        <p className="legal-english-notice">{t('legal.englishOnlyNotice')}</p>

        <h2 className="heading-display heading-3">What PULLI collects</h2>
        <p className="body-text">
          PULLI collects two kinds of information: account information you provide if you
          register, and the images you upload if you use the Detect page. It does not collect
          anything else beyond what your browser and our hosting infrastructure exchange to
          serve the site (standard web request handling described below).
        </p>

        <h2 className="heading-display heading-3">Account information</h2>
        <p className="body-text">
          If you create an account, we store your email address, a display name you choose, a
          <strong> bcrypt hash</strong> of your password (never the password itself, and never
          logged anywhere), and timestamps for account creation and last login. We do not
          currently offer a self-service way to edit or delete this information from within the
          app -- contact us (see the Contact page) to request a change or deletion.
        </p>

        <h2 className="heading-display heading-3">Uploaded images</h2>
        <p className="body-text">
          When you upload an image on the Detect page, it is sent to our backend, written to a
          temporary file for the duration of that single request (detection, analysis, or
          reconstruction), and <strong>deleted immediately after processing completes</strong>.
          We do not store uploaded images, do not log their contents, and do not use them to
          train any model -- this reflects what the code actually does (`api/main.py` deletes
          the temp file in a `finally` block on every request), not an aspirational policy.
        </p>

        <h2 className="heading-display heading-3">API and request metadata</h2>
        <p className="body-text">
          Like most web servers, our backend process (uvicorn) writes basic request logs
          (method, path, status code, timing) to its console output while running, for
          operational debugging. We do not currently run any persistent analytics, tracking, or
          request-metadata database -- there is no dashboard or export of this information
          beyond ordinary server console output.
        </p>

        <h2 className="heading-display heading-3">Cookies and browser storage</h2>
        <p className="body-text">
          PULLI sets one cookie: <code>pulli_session</code>, used only to keep you signed in.
          It is <strong>HttpOnly</strong> (invisible to page JavaScript) and is not used for
          advertising or tracking. Separately, your browser's local storage (not a cookie) holds
          your chosen interface language and light/dark theme preference -- these stay on your
          device and are never sent to our servers.
        </p>

        <h2 className="heading-display heading-3">Retention</h2>
        <p className="body-text">
          Uploaded images: not retained at all (see above). Session records: expire
          automatically after 14 days, or immediately when you log out. Account records: kept
          until you ask us to delete them (see Contact).
        </p>

        <h2 className="heading-display heading-3">Third-party services</h2>
        <p className="body-text">
          None are integrated into PULLI at this time. The classical detector and the
          experimental ML detector both run inside our own backend process on our own
          infrastructure -- no image or account data is sent to a third-party API, analytics
          provider, or ad network.
        </p>

        <h2 className="heading-display heading-3">Security</h2>
        <p className="body-text">
          Passwords are hashed with bcrypt before storage and are never logged or returned by
          any API response. We do not currently claim encryption at rest for the database, and
          we have not undergone a formal security audit, SOC 2, or HIPAA assessment -- stating
          otherwise would not be accurate to what is actually implemented.
        </p>

        <h2 className="heading-display heading-3">Your rights</h2>
        <p className="body-text">
          We have not conducted a jurisdiction-specific legal assessment (e.g. GDPR or CCPA
          compliance), so we are not asserting compliance with any specific regulatory
          framework here. In practice: you can contact us at any time to ask what data we hold
          about your account and to request its deletion.
        </p>

        <h2 className="heading-display heading-3">Changes to this policy</h2>
        <p className="body-text">
          If this policy changes, the effective date above will be updated. We do not currently
          send out change notifications by email.
        </p>

        <h2 className="heading-display heading-3">Contact</h2>
        <p className="body-text">
          See the <Link to="/contact">Contact page</Link> for how to reach us about privacy
          questions or data requests.
        </p>
      </section>
    </main>
  )
}
