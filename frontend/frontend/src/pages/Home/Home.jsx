import { useState } from 'react'
import Hero from '../../components/Hero/Hero'
import FeatureStrip from '../../components/FeatureStrip/FeatureStrip'
import AnalysisPipeline from '../../components/AnalysisPipeline/AnalysisPipeline'
import GeneratedVariations from '../../components/GeneratedVariations/GeneratedVariations'
import './Home.css'

export default function Home() {
  const [uploadedImage, setUploadedImage] = useState(null)
  const [analysisProgress, setAnalysisProgress] = useState(56)

  const handleUploadImage = (imageDataUrl) => {
    setUploadedImage(imageDataUrl)
    setAnalysisProgress(10)
    
    // Simulate pipeline progress animation
    let current = 10
    const interval = setInterval(() => {
      current += 15
      if (current >= 100) {
        current = 100
        clearInterval(interval)
      }
      setAnalysisProgress(current)
    }, 400)
  }

  return (
    <main className="home-clone-main">
      {/* 1. HERO SECTION */}
      <Hero onUploadImage={handleUploadImage} />

      {/* 2. FEATURE STRIP */}
      <FeatureStrip />

      {/* 3. MAIN CONTENT: TWO COLUMN LAYOUT */}
      <section className="main-content-section">
        <div className="main-content-container">
          <div className="main-content-grid">
            {/* LEFT CARD: LIVE ANALYSIS PIPELINE */}
            <AnalysisPipeline customImage={uploadedImage} progress={analysisProgress} />

            {/* RIGHT CARD: GENERATED VARIATIONS & RULE SUMMARY */}
            <GeneratedVariations />
          </div>
        </div>
      </section>
    </main>
  )
}
