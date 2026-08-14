import { Link } from 'react-router-dom'
import { useLanguage } from '../../context/LanguageContext'
import '../../styles/legal.css'

const EFFECTIVE_DATE = '2026-08-14'

export default function Terms() {
  const { t } = useLanguage()

  return (
    <main id="main-content" className="legal-page">
      <header className="legal-header section section--bordered">
        <div className="container">
          <p className="eyebrow eyebrow--accent">{t('legal.termsEyebrow')}</p>
          <h1 className="heading-display heading-2">{t('legal.termsTitle')}</h1>
        </div>
      </header>

      <section className="container section legal-content">
        <p className="legal-effective-date label-tech">Effective date: {EFFECTIVE_DATE}</p>
        <p className="legal-english-notice">{t('legal.englishOnlyNotice')}</p>

        <h2 className="heading-display heading-3">Acceptance of these terms</h2>
        <p className="body-text">
          By using PULLI, you agree to these terms. If you do not agree, please do not use the
          service.
        </p>

        <h2 className="heading-display heading-3">What PULLI is</h2>
        <p className="body-text">
          PULLI is a research and educational platform for studying Pulli Kolam (South Indian
          dot-grid) design principles through computational geometry, graph theory, and an
          experimental machine-learning detector. It includes a live image-analysis workflow
          (the Detect page), a static walkthrough of a precomputed dataset, and illustrative
          examples of pattern reconstruction.
        </p>

        <h2 className="heading-display heading-3">Permitted use</h2>
        <p className="body-text">
          You may use PULLI to analyze images you have the right to upload, for personal,
          academic, or research purposes. Do not use it to process content you don't have
          permission to use, or in any way that violates applicable law.
        </p>

        <h2 className="heading-display heading-3">User accounts</h2>
        <p className="body-text">
          You're responsible for keeping your password confidential and for activity under your
          account. Provide accurate information when registering. PULLI does not currently
          verify age or identity, so you must independently be able to legally agree to these
          terms where you live.
        </p>

        <h2 className="heading-display heading-3">Uploaded content</h2>
        <p className="body-text">
          You retain ownership of any image you upload. You grant us only the limited right to
          process it for the purpose of returning a result to you. As described in our{' '}
          <Link to="/privacy">Privacy Policy</Link>, uploaded images are deleted immediately
          after processing and are not retained or used for training.
        </p>

        <h2 className="heading-display heading-3">Intellectual property</h2>
        <p className="body-text">
          The PULLI name, codebase, and design are our project's own work except where noted.
          We don't claim ownership over the traditional Kolam art form itself or over images you
          upload.
        </p>

        <h2 className="heading-display heading-3">Experimental and research limitations</h2>
        <p className="body-text">
          <strong>Read this section carefully.</strong> PULLI's structural analysis (dot
          detection, graph construction, motif induction, Eulerian-validity checking) and its
          machine-learning detector are research components, not certified or authoritative
          measurement tools:
        </p>
        <ul className="body-text">
          <li>The classical detector is deterministic but can over- or under-detect dots on
            real, non-dataset photographs, especially with unusual lighting, angle, or image
            quality.</li>
          <li>The experimental ML detector (M4.2) has a measured high false-positive rate on
            real photographs in our own evaluation and is <strong>not the default detector</strong>
            for this reason -- it is offered for comparison, not as a recommended primary tool.</li>
          <li>Reconstruction and any generated/illustrative pattern output are not guaranteed to
            be structurally valid, aesthetically representative, or free of errors. Do not treat
            any PULLI output as an authoritative statement about a pattern's mathematical
            properties without independent verification.</li>
        </ul>

        <h2 className="heading-display heading-3">Availability</h2>
        <p className="body-text">
          PULLI is provided on a best-effort basis with no uptime guarantee. Features,
          including experimental ones, may change or be removed without notice.
        </p>

        <h2 className="heading-display heading-3">Prohibited use</h2>
        <p className="body-text">
          Do not attempt to disrupt, overload, or gain unauthorized access to PULLI's systems;
          do not upload unlawful content; do not use the service to violate anyone's rights.
        </p>

        <h2 className="heading-display heading-3">Disclaimers</h2>
        <p className="body-text">
          PULLI is provided "as is" and "as available," without warranties of any kind, express
          or implied, including as to accuracy, fitness for a particular purpose, or
          non-infringement.
        </p>

        <h2 className="heading-display heading-3">Limitation of liability</h2>
        <p className="body-text">
          To the maximum extent permitted by applicable law, PULLI and its contributors are not
          liable for any indirect, incidental, or consequential damages arising from your use of
          the service.
        </p>

        <h2 className="heading-display heading-3">Termination</h2>
        <p className="body-text">
          We may suspend or terminate accounts that violate these terms. You may stop using
          PULLI, and request account deletion, at any time (see Contact).
        </p>

        <h2 className="heading-display heading-3">Changes to these terms</h2>
        <p className="body-text">
          We may update these terms from time to time; the effective date above will reflect
          the most recent change.
        </p>

        <h2 className="heading-display heading-3">Governing law</h2>
        <p className="body-text">
          A specific governing jurisdiction has not been established for this project yet. This
          section will be updated once one is determined.
        </p>

        <h2 className="heading-display heading-3">Contact</h2>
        <p className="body-text">
          See the <Link to="/contact">Contact page</Link>.
        </p>
      </section>
    </main>
  )
}
