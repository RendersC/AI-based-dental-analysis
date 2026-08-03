import { useCallback, useEffect, useState } from "react";

/**
 * Блок «Официальный статус проекта» на лендинге.
 *
 * Статичная адаптивная сетка карточек (скан + подпись), содержимое ведёт админ
 * через раздел «Официальные документы». По клику скан открывается на весь экран
 * с затемнением; закрывается крестиком, кликом по фону или клавишей Esc.
 *
 * Данные тянем голым fetch, а не общим api-клиентом: у того в интерцепторе
 * висит подстановка токена и редирект на /login при 401, а лендинг — публичная
 * страница для неавторизованных. Если документов нет или запрос не удался,
 * компонент не рисует ничего — секция просто отсутствует.
 */
export default function OfficialDocs() {
  const [docs, setDocs] = useState([]);
  const [active, setActive] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/settings/official-documents/")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        const list = Array.isArray(data.results) ? data.results : [];
        setDocs(list.filter((d) => d.image_url));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const close = useCallback(() => setActive(null), []);

  // Пока открыт полноэкранный просмотр — гасим прокрутку страницы под ним
  // и слушаем Esc. Оба эффекта снимаются при закрытии.
  useEffect(() => {
    if (!active) return;
    const onKey = (e) => {
      if (e.key === "Escape") close();
    };
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [active, close]);

  if (docs.length === 0) return null;

  return (
    <section className="rs-section rs-section--wash" id="official">
      <div className="rs-container">
        <div className="rs-section__head">
          <span className="rs-eyebrow">Документы</span>
          <h2 className="rs-h2">Официальный статус проекта</h2>
          <p className="rs-sub">
            Свидетельства и документы, подтверждающие правовой статус сервиса.
            Нажмите на документ, чтобы рассмотреть его полностью.
          </p>
        </div>

        <div className="rs-docs">
          {docs.map((d, i) => (
            <button
              type="button"
              className="rs-doc"
              key={d.id}
              style={{ animationDelay: `${Math.min(i, 7) * 60}ms` }}
              onClick={() => setActive(d)}
              aria-label={`Открыть документ: ${d.caption}`}
            >
              <span className="rs-doc__thumb">
                <img src={d.image_url} alt={d.caption} loading="lazy" />
              </span>
              <span className="rs-doc__caption">{d.caption}</span>
            </button>
          ))}
        </div>
      </div>

      {active && (
        <div
          className="rs-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={active.caption}
          onClick={close}
        >
          <button
            type="button"
            className="rs-lightbox__close"
            onClick={close}
            aria-label="Закрыть"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path
                d="M6 6l12 12M18 6L6 18"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
          {/* Клик по самой картинке не должен закрывать окно — гасим всплытие */}
          <figure
            className="rs-lightbox__figure"
            onClick={(e) => e.stopPropagation()}
          >
            <img src={active.image_url} alt={active.caption} />
            <figcaption>{active.caption}</figcaption>
          </figure>
        </div>
      )}
    </section>
  );
}
