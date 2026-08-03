/* eslint-disable react-refresh/only-export-components */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Language = 'en' | 'ru'

export type Translate = (key: string, params?: Record<string, string | number>) => string

const STORAGE_KEY = 'domain-analyzer-language'

const messages: Record<Language, Record<string, string>> = {
  en: {
    language: 'Language',
    english: 'English',
    russian: 'Русский',
    domainAnalyzer: 'Domain Analyzer',
    domainAnalysisForm: 'Domain analysis form',
    resultsStay: 'Results stay in your browser until you analyze another domain.',
    waitingWorker: 'Waiting for an analysis worker…',
    collectingSignals: 'Collecting public domain signals…',
    analysisCouldNotBeCompleted: 'Analysis could not be completed',
    rateLimitMessage: '{message} The rate limit will reset shortly.',
    serviceUnavailableMessage: '{message} Check that Redis and the analysis worker are running.',
    missingAnalysisResult: 'The analysis completed without a result.',
    workerFailed: 'The analysis worker failed to produce a result.',
    unexpectedFailure: 'The analysis failed unexpectedly.',
    tryAgain: 'Try again',
    domainName: 'Domain name',
    cancel: 'Cancel',
    analyzeDomain: 'Analyze domain',
    domainHelp: 'Enter a public domain. The backend validates the target and returns partial results when a provider is unavailable.',
    liveStatus: 'Live status',
    analysisProgress: 'Analysis progress',
    preparingChecks: 'Preparing checks…',
    workerPreparingQueue: 'The worker is preparing the analysis queue.',
    progressSummary: '{completed} of {total} checks complete{running}.',
    progressRunning: ', {count} running',
    check: 'Check',
    status: 'Status',
    queued: 'Queued',
    running: 'Running',
    successful: 'Successful',
    partial: 'Partial',
    failed: 'Failed',
    rdap: 'RDAP registration',
    dns: 'DNS records',
    dns_propagation: 'DNS propagation',
    geoip: 'GeoIP and ASN',
    http: 'HTTP and HTTPS',
    ssl: 'TLS certificate',
    ports: 'Port scan',
    latency: 'TCP latency',
    analysisReport: 'Analysis report',
    completeWithWarnings: 'Complete with {count} warning(s)',
    exportReport: 'Export report',
    json: 'JSON',
    markdown: 'Markdown',
    registrar: 'Registrar',
    rdapServer: 'RDAP server',
    nameservers: 'Nameservers',
    registered: 'Registered',
    expires: 'Expires',
    updated: 'Updated',
    analysisWarnings: 'Analysis warnings',
    someChecksUnavailable: 'Some checks were unavailable',
    emptyData: 'No data available.',
    noRecords: 'No records returned.',
    registration: 'Registration',
    registrationDescription: 'RDAP registration metadata.',
    dnsRecords: 'DNS records',
    dnsDescription: 'Authoritative records and public resolver propagation.',
    geoipAsn: 'GeoIP & ASN',
    geoipDescription: 'Location and network ownership for resolved addresses.',
    httpHttps: 'HTTP & HTTPS',
    httpDescription: 'Reachability, response timing, redirects, and selected headers.',
    tlsCertificate: 'TLS certificate',
    tlsDescription: 'Certificate validity and negotiated connection details.',
    portsLatency: 'Ports & latency',
    portsDescription: 'Common TCP service ports and connection timing.',
    primary: 'Primary',
    responsible: 'Responsible',
    serial: 'Serial',
    propagation: 'Propagation',
    recordsConsistent: 'Records are consistent',
    recordsInconsistent: 'Resolvers returned different records',
    resolver: 'Resolver',
    ipAddress: 'IP address',
    location: 'Location',
    organization: 'Organization',
    asn: 'ASN',
    reachable: 'Reachable',
    unavailable: 'Unavailable',
    response: 'Response',
    server: 'Server',
    contentType: 'Content type',
    finalUrl: 'Final URL',
    redirects: '{count} redirect(s)',
    certificateValid: 'Certificate is valid',
    certificateFailed: 'Certificate validation failed',
    protocol: 'Protocol',
    cipher: 'Cipher',
    subject: 'Subject',
    issuer: 'Issuer',
    validFrom: 'Valid from',
    validUntil: 'Valid until',
    daysRemaining: 'Days remaining',
    signature: 'Signature',
    subjectAlternativeNames: 'Subject alternative names',
    portScan: 'Port scan',
    port: 'Port',
    service: 'Service',
    min: 'Min',
    average: 'Average',
    max: 'Max',
    loss: 'Loss',
    freshnessSources: 'Freshness and sources',
    freshnessDescription: 'When each check completed, how long it took, and which public source was used.',
    completed: 'Completed',
    analysisDuration: 'Analysis duration',
    checksReported: 'Checks reported',
    checkSources: 'Check sources',
    duration: 'Duration',
    source: 'Source',
    securityReview: 'Heuristic review',
    securitySignals: 'Security signals',
    securityScore: 'Security signal score: {score}',
    notAssessed: 'Not assessed',
    securityNoteScored: 'This is a transparent signal check, not a complete security audit. The score uses {count} collected signal(s).',
    securityNoteUnavailable: 'This is a transparent signal check, not a complete security audit. The available data was not sufficient to calculate a score.',
    noActionableSignals: 'No actionable signals were found in the collected responses.',
    severityHigh: 'High',
    severityMedium: 'Medium',
    severityLow: 'Low',
    severityInfo: 'Info',
    'status.active': 'Active',
    'status.open': 'Open',
    'status.closed': 'Closed',
    'status.filtered': 'Filtered',
    'status.timeout': 'Timeout',
    'status.ok': 'OK',
    'status.error': 'Error',
    'status.successful': 'Successful',
    'status.partial': 'Partial',
    'status.failed': 'Failed',
    'status.queued': 'Queued',
    'status.running': 'Running',
    'finding.http-check-unavailable.title': 'HTTP security signals could not be assessed',
    'finding.http-check-unavailable.recommendation': 'Run the HTTP check again to inspect HTTPS reachability and response headers.',
    'finding.https-check-unavailable.title': 'HTTPS security signals could not be assessed',
    'finding.https-check-unavailable.recommendation': 'Run the HTTP check again to inspect HTTPS reachability and response headers.',
    'finding.https-unavailable.title': 'HTTPS is not reachable',
    'finding.https-unavailable.recommendation': 'Serve the domain over HTTPS with a valid certificate and keep HTTP only as a redirect or compatibility endpoint.',
    'finding.http-not-redirected.title': 'HTTP does not redirect to HTTPS',
    'finding.http-not-redirected.recommendation': 'Redirect HTTP requests to the canonical HTTPS URL to reduce accidental plaintext access.',
    'finding.tls-check-unavailable.title': 'TLS could not be assessed',
    'finding.tls-check-unavailable.recommendation': 'Run the TLS check again and verify that the target accepts connections on port 443.',
    'finding.tls-invalid.title': 'TLS certificate validation failed',
    'finding.tls-invalid.recommendation': 'Renew or correctly configure the certificate chain, hostname coverage, and expiration settings.',
    'finding.tls-expiring-soon.title': 'TLS certificate expires in {days} day(s)',
    'finding.tls-expiring-soon.recommendation': 'Renew the certificate before expiration and confirm that automated renewal is working.',
    'finding.missing-content_security_policy.title': 'Content-Security-Policy is missing',
    'finding.missing-content_security_policy.recommendation': 'Define a restrictive Content-Security-Policy and tune it against the application resources.',
    'finding.missing-strict_transport_security.title': 'Strict-Transport-Security is missing',
    'finding.missing-strict_transport_security.recommendation': 'Add HSTS on HTTPS responses after confirming that all covered hosts support HTTPS.',
    'finding.missing-x_frame_options.title': 'X-Frame-Options is missing',
    'finding.missing-x_frame_options.recommendation': 'Set a framing policy, preferably through Content-Security-Policy frame-ancestors.',
    'finding.missing-x_content_type_options.title': 'X-Content-Type-Options is missing',
    'finding.missing-x_content_type_options.recommendation': 'Send X-Content-Type-Options: nosniff for responses that contain user-controlled or executable content.',
    'finding.missing-referrer_policy.title': 'Referrer-Policy is missing',
    'finding.missing-referrer_policy.recommendation': 'Set an explicit Referrer-Policy such as strict-origin-when-cross-origin.',
    'finding.missing-permissions_policy.title': 'Permissions-Policy is missing',
    'finding.missing-permissions_policy.recommendation': 'Restrict browser features that the application does not need with Permissions-Policy.',
  },
  ru: {
    language: 'Язык',
    english: 'English',
    russian: 'Русский',
    domainAnalyzer: 'Анализатор доменов',
    domainAnalysisForm: 'Форма анализа домена',
    resultsStay: 'Результаты остаются в браузере, пока вы не начнёте анализ другого домена.',
    waitingWorker: 'Ожидание свободного worker…',
    collectingSignals: 'Сбор публичных данных о домене…',
    analysisCouldNotBeCompleted: 'Не удалось завершить анализ',
    rateLimitMessage: '{message} Лимит запросов скоро сбросится.',
    serviceUnavailableMessage: '{message} Проверьте, что Redis и worker анализа запущены.',
    missingAnalysisResult: 'Анализ завершился без результата.',
    workerFailed: 'Worker анализа не смог сформировать результат.',
    unexpectedFailure: 'Произошла непредвиденная ошибка анализа.',
    tryAgain: 'Повторить',
    domainName: 'Имя домена',
    cancel: 'Отменить',
    analyzeDomain: 'Анализировать домен',
    domainHelp: 'Введите публичный домен. Backend проверит цель и вернёт частичный результат, если провайдер недоступен.',
    liveStatus: 'Текущий статус',
    analysisProgress: 'Прогресс анализа',
    preparingChecks: 'Подготовка проверок…',
    workerPreparingQueue: 'Worker подготавливает очередь анализа.',
    progressSummary: 'Завершено проверок: {completed} из {total}{running}.',
    progressRunning: ', выполняется: {count}',
    check: 'Проверка',
    status: 'Статус',
    queued: 'В очереди',
    running: 'Выполняется',
    successful: 'Успешно',
    partial: 'Частично',
    failed: 'Ошибка',
    rdap: 'Регистрация RDAP',
    dns: 'DNS-записи',
    dns_propagation: 'Распространение DNS',
    geoip: 'GeoIP и ASN',
    http: 'HTTP и HTTPS',
    ssl: 'TLS-сертификат',
    ports: 'Сканирование портов',
    latency: 'Задержка TCP',
    analysisReport: 'Отчёт анализа',
    completeWithWarnings: 'Завершено с предупреждениями: {count}',
    exportReport: 'Экспортировать отчёт',
    json: 'JSON',
    markdown: 'Markdown',
    registrar: 'Регистратор',
    rdapServer: 'RDAP-сервер',
    nameservers: 'Серверы имён',
    registered: 'Зарегистрирован',
    expires: 'Истекает',
    updated: 'Обновлён',
    analysisWarnings: 'Предупреждения анализа',
    someChecksUnavailable: 'Некоторые проверки недоступны',
    emptyData: 'Данные отсутствуют.',
    noRecords: 'Записи не получены.',
    registration: 'Регистрация',
    registrationDescription: 'Метаданные регистрации RDAP.',
    dnsRecords: 'DNS-записи',
    dnsDescription: 'Авторитетные записи и распространение через публичные резолверы.',
    geoipAsn: 'GeoIP и ASN',
    geoipDescription: 'Расположение и владелец сети для найденных адресов.',
    httpHttps: 'HTTP и HTTPS',
    httpDescription: 'Доступность, время ответа, перенаправления и выбранные заголовки.',
    tlsCertificate: 'TLS-сертификат',
    tlsDescription: 'Валидность сертификата и параметры соединения.',
    portsLatency: 'Порты и задержка',
    portsDescription: 'Распространённые TCP-порты и время соединения.',
    primary: 'Основной сервер',
    responsible: 'Ответственный',
    serial: 'Серийный номер',
    propagation: 'Распространение',
    recordsConsistent: 'Записи совпадают',
    recordsInconsistent: 'Резолверы вернули разные записи',
    resolver: 'Резолвер',
    ipAddress: 'IP-адрес',
    location: 'Расположение',
    organization: 'Организация',
    asn: 'ASN',
    reachable: 'Доступен',
    unavailable: 'Недоступен',
    response: 'Ответ',
    server: 'Сервер',
    contentType: 'Тип содержимого',
    finalUrl: 'Итоговый URL',
    redirects: 'Перенаправлений: {count}',
    certificateValid: 'Сертификат действителен',
    certificateFailed: 'Проверка сертификата не пройдена',
    protocol: 'Протокол',
    cipher: 'Шифр',
    subject: 'Субъект',
    issuer: 'Издатель',
    validFrom: 'Действителен с',
    validUntil: 'Действителен до',
    daysRemaining: 'Осталось дней',
    signature: 'Подпись',
    subjectAlternativeNames: 'Альтернативные имена субъекта',
    portScan: 'Сканирование портов',
    port: 'Порт',
    service: 'Сервис',
    min: 'Минимум',
    average: 'Среднее',
    max: 'Максимум',
    loss: 'Потери',
    freshnessSources: 'Актуальность и источники',
    freshnessDescription: 'Когда завершилась каждая проверка, сколько она заняла и какой публичный источник использовался.',
    completed: 'Завершено',
    analysisDuration: 'Длительность анализа',
    checksReported: 'Проверок в отчёте',
    checkSources: 'Источники проверок',
    duration: 'Длительность',
    source: 'Источник',
    securityReview: 'Эвристическая проверка',
    securitySignals: 'Сигналы безопасности',
    securityScore: 'Оценка сигналов безопасности: {score}',
    notAssessed: 'Не оценено',
    securityNoteScored: 'Это прозрачная проверка сигналов, а не полный аудит безопасности. Оценка использует сигналов: {count}.',
    securityNoteUnavailable: 'Это прозрачная проверка сигналов, а не полный аудит безопасности. Данных недостаточно для расчёта оценки.',
    noActionableSignals: 'В полученных ответах не найдено сигналов, требующих действий.',
    severityHigh: 'Высокий',
    severityMedium: 'Средний',
    severityLow: 'Низкий',
    severityInfo: 'Информация',
    'status.active': 'Активен',
    'status.open': 'Открыт',
    'status.closed': 'Закрыт',
    'status.filtered': 'Отфильтрован',
    'status.timeout': 'Таймаут',
    'status.ok': 'OK',
    'status.error': 'Ошибка',
    'status.successful': 'Успешно',
    'status.partial': 'Частично',
    'status.failed': 'Ошибка',
    'status.queued': 'В очереди',
    'status.running': 'Выполняется',
    'finding.http-check-unavailable.title': 'Сигналы безопасности HTTP не удалось оценить',
    'finding.http-check-unavailable.recommendation': 'Запустите проверку HTTP ещё раз, чтобы проверить HTTPS и заголовки ответа.',
    'finding.https-check-unavailable.title': 'Сигналы безопасности HTTPS не удалось оценить',
    'finding.https-check-unavailable.recommendation': 'Запустите проверку HTTP ещё раз, чтобы проверить HTTPS и заголовки ответа.',
    'finding.https-unavailable.title': 'HTTPS недоступен',
    'finding.https-unavailable.recommendation': 'Настройте домен на HTTPS с действительным сертификатом, а HTTP оставьте для перенаправления.',
    'finding.http-not-redirected.title': 'HTTP не перенаправляет на HTTPS',
    'finding.http-not-redirected.recommendation': 'Перенаправляйте HTTP-запросы на основной HTTPS-адрес, чтобы исключить случайный доступ без шифрования.',
    'finding.tls-check-unavailable.title': 'TLS не удалось оценить',
    'finding.tls-check-unavailable.recommendation': 'Запустите проверку TLS ещё раз и убедитесь, что цель принимает соединения на порту 443.',
    'finding.tls-invalid.title': 'Проверка TLS-сертификата не пройдена',
    'finding.tls-invalid.recommendation': 'Обновите или корректно настройте цепочку сертификатов, имена хостов и срок действия.',
    'finding.tls-expiring-soon.title': 'Срок TLS-сертификата истекает через {days} дн.',
    'finding.tls-expiring-soon.recommendation': 'Обновите сертификат до истечения срока и проверьте автоматическое продление.',
    'finding.missing-content_security_policy.title': 'Отсутствует Content-Security-Policy',
    'finding.missing-content_security_policy.recommendation': 'Определите строгую Content-Security-Policy и настройте её под ресурсы приложения.',
    'finding.missing-strict_transport_security.title': 'Отсутствует Strict-Transport-Security',
    'finding.missing-strict_transport_security.recommendation': 'Добавьте HSTS в HTTPS-ответы после проверки поддержки HTTPS всеми охваченными хостами.',
    'finding.missing-x_frame_options.title': 'Отсутствует X-Frame-Options',
    'finding.missing-x_frame_options.recommendation': 'Задайте политику встраивания, предпочтительно через frame-ancestors в Content-Security-Policy.',
    'finding.missing-x_content_type_options.title': 'Отсутствует X-Content-Type-Options',
    'finding.missing-x_content_type_options.recommendation': 'Отправляйте X-Content-Type-Options: nosniff для ответов с пользовательским или исполняемым содержимым.',
    'finding.missing-referrer_policy.title': 'Отсутствует Referrer-Policy',
    'finding.missing-referrer_policy.recommendation': 'Задайте явную Referrer-Policy, например strict-origin-when-cross-origin.',
    'finding.missing-permissions_policy.title': 'Отсутствует Permissions-Policy',
    'finding.missing-permissions_policy.recommendation': 'Ограничьте браузерные возможности, которые приложению не нужны, через Permissions-Policy.',
  },
}

function isLanguage(value: string | null): value is Language {
  return value === 'en' || value === 'ru'
}

export function detectBrowserLanguage(languages: readonly string[]): Language {
  const supportedLanguage = languages.find((language) => {
    const normalizedLanguage = language.toLowerCase()
    return normalizedLanguage.startsWith('ru') || normalizedLanguage.startsWith('en')
  })

  return supportedLanguage?.toLowerCase().startsWith('ru') ? 'ru' : 'en'
}

function readStoredLanguage(): Language | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const storedLanguage = window.localStorage.getItem(STORAGE_KEY)
    return isLanguage(storedLanguage) ? storedLanguage : null
  } catch {
    return null
  }
}

function initialLanguage(): Language {
  const storedLanguage = readStoredLanguage()
  if (storedLanguage) {
    return storedLanguage
  }

  if (typeof navigator === 'undefined') {
    return 'en'
  }

  const browserLanguages = navigator.languages?.length ? navigator.languages : [navigator.language]
  return detectBrowserLanguage(browserLanguages)
}

function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) {
    return template
  }

  return template.replace(/\{(\w+)\}/g, (match, key: string) => {
    const value = params[key]
    return value === undefined ? match : String(value)
  })
}

function createTranslator(language: Language): Translate {
  return (key, params) => interpolate(messages[language][key] ?? messages.en[key] ?? key, params)
}

interface I18nContextValue {
  language: Language
  locale: string
  setLanguage: (language: Language) => void
  t: Translate
}

const defaultContext: I18nContextValue = {
  language: 'en',
  locale: 'en-US',
  setLanguage: () => undefined,
  t: createTranslator('en'),
}

const I18nContext = createContext<I18nContextValue>(defaultContext)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(initialLanguage)
  const locale = language === 'ru' ? 'ru-RU' : 'en-US'
  const t = useMemo(() => createTranslator(language), [language])

  useEffect(() => {
    document.documentElement.lang = language
    document.title = t('domainAnalyzer')

    try {
      window.localStorage.setItem(STORAGE_KEY, language)
    } catch {
      // Ignore storage restrictions and keep the in-memory language selection.
    }
  }, [language, t])

  const value = useMemo(() => ({ language, locale, setLanguage, t }), [language, locale, t])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  return useContext(I18nContext)
}
