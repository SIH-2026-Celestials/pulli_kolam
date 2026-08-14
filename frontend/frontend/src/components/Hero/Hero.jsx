import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Upload, Landmark, Cpu, Network, Sparkles, HeartHandshake, Sparkle } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { validateImageFile } from '../../lib/validateImageFile'
import KolamHeroSvg from './KolamHeroSvg'
import KolamCornerDecoration from '../kolam/KolamCornerDecoration'
import KolamGridPattern from '../kolam/KolamGridPattern'
import './Hero.css'

export default function Hero() {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const closeButtonRef = useRef(null)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [uploadError, setUploadError] = useState(null)

  // Move focus into the modal on open and let Escape close it, so
  // keyboard/screen-reader users aren't left stranded behind the overlay.
  useEffect(() => {
    if (!uploadModalOpen) return
    closeButtonRef.current?.focus()
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setUploadModalOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [uploadModalOpen])

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  // Hands the file to the real /detect page instead of running a local
  // fake analysis -- this component has no backend of its own to call.
  const processFile = (file) => {
    if (!file) return
    const result = validateImageFile(file)
    if (!result.valid) {
      setUploadError(result.message)
      return
    }
    setUploadError(null)
    setUploadModalOpen(false)
    navigate('/detect', { state: { incomingFile: file } })
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      processFile(file)
    }
  }

  return (
    <section className="hero-clone-section">
      {/* Subtle Background Corner Decorative SVG Elements */}
      <KolamCornerDecoration position="top-left" />
      <KolamCornerDecoration position="top-right" />
      <KolamCornerDecoration position="bottom-left" />
      <KolamCornerDecoration position="bottom-right" />
      <KolamGridPattern opacity={0.03} />

      <div className="hero-container">
        {/* LEFT COLUMN: Typography & Actions */}
        <div className="hero-col-left">
          <h1 className="hero-main-title">
            <span>{t('hero.line1')}</span>
            <span>{t('hero.line2')}</span>
            <span className="title-accent">{t('hero.line3')}</span>
          </h1>

          <p className="hero-lead-text">
            {t('hero.lead')}
          </p>

          <div className="hero-btn-group">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="image/png, image/jpeg, image/webp"
              style={{ display: 'none' }}
            />
            <button
              className="btn-primary-maroon"
              onClick={() => {
                setUploadError(null)
                setUploadModalOpen(true)
              }}
            >
              <Upload size={16} />
              <span>{t('hero.primaryBtn')}</span>
            </button>

            <Link to="/explore" className="btn-secondary-outline">
              {t('hero.secondaryBtn')}
            </Link>
          </div>

          <span className="hero-file-hint">{t('hero.fileHint')}</span>
        </div>

        {/* CENTER COLUMN: Central Kolam Illustration */}
        <div className="hero-col-center">
          <KolamHeroSvg />
        </div>

        {/* RIGHT COLUMN: AI Meets Tradition Card */}
        <div className="hero-col-right">
          <div className="tradition-card">
            <KolamGridPattern opacity={0.03} />
            <div className="card-header-row">
              <div className="header-icon-box">
                <Sparkle size={18} fill="var(--color-gold)" color="var(--color-gold)" />
              </div>
              <h2 className="card-title">{t('aiCard.title')}</h2>
            </div>

            <p className="card-description">
              {t('aiCard.desc')}
            </p>

            <div className="tradition-features-list">
              <div className="feature-row">
                <Landmark size={18} className="row-icon" />
                <span>{t('aiCard.features.iks')}</span>
              </div>
              <div className="feature-row">
                <Cpu size={18} className="row-icon" />
                <span>{t('aiCard.features.mlcv')}</span>
              </div>
              <div className="feature-row">
                <Network size={18} className="row-icon" />
                <span>{t('aiCard.features.graph')}</span>
              </div>
              <div className="feature-row">
                <Sparkles size={18} className="row-icon" />
                <span>{t('aiCard.features.generative')}</span>
              </div>
              <div className="feature-row">
                <HeartHandshake size={18} className="row-icon" />
                <span>{t('aiCard.features.heritage')}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── DRAG & DROP FILE UPLOAD MODAL ── */}
      {uploadModalOpen && (
        <div className="upload-modal-overlay" onClick={() => setUploadModalOpen(false)}>
          <div
            className="upload-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              ref={closeButtonRef}
              className="upload-modal-close"
              onClick={() => setUploadModalOpen(false)}
              aria-label="Close upload dialog"
            >
              ✕
            </button>
            <h3 id="upload-modal-title" className="upload-modal-title">Upload your Kolam</h3>

            <div
              className={`upload-dropzone${dragActive ? ' drag-active' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
            >
              <Upload size={32} className="upload-dropzone-icon" />
              <p className="upload-dropzone-text">Drag & drop your image here</p>
              <span className="upload-dropzone-or">or</span>
              <button className="btn-primary-maroon upload-browse-btn" onClick={() => fileInputRef.current?.click()}>
                Browse files
              </button>
            </div>
            {uploadError && (
              <p className="upload-modal-error" role="alert">{uploadError}</p>
            )}
            <p className="upload-modal-hint">{t('hero.fileHint')}</p>
          </div>
        </div>
      )}
    </section>
  )
}
