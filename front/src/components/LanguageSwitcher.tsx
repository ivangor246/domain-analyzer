import { useI18n } from '../i18n-context'

function LanguageSwitcher() {
  const { language, setLanguage, t } = useI18n()

  const handleChange = (value: string) => {
    if (value === 'en' || value === 'ru') {
      setLanguage(value)
    }
  }

  return (
    <div className="language-switcher">
      <label htmlFor="language-select">{t('language')}</label>
      <select
        id="language-select"
        value={language}
        onChange={(event) => handleChange(event.target.value)}
      >
        <option value="en">{t('english')}</option>
        <option value="ru">{t('russian')}</option>
      </select>
    </div>
  )
}

export default LanguageSwitcher
