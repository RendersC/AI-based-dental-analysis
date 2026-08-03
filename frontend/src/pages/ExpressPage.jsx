import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import useAnalysisStore from '../store/analysisStore'
import useAuthStore from '../store/authStore'
import AnalysisProgress, { EXPRESS_TEXTS } from '../components/AnalysisProgress'

const AGE_GROUPS = [
  { value: 'milk', label: '3 года – 5 лет 11 мес.', sub: 'молочный прикус' },
  { value: 'mixed', label: '6 лет – 11 лет 11 мес.', sub: 'сменный прикус' },
  { value: 'permanent_teen', label: '12 лет – 17 лет 11 мес.', sub: 'постоянный прикус (подростки)' },
  { value: 'permanent_adult', label: '18+ лет', sub: 'постоянный прикус (взрослые)' },
]

const UNDERAGE = new Set(['milk', 'mixed', 'permanent_teen'])
const MAX_NOTE_LENGTH = 1000

export default function ExpressPage() {
  const [item, setItem] = useState(null)
  const [ageGroup, setAgeGroup] = useState('')
  const [legalRepConsent, setLegalRepConsent] = useState(false)
  const [note, setNote] = useState('')
  const fileRef = useRef(null)
  const navigate = useNavigate()
  const { createExpress, isLoading, error, clearError, progress } = useAnalysisStore()
  const { user, fetchMe } = useAuthStore()

  useEffect(() => () => { if (item) URL.revokeObjectURL(item.preview) }, [item])

  useEffect(() => {
    if (!UNDERAGE.has(ageGroup)) setLegalRepConsent(false)
  }, [ageGroup])

  const setFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return
    clearError()
    setItem((prev) => {
      if (prev) URL.revokeObjectURL(prev.preview)
      return { file, preview: URL.createObjectURL(file) }
    })
  }

  const consentRequired = UNDERAGE.has(ageGroup)
  const canSubmit = !!item && !!ageGroup && (!consentRequired || legalRepConsent) && !isLoading

  const handleSubmit = async () => {
    if (!canSubmit) return
    const result = await createExpress({ photo: item.file, ageGroup, legalRepConsent, note: note.trim() })
    if (result) {
      await fetchMe()
      navigate(`/result/${result.id}`)
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-white sticky top-0 z-10" style={{ borderBottom: '1px solid #E2E8F0' }}>
        <div className="max-w-2xl mx-auto px-3 sm:px-4 h-14 flex items-center gap-2 sm:gap-3">
          <button onClick={() => navigate('/dashboard')} className="ds-btn-ghost text-xs px-2 flex-shrink-0">
            ← Назад
          </button>
          <span className="font-semibold text-on-surface text-sm truncate" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
            Экспресс-оценка
          </span>
          <span className="ml-auto text-xs text-on-surface-variant flex-shrink-0">
            Осталось: <b style={{ color: '#00548d' }}>{user?.express_attempts_left ?? 0}</b>
          </span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-3 sm:px-4 py-4 sm:py-6 space-y-4">

        {/* Что это за режим и чем отличается от полного анализа */}
        <div className="ds-card">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: '#f4f8fb', border: '1px solid #E2E8F0' }}>
              <img src="/icons/008--7.png" alt="" className="w-6 h-6 object-contain" />
            </div>
            <h2 className="text-sm font-semibold text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              Одно фото, без индикатора
            </h2>
          </div>
          <p className="text-sm text-on-surface-variant leading-relaxed">
            Просто сфотографируйте зубы при хорошем освещении — индикатор налёта не нужен.
            ИИ посмотрит на снимок и опишет, что видно: общая чистота, заметный налёт,
            состояние дёсен, — и даст рекомендации по уходу.
          </p>
          <p className="text-sm text-on-surface-variant leading-relaxed mt-2">
            Это ознакомительная оценка <b>без баллов и процентов</b>. Точные цифры, проблемные
            зоны и динамику даёт анализ с индикатором налёта.
          </p>
        </div>

        <div className="ds-card">
          <h2 className="text-sm font-semibold text-on-surface mb-3" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
            Возрастная группа пациента
          </h2>
          <div className="grid grid-cols-1 gap-2">
            {AGE_GROUPS.map((g) => {
              const active = ageGroup === g.value
              return (
                <label key={g.value}
                  className="flex items-start gap-3 p-3 rounded cursor-pointer transition-all"
                  style={{
                    border: `2px solid ${active ? '#00548d' : '#E2E8F0'}`,
                    background: active ? '#f4f8fb' : 'white',
                  }}>
                  <input type="radio" name="age_group" value={g.value} checked={active}
                    onChange={(e) => setAgeGroup(e.target.value)} className="mt-1" />
                  <span className="text-sm">
                    <span className="font-medium text-on-surface">{g.label}</span>
                    <span className="block text-xs text-on-surface-variant">{g.sub}</span>
                  </span>
                </label>
              )
            })}
          </div>
        </div>

        {consentRequired && (
          <div className="ds-card" style={{ background: '#fff8e1', borderColor: '#f6cf6c' }}>
            <label className="flex items-start gap-3 cursor-pointer">
              <input type="checkbox" checked={legalRepConsent}
                onChange={(e) => setLegalRepConsent(e.target.checked)} className="mt-1" />
              <span className="text-xs text-on-surface-variant leading-relaxed">
                Я, как законный представитель, даю согласие на обработку персональных данных
                и данных о состоянии здоровья моего несовершеннолетнего ребёнка в соответствии
                с{' '}
                <a href="/docs/child-consent.html" target="_blank" rel="noopener noreferrer"
                  className="font-medium hover:underline" style={{ color: '#00548d' }}>
                  Согласием на обработку данных ребёнка (152-ФЗ)
                </a>.
              </span>
            </label>
          </div>
        )}

        <div
          className="ds-card cursor-pointer transition-all duration-150"
          style={item ? {} : { borderStyle: 'dashed', borderColor: '#c1c7d2' }}
          onDrop={(e) => { e.preventDefault(); setFile((e.dataTransfer.files || [])[0]) }}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileRef.current?.click()}
        >
          {!item ? (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center"
                style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
                <img src="/icons/008--7.png" alt="" className="w-10 h-10 object-contain" />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                  Нажмите или перетащите фото
                </p>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  Одно фото · JPG, PNG, HEIC до 10 МБ
                </p>
              </div>
            </div>
          ) : (
            <div className="relative">
              <img src={item.preview} alt="Фото для экспресс-оценки"
                className="w-full rounded object-cover" style={{ maxHeight: 260 }} />
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  URL.revokeObjectURL(item.preview)
                  setItem(null)
                }}
                className="absolute top-2 right-2 w-7 h-7 rounded-full flex items-center justify-center text-white text-xs"
                style={{ background: 'rgba(0,0,0,0.6)' }}
                aria-label="Убрать фото"
              >
                ✕
              </button>
            </div>
          )}
        </div>

        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => { setFile((e.target.files || [])[0]); e.target.value = '' }}
        />

        <div className="ds-card">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              Заметка (необязательно)
            </h2>
            <span className="text-xs text-on-surface-variant">{note.length}/{MAX_NOTE_LENGTH}</span>
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value.slice(0, MAX_NOTE_LENGTH))}
            placeholder="Например: сменили щётку на электрическую, началось прорезывание зуба…"
            rows={3}
            className="w-full text-sm rounded p-2.5"
            style={{ border: '1px solid #E2E8F0', resize: 'vertical' }}
          />
          <p className="text-xs text-on-surface-variant mt-1.5">
            Заметка сохранится вместе с анализом и будет видна только вам в истории.
          </p>
        </div>

        {error && (
          <div className="flex items-start gap-2.5 p-3 rounded text-sm"
            style={{ background: '#ffdad6', border: '1px solid rgb(186 26 26 / 0.2)', color: '#ba1a1a' }}>
            <svg className="w-4 h-4 flex-shrink-0 mt-0.5" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm-.75 3.75h1.5v4.5h-1.5v-4.5zm0 6h1.5v1.5h-1.5v-1.5z" />
            </svg>
            <span>{typeof error === 'string' ? error : JSON.stringify(error)}</span>
          </div>
        )}

        {isLoading && <AnalysisProgress progress={progress} texts={EXPRESS_TEXTS} />}

        <button onClick={handleSubmit} disabled={!canSubmit} className="ds-btn-primary w-full py-3">
          {isLoading ? 'Оценка идёт…' : 'Получить экспресс-оценку'}
        </button>

        <p className="text-xs text-center text-on-surface-variant px-2">
          Сервис носит информационно-образовательный характер и не является медицинской услугой.
        </p>

      </main>
    </div>
  )
}
