import { useState, useMemo } from 'react'
import KolamCard from '../../components/KolamCard/KolamCard'
import { useLanguage } from '../../context/LanguageContext'
import { kolam19 } from '../../data/kolams'
import './Explore.css'

const ITEMS_PER_PAGE = 36

export default function Explore() {
  const { t } = useLanguage()
  const [search, setSearch] = useState('')
  const [visibleCount, setVisibleCount] = useState(ITEMS_PER_PAGE)

  const filteredKolams = useMemo(() => {
    if (!search.trim()) return kolam19
    const query = search.trim().toLowerCase()
    return kolam19.filter(k => 
      k.id.toString().includes(query) || 
      `kolam ${k.id}`.includes(query) ||
      `kolam19-${k.id-1}`.includes(query)
    )
  }, [search])

  const visibleKolams = useMemo(() => {
    return filteredKolams.slice(0, visibleCount)
  }, [filteredKolams, visibleCount])

  const handleLoadMore = () => {
    setVisibleCount(prev => prev + ITEMS_PER_PAGE)
  }

  return (
    <main id="main-content" className="explore-page">
      <header className="explore-header section">
        <div className="container--narrow">
          <p className="eyebrow">{t('pages.gallery.eyebrow')}</p>
          <h1 className="heading-display heading-2 explore-title">
            {t('pages.gallery.title')}
          </h1>
          <p className="body-text explore-sub">
            {t('pages.gallery.sub')}
          </p>

          {/* Search / Filter bar */}
          <div className="explore-toolbar">
            <div className="explore-search-wrap">
              <span className="explore-search-icon" aria-hidden="true">🔍</span>
              <input
                type="text"
                className="explore-search-input"
                placeholder={t('pages.gallery.searchPlaceholder')}
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setVisibleCount(ITEMS_PER_PAGE)
                }}
                aria-label="Filter Kolam patterns by number"
              />
              {search && (
                <button
                  className="explore-search-clear"
                  onClick={() => {
                    setSearch('')
                    setVisibleCount(ITEMS_PER_PAGE)
                  }}
                  aria-label="Clear filter"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="explore-meta label-tech">
              {t('pages.gallery.showing', { shown: visibleKolams.length, total: filteredKolams.length })}
            </div>
          </div>
        </div>
      </header>

      {/* Grid gallery */}
      <section className="explore-gallery-section container--narrow">
        {filteredKolams.length === 0 ? (
          <div className="explore-empty">
            <p className="heading-display heading-4">{t('pages.gallery.noMatch')}</p>
            <p className="body-text">{t('pages.gallery.tryNumber')}</p>
          </div>
        ) : (
          <>
            <div className="explore-grid">
              {visibleKolams.map(kolam => (
                <KolamCard key={kolam.id} kolam={kolam} />
              ))}
            </div>

            {visibleCount < filteredKolams.length && (
              <div className="explore-load-more">
                <button
                  onClick={handleLoadMore}
                  className="btn btn--outline"
                >
                  {t('pages.gallery.loadMore', { remaining: filteredKolams.length - visibleCount })}
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  )
}
