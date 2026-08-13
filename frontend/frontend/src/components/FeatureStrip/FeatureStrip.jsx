import { ScanSearch, Repeat, Sparkles, ShieldCheck, Landmark } from 'lucide-react'
import './FeatureStrip.css'

export default function FeatureStrip() {
  const features = [
    {
      icon: <ScanSearch size={22} className="strip-icon" />,
      title: 'AI Powered Analysis',
      desc: 'Detects dots, symmetry, motifs and stroke structure.'
    },
    {
      icon: <Repeat size={22} className="strip-icon" />,
      title: 'Rule Based Understanding',
      desc: 'Extracts the mathematical rules behind the kolam.'
    },
    {
      icon: <Sparkles size={22} className="strip-icon" />,
      title: 'Unique Regeneration',
      desc: 'Generates new, never-seen-before kolams using learned rules.'
    },
    {
      icon: <ShieldCheck size={22} className="strip-icon" />,
      title: 'Authentic & Valid',
      desc: 'Ensures single-stroke validity through Eulerian verification.'
    },
    {
      icon: <Landmark size={22} className="strip-icon" />,
      title: 'Preserve Heritage',
      desc: "Technology for the protection of India's rich cultural art."
    }
  ]

  return (
    <section className="feature-strip-section">
      <div className="feature-strip-container">
        <div className="feature-strip-card">
          {features.map((item, index) => (
            <div key={index} className="strip-item">
              <div className="strip-icon-wrapper">{item.icon}</div>
              <div className="strip-text-box">
                <h3 className="strip-item-title">{item.title}</h3>
                <p className="strip-item-desc">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
