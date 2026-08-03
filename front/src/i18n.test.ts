import { describe, expect, it } from 'vitest'

import { detectBrowserLanguage } from './i18n'

describe('detectBrowserLanguage', () => {
  it('selects the first supported browser language', () => {
    expect(detectBrowserLanguage(['de-DE', 'ru-RU', 'en-US'])).toBe('ru')
    expect(detectBrowserLanguage(['en-US', 'ru-RU'])).toBe('en')
  })

  it('falls back to English for unsupported languages', () => {
    expect(detectBrowserLanguage(['de-DE', 'fr-FR'])).toBe('en')
  })

  it('falls back to English when the browser has no language preference', () => {
    expect(detectBrowserLanguage([])).toBe('en')
  })
})
