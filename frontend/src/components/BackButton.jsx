import { useLocation, useNavigate } from 'react-router-dom'

/**
 * Кнопка «Назад» для страниц входа и регистрации.
 *
 * Зачем: сервис часто открывают с ярлыка на домашнем экране телефона. Такое
 * окно запускается без панели браузера — системной кнопки «назад» в нём нет,
 * и со страницы регистрации уйти было можно только закрыв приложение целиком.
 *
 * Куда возвращаемся: location.key равен 'default' только на первом экране
 * сессии роутера, то есть когда страницу открыли напрямую (ярлык, ссылка из
 * письма, новая вкладка) и внутри сайта возвращаться некуда — тогда уводим на
 * заданный адрес. Если пользователь пришёл сюда переходом внутри приложения,
 * ключ уже сгенерирован и можно честно шагнуть на экран назад.
 *
 * Именно ключ, а не window.history.length: длина истории считает и чужие
 * записи (пустая вкладка, предыдущий сайт), и шаг назад по ней уводит с сайта.
 */
export default function BackButton({ to = '/', label = 'Назад' }) {
  const navigate = useNavigate()
  const location = useLocation()

  const goBack = () => {
    if (location.key && location.key !== 'default') navigate(-1)
    else navigate(to, { replace: true })
  }

  return (
    <button type="button" onClick={goBack} className="ds-btn-ghost gap-1.5" aria-label={label}>
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M15 5l-7 7 7 7" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {label}
    </button>
  )
}
