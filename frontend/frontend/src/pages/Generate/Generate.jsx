import { useLanguage } from '../../context/LanguageContext'
import GeneratedVariations from '../../components/GeneratedVariations/GeneratedVariations'
import './Generate.css'

export default function Generate() {
  const { t } = useLanguage()

  return (
    <main id="main-content" className="generate-page">
      <header className="generate-header section section--bordered">
        <div className="container--narrow">
          <p className="eyebrow eyebrow--accent">{t('pages.generate.eyebrow')}</p>
          <h1 className="heading-display heading-2 generate-title">
            {t('pages.generate.title')}
          </h1>
          <p className="body-text generate-sub">
            {t('pages.generate.sub')}
          </p>
        </div>
      </header>

      <section className="container--narrow section generate-content">
        <GeneratedVariations />
      </section>
    </main>
  )
}
