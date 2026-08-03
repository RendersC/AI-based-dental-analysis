import { create } from 'zustand'
import api from '../api/axios'

function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return null
  }
}

const useAuthStore = create((set, get) => ({
  user: null,
  isLoading: false,
  error: null,

  initFromStorage: () => {
    const token = localStorage.getItem('access_token')
    if (token) {
      const payload = parseJwt(token)
      if (payload && payload.exp * 1000 > Date.now()) {
        set({
          user: {
            id: payload.user_id,
            email: payload.email,
            name: payload.name,
            role: payload.role,
            attempts_left: payload.attempts_left,
          },
        })
        return true
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
    return false
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post('/auth/login/', { email, password })
      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)
      const payload = parseJwt(data.access)
      set({
        user: {
          id: payload.user_id,
          email: payload.email,
          name: payload.name,
          role: payload.role,
          attempts_left: payload.attempts_left,
        },
        isLoading: false,
      })
      return true
    } catch (err) {
      const msg = err.response?.data?.detail || 'Неверный email или пароль'
      set({ error: msg, isLoading: false })
      return false
    }
  },

  register: async (email, name, password, password2, dateOfBirth, consents = {}) => {
    set({ isLoading: true, error: null })
    try {
      await api.post('/auth/register/', {
        email, name, password, password2,
        date_of_birth: dateOfBirth,
        ...consents,
      })
      set({ isLoading: false })
      return true
    } catch (err) {
      const data = err.response?.data
      const msg = data?.email?.[0] || data?.password?.[0] || data?.password2?.[0] ||
        data?.date_of_birth?.[0] ||
        data?.consent_terms?.[0] || data?.consent_privacy?.[0] ||
        data?.consent_personal_data?.[0] || data?.consent_health_data?.[0] ||
        data?.consent_cross_border?.[0] || data?.detail || 'Ошибка регистрации'
      set({ error: msg, isLoading: false })
      return false
    }
  },

  logout: async () => {
    const refresh = localStorage.getItem('refresh_token')
    if (refresh) {
      try {
        await api.post('/auth/logout/', { refresh })
      } catch {
        // блэклист всё равно лучше выполнить, но если упал — чистим локально
      }
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, error: null })
  },

  // Запрос ссылки на сброс пароля. Бэкенд всегда отвечает 200 (не раскрывает,
  // есть ли такой email), поэтому фронт показывает один и тот же успех.
  requestPasswordReset: async (email) => {
    set({ isLoading: true, error: null })
    try {
      await api.post('/auth/password-reset/', { email })
      set({ isLoading: false })
      return true
    } catch (err) {
      const msg = err.response?.status === 429
        ? 'Слишком много попыток. Попробуйте позже.'
        : (err.response?.data?.email?.[0] || 'Не удалось отправить письмо. Попробуйте позже.')
      set({ error: msg, isLoading: false })
      return false
    }
  },

  // Подтверждение сброса: uid+token из ссылки в письме + новый пароль.
  confirmPasswordReset: async (uid, token, newPassword, newPassword2) => {
    set({ isLoading: true, error: null })
    try {
      await api.post('/auth/password-reset/confirm/', {
        uid, token,
        new_password: newPassword,
        new_password2: newPassword2,
      })
      set({ isLoading: false })
      return true
    } catch (err) {
      const data = err.response?.data
      const msg = err.response?.status === 429
        ? 'Слишком много попыток. Попробуйте позже.'
        : (data?.new_password?.[0] || data?.new_password2?.[0] ||
           data?.token?.[0] || data?.detail || 'Не удалось изменить пароль.')
      set({ error: msg, isLoading: false })
      return false
    }
  },

  clearError: () => set({ error: null }),

  fetchMe: async () => {
    try {
      const { data } = await api.get('/auth/me/')
      set((state) => ({ user: { ...state.user, ...data } }))
    } catch {
      // handled by axios interceptor
    }
  },
}))

export default useAuthStore
