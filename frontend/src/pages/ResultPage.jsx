import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import useAnalysisStore from '../store/analysisStore'
import SurveyPrompt from '../components/SurveyPrompt'
import SampleReportPreview from '../components/SampleReportPreview'
import PhotoImage from '../components/PhotoImage'
import { ScoreGauge, PlaqueBar } from '../components/ReportVisuals'

export default function ResultPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { currentAnalysis, fetchAnalysis, isLoading, survey, clearSurvey } = useAnalysisStore()
  // Подсветка зон налёта: по умолчанию показываем её (это главная ценность
  // измерения), переключатель возвращает оригинал. Есть только у анализов,
  // где CV-скрипт измерил налёт и сохранил оверлеи.
  const [showOverlay, setShowOverlay] = useState(true)

  useEffect(() => {
    if (id) fetchAnalysis(id)
  }, [id])

  // Карточка анкеты убирается при уходе со страницы, чтобы не «всплыла» на чужом результате.
  useEffect(() => () => clearSurvey(), [])

  if (isLoading || !currentAnalysis) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <svg className="ds-spinner w-8 h-8 text-primary" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    )
  }

  const a = currentAnalysis
  const isExpress = a.kind === 'express'
  const retryPath = isExpress ? '/express' : '/analysis'

  if (!a.is_valid) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center px-4">
        <div className="ds-card max-w-sm w-full text-center">
          <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ background: '#ffdad6' }}>
            <svg className="w-7 h-7" style={{ color: '#ba1a1a' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-on-surface mb-2" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
            Фото не подходит
          </h2>
          <p className="text-sm text-on-surface-variant mb-5">
            {isExpress
              ? 'ИИ не смог распознать зубы на снимке. Попробуйте сделать более чёткое фото при хорошем освещении.'
              : 'ИИ не смог распознать зубы с индикатором. Попробуйте сделать более чёткое фото при хорошем освещении.'}
          </p>
          <button onClick={() => navigate(retryPath)} className="ds-btn-primary w-full py-2.5">
            Попробовать снова
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="ds-btn-ghost w-full py-2.5 mt-2"
            style={{ border: '1px solid #E2E8F0' }}
          >
            На главную
          </button>
        </div>
        {survey.show && survey.url && (
          <SurveyPrompt url={survey.url} onClose={clearSurvey} />
        )}
      </div>
    )
  }

  if (isExpress) {
    const photos = (a.photos && a.photos.length > 0)
      ? a.photos.map((p) => p.photo)
      : (a.photo_url ? [a.photo_url] : [])

    return (
      <div className="min-h-screen bg-surface">
        <header className="bg-white sticky top-0 z-10" style={{ borderBottom: '1px solid #E2E8F0' }}>
          <div className="max-w-2xl mx-auto px-3 sm:px-4 h-14 flex items-center gap-2 sm:gap-3">
            <button onClick={() => navigate('/history')} className="ds-btn-ghost text-xs px-2 flex-shrink-0">
              ← К списку анализов
            </button>
            <span className="font-semibold text-on-surface text-sm truncate" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              Экспресс-оценка
            </span>
          </div>
        </header>

        <main className="max-w-2xl mx-auto px-3 sm:px-4 py-4 sm:py-6 space-y-4">

          {/* Наблюдения — единственный результат этого режима: без балла и процентов */}
          <div className="ds-card">
            <div className="flex items-center justify-between mb-4 gap-2 flex-wrap">
              <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Что видно на фото
              </p>
              {a.age_group_display && (
                <span className="text-[10px] px-2 py-0.5 rounded-full"
                  style={{ background: '#e8eef5', color: '#00548d', fontWeight: 500 }}>
                  {a.age_group_display}
                </span>
              )}
            </div>
            {a.observations?.length > 0 ? (
              <div className="space-y-3">
                {a.observations.map((text, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0 mt-2"
                      style={{ background: '#00548d' }} />
                    <p className="text-sm text-on-surface leading-relaxed">{text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-on-surface-variant">Описание недоступно.</p>
            )}
          </div>

          {a.recommendations?.length > 0 && (
            <div className="ds-card">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
                  <img src="/icons/003--2.png" alt="" className="w-6 h-6 object-contain" />
                </div>
                <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                  style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                  Рекомендации
                </h3>
              </div>
              <div className="space-y-3">
                {a.recommendations.map((rec, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <span className="w-6 h-6 rounded flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5"
                      style={{ background: '#00548d', fontFamily: "'Geist', 'Inter', system-ui", fontSize: '10px' }}>
                      {i + 1}
                    </span>
                    <p className="text-sm text-on-surface leading-relaxed">{rec}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {a.doctor_comment && (
            <div className="ds-card">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
                  <img src="/icons/001-.png" alt="" className="w-6 h-6 object-contain" />
                </div>
                <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                  style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                  Комментарий эксперта
                </h3>
              </div>
              <p className="text-sm text-on-surface leading-relaxed">{a.doctor_comment}</p>
            </div>
          )}

          {a.note && (
            <div className="ds-card">
              <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase mb-2"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Ваша заметка
              </p>
              <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">{a.note}</p>
            </div>
          )}

          {/* Почему тут нет цифр — говорим честно, до того как пользователь спросит */}
          <div className="rounded p-4 flex items-start gap-3"
            style={{ background: '#fff8e1', border: '1px solid #f6cf6c' }}>
            <svg className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: '#8a6100' }}
              viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              Это приблизительная ознакомительная оценка по обычному фото. Без индикатора
              налёта его площадь измерить нельзя, поэтому здесь нет баллов и процентов.
              По этой же причине экспресс-оценка не попадает в график динамики гигиены:
              в нём участвуют только анализы с индикатором.
              Сервис носит информационно-образовательный характер и не является медицинской услугой.
            </p>
          </div>

          {photos.length > 0 && (
            <div className="ds-card">
              <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase mb-3"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Ваше фото
              </p>
              <a href={photos[0]} target="_blank" rel="noopener noreferrer" className="block">
                <PhotoImage src={photos[0]} alt="Фото экспресс-оценки"
                  className="rounded object-cover" style={{ maxHeight: 240 }} />
              </a>
            </div>
          )}

          {/* Воронка: показываем, что даёт полный анализ, и ведём к нему */}
          <SampleReportPreview />

          <button
            onClick={() => navigate('/dashboard')}
            className="ds-btn-ghost w-full py-3"
            style={{ border: '1px solid #E2E8F0' }}
          >
            На главную
          </button>

        </main>

        {survey.show && survey.url && (
          <SurveyPrompt url={survey.url} onClose={clearSurvey} />
        )}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-white sticky top-0 z-10" style={{ borderBottom: '1px solid #E2E8F0' }}>
        <div className="max-w-2xl mx-auto px-3 sm:px-4 h-14 flex items-center gap-2 sm:gap-3">
          <button
            onClick={() => navigate('/history')}
            className="ds-btn-ghost text-xs px-2 flex-shrink-0"
          >
            ← К списку анализов
          </button>
          <span className="font-semibold text-on-surface text-sm truncate" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
            Результат анализа
          </span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-3 sm:px-4 py-4 sm:py-6 space-y-4">

        {/* Score */}
        <div className="ds-card">
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              Общая оценка гигиены
            </p>
            {a.age_group_display && (
              <span className="text-[10px] px-2 py-0.5 rounded-full"
                style={{ background: '#e8eef5', color: '#00548d', fontWeight: 500 }}>
                {a.age_group_display}
              </span>
            )}
          </div>
          <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-6">
            <ScoreGauge score={a.score} />
            <div className="flex-1 w-full space-y-3">
              <PlaqueBar label="Мягкий налёт (розовый)" value={a.fresh_plaque_percent} color="#F45EAC" />
              <PlaqueBar label="Зрелый налёт (синий)" value={a.old_plaque_percent} color="#00548d" />
            </div>
          </div>
        </div>

        {/* Dynamics */}
        {a.dynamics_text && (
          <div className="rounded p-4 flex items-start gap-3"
            style={{ background: 'linear-gradient(135deg, #00548d 0%, #006971 100%)' }}>
            <img src="/icons/013--12.png" alt="" className="w-8 h-8 object-contain flex-shrink-0 mt-0.5 brightness-0 invert" />
            <div>
              <p className="text-xs font-semibold tracking-widest uppercase mb-1"
                style={{ fontFamily: "'Geist', 'Inter', system-ui", color: 'rgba(255,255,255,0.6)' }}>
                Динамика
              </p>
              <p className="text-sm text-white">{a.dynamics_text}</p>
            </div>
          </div>
        )}

        {/* Problem zones */}
        {a.problem_zones?.length > 0 && (
          <div className="ds-card">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: '#ffdad6', border: '1px solid rgb(186 26 26 / 0.15)' }}>
                <img src="/icons/006--5.png" alt="" className="w-6 h-6 object-contain" />
              </div>
              <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Проблемные зоны
              </h3>
            </div>
            <div className="flex flex-wrap gap-2">
              {a.problem_zones.map((zone, i) => (
                <span key={i} className="px-2.5 py-1 rounded-full text-xs font-medium"
                  style={{ background: '#ffdad6', color: '#ba1a1a', fontFamily: "'Geist', 'Inter', system-ui" }}>
                  {zone}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Recommendations */}
        {a.recommendations?.length > 0 && (
          <div className="ds-card">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
                <img src="/icons/003--2.png" alt="" className="w-6 h-6 object-contain" />
              </div>
              <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Рекомендации
              </h3>
            </div>
            <div className="space-y-3">
              {a.recommendations.map((rec, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="w-6 h-6 rounded flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5"
                    style={{ background: '#00548d', fontFamily: "'Geist', 'Inter', system-ui", fontSize: '10px' }}>
                    {i + 1}
                  </span>
                  <p className="text-sm text-on-surface leading-relaxed">{rec}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Doctor comment */}
        {a.doctor_comment && (
          <div className="ds-card">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
                <img src="/icons/001-.png" alt="" className="w-6 h-6 object-contain" />
              </div>
              <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Комментарий эксперта
              </h3>
            </div>
            <p className="text-sm text-on-surface leading-relaxed">{a.doctor_comment}</p>
          </div>
        )}

        {a.note && (
          <div className="ds-card">
            <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase mb-2"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              Ваша заметка
            </p>
            <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">{a.note}</p>
          </div>
        )}

        {/* Photos: при наличии подсветки от CV-скрипта — переключатель оригинал/подсветка */}
        {(() => {
          const items = (a.photos && a.photos.length > 0)
            ? a.photos.map((p) => ({ photo: p.photo, overlay: p.overlay }))
            : (a.photo_url ? [{ photo: a.photo_url, overlay: null }] : [])
          if (items.length === 0) return null
          const hasOverlay = items.some((it) => it.overlay)
          const overlayOn = hasOverlay && showOverlay
          return (
            <div className="ds-card">
              <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
                <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                  style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                  {items.length > 1 ? `Фото анализа (${items.length})` : 'Фото анализа'}
                </p>
                {hasOverlay && (
                  <div className="flex rounded overflow-hidden" style={{ border: '1px solid #E2E8F0' }}>
                    {[
                      { key: true, label: 'Подсветка налёта' },
                      { key: false, label: 'Оригинал' },
                    ].map(({ key, label }) => (
                      <button
                        key={label}
                        onClick={() => setShowOverlay(key)}
                        className="px-2.5 py-1 text-xs font-medium"
                        style={overlayOn === key
                          ? { background: '#00548d', color: '#fff' }
                          : { background: '#fff', color: '#64748B' }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {overlayOn && (
                <p className="text-xs text-on-surface-variant mb-2">
                  Розовым подсвечен свежий налёт, синим — зрелый (зоны найдены по цвету индикатора).
                </p>
              )}
              <div className={items.length > 1 ? 'grid grid-cols-2 sm:grid-cols-3 gap-2' : ''}>
                {items.map((it, i) => {
                  const src = (overlayOn && it.overlay) ? it.overlay : it.photo
                  return (
                    <a key={`${i}-${src}`} href={src} target="_blank" rel="noopener noreferrer" className="block">
                      <PhotoImage src={src} alt={`Фото ${i + 1}`}
                        className="rounded object-cover"
                        style={{ maxHeight: items.length > 1 ? 200 : 240 }} />
                    </a>
                  )
                })}
              </div>
            </div>
          )
        })()}

        <button onClick={() => navigate('/analysis')} className="ds-btn-primary w-full py-3">
          Новый анализ
        </button>
        {/* «К списку анализов» — в верхней шапке; внизу не дублируем. */}
        <button
          onClick={() => navigate('/dashboard')}
          className="ds-btn-ghost w-full py-3"
          style={{ border: '1px solid #E2E8F0' }}
        >
          На главную
        </button>

      </main>

      {survey.show && survey.url && (
        <SurveyPrompt url={survey.url} onClose={clearSurvey} />
      )}
    </div>
  )
}
