import { useEffect, useState } from 'react'

/**
 * Фото анализа с презентабельным поведением при загрузке и сбоях.
 *
 * Клиент сообщил: фото в результате анализа отображаются «через раз» — то есть,
 * то нет. Сервер (MinIO/RU-nginx) на своей стороне ошибок не отдаёт, значит дело
 * в браузере: обычный <img> без зарезервированной высоты схлопывается в 0px, пока
 * грузится presigned-ссылка на РФ-сервер, и остаётся пустым молча при сетевом сбое
 * (мобильная сеть, разрыв на секунду). Со стороны это выглядит как «фото пропало».
 *
 * Решение: резервируем место рамкой-плейсхолдером на время загрузки, чтобы карточка
 * никогда не выглядела пустой, и до 2 раз тихо повторяем запрос при ошибке —
 * presigned-подпись живёт 7 дней, повтор той же ссылки безопасен и почти всегда
 * чинит одиночный сетевой сбой. Если не помогло — понятная кнопка «Повторить»
 * вместо молчаливой пустоты.
 */
export default function PhotoImage({ src, alt, className, style, wrapperClassName }) {
  const [status, setStatus] = useState('loading') // loading | loaded | error
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    setStatus('loading')
    setAttempt(0)
  }, [src])

  const handleError = () => {
    if (attempt < 2) {
      setTimeout(() => setAttempt((n) => n + 1), 800)
    } else {
      setStatus('error')
    }
  }

  return (
    <div
      className={wrapperClassName}
      style={{
        position: 'relative',
        background: '#f2f4f6',
        borderRadius: 6,
        overflow: 'hidden',
        minHeight: status === 'loaded' ? undefined : 140,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        ...style,
      }}
    >
      {status !== 'error' && (
        <img
          key={attempt}
          src={src}
          alt={alt}
          onLoad={() => setStatus('loaded')}
          onError={handleError}
          className={className}
          style={{ display: status === 'loaded' ? 'block' : 'none', width: '100%' }}
        />
      )}
      {status === 'loading' && (
        <svg className="ds-spinner w-6 h-6 text-primary" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {status === 'error' && (
        <button
          type="button"
          onClick={() => { setStatus('loading'); setAttempt((n) => n + 1) }}
          className="text-xs font-medium px-3 py-1.5 rounded"
          style={{ color: '#00548d', background: '#fff', border: '1px solid #E2E8F0' }}
        >
          Фото не загрузилось. Повторить
        </button>
      )}
    </div>
  )
}
