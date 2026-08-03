import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
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

export default function ResetPasswordPage() {
  const { uid, token } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState({ password: '', password2: '' })
  const [done, setDone] = useState(false)
  const { confirmPasswordReset, isLoading, error, clearError } = useAuthStore()

  const handleChange = (e) => {
    clearError()
    setForm((p) => ({ ...p, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const ok = await confirmPasswordReset(uid, token, form.password, form.password2)
    if (ok) setDone(true)
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4 relative overflow-hidden">
      <div
        className="absolute -top-40 -right-40 w-96 h-96 rounded-full blur-3xl opacity-40 pointer-events-none"
        style={{ background: 'radial-gradient(circle, #FF2EE9 0%, #52DCFF 100%)' }}
      />
      <div
        className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full blur-3xl opacity-20 pointer-events-none"
        style={{ background: 'radial-gradient(circle, #00548d 0%, #006971 100%)' }}
      />

      <div className="w-full max-w-md relative z-10">
        <div className="mb-4">
          {/* Страницу открывают по ссылке из письма — истории может не быть,
              поэтому запасной адрес это вход, а не главная */}
          <BackButton to="/login" />
        </div>
        <div className="flex justify-center mb-8">
          <Brand size="lg" href="/" />
        </div>

        <div className="glass-card">
          {done ? (
            <>
              <h2 className="text-xl font-semibold text-on-surface mb-0.5"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Пароль изменён
              </h2>
              <p className="text-sm text-on-surface-variant mb-6">
                Готово. Теперь войдите в аккаунт с новым паролем.
              </p>
              <button onClick={() => navigate('/login')} className="ds-btn-primary w-full py-3">
                Войти
              </button>
            </>
          ) : (
            <>
              <h2 className="text-xl font-semibold text-on-surface mb-0.5"
                style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
                Новый пароль
              </h2>
              <p className="text-sm text-on-surface-variant mb-6">
                Придумайте новый пароль. Минимум 8 символов, буквы и цифры.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="ds-label">Новый пароль</label>
                  <input
                    type="password"
                    name="password"
                    value={form.password}
                    onChange={handleChange}
                    className="ds-input"
                    placeholder="••••••••"
                    required
                    minLength={8}
                    autoComplete="new-password"
                  />
                </div>

                <div>
                  <label className="ds-label">Повторите пароль</label>
                  <input
                    type="password"
                    name="password2"
                    value={form.password2}
                    onChange={handleChange}
                    className="ds-input"
                    placeholder="••••••••"
                    required
                    minLength={8}
                    autoComplete="new-password"
                  />
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

                <button type="submit" disabled={isLoading} className="ds-btn-primary w-full py-3">
                  {isLoading ? <Spinner text="Сохраняем..." /> : 'Сохранить пароль'}
                </button>
              </form>

              <p className="text-center text-sm text-on-surface-variant mt-5">
                <Link to="/login" className="font-medium hover:underline" style={{ color: '#00548d' }}>
                  Вернуться ко входу
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
