import { describe, it, expect } from 'vitest'
import { TRANSLATIONS } from '../index'

function keyPaths(obj, prefix = '') {
  return Object.entries(obj).flatMap(([k, v]) => {
    const path = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) return keyPaths(v, path)
    return [path]
  })
}

describe('i18n translation parity', () => {
  const locales = Object.keys(TRANSLATIONS)
  const referenceKeys = keyPaths(TRANSLATIONS.en).sort()

  it('has more than one locale to compare', () => {
    expect(locales.length).toBeGreaterThan(1)
  })

  it.each(locales)('%s has the same key set as en (no missing/extra keys)', (locale) => {
    const keys = keyPaths(TRANSLATIONS[locale]).sort()
    expect(keys).toEqual(referenceKeys)
  })

  it.each(locales)('%s has no empty string values', (locale) => {
    const empties = keyPaths(TRANSLATIONS[locale]).filter((path) => {
      const value = path.split('.').reduce((o, k) => o?.[k], TRANSLATIONS[locale])
      return typeof value === 'string' && value.trim() === ''
    })
    expect(empties).toEqual([])
  })
})
