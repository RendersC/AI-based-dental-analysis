import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import api from '../api/axios'
import { loadMetrika, metrikaHit, isMetrikaLoaded } from '../utils/metrika'

// Решение хранится в localStorage: 'accepted' | 'rejected'.
// Аналитика поднимается только при 'accepted'. Должен рендериться внутри Router —
// использует useLocation для подсчёта переходов в SPA.
const STORAGE_KEY = 'cookie_consent'

export default function CookieConsent() {
  const [decision, setDecision] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) } catch { return null }
  })
  const location = useLocation()
  const initialHitDone = useRef(false)

  // Поднять Метрику, если согласие уже дано (в т.ч. при возврате на сайт).
  useEffect(() => {
    if (decision !== 'accepted' || isMetrikaLoaded()) return
    api.get('/settings/')
      .then(({ data }) => {
        if (data?.yandex_metrika_id) {
          loadMetrika(data.yandex_metrika_id)
          initialHitDone.current = true // init сам считает первый просмотр
        }
      })
      .catch(() => {})
  }, [decision])

  // SPA: считать переход при смене маршрута (первый просмотр уже посчитан init'ом).
  useEffect(() => {
    if (!isMetrikaLoaded()) return
    if (!initialHitDone.current) { initialHitDone.current = true; return }
    metrikaHit(location.pathname + location.search)
  }, [location])

  const choose = (value) => {
    try { localStorage.setItem(STORAGE_KEY, value) } catch { /* приватный режим */ }
    setDecision(value)
  }

  if (decision) return null

  return (
    <div
      role="dialog"
      aria-label="Согласие на использование файлов cookie"
      className="fixed inset-x-0 bottom-0 z-50 px-3 pb-3 sm:px-4 sm:pb-4 pointer-events-none"
    >
      <div
        className="mx-auto max-w-2xl rounded-xl bg-white p-4 sm:p-5 pointer-events-auto"
        style={{ border: '1px solid #E2E8F0', boxShadow: '0 8px 30px rgba(0,0,0,0.12)' }}
      >
        <div className="flex items-start gap-3">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-lg"
            style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}
          >
            🍪
          </div>
          <div className="flex-1 min-w-0">
            <p
              className="text-sm font-semibold text-on-surface"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}
            >
              Мы используем файлы cookie
            </p>
            <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
              Cookie нужны для работы сервиса и, с вашего согласия, для аналитики
              посещаемости (Яндекс.Метрика). Подробнее — в{' '}
              <a
                href="/docs/cookie-policy.html"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: '#00548d', textDecoration: 'underline' }}
              >
                Политике использования cookie
              </a>
              .
            </p>
            <div className="flex flex-col sm:flex-row gap-2 mt-3">
              <button
                onClick={() => choose('accepted')}
                className="py-2.5 px-4 rounded text-sm font-medium text-white transition-all duration-150"
                style={{ background: '#00548d', fontFamily: "'Geist', 'Inter', system-ui" }}
              >
                Принять все
              </button>
              <button
                onClick={() => choose('rejected')}
                className="ds-btn-ghost py-2.5 px-4 text-sm"
              >
                Только необходимые
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
