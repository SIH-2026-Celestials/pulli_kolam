import { useLanguage } from '../../context/LanguageContext'
import './About.css'

export default function About() {
  const { t } = useLanguage()

  return (
    <main id="main-content" className="about-page">
      <header className="about-header section">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">{t('pages.about.eyebrow')}</p>
          <h1 className="heading-display heading-2 about-title">
            {t('pages.about.title')}
          </h1>
          <p className="body-text about-sub">
            {t('pages.about.sub')}
          </p>
        </div>
      </header>

      <section className="container--narrow section about-content">
        <div className="about-grid">
          {/* Main overview */}
          <div className="about-main">
            <h2 className="heading-display heading-3">{t('pages.about.researchObjective')}</h2>
            <p className="body-text">
              {t('pages.about.researchP1')}
            </p>
            <p className="body-text">
              {t('pages.about.researchP2')}
            </p>

            <h2 className="heading-display heading-3" style={{ marginTop: '2rem' }}>{t('pages.about.datasetAttribution')}</h2>
            <p className="body-text">
              {t('pages.about.datasetP1Pre')} <strong>One-Stroke Dotted Pulli Kolam</strong> {t('pages.about.datasetP1Post')} <code>kolam19</code>, <code>kolam29</code>, <code>kolam109</code>.
            </p>
            <p className="body-text">
              {t('pages.about.datasetP2')}
            </p>

            <h2 className="heading-display heading-3" style={{ marginTop: '2rem' }}>{t('pages.about.institutionalAlignment')}</h2>
            <p className="body-text">
              {t('pages.about.institutionalP')}
            </p>
          </div>

          {/* Sidebar specs */}
          <div className="about-sidebar">
            <div className="about-card">
              <h3 className="eyebrow">{t('pages.about.techStack')}</h3>
              <ul className="about-tech-list label-tech">
                <li><span>{t('pages.about.techLanguage')}</span> Python 3.10+</li>
                <li><span>{t('pages.about.techGraphCore')}</span> NetworkX (MultiGraph)</li>
                <li><span>{t('pages.about.techDataProcessing')}</span> Pandas, NumPy</li>
                <li><span>{t('pages.about.techVisualization')}</span> Matplotlib</li>
                <li><span>{t('pages.about.techFrontend')}</span> React 19, Vite, Plain CSS</li>
                <li><span>{t('pages.about.techApi')}</span> FastAPI</li>
              </ul>
            </div>

            <div className="about-card">
              <h3 className="eyebrow">{t('pages.about.projectTeam')}</h3>
              <div className="team-list body-text body-text--sm">
                <div className="team-member">
                  <strong>{t('pages.about.teamName')}</strong>
                  <span>{t('pages.about.teamDesc')}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
