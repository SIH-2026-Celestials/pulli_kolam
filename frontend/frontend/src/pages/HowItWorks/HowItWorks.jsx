import { Link } from 'react-router-dom'
import { useLanguage } from '../../context/LanguageContext'
import './HowItWorks.css'

export default function HowItWorks() {
  const { t } = useLanguage()

  const steps = [
    { num: '01', title: t('pages.howItWorks.step1Title'), subtitle: t('pages.howItWorks.step1Subtitle'), desc: t('pages.howItWorks.step1Desc') },
    { num: '02', title: t('pages.howItWorks.step2Title'), subtitle: t('pages.howItWorks.step2Subtitle'), desc: t('pages.howItWorks.step2Desc') },
    { num: '03', title: t('pages.howItWorks.step3Title'), subtitle: t('pages.howItWorks.step3Subtitle'), desc: t('pages.howItWorks.step3Desc') },
    { num: '04', title: t('pages.howItWorks.step4Title'), subtitle: t('pages.howItWorks.step4Subtitle'), desc: t('pages.howItWorks.step4Desc') },
    { num: '05', title: t('pages.howItWorks.step5Title'), subtitle: t('pages.howItWorks.step5Subtitle'), desc: t('pages.howItWorks.step5Desc') },
    { num: '06', title: t('pages.howItWorks.step6Title'), subtitle: t('pages.howItWorks.step6Subtitle'), desc: t('pages.howItWorks.step6Desc'), isFuture: true },
  ]

  return (
    <main id="main-content" className="how-it-works-page">
      <header className="how-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">{t('pages.howItWorks.eyebrow')}</p>
          <h1 className="heading-display heading-2 how-title">
            {t('pages.howItWorks.title')}
          </h1>
          <p className="body-text how-sub">
            {t('pages.howItWorks.sub')}
          </p>
        </div>
      </header>

      {/* Visual Pipeline Grid */}
      <section className="container--narrow section section--bordered">
        <div className="pipeline-grid">
          {steps.map((step) => (
            <div key={step.num} className={`pipeline-card archival-frame ${step.isFuture ? 'pipeline-card--future' : ''}`}>
              <div className="card-top">
                <span className="step-tag label-tech">{step.num} - {step.subtitle}</span>
                {step.isFuture && <span className="future-tag label-tech">{t('pages.howItWorks.inProgress')}</span>}
              </div>
              <h2 className="heading-display heading-4 step-heading">{step.title}</h2>
              <p className="body-text body-text--sm step-text">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Deep-Dive Technical Detail */}
      <section className="container--narrow section">
        <div className="tech-explain-grid">
          <div>
            <p className="eyebrow">{t('pages.howItWorks.graphRepresentation')}</p>
            <h2 className="heading-display heading-3" style={{ marginTop: '0.5rem' }}>
              {t('pages.howItWorks.whyMultiGraph')}
            </h2>
          </div>
          <div className="body-text">
            <p>
              {t('pages.howItWorks.whyP1')}
            </p>
            <p style={{ marginTop: '1rem' }}>
              {t('pages.howItWorks.whyP2')}
            </p>
            <div style={{ marginTop: '1.5rem' }}>
              <Link to="/technology" className="btn btn--primary">
                {t('pages.howItWorks.viewSpecs')}
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
