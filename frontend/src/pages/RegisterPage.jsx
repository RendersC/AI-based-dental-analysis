import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import Brand from '../components/Brand'
import BackButton from '../components/BackButton'

function Spinner({ text }) {
  return (
    <span className="flex items-center gap-2 justify-center">
      <svg className="ds-spinner" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {text}
    </span>
  )
}

function ConsentCheck({ id, checked, onChange, children }) {
  return (
    <label htmlFor={id} className="flex items-start gap-3 cursor-pointer group">
      <div className="flex-shrink-0 mt-0.5">
        <div
          className="w-5 h-5 rounded border-2 flex items-center justify-center transition-all duration-150"
          style={{
            borderColor: checked ? '#00548d' : '#c1c7d2',
            background: checked ? '#00548d' : 'white',
          }}
        >
          {checked && (
            <svg className="w-3 h-3 text-white" viewBox="0 0 12 12" fill="none">
              <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </div>
        <input id={id} type="checkbox" checked={checked} onChange={onChange} className="sr-only" />
      </div>
      <span className="text-xs text-on-surface-variant leading-relaxed">{children}</span>
    </label>
  )
}

const MIN_AGE = 14

function calcAge(birthDateStr) {
  if (!birthDateStr) return null
  const bd = new Date(birthDateStr)
  if (Number.isNaN(bd.getTime())) return null
  const today = new Date()
  let years = today.getFullYear() - bd.getFullYear()
  const m = today.getMonth() - bd.getMonth()
  if (m < 0 || (m === 0 && today.getDate() < bd.getDate())) years -= 1
  return years
}

export default function RegisterPage() {
  const [form, setForm] = useState({ email: '', name: '', password: '', password2: '', date_of_birth: '' })
  const [consents, setConsents] = useState({
    consent_terms: false,
    consent_privacy: false,
    consent_personal_data: false,
    consent_health_data: false,
    consent_cross_border: false,
  })
  const [success, setSuccess] = useState(false)
  const { register, isLoading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleChange = (e) => {
    clearError()
    setForm((p) => ({ ...p, [e.target.name]: e.target.value }))
  }

  const toggleConsent = (key) => {
    clearError()
    setConsents((p) => ({ ...p, [key]: !p[key] }))
  }

  const allConsents = Object.values(consents).every(Boolean)
  const passwordMismatch = form.password2 && form.password !== form.password2
  const age = calcAge(form.date_of_birth)
  const ageTooLow = form.date_of_birth && age !== null && age < MIN_AGE
  const today = new Date().toISOString().slice(0, 10)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (form.password !== form.password2 || !allConsents || ageTooLow || !form.date_of_birth) return
    const ok = await register(
      form.email, form.name, form.password, form.password2,
      form.date_of_birth,
      consents,
    )
    if (ok) {
      setSuccess(true)
      setTimeout(() => navigate('/login'), 2000)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center px-4">
        <div className="glass-card text-center max-w-sm w-full">
          <div className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ background: 'linear-gradient(135deg, #00548d, #006971)' }}>
            <svg className="w-7 h-7 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-on-surface mb-2"
            style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Аккаунт создан!</h2>
          <p className="text-sm text-on-surface-variant">Перенаправляем на страницу входа...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4 relative overflow-hidden">
      <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full blur-3xl opacity-40 pointer-events-none"
        style={{ background: 'radial-gradient(circle, #52DCFF 0%, #FF2EE9 100%)' }} />
      <div className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full blur-3xl opacity-20 pointer-events-none"
        style={{ background: 'radial-gradient(circle, #006971 0%, #00548d 100%)' }} />

      <div className="w-full max-w-md relative z-10">
        <div className="mb-4">
          <BackButton />
        </div>
        <div className="flex justify-center mb-8">
          <Brand size="lg" href="/" />
        </div>

        <div className="glass-card">
          <h2 className="text-xl font-semibold text-on-surface mb-0.5"
            style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Создать аккаунт</h2>
          <p className="text-sm text-on-surface-variant mb-6">Заполните данные для регистрации</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="ds-label">Имя</label>
              <input type="text" name="name" value={form.name} onChange={handleChange}
                className="ds-input" placeholder="Иван Иванов" required />
            </div>
            <div>
              <label className="ds-label">Email</label>
              <input type="email" name="email" value={form.email} onChange={handleChange}
                className="ds-input" placeholder="your@email.com" required autoComplete="email" />
            </div>
            <div>
              <label className="ds-label">Дата рождения</label>
              <input type="date" name="date_of_birth" value={form.date_of_birth} onChange={handleChange}
                className={`ds-input${ageTooLow ? ' ds-input-error' : ''}`}
                max={today} required />
              {ageTooLow && (
                <p className="text-xs mt-1" style={{ color: '#ba1a1a' }}>
                  Регистрация доступна с {MIN_AGE} лет. Для младших пользователей сервисом пользуется законный представитель.
                </p>
              )}
            </div>
            <div>
              <label className="ds-label">Пароль</label>
              <input type="password" name="password" value={form.password} onChange={handleChange}
                className="ds-input" placeholder="От 8 символов, буквы и цифры" required minLength={8} autoComplete="new-password" />
            </div>
            <div>
              <label className="ds-label">Повторите пароль</label>
              <input type="password" name="password2" value={form.password2} onChange={handleChange}
                className={`ds-input${passwordMismatch ? ' ds-input-error' : ''}`}
                placeholder="••••••••" required autoComplete="new-password" />
              {passwordMismatch && (
                <p className="text-xs mt-1" style={{ color: '#ba1a1a' }}>Пароли не совпадают</p>
              )}
            </div>

            {/* Consents */}
            <div className="space-y-3 pt-1">
              <p className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Согласия</p>
              <ConsentCheck id="c0" checked={consents.consent_terms}
                onChange={() => toggleConsent('consent_terms')}>
                Я принимаю <a href="/docs/terms.html" target="_blank" rel="noopener noreferrer" className="font-medium hover:underline" style={{ color: '#00548d' }}>Пользовательское соглашение</a>
              </ConsentCheck>
              <ConsentCheck id="cp" checked={consents.consent_privacy}
                onChange={() => toggleConsent('consent_privacy')}>
                Я ознакомлен(а) с <a href="/docs/privacy.html" target="_blank" rel="noopener noreferrer" className="font-medium hover:underline" style={{ color: '#00548d' }}>Политикой конфиденциальности</a>
              </ConsentCheck>
              <ConsentCheck id="c1" checked={consents.consent_personal_data}
                onChange={() => toggleConsent('consent_personal_data')}>
                Я согласен(а) на <a href="/docs/personal-data-consent.html" target="_blank" rel="noopener noreferrer" className="font-medium hover:underline" style={{ color: '#00548d' }}>обработку персональных данных</a> в соответствии с 152-ФЗ
              </ConsentCheck>
              <ConsentCheck id="c2" checked={consents.consent_health_data}
                onChange={() => toggleConsent('consent_health_data')}>
                Я согласен(а) на <a href="/docs/health-data-consent.html" target="_blank" rel="noopener noreferrer" className="font-medium hover:underline" style={{ color: '#00548d' }}>обработку данных о состоянии здоровья</a> (фотографии зубов)
              </ConsentCheck>
              <ConsentCheck id="c3" checked={consents.consent_cross_border}
                onChange={() => toggleConsent('consent_cross_border')}>
                Я согласен(а) на <a href="/docs/cross-border-consent.html" target="_blank" rel="noopener noreferrer" className="font-medium hover:underline" style={{ color: '#00548d' }}>трансграничную передачу данных</a> (обработка фото сервисами Google/США)
              </ConsentCheck>
            </div>

            {error && (
              <div className="flex items-start gap-2.5 p-3 rounded text-sm"
                style={{ background: '#ffdad6', border: '1px solid rgb(186 26 26 / 0.2)', color: '#ba1a1a' }}>
                <svg className="w-4 h-4 flex-shrink-0 mt-0.5" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm-.75 3.75h1.5v4.5h-1.5v-4.5zm0 6h1.5v1.5h-1.5v-1.5z" />
                </svg>
                <span>{error}</span>
              </div>
            )}

            <button type="submit"
              disabled={isLoading || !!passwordMismatch || !allConsents || ageTooLow || !form.date_of_birth}
              className="ds-btn-primary w-full py-3">
              {isLoading ? <Spinner text="Создание..." /> : 'Зарегистрироваться'}
            </button>
          </form>

          <p className="text-center text-sm text-on-surface-variant mt-5">
            Уже есть аккаунт?{' '}
            <Link to="/login" className="font-medium hover:underline" style={{ color: '#00548d' }}>Войти</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
