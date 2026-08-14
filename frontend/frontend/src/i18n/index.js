import en from './translations/en'
import hi from './translations/hi'
import ta from './translations/ta'
import te from './translations/te'
import kn from './translations/kn'
import ml from './translations/ml'

export const TRANSLATIONS = { en, hi, ta, te, kn, ml }

export const LANGUAGES = [
  { code: 'en', label: 'English',    nativeName: 'English',    script: 'A' },
  { code: 'ta', label: 'Tamil',      nativeName: 'தமிழ்(Tamil)',      script: 'த' },
  { code: 'hi', label: 'Hindi',      nativeName: 'हिन्दी(Hindi)',     script: 'ह' },
  { code: 'te', label: 'Telugu',     nativeName: 'తెలుగు(Telugu)',    script: 'తె' },
  { code: 'kn', label: 'Kannada',    nativeName: 'ಕನ್ನಡ(Kannada)',    script: 'ಕ' },
  { code: 'ml', label: 'Malayalam',  nativeName: 'മലയാളം(Malayalam)',  script: 'മ' },
]

export const ALL_LANGUAGES = [
  ...LANGUAGES,
  { code: 'bn', label: 'Bengali',    nativeName: 'বাংলা',     script: 'ব' },
  { code: 'gu', label: 'Gujarati',   nativeName: 'ગુજરાતી',  script: 'ગ' },
  { code: 'mr', label: 'Marathi',    nativeName: 'मराठी',      script: 'म' },
  { code: 'pa', label: 'Punjabi',    nativeName: 'ਪੰਜਾਬੀ',  script: 'ਪ' },
  { code: 'ur', label: 'Urdu',       nativeName: 'اردو',       script: 'ا' },
  { code: 'or', label: 'Odia',       nativeName: 'ଓଡ଼ିଆ',     script: 'ଓ' },
  { code: 'as', label: 'Assamese',   nativeName: 'অসমীয়া',   script: 'অ' },
]

const STORAGE_KEY = 'pulli-language'

export function getSavedLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && TRANSLATIONS[saved]) return saved
  } catch {
    // ignore
  }
  return 'en'
}

export function saveLanguage(code) {
  try {
    localStorage.setItem(STORAGE_KEY, code)
  } catch {
    // ignore
  }
}

/**
 * Resolve a dot-path key like "nav.home" from a translations object,
 * optionally interpolating {placeholder} tokens from `vars`.
 */
export function resolve(translations, key, vars) {
  const value = key.split('.').reduce((obj, k) => (obj ? obj[k] : undefined), translations) ?? key
  if (!vars || typeof value !== 'string') return value
  return value.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? vars[name] : match))
}
