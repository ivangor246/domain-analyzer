import { createContext, useContext } from 'react'

import type { Language, Translate } from './i18n-utils'

export interface I18nContextValue {
  language: Language
  locale: string
  setLanguage: (language: Language) => void
  t: Translate
}

export const I18nContext = createContext<I18nContextValue | null>(null)

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)

  if (!context) {
    throw new Error('useI18n must be used within a LanguageProvider')
  }

  return context
}
