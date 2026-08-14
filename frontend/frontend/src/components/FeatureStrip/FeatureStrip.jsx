import { ScanSearch, Repeat, Sparkles, ShieldCheck, Landmark } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import './FeatureStrip.css'

export default function FeatureStrip() {
  const { t } = useLanguage()

  const features = [
    {
      icon: <ScanSearch size={22} className="strip-icon" />,
      title: t('features.aiAnalysis'),
      desc: t('features.aiAnalysisDesc')
    },
    {
      icon: <Repeat size={22} className="strip-icon" />,
      title: t('features.ruleBased'),
      desc: t('features.ruleBasedDesc')
    },
    {
      icon: <Sparkles size={22} className="strip-icon" />,
      title: t('features.uniqueRegen'),
      desc: t('features.uniqueRegenDesc')
    },
    {
      icon: <ShieldCheck size={22} className="strip-icon" />,
      title: t('features.authentic'),
      desc: t('features.authenticDesc')
    },
    {
      icon: <Landmark size={22} className="strip-icon" />,
      title: t('features.heritage'),
      desc: t('features.heritageDesc')
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
