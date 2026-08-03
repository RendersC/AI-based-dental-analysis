import { useEffect, useState } from 'react'

// Сменяющиеся фразы на этапе ожидания ответа ИИ, чтобы было видно что процесс идёт.
export const ANALYZE_TEXTS = [
  'Смотрим фото…',
  'Оцениваем налёт…',
  'Сравниваем с прошлыми анализами…',
  'Готовим рекомендации…',
  'Почти готово…',
]

// Экспресс-оценка не смотрит историю и ничего не измеряет — свои формулировки,
// чтобы не обещать пользователю того, чего в этом режиме не происходит.
export const EXPRESS_TEXTS = [
  'Смотрим фото…',
  'Оцениваем состояние зубов и дёсен…',
  'Готовим рекомендации…',
  'Почти готово…',
]

export default function AnalysisProgress({ progress, texts = ANALYZE_TEXTS }) {
  const [textIdx, setTextIdx] = useState(0)

  useEffect(() => {
    if (progress.stage !== 'analyze') {
      setTextIdx(0)
      return
    }
    const id = setInterval(() => {
      setTextIdx((i) => Math.min(i + 1, texts.length - 1))
    }, 6000)
    return () => clearInterval(id)
  }, [progress.stage, texts])

  let label
  let barPercent
  if (progress.stage === 'compress') {
    label = 'Подготавливаем фото…'
    barPercent = 5
  } else if (progress.stage === 'upload') {
    label = `Загружаем фото… ${progress.percent}%`
    // Загрузка занимает полосу 5-70%, остаток оставляем под анализ
    barPercent = 5 + Math.round(progress.percent * 0.65)
  } else {
    label = texts[Math.min(textIdx, texts.length - 1)]
    barPercent = 80 + textIdx * 4
  }

  return (
    <div className="ds-card">
      <div className="flex items-center gap-2 mb-2">
        <svg className="ds-spinner w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" style={{ color: '#00548d' }}>
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <span className="text-sm font-medium text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
          {label}
        </span>
      </div>
      <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: '#E2E8F0' }}>
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${barPercent}%`, background: '#00548d' }}
        />
      </div>
      <p className="text-xs text-on-surface-variant mt-2">
        Не закрывайте страницу — анализ обычно занимает меньше минуты
      </p>
    </div>
  )
}
