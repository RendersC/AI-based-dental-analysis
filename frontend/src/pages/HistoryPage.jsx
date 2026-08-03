import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAnalysisStore from '../store/analysisStore'

function ScoreBadge({ score }) {
  const color = score >= 7 ? '#006971' : score >= 4 ? '#b45309' : '#ba1a1a'
  const bg = score >= 7 ? '#d1fae5' : score >= 4 ? '#fef3c7' : '#ffdad6'
  return (
    <span className="text-xs font-bold px-2 py-0.5 rounded-full"
      style={{ background: bg, color, fontFamily: "'Geist', 'Inter', system-ui" }}>
      {score}/10
    </span>
  )
}

// История общая для обоих режимов, поэтому у каждой записи явная пометка типа —
// иначе непонятно, почему у одних анализов есть балл, а у других нет.
function KindBadge({ isExpress }) {
  return (
    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
      style={isExpress
        ? { background: '#e0f2f1', color: '#006971' }
        : { background: '#e8eef5', color: '#00548d' }}>
      {isExpress ? 'Экспресс-оценка' : 'С индикатором'}
    </span>
  )
}

// Фильтр по типу анализа. Пустая строка = оба режима (бэк принимает ?kind=).
const KIND_TABS = [
  { value: '', label: 'Все' },
  { value: 'indicator', label: 'С индикатором' },
  { value: 'express', label: 'Экспресс' },
]

export default function HistoryPage() {
  const navigate = useNavigate()
  const {
    history, historyHasNext, historyTotal, historyLoading, historyValidOnly, historyKind,
    fetchHistory, resetHistory,
  } = useAnalysisStore()

  useEffect(() => {
    resetHistory()
    fetchHistory({ reset: true })
  }, [])

  const toggleValidOnly = () => {
    fetchHistory({ reset: true, validOnly: !historyValidOnly })
  }

  const selectKind = (kind) => {
    if (kind === historyKind) return
    fetchHistory({ reset: true, kind })
  }

  const kindLabel = KIND_TABS.find((t) => t.value === historyKind)?.label

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-white sticky top-0 z-10" style={{ borderBottom: '1px solid #E2E8F0' }}>
        <div className="max-w-2xl mx-auto px-3 sm:px-4 h-14 flex items-center gap-2 sm:gap-3">
          <button onClick={() => navigate('/dashboard')} className="ds-btn-ghost text-xs px-2">
            ← Назад
          </button>
          <span className="font-semibold text-on-surface text-sm truncate" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
            Вся история анализов
          </span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-3 sm:px-4 py-4 sm:py-6 space-y-4">

        <div className="ds-card">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                {historyKind ? `${kindLabel}: анализов` : 'Всего анализов'}
              </p>
              <p className="text-2xl sm:text-3xl font-bold mt-1"
                style={{ fontFamily: "'Geist', 'Inter', system-ui", color: '#00548d' }}>
                {historyTotal}
              </p>
            </div>
            <button
              onClick={toggleValidOnly}
              className="text-xs px-3 py-2 rounded transition-colors"
              style={{
                background: historyValidOnly ? '#00548d' : 'white',
                color: historyValidOnly ? 'white' : '#00548d',
                border: `1px solid ${historyValidOnly ? '#00548d' : '#c1c7d2'}`,
                fontFamily: "'Geist', 'Inter', system-ui",
              }}>
              {historyValidOnly ? 'Все' : 'Только успешные'}
            </button>
          </div>

          <div className="flex gap-2 mt-4">
            {KIND_TABS.map((tab) => {
              const active = tab.value === historyKind
              return (
                <button
                  key={tab.value || 'all'}
                  onClick={() => selectKind(tab.value)}
                  className="flex-1 text-xs px-2 py-2 rounded transition-colors"
                  style={{
                    background: active ? '#e8eef5' : 'white',
                    color: active ? '#00548d' : '#5f6b7a',
                    border: `1px solid ${active ? '#00548d' : '#c1c7d2'}`,
                    fontWeight: active ? 600 : 400,
                    fontFamily: "'Geist', 'Inter', system-ui",
                  }}>
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>

        {history.length === 0 && !historyLoading && (
          <div className="ds-card">
            <div className="text-center py-8">
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-3"
                style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
                <img src="/icons/003--2.png" alt="" className="w-10 h-10 object-contain opacity-40" />
              </div>
              <p className="text-sm text-on-surface-variant">
                {historyKind === 'express' && 'Экспресс-оценок пока нет'}
                {historyKind === 'indicator' && 'Анализов с индикатором пока нет'}
                {!historyKind && (historyValidOnly ? 'Успешных анализов пока нет' : 'Здесь появятся ваши анализы')}
              </p>
            </div>
          </div>
        )}

        {history.length > 0 && (
          <div className="ds-card">
            <div className="space-y-2">
              {history.map((a) => (
                <button
                  key={a.id}
                  onClick={() => navigate(`/result/${a.id}`, { state: { from: 'history' } })}
                  className="w-full flex items-center gap-3 p-3 rounded-lg transition-colors duration-150 text-left"
                  style={{ background: '#f7f9fb', border: '1px solid #E2E8F0' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#f2f4f6'}
                  onMouseLeave={e => e.currentTarget.style.background = '#f7f9fb'}
                >
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: '#E2E8F0' }}>
                    <img src="/icons/018--17.png" alt="" className="w-6 h-6 object-contain" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium text-on-surface truncate"
                        style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                        {a.kind === 'express' ? 'Экспресс' : 'Анализ'} #{a.id}
                      </p>
                      <KindBadge isExpress={a.kind === 'express'} />
                      {a.is_valid && a.score != null && <ScoreBadge score={a.score} />}
                      {!a.is_valid && (
                        <span className="text-xs px-2 py-0.5 rounded-full"
                          style={{ background: '#ffdad6', color: '#ba1a1a' }}>
                          Неверное фото
                        </span>
                      )}
                      {a.age_group_display && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full"
                          style={{ background: '#e8eef5', color: '#00548d', fontWeight: 500 }}>
                          {a.age_group_display}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-on-surface-variant mt-0.5">
                      {new Date(a.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })}
                    </p>
                    {a.note && (
                      <p className="text-xs text-on-surface-variant mt-1 truncate" style={{ fontStyle: 'italic' }}>
                        «{a.note}»
                      </p>
                    )}
                  </div>
                  <svg className="w-4 h-4 flex-shrink-0" style={{ color: '#c1c7d2' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              ))}
            </div>

            {historyHasNext && (
              <button
                onClick={() => fetchHistory()}
                disabled={historyLoading}
                className="ds-btn-ghost w-full mt-3 py-2.5 text-sm disabled:opacity-50">
                {historyLoading ? 'Загрузка...' : 'Показать ещё'}
              </button>
            )}
          </div>
        )}

        {historyLoading && history.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <svg className="ds-spinner w-6 h-6" style={{ color: '#00548d' }} viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        )}

      </main>
    </div>
  )
}
