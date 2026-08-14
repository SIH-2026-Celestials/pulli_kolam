import { useCallback, useState } from 'react'
import Hero from '../../components/Hero/Hero'
import FeatureStrip from '../../components/FeatureStrip/FeatureStrip'
import AnalysisPipeline from '../../components/AnalysisPipeline/AnalysisPipeline'
import GeneratedVariations from '../../components/GeneratedVariations/GeneratedVariations'
import RecentKolams from '../../components/RecentKolams/RecentKolams'
import { useKolamAnalysis } from '../../lib/api/useKolamAnalysis'
import { useLanguage } from '../../context/LanguageContext'
import './Home.css'

export default function Home() {
  const { t } = useLanguage()
  const { analysisState, startAnalysis, reset } = useKolamAnalysis()
  const [detector, setDetector] = useState('classical')

  // Enrich analysisState with the uploaded file preview URL so the
  // AnalysisPipeline component can show the real image in panel 1.
  const [previewUrl, setPreviewUrl] = useState(null)

  const handleUpload = useCallback((file, selectedDetector) => {
    // Revoke any previous object URL to avoid memory leaks.
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    startAnalysis(file, selectedDetector || detector)
  }, [previewUrl, startAnalysis, detector])

  const handleReset = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
    reset()
  }, [previewUrl, reset])

  // Attach the preview URL into analysisState without mutating hook state.
  const enrichedState = analysisState
    ? { ...analysisState, uploadedPreview: previewUrl }
    : null

  return (
    <main className="home-clone-main">
      {/* 1. HERO SECTION */}
      <Hero />

      {/* 2. FEATURE STRIP */}
      <FeatureStrip />

      {/* 3. MAIN CONTENT: TWO COLUMN LAYOUT */}
      <section className="main-content-section">
        <div className="main-content-container">
          {/* Badge clarifying that the card below is now a live demo */}
          <div className="illustrative-banner">
            <span className="illustrative-badge label-tech">
              {analysisState?.status === 'idle'
                ? t('home.illustrativeBadge')
                : 'Live ML Pipeline'}
            </span>
            {analysisState?.status !== 'idle' && (
              <button className="illustrative-cta illustrative-cta--reset" onClick={handleReset}>
                ← Reset
              </button>
            )}
            {analysisState?.status === 'idle' && (
              <a href="/detect" className="illustrative-cta">{t('home.tryDetectCta')}</a>
            )}
          </div>

          <div className="main-content-grid">
            {/* LEFT CARD: LIVE ANALYSIS PIPELINE (real ML, driven by SSE) */}
            <AnalysisPipeline
              analysisState={enrichedState}
              onUpload={handleUpload}
              detector={detector}
              onDetectorChange={setDetector}
            />

            {/* RIGHT CARD: GENERATED VARIATIONS & RULE SUMMARY */}
            <GeneratedVariations />
          </div>

          {/* 4. RECENTLY GENERATED KOLAMS — full width below both columns */}
          <RecentKolams />

          {/* 5. AICTE INITIATIVE SECTION */}
          <section className="aicte-section">
            <div className="aicte-card">
              <div className="aicte-content">
                <h3 className="aicte-title">AICTE Initiative</h3>
                <p className="aicte-desc">
                  This project is supported under the <strong>AICTE Heritage &amp; Culture</strong> initiative to promote <strong>Indian Knowledge Systems</strong> and digital innovation.
                </p>
                <a
                  href="https://www.aicte-india.org/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="aicte-link"
                >
                  Know more about AICTE &rarr;
                </a>
              </div>

              {/* Heritage Building Line Art SVG */}
              <div className="aicte-illustration" aria-hidden="true">
                <svg viewBox="0 0 320 260" fill="none" stroke="currentColor" xmlns="http://www.w3.org/2000/svg">
                  {/* Base stairs */}
                  <path d="M40 220 H280 M50 225 H270 M60 230 H260 M70 235 H250" strokeWidth="1" />
                  
                  {/* Main Building Frame */}
                  <rect x="70" y="130" width="180" height="90" rx="2" strokeWidth="1" />
                  
                  {/* Central Gate / Archway */}
                  <path d="M130 220 V170 C130 155 190 155 190 170 V220" strokeWidth="1.2" />
                  {/* Inner arch lines */}
                  <path d="M138 220 V174 C138 162 182 162 182 174 V220" strokeWidth="0.8" strokeDasharray="2 1" />
                  <path d="M146 220 V178 C146 170 174 170 174 178 V220" strokeWidth="0.8" />
                  
                  {/* Entrance door details */}
                  <path d="M150 220 V190 C150 185 170 185 170 190 V220" strokeWidth="1" />
                  
                  {/* Columns/Pillars on facade */}
                  <line x1="88" y1="130" x2="88" y2="220" strokeWidth="0.8" />
                  <line x1="108" y1="130" x2="108" y2="220" strokeWidth="0.8" />
                  <line x1="212" y1="130" x2="212" y2="220" strokeWidth="0.8" />
                  <line x1="232" y1="130" x2="232" y2="220" strokeWidth="0.8" />

                  {/* Balcony / First floor cornice */}
                  <line x1="65" y1="130" x2="255" y2="130" strokeWidth="1.5" />
                  <line x1="68" y1="126" x2="252" y2="126" strokeWidth="0.8" />
                  <line x1="72" y1="122" x2="248" y2="122" strokeWidth="0.8" />

                  {/* Second floor chhatris / windows */}
                  <rect x="85" y="95" width="26" height="31" strokeWidth="1" />
                  <rect x="209" y="95" width="26" height="31" strokeWidth="1" />
                  
                  {/* Onion Domes over chhatris */}
                  <path d="M85 95 C85 85 91 80 98 80 C105 80 111 85 111 95 Z" strokeWidth="1" />
                  <path d="M98 75 V80" strokeWidth="1" />
                  <circle cx="98" cy="74" r="1.5" />

                  <path d="M209 95 C209 85 215 80 222 80 C229 80 235 85 235 95 Z" strokeWidth="1" />
                  <path d="M222 75 V80" strokeWidth="1" />
                  <circle cx="222" cy="74" r="1.5" />
                  
                  {/* Center Dome drum structure */}
                  <rect x="125" y="90" width="70" height="36" strokeWidth="1.2" />
                  {/* Drum windows */}
                  <path d="M135 120 V102 C135 98 143 98 143 102 V120 M156 120 V102 C156 98 164 98 164 102 V120 M177 120 V102 C177 98 185 98 185 102 V120" strokeWidth="0.8" />
                  <line x1="120" y1="90" x2="200" y2="90" strokeWidth="1.5" />

                  {/* Main onion dome */}
                  <path d="M125 90 C125 70 135 55 160 55 C185 55 195 70 195 90 Z" strokeWidth="1.2" />
                  <path d="M125 90 C125 80 135 70 160 70 C185 70 195 80 195 90" strokeWidth="0.8" strokeDasharray="2 2" />
                  
                  {/* Onion dome pointed top & finial */}
                  <path d="M160 30 V55" strokeWidth="1.2" />
                  <circle cx="160" cy="30" r="2.5" />
                  <circle cx="160" cy="22" r="1.5" />
                  <circle cx="160" cy="16" r="0.8" />

                  {/* Dome ribbed lines */}
                  <path d="M142 90 C144 75 150 63 160 55 C170 63 176 75 178 90" strokeWidth="0.8" />
                  <path d="M151 90 C153 82 156 70 160 55 C164 70 167 82 169 90" strokeWidth="0.5" />
                </svg>
              </div>
            </div>
          </section>
        </div>
      </section>
    </main>
  )
}

