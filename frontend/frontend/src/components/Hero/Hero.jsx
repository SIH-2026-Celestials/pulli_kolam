import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { Upload, Landmark, Cpu, Network, Sparkles, HeartHandshake, Sparkle } from 'lucide-react'
import KolamHeroSvg from './KolamHeroSvg'
import './Hero.css'

export default function Hero({ onUploadImage }) {
  const fileInputRef = useRef(null)

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file && onUploadImage) {
      const reader = new FileReader()
      reader.onload = (event) => {
        onUploadImage(event.target.result)
      }
      reader.readAsDataURL(file)
    }
  }

  return (
    <section className="hero-clone-section">
      {/* Subtle Background Corner Decorative SVG Elements */}
      <div className="bg-decor bg-decor-tl">
        <svg width="180" height="180" viewBox="0 0 200 200" fill="none" opacity="0.15">
          <circle cx="100" cy="100" r="80" stroke="#B88735" strokeWidth="1" strokeDasharray="4 8" />
          <path d="M 20 100 Q 100 20 180 100 Q 100 180 20 100 Z" stroke="#B88735" strokeWidth="1" />
        </svg>
      </div>
      <div className="bg-decor bg-decor-tr">
        <svg width="180" height="180" viewBox="0 0 200 200" fill="none" opacity="0.15">
          <circle cx="100" cy="100" r="80" stroke="#B88735" strokeWidth="1" strokeDasharray="4 8" />
          <path d="M 100 20 Q 180 100 100 180 Q 20 100 100 20 Z" stroke="#B88735" strokeWidth="1" />
        </svg>
      </div>

      <div className="hero-container">
        {/* LEFT COLUMN: Typography & Actions */}
        <div className="hero-col-left">
          <h1 className="hero-main-title">
            <span>Understand the pattern.</span>
            <span>Preserve the rule.</span>
            <span className="title-accent">Create something new.</span>
          </h1>

          <p className="hero-lead-text">
            Upload a kolam image and our ML model identifies the design principles behind it and regenerates unique, valid kolam designs.
          </p>

          <div className="hero-btn-group">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="image/png, image/jpeg, image/webp"
              style={{ display: 'none' }}
            />
            <button className="btn-primary-maroon" onClick={() => fileInputRef.current?.click()}>
              <Upload size={16} />
              <span>Analyze a Kolam</span>
            </button>

            <Link to="/explore" className="btn-secondary-outline">
              Explore Gallery
            </Link>
          </div>

          <span className="hero-file-hint">PNG, JPG up to 10MB</span>
        </div>

        {/* CENTER COLUMN: Central Kolam Illustration */}
        <div className="hero-col-center">
          <KolamHeroSvg />
        </div>

        {/* RIGHT COLUMN: AI Meets Tradition Card */}
        <div className="hero-col-right">
          <div className="tradition-card">
            <div className="card-header-row">
              <div className="header-icon-box">
                <Sparkle size={18} fill="#B88735" color="#B88735" />
              </div>
              <h2 className="card-title">AI meets tradition</h2>
            </div>

            <p className="card-description">
              PULLLI combines computer vision, graph theory and machine learning to understand the grammar of traditional kolams and generate new ones that follow the same rules.
            </p>

            <div className="tradition-features-list">
              <div className="feature-row">
                <Landmark size={18} className="row-icon" />
                <span>Indian Knowledge Systems</span>
              </div>
              <div className="feature-row">
                <Cpu size={18} className="row-icon" />
                <span>Advanced ML &amp; Computer Vision</span>
              </div>
              <div className="feature-row">
                <Network size={18} className="row-icon" />
                <span>Graph Theory &amp; Mathematics</span>
              </div>
              <div className="feature-row">
                <Sparkles size={18} className="row-icon" />
                <span>Generative Design</span>
              </div>
              <div className="feature-row">
                <HeartHandshake size={18} className="row-icon" />
                <span>Heritage Preservation</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
