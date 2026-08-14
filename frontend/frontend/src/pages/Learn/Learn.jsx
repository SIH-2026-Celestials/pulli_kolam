import { useLanguage } from '../../context/LanguageContext'
import ModuleCard from '../../components/ModuleCard/ModuleCard'
import { learnModules } from '../../data/learnData'
import './Learn.css'

export default function Learn() {
  const { t } = useLanguage()

  return (
    <main id="main-content" className="learn-page">
      {/* ── 1. HERO SECTION ────────────────────────────────────────────── */}
      <header className="learn-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">{t('learn.eyebrow')}</p>
          <h1 className="heading-display heading-2 learn-title">
            {t('learn.title')}
          </h1>
          <p className="body-text learn-sub">
            {t('learn.sub')}
          </p>
        </div>
      </header>

      {/* ── 2. MODULE CARDS GRID ───────────────────────────────────────── */}
      <section className="container--narrow section section--bordered">
        <div className="section-title-block">
          <p className="eyebrow">{t('learn.curriculumEyebrow')}</p>
          <h2 className="heading-display heading-3">{t('learn.curriculumTitle')}</h2>
          <p className="body-text body-text--sm">
            {t('learn.curriculumSub')}
          </p>
        </div>

        <div className="learn-modules-grid">
          {learnModules.map(module => (
            <ModuleCard key={module.id} module={module} />
          ))}
        </div>
      </section>

      {/* ── 3. WHY STUDY KOLAM? (3 VALUE PILLARS) ──────────────────────── */}
      <section className="section section--bordered learn-why-section">
        <div className="container--narrow">
          <div className="section-title-block">
            <p className="eyebrow eyebrow--accent">{t('learn.whyEyebrow')}</p>
            <h2 className="heading-display heading-3">{t('learn.whyTitle')}</h2>
            <p className="body-text body-text--sm">
              {t('learn.whySub')}
            </p>
          </div>

          <div className="why-grid">
            <div className="why-card archival-frame">
              <span className="eyebrow eyebrow--accent">{t('learn.p1Eyebrow')}</span>
              <h3 className="heading-display heading-4">{t('learn.p1Title')}</h3>
              <p className="body-text body-text--sm">
                {t('learn.p1Desc')}
              </p>
            </div>

            <div className="why-card archival-frame">
              <span className="eyebrow eyebrow--accent">{t('learn.p2Eyebrow')}</span>
              <h3 className="heading-display heading-4">{t('learn.p2Title')}</h3>
              <p className="body-text body-text--sm">
                {t('learn.p2Desc')}
              </p>
            </div>

            <div className="why-card archival-frame">
              <span className="eyebrow eyebrow--accent">{t('learn.p3Eyebrow')}</span>
              <h3 className="heading-display heading-4">{t('learn.p3Title')}</h3>
              <p className="body-text body-text--sm">
                {t('learn.p3Desc')}
              </p>
            </div>
          </div>
        </div>
      </section>


    </main>
  )
}
