// Яндекс.Метрика. Загружается ТОЛЬКО после согласия пользователя на cookie —
// никакого статического сниппета в index.html, чтобы счётчик не стартовал до согласия.
// ID счётчика приходит из публичных настроек (admin-редактируемый), поэтому
// инициализация динамическая: клиент может сменить номер без пересборки фронта.

let loadedId = null

export function isMetrikaLoaded() {
  return loadedId !== null
}

// Вставляет официальный tag.js и инициализирует счётчик.
// webvisor НАМЕРЕННО выключен: сервис медицинский, на экранах фото зубов и
// данные пациента — запись сессий могла бы фиксировать ПД (152-ФЗ).
export function loadMetrika(id) {
  if (!id || loadedId !== null || typeof window === 'undefined') return
  const numId = Number(id)
  if (!numId) return
  loadedId = numId

  ;(function (m, e, t, r, i) {
    m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments) }
    m[i].l = 1 * new Date()
    const k = e.createElement(t)
    const a = e.getElementsByTagName(t)[0]
    k.async = 1
    k.src = r
    a.parentNode.insertBefore(k, a)
  })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js', 'ym')

  window.ym(numId, 'init', {
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    webvisor: false,
  })
}

// Засчитать переход в SPA при смене маршрута (первый просмотр init считает сам).
export function metrikaHit(url) {
  if (loadedId !== null && typeof window !== 'undefined' && window.ym) {
    window.ym(loadedId, 'hit', url)
  }
}
