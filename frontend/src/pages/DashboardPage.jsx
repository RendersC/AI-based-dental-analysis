import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import useAnalysisStore from '../store/analysisStore'
import api from '../api/axios'
import Brand from '../components/Brand'
import DynamicsChart from '../components/DynamicsChart'

// Полный путь — анализ с индикатором: он даёт цифры, зоны и динамику.
const STEPS = [
  { num: 1, icon: '/icons/004--3.png', title: 'Раскрасьте зубы', desc: 'Используйте индикатор налёта' },
  { num: 2, icon: '/icons/008--7.png', title: 'Сфотографируйте', desc: 'Чёткое фото при хорошем освещении' },
  { num: 3, icon: '/icons/018--17.png', title: 'ИИ-анализ', desc: 'Получите детальный отчёт за секунды' },
  { num: 4, icon: '/icons/013--12.png', title: 'Отслеживайте прогресс', desc: 'Смотрите динамику улучшений' },
]

// Короткий путь — экспресс-оценка: без индикатора, без цифр, зато сразу.
const EXPRESS_STEPS = [
  { num: 1, icon: '/icons/008--7.png', title: 'Сфотографируйте зубы', desc: 'Индикатор налёта не нужен' },
  { num: 2, icon: '/icons/018--17.png', title: 'ИИ опишет, что видно', desc: 'Наблюдения и советы по уходу' },
  { num: 3, icon: '/icons/004--3.png', title: 'Нужны точные цифры', desc: 'Пройдите анализ с индикатором' },
]

function AttemptsIndicator({ count, color = '#00548d' }) {
  const MAX = 3
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: MAX }).map((_, i) => (
        <div key={i} className="transition-all duration-300" style={{
          width: i < count ? 28 : 12, height: 8, borderRadius: 4,
          background: i < count ? color : '#E2E8F0',
        }} />
      ))}
    </div>
  )
}

function StepList({ steps }) {
  return (
    <div className="space-y-4">
      {steps.map(({ num, icon, title, desc }) => (
        <div key={num} className="flex items-center gap-3 sm:gap-4">
          <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
            <img src={icon} alt={title} className="w-6 h-6 sm:w-7 sm:h-7 object-contain" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold w-5 h-5 rounded flex items-center justify-center text-white flex-shrink-0"
                style={{ fontFamily: "'Geist', 'Inter', system-ui", background: '#00548d', fontSize: '10px' }}>
                {num}
              </span>
              <p className="text-sm font-medium text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>{title}</p>
            </div>
            <p className="text-xs text-on-surface-variant mt-0.5 ml-7">{desc}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { user, logout, fetchMe } = useAuthStore()
  const { analysesTotal, fetchAnalyses, dynamics, fetchDynamics } = useAnalysisStore()
  const navigate = useNavigate()
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [instructionUrl, setInstructionUrl] = useState(null)
  const [surveyUrl, setSurveyUrl] = useState('')

  useEffect(() => {
    fetchMe()
    fetchAnalyses()
    fetchDynamics()
    api.get('/settings/instruction/').then(({ data }) => setInstructionUrl(data.url)).catch(() => {})
    api.get('/settings/').then(({ data }) => setSurveyUrl(data.survey_url || '')).catch(() => {})
  }, [])

  const handleLogout = async () => { await logout(); navigate('/login') }

  const handleDeleteAccount = async () => {
    setDeleting(true)
    try {
      await api.delete('/auth/delete/')
      logout()
      navigate('/login')
    } catch {
      setDeleting(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-white sticky top-0 z-10" style={{ borderBottom: '1px solid #E2E8F0' }}>
        <div className="max-w-2xl mx-auto px-3 sm:px-4 h-16 sm:h-20 flex items-center justify-between gap-2">
          <Brand size="sm" />
          <button onClick={handleLogout} className="ds-btn-ghost text-xs flex-shrink-0">Выйти</button>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-3 sm:px-4 py-4 sm:py-6 space-y-4">

        {/* Welcome card */}
        <div className="ds-card">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Добро пожаловать</p>
              <h2 className="text-xl sm:text-2xl font-bold text-on-surface mt-1 truncate"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>{user?.name}</h2>
              <p className="text-sm text-on-surface-variant mt-0.5 truncate">{user?.email}</p>
            </div>
            <div className="w-11 h-11 rounded flex items-center justify-center font-bold text-white text-lg flex-shrink-0"
              style={{ fontFamily: "'Geist', 'Inter', system-ui", background: 'linear-gradient(135deg, #00548d 0%, #1a6daf 100%)' }}>
              {user?.name?.charAt(0)?.toUpperCase()}
            </div>
          </div>
          {/* Два независимых счётчика: экспресс-оценка не тратит баланс полных анализов */}
          <div className="mt-4 pt-4" style={{ borderTop: '1px solid #E2E8F0' }}>
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                  style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Анализов с индикатором</p>
                <p className="text-4xl font-bold mt-1"
                  style={{ fontFamily: "'Geist', 'Inter', system-ui", color: '#00548d' }}>
                  {user?.attempts_left ?? 0}
                </p>
              </div>
              <AttemptsIndicator count={user?.attempts_left ?? 0} />
            </div>
            <div className="flex items-center justify-between gap-3 mt-3 pt-3"
              style={{ borderTop: '1px dashed #E2E8F0' }}>
              <div className="min-w-0">
                <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                  style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Экспресс-оценок</p>
                <p className="text-2xl font-bold mt-1"
                  style={{ fontFamily: "'Geist', 'Inter', system-ui", color: '#006971' }}>
                  {user?.express_attempts_left ?? 0}
                </p>
              </div>
              <AttemptsIndicator count={user?.express_attempts_left ?? 0} color="#006971" />
            </div>
          </div>
        </div>

        {/* New Analysis CTA */}
        <div className="rounded p-4 sm:p-5 text-white relative overflow-hidden"
          style={{ background: 'linear-gradient(135deg, #00548d 0%, #006971 100%)' }}>
          <div className="absolute inset-0 pointer-events-none" style={{
            background: 'radial-gradient(ellipse at 90% 10%, rgba(255,46,233,0.18) 0%, transparent 55%)',
          }} />
          <div className="relative">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold tracking-widest uppercase"
                  style={{ fontFamily: "'Geist', 'Inter', system-ui", color: 'rgba(255,255,255,0.6)' }}>
                  С индикатором
                </p>
                <h3 className="text-base sm:text-lg font-semibold mt-1" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                  Полный анализ с индикатором налёта
                </h3>
                <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.65)' }}>
                  Сфотографируйте зубы после использования индикатора
                </p>
              </div>
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
                style={{ background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(4px)' }}>
                <img src="/icons/002--1.png" alt="" className="w-8 h-8 sm:w-9 sm:h-9 object-contain" />
              </div>
            </div>
            <button
              disabled={!user?.attempts_left}
              onClick={() => navigate('/analysis')}
              className="mt-4 w-full py-2.5 rounded text-sm font-medium transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                fontFamily: "'Geist', 'Inter', system-ui",
                background: 'rgba(255,255,255,0.12)',
                border: '1px solid rgba(255,255,255,0.22)',
                backdropFilter: 'blur(4px)', color: 'white',
              }}>
              {user?.attempts_left ? 'Начать анализ' : 'Нет доступных попыток'}
            </button>
          </div>
        </div>

        {/* Экспресс-оценка: запасной вход для тех, у кого нет индикатора под рукой */}
        <div className="ds-card">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Без индикатора
              </p>
              <h3 className="text-base sm:text-lg font-semibold text-on-surface mt-1"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Экспресс-оценка
              </h3>
              <p className="text-sm text-on-surface-variant mt-1">
                Одно фото без индикатора. ИИ опишет, что видно, и подскажет по уходу.
                Без баллов и процентов, в график динамики не попадает.
              </p>
            </div>
            <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
              style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
              <img src="/icons/008--7.png" alt="" className="w-8 h-8 sm:w-9 sm:h-9 object-contain" />
            </div>
          </div>
          <button
            disabled={!user?.express_attempts_left}
            onClick={() => navigate('/express')}
            className="mt-4 w-full py-2.5 rounded text-sm font-medium transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              fontFamily: "'Geist', 'Inter', system-ui",
              background: 'white',
              border: '1px solid #006971',
              color: '#006971',
            }}>
            {user?.express_attempts_left
              ? 'Пройти экспресс-оценку'
              : 'Экспресс-оценки закончились'}
          </button>
        </div>

        {/* График динамики — показываем, как только есть хотя бы один анализ */}
        {dynamics && dynamics.summary?.count >= 1 && (
          <DynamicsChart data={dynamics} />
        )}

        {/* Steps — два пути: полный анализ и экспресс-оценка */}
        <div className="ds-card">
          <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase mb-1"
            style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Как это работает</h3>
          <p className="text-xs text-on-surface-variant mb-4">
            Анализ с индикатором — точные цифры и динамика
          </p>
          <StepList steps={STEPS} />

          <div className="mt-5 pt-4" style={{ borderTop: '1px dashed #E2E8F0' }}>
            <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase mb-1"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Экспресс-оценка</h3>
            <p className="text-xs text-on-surface-variant mb-4">
              Если индикатора нет под рукой — общая оценка без цифр
            </p>
            <StepList steps={EXPRESS_STEPS} />
          </div>
        </div>

        {/* Instruction */}
        {instructionUrl && (
          <a href={instructionUrl} target="_blank" rel="noopener noreferrer"
            className="ds-card flex items-center gap-3 hover:bg-surface transition-colors duration-150">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-xl"
              style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
              📖
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Инструкция
              </p>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Как сделать правильное фото и пользоваться сервисом
              </p>
            </div>
            <svg className="w-4 h-4 flex-shrink-0" style={{ color: '#c1c7d2' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 3h7v7M21 3l-9 9M5 5h6M5 19h14" />
            </svg>
          </a>
        )}

        {/* Анкета (Яндекс.Формы). Появляется только если ссылка задана в админке. */}
        {surveyUrl && (
          <a href={surveyUrl} target="_blank" rel="noopener noreferrer"
            className="ds-card flex items-center gap-3 hover:bg-surface transition-colors duration-150">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-xl"
              style={{ background: '#f4f8fb', border: '1px solid #E2E8F0' }}>
              💬
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Пройти анкету
              </p>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Помогите нам стать лучше — это займёт пару минут
              </p>
            </div>
            <svg className="w-4 h-4 flex-shrink-0" style={{ color: '#c1c7d2' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 3h7v7M21 3l-9 9M5 5h6M5 19h14" />
            </svg>
          </a>
        )}

        {/* History — отдельная страница /history. На Dashboard только вход. */}
        <button
          onClick={() => navigate('/history')}
          className="ds-card w-full flex items-center gap-3 text-left hover:bg-surface transition-colors duration-150">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
            <img src="/icons/003--2.png" alt="" className="w-6 h-6 object-contain" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              История анализов
            </p>
            <p className="text-xs text-on-surface-variant mt-0.5">
              {analysesTotal > 0
                ? `Всего ${analysesTotal} ${analysesTotal === 1 ? 'анализ' : analysesTotal < 5 ? 'анализа' : 'анализов'}`
                : 'Здесь появятся ваши анализы'}
            </p>
          </div>
          <svg className="w-4 h-4 flex-shrink-0" style={{ color: '#c1c7d2' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {/* Delete account */}
        <div className="ds-card">
          <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase mb-3"
            style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Управление аккаунтом</h3>
          <button
            onClick={() => setShowDeleteModal(true)}
            className="text-sm font-medium transition-colors duration-150"
            style={{ color: '#ba1a1a', fontFamily: "'Geist', 'Inter', system-ui" }}>
            Удалить аккаунт
          </button>
        </div>

      </main>

      {/* Delete modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }}>
          <div className="bg-white rounded-xl p-6 max-w-sm w-full shadow-2xl">
            <h3 className="text-lg font-semibold text-on-surface mb-2"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Удалить аккаунт?</h3>
            <p className="text-sm text-on-surface-variant mb-5">
              Все ваши данные и история анализов будут безвозвратно удалены.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setShowDeleteModal(false)}
                className="ds-btn-ghost flex-1 py-2.5 text-sm">
                Отмена
              </button>
              <button onClick={handleDeleteAccount} disabled={deleting}
                className="flex-1 py-2.5 rounded text-sm font-medium text-white transition-all duration-150 disabled:opacity-50"
                style={{ background: '#ba1a1a', fontFamily: "'Geist', 'Inter', system-ui" }}>
                {deleting ? 'Удаление...' : 'Удалить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
