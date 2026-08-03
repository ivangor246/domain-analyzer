export type Language = 'en' | 'ru'

export type Translate = (key: string, params?: Record<string, string | number>) => string

export function detectBrowserLanguage(languages: readonly string[]): Language {
  const supportedLanguage = languages.find((language) => {
    const normalizedLanguage = language.toLowerCase()
    return normalizedLanguage.startsWith('ru') || normalizedLanguage.startsWith('en')
  })

  return supportedLanguage?.toLowerCase().startsWith('ru') ? 'ru' : 'en'
}
