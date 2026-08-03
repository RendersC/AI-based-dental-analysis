import { create } from 'zustand'
import api from '../api/axios'
import { compressImage } from '../utils/compressImage'

const useAnalysisStore = create((set, get) => ({
  analyses: [],
  currentAnalysis: null,
  isLoading: false,
  error: null,

  // Стадии создания анализа для прогресс-бара:
  // idle | compress (сжимаем фото) | upload (грузим, percent 0-100) | analyze (ждём ИИ)
  progress: { stage: 'idle', percent: 0 },

  // Полная история (для /history): курсор по странице, totalCount, фильтры.
  // historyKind: '' (оба режима) | 'indicator' | 'express' — уходит в ?kind=
  history: [],
  historyPage: 1,
  historyHasNext: false,
  historyTotal: 0,
  historyLoading: false,
  historyValidOnly: false,
  historyKind: '',

  analysesTotal: 0,

  // Анкета: показать ли карточку после анализа (раз в 3 анализа, если не проходил).
  // Заполняется из ответа создания анализа; ResultPage показывает SurveyPrompt.
  survey: { show: false, url: '' },
  clearSurvey: () => set({ survey: { show: false, url: '' } }),

  fetchAnalyses: async () => {
    set({ isLoading: true, error: null })
    try {
      // Dashboard показывает только 5 последних — page_size=5 экономит трафик.
      // analysesTotal приходит из data.count и нужен для кнопки «Показать всю историю».
      const { data } = await api.get('/analysis/', { params: { page_size: 5 } })
      const results = data.results ?? data
      set({
        analyses: results,
        analysesTotal: data.count ?? results.length,
        isLoading: false,
      })
    } catch {
      set({ isLoading: false })
    }
  },

  fetchHistory: async ({ reset = false, validOnly, kind } = {}) => {
    const state = get()
    const nextValidOnly = validOnly ?? state.historyValidOnly
    const nextKind = kind ?? state.historyKind
    const nextPage = reset ? 1 : state.historyPage
    set({ historyLoading: true })
    try {
      const params = { page: nextPage }
      if (nextValidOnly) params.valid_only = 'true'
      if (nextKind) params.kind = nextKind
      const { data } = await api.get('/analysis/', { params })
      const results = data.results ?? data
      set({
        history: reset ? results : [...state.history, ...results],
        historyPage: nextPage + 1,
        historyHasNext: Boolean(data.next),
        historyTotal: data.count ?? results.length,
        historyValidOnly: nextValidOnly,
        historyKind: nextKind,
        historyLoading: false,
      })
    } catch {
      set({ historyLoading: false })
    }
  },

  resetHistory: () => set({
    history: [], historyPage: 1, historyHasNext: false, historyTotal: 0,
    historyValidOnly: false, historyKind: '',
  }),

  fetchAnalysis: async (id) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.get(`/analysis/${id}/`)
      set({ currentAnalysis: data, isLoading: false })
      return data
    } catch (err) {
      set({ error: err.response?.data?.detail || 'Ошибка', isLoading: false })
      return null
    }
  },

  createAnalysis: async ({ photos, ageGroup, legalRepConsent, note }) => {
    set({ isLoading: true, error: null, progress: { stage: 'compress', percent: 0 } })
    try {
      const compressed = await Promise.all(photos.map((f) => compressImage(f)))
      const form = new FormData()
      for (const f of compressed) form.append('photos', f)
      form.append('age_group', ageGroup)
      form.append('legal_rep_consent', legalRepConsent ? 'true' : 'false')
      if (note) form.append('note', note)
      set({ progress: { stage: 'upload', percent: 0 } })
      const { data } = await api.post('/analysis/create/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          const percent = e.total ? Math.round((e.loaded / e.total) * 100) : 0
          // Тело ушло целиком — дальше ждём ответ нейросети
          set({ progress: percent >= 100 ? { stage: 'analyze', percent: 100 } : { stage: 'upload', percent } })
        },
      })
      set({
        currentAnalysis: data,
        isLoading: false,
        progress: { stage: 'idle', percent: 0 },
        survey: { show: Boolean(data.show_survey), url: data.survey_url || '' },
      })
      return data
    } catch (err) {
      const data = err.response?.data
      const msg = data?.detail
        || data?.photos
        || data?.age_group?.[0]
        || data?.legal_rep_consent?.[0]
        || (typeof data === 'string' ? data : null)
        || 'Ошибка анализа'
      set({ error: msg, isLoading: false, progress: { stage: 'idle', percent: 0 } })
      return null
    }
  },

  // Экспресс-оценка: одно фото, без индикатора. Отдельный эндпоинт и отдельный
  // счётчик попыток на бэке; ответ приходит без балла и процентов — только наблюдения.
  createExpress: async ({ photo, ageGroup, legalRepConsent, note }) => {
    set({ isLoading: true, error: null, progress: { stage: 'compress', percent: 0 } })
    try {
      const compressed = await compressImage(photo)
      const form = new FormData()
      form.append('photos', compressed)
      form.append('age_group', ageGroup)
      form.append('legal_rep_consent', legalRepConsent ? 'true' : 'false')
      if (note) form.append('note', note)
      set({ progress: { stage: 'upload', percent: 0 } })
      const { data } = await api.post('/analysis/express/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          const percent = e.total ? Math.round((e.loaded / e.total) * 100) : 0
          set({ progress: percent >= 100 ? { stage: 'analyze', percent: 100 } : { stage: 'upload', percent } })
        },
      })
      set({
        currentAnalysis: data,
        isLoading: false,
        progress: { stage: 'idle', percent: 0 },
        survey: { show: Boolean(data.show_survey), url: data.survey_url || '' },
      })
      return data
    } catch (err) {
      const data = err.response?.data
      const msg = data?.detail
        || data?.photos
        || data?.age_group?.[0]
        || data?.legal_rep_consent?.[0]
        || (typeof data === 'string' ? data : null)
        || 'Ошибка экспресс-оценки'
      set({ error: msg, isLoading: false, progress: { stage: 'idle', percent: 0 } })
      return null
    }
  },

  // График динамики: точки оценок + сводка. Источник — /analysis/dynamics/.
  dynamics: null,
  dynamicsLoading: false,

  fetchDynamics: async () => {
    set({ dynamicsLoading: true })
    try {
      const { data } = await api.get('/analysis/dynamics/')
      set({ dynamics: data, dynamicsLoading: false })
      return data
    } catch {
      set({ dynamicsLoading: false })
      return null
    }
  },

  clearError: () => set({ error: null }),
  clearCurrent: () => set({ currentAnalysis: null }),
}))

export default useAnalysisStore
