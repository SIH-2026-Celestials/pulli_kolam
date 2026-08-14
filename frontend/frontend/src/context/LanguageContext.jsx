import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { TRANSLATIONS, getSavedLanguage, saveLanguage, resolve } from '../i18n/index'

const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(getSavedLanguage)

  // Keep the document's lang attribute in sync so screen readers and
  // search engines get the correct language signal for the active locale.
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLanguage = useCallback((code) => {
    if (TRANSLATIONS[code]) {
      setLang(code)
      saveLanguage(code)
    }
  }, [])

  /** t('nav.home') → translated string. t('a.b', { n: 5 }) interpolates {n}. */
  const t = useCallback(
    (key, vars) => resolve(TRANSLATIONS[lang], key, vars),
    [lang]
  )

  return (
    <LanguageContext.Provider value={{ lang, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used inside <LanguageProvider>')
  return ctx
}
