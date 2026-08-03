import { useEffect, useState } from 'react'
import api from '../api/axios'

/**
 * Небольшая карточка-приглашение пройти анкету. Плавно выезжает из правого
 * нижнего угла (не модалка по центру — чтобы не быть навязчивой).
 * Показывается на странице результата раз в 3 анализа тем, кто ещё не проходил.
 *
 * props:
 *  - url: ссылка на Яндекс.Форму
 *  - onClose: вызвать чтобы убрать карточку (и «Пройти», и «Закрыть»)
 */
export default function SurveyPrompt({ url, onClose }) {
  const [shown, setShown] = useState(false)
  const [leaving, setLeaving] = useState(false)

  // Выезд после монтирования.
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(true))
    return () => cancelAnimationFrame(id)
  }, [])

  const close = () => {
    setLeaving(true)
    setTimeout(onClose, 250) // дождаться анимации ухода
  }

  const handleTake = () => {
    // Помечаем анкету как пройденную, чтобы больше не предлагать (до сброса версии).
    // Ошибку глушим — даже если запрос не прошёл, не мешаем пользователю открыть форму.
    api.post('/auth/survey/complete/').catch(() => {})
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
    close()
  }

  const visible = shown && !leaving

  return (
    <div
      role="dialog"
      aria-label="Приглашение пройти анкету"
      className="fixed z-50"
      style={{
        right: 16,
        bottom: 16,
        maxWidth: 'calc(100vw - 32px)',
        width: 320,
        transform: visible ? 'translateY(0)' : 'translateY(140%)',
        opacity: visible ? 1 : 0,
        transition: 'transform 0.35s cubic-bezier(0.16,1,0.3,1), opacity 0.35s ease',
      }}
    >
      <div className="ds-card" style={{ boxShadow: '0 12px 32px rgba(11,61,107,0.22)' }}>
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-lg"
            style={{ background: '#f4f8fb', border: '1px solid #E2E8F0' }}>
            💬
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-on-surface"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              Помогите нам стать лучше!
            </p>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Пройдите короткую анкету.
            </p>
          </div>
          <button onClick={close} aria-label="Закрыть"
            className="flex-shrink-0 text-on-surface-variant hover:text-on-surface transition-colors"
            style={{ fontSize: 18, lineHeight: 1, marginTop: -2 }}>
            ✕
          </button>
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={handleTake} className="ds-btn-primary flex-1 py-2 text-sm">
            Пройти
          </button>
          <button onClick={close} className="ds-btn-ghost flex-1 py-2 text-sm"
            style={{ border: '1px solid #E2E8F0' }}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  )
}
