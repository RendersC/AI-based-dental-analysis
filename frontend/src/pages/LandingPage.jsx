import { useCallback, useEffect, useRef, useState } from "react";
import Lottie from "lottie-react";
import { Warp } from "@paper-design/shaders-react";
import OfficialDocs from "../components/OfficialDocs";
import "./LandingPage.css";

// Lottie-анимации (положены в src/assets/lotties)
import stepColor from "../assets/lotties/step-color.json";
import stepPhoto from "../assets/lotties/step-photo.json";
import toothSparkle from "../assets/lotties/tooth-sparkle.json";
import stepReport from "../assets/lotties/step-report.json";
import dataSecurity from "../assets/lotties/data-security.json";

/* ============================================================
   Маленькие иконки (inline SVG, тонкая обводка)
   ============================================================ */
const Icon = {
  check: (p) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  telegram: (p) => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" {...p}>
      <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71l-4.13-3.05-1.98 1.93c-.23.23-.42.42-.86.42z" />
    </svg>
  ),
  vk: (p) => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" {...p}>
      <path d="M12.79 15.7h.96s.29-.03.44-.19c.14-.15.13-.42.13-.42s-.02-1.28.58-1.47c.59-.19 1.34 1.24 2.14 1.79.6.42 1.06.32 1.06.32l2.13-.03s1.11-.07.58-.94c-.04-.07-.31-.65-1.6-1.84-1.35-1.25-1.17-1.05.46-3.21.99-1.32 1.39-2.12 1.26-2.46-.12-.33-.84-.24-.84-.24l-2.4.01s-.18-.02-.31.06c-.13.08-.21.26-.21.26s-.38 1.01-.88 1.87c-1.07 1.8-1.49 1.9-1.66 1.79-.4-.26-.3-1.05-.3-1.61 0-1.76.27-2.49-.52-2.68-.26-.06-.46-.1-1.13-.11-.86-.01-1.59 0-2 .2-.27.13-.49.43-.36.45.16.02.53.1.72.37.25.35.24 1.14.24 1.14s.15 2.13-.34 2.4c-.34.18-.8-.19-1.75-1.83-.49-.84-.86-1.77-.86-1.77s-.07-.17-.2-.27c-.15-.11-.37-.14-.37-.14l-2.28.01s-.34.01-.47.16c-.11.13-.01.41-.01.41s1.79 4.11 3.81 6.18c1.86 1.9 3.97 1.78 3.97 1.78z" />
    </svg>
  ),
  arrow: (p) => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M7 17L17 7M9 7h8v8" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  gauge: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M5 19a9 9 0 1 1 14 0" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" />
      <path d="M12 13l4-4" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" />
      <circle cx="12" cy="13" r="1.6" fill="currentColor" />
    </svg>
  ),
  drop: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M12 3.5s6 6.4 6 10.2A6 6 0 1 1 6 13.7C6 9.9 12 3.5 12 3.5z"
        stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  ),
  target: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="2" />
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
    </svg>
  ),
  list: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M9 6h11M9 12h11M9 18h11" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" />
      <circle cx="4.5" cy="6" r="1.4" fill="currentColor" />
      <circle cx="4.5" cy="12" r="1.4" fill="currentColor" />
      <circle cx="4.5" cy="18" r="1.4" fill="currentColor" />
    </svg>
  ),
  trend: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M4 16l5-5 3 3 7-7" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15 7h5v5" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  chat: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9l-4 3.5V16H6a2 2 0 0 1-2-2V6z"
        stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  ),
  shield: (p) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z"
        stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  ),
  lock: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <rect x="5" y="10" width="14" height="10" rx="2.5"
        stroke="currentColor" strokeWidth="2" />
      <path d="M8 10V7.5a4 4 0 0 1 8 0V10" stroke="currentColor" strokeWidth="2" />
    </svg>
  ),
  doc: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M7 3h7l4 4v14H7z" stroke="currentColor" strokeWidth="2"
        strokeLinejoin="round" />
      <path d="M14 3v4h4M9.5 13h5M9.5 16.5h5" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  clock: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="2" />
      <path d="M12 7.5V12l3 2" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  globe: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="2" />
      <path d="M3.5 12h17M12 3.5c2.6 3 2.6 14 0 17M12 3.5c-2.6 3-2.6 14 0 17"
        stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  user: (p) => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="2" />
      <path d="M5 20a7 7 0 0 1 14 0" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" />
    </svg>
  ),
  chevron: (p) => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" {...p}>
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  info: (p) => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" {...p}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
      <path d="M12 11v5M12 8.2v.1" stroke="currentColor" strokeWidth="2.2"
        strokeLinecap="round" />
    </svg>
  ),
};

/* ============================================================
   Hook: появление при скролле
   ============================================================ */
function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-in");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    el.querySelectorAll(".rs-reveal").forEach((n) => io.observe(n));
    return () => io.disconnect();
  }, []);
  return ref;
}

/* ============================================================
   Hero-визуал: слайдер «до / после» окрашивания индикатором
   ============================================================ */
function BeforeAfter() {
  const [pos, setPos] = useState(52);
  const [drag, setDrag] = useState(false);
  const wrapRef = useRef(null);

  const move = useCallback((clientX) => {
    const el = wrapRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const next = Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100));
    setPos(next);
  }, []);

  useEffect(() => {
    if (!drag) return;
    const onMove = (e) => move(e.touches ? e.touches[0].clientX : e.clientX);
    const onUp = () => setDrag(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("touchmove", onMove, { passive: true });
    window.addEventListener("touchend", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("touchmove", onMove);
      window.removeEventListener("touchend", onUp);
    };
  }, [drag, move]);

  const onKey = (e) => {
    if (e.key === "ArrowLeft") setPos((p) => Math.max(0, p - 4));
    if (e.key === "ArrowRight") setPos((p) => Math.min(100, p + 4));
    if (e.key === "Home") setPos(0);
    if (e.key === "End") setPos(100);
  };

  return (
    <div className="rs-ba" ref={wrapRef}>
      <img
        className="rs-ba__img rs-ba__img--base"
        src="/hero-teeth-after.jpg"
        alt="Зубы после чистки — без налёта"
        draggable="false"
      />
      <div className="rs-ba__top" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
        <img
          className="rs-ba__img"
          src="/hero-teeth-before.jpg"
          alt="Зубы, окрашенные индикатором налёта"
          draggable="false"
        />
      </div>

      <span className="rs-ba__label rs-ba__label--left">До</span>
      <span className="rs-ba__label rs-ba__label--right">После</span>

      <div
        className={"rs-ba__handle" + (drag ? " is-dragging" : "")}
        style={{ left: `${pos}%` }}
        onMouseDown={(e) => { e.preventDefault(); setDrag(true); }}
        onTouchStart={() => setDrag(true)}
      >
        <div
          className="rs-ba__knob"
          role="slider"
          tabIndex={0}
          aria-label="Сравнение зубов до и после чистки"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pos)}
          onKeyDown={onKey}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M9 6l-4 6 4 6M15 6l4 6-4 6" stroke="currentColor"
              strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Данные секций
   ============================================================ */
const STEPS = [
  {
    art: stepColor,
    title: "Используйте индикатор налёта",
    text: "Безопасный пищевой краситель окрасит зубной налёт в яркие цвета.",
  },
  {
    art: stepPhoto,
    title: "Сделайте фото",
    text: "Сфотографируйте зубы крупным планом при хорошем освещении. Подробная инструкция — в личном кабинете.",
  },
  {
    art: toothSparkle,
    title: "ИИ проанализирует окрашенные зоны",
    text: "Алгоритм определит площадь налёта и зоны с большим количеством налёта, оценит уровень гигиены.",
  },
  {
    art: stepReport,
    title: "Получите результат",
    text: "Оценка от 1 до 10, описание состояния и три совета по уходу. История анализов сохраняется — отслеживайте динамику.",
  },
];

const BENEFITS = [
  {
    ico: Icon.clock,
    title: "Быстро",
    text: "Несколько минут — и результат готов.",
  },
  {
    ico: Icon.globe,
    title: "Без приложений",
    text: "Работает прямо в браузере телефона.",
  },
  {
    ico: Icon.trend,
    title: "С историей",
    text: "Все проверки сохраняются, видна динамика.",
  },
  {
    ico: Icon.user,
    title: "Самостоятельно",
    text: "Вы делаете это сами, когда удобно вам.",
  },
];

/* Список 13 вопросов FAQ */
const FAQ = [
  {
    q: "Это медицинская диагностика?",
    a: "Нет. РАДУГА УЛЫБОК — информационно-образовательный сервис. Мы не ставим диагнозы и не заменяем визит к стоматологу. Все рекомендации носят общий характер.",
  },
  {
    q: "Насколько точны рекомендации?",
    a: "Сервис даёт общую информационную оценку гигиены на основе фото и не заменяет осмотр стоматолога. Для точной диагностики обратитесь к врачу.",
  },
  {
    q: "Подходит ли сервис детям?",
    a: "Да, сервис подходит для всей семьи. Детям рекомендуем делать фото вместе с родителями.",
  },
  {
    q: "Как часто делать анализ?",
    a: "Оптимально — 1 раз в неделю, но ограничений нет.",
  },
  {
    q: "Где купить индикаторы?",
    a: "В любой аптеке или на маркетплейсах.",
  },
  {
    q: "Это безопасно?",
    a: "Да, индикаторы сделаны на основе пищевых красителей и одобрены для использования детьми и взрослыми.",
  },
  {
    q: "Можно ли использовать сервис без индикатора?",
    a: "Нет. ИИ анализирует именно окрашенные зоны налёта. Без индикатора на фото не будет данных для анализа.",
  },
  {
    q: "Окрасится ли язык?",
    a: "Да, может окраситься. Эффект временный.",
  },
  {
    q: "Нужны ли специальные условия для фото?",
    a: "Хорошее освещение (лучше дневное) и крупный план. Подробные инструкции в личном кабинете.",
  },
  {
    q: "Что с моими фотографиями?",
    a: "Фото доступны только вам в личном кабинете. Мы не передаём их третьим лицам и используем исключительно для анализа. Вы можете удалить снимки в любой момент.",
  },
  {
    q: "Сколько стоит?",
    a: "При регистрации вы получаете бесплатные попытки. Сейчас проект на этапе развития и работает полностью бесплатно. Когда попытки закончатся, напишите администратору на электронную почту — мы добавим новые.",
  },
  {
    q: "Нужно скачивать приложение?",
    a: "Нет. Сервис открывается прямо в браузере телефона.",
  },
];

/* Чек-пункты для блока про индикаторы */
const INDICATOR_FACTS = [
  "Безопасны (одобрены для детей)",
  "Продаются в аптеках и маркетплейсах",
  "Окрашивают только налёт, не эмаль",
  "Цвет смывается после чистки",
];

/* бренд-конфиги шейдера Warp (розовый / фиолет / циан, тон в тон с палитрой) */
const BENEFIT_SHADERS = [
  {
    proportion: 0.35, softness: 0.9, distortion: 0.16, swirl: 0.7,
    swirlIterations: 10, shape: "checks", shapeScale: 0.1,
    colors: ["hsl(272,72%,26%)", "hsl(330,82%,56%)", "hsl(300,70%,44%)", "hsl(320,90%,68%)"],
  },
  {
    proportion: 0.42, softness: 1.1, distortion: 0.2, swirl: 0.85,
    swirlIterations: 12, shape: "dots", shapeScale: 0.12,
    colors: ["hsl(205,80%,22%)", "hsl(193,78%,55%)", "hsl(210,70%,40%)", "hsl(188,88%,68%)"],
  },
  {
    proportion: 0.38, softness: 0.95, distortion: 0.18, swirl: 0.75,
    swirlIterations: 11, shape: "checks", shapeScale: 0.11,
    colors: ["hsl(330,78%,28%)", "hsl(340,86%,58%)", "hsl(315,75%,44%)", "hsl(345,92%,70%)"],
  },
  {
    proportion: 0.44, softness: 1.05, distortion: 0.21, swirl: 0.8,
    swirlIterations: 13, shape: "dots", shapeScale: 0.1,
    colors: ["hsl(262,74%,26%)", "hsl(250,76%,55%)", "hsl(210,70%,44%)", "hsl(193,86%,66%)"],
  },
];

const TRUST = [
  {
    ico: Icon.lock,
    title: "Данные под защитой",
    text: "Передача и хранение по защищённым каналам с шифрованием. Доступ только у вас.",
  },
  {
    ico: Icon.shield,
    title: "Соответствие 152-ФЗ",
    text: "Обработка персональных данных по требованиям закона РФ «О персональных данных».",
  },
  {
    ico: Icon.doc,
    title: "Конфиденциальность фото",
    text: "Снимки используются только для анализа и не передаются третьим лицам.",
  },
];

const FOOTER_MENU = [
  {
    title: "Продукт",
    links: [
      { text: "Как это работает", url: "#how", id: "how" },
      { text: "Индикаторы налёта", url: "#indicators", id: "indicators" },
      { text: "Удобно и доступно", url: "#features", id: "features" },
      { text: "Частые вопросы", url: "#faq", id: "faq" },
    ],
  },
  {
    title: "Аккаунт",
    links: [
      { text: "Войти", url: "/login" },
      { text: "Регистрация", url: "/register" },
    ],
  },
  {
    title: "Контакты",
    links: [
      { text: "support@radugaulybok-dent.ru", url: "mailto:support@radugaulybok-dent.ru" },
    ],
  },
];

const FOOTER_DOCS = [
  { text: "Пользовательское соглашение", url: "/docs/terms.html" },
  { text: "Политика конфиденциальности", url: "/docs/privacy.html" },
  { text: "Согласие на обработку персональных данных", url: "/docs/personal-data-consent.html" },
  { text: "Согласие на обработку данных о здоровье", url: "/docs/health-data-consent.html" },
  { text: "Согласие на обработку данных ребёнка", url: "/docs/child-consent.html" },
  { text: "Согласие на трансграничную передачу данных", url: "/docs/cross-border-consent.html" },
  { text: "Политика использования cookie", url: "/docs/cookie-policy.html" },
];

/* ============================================================
   Аккордеон FAQ
   ============================================================ */
function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={"rs-faq__item" + (open ? " is-open" : "")}>
      <button
        type="button"
        className="rs-faq__q"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="rs-faq__qtext">{q}</span>
        <span className="rs-faq__chev" aria-hidden="true">{Icon.chevron()}</span>
      </button>
      <div className="rs-faq__a">
        <div className="rs-faq__ainner">
          <p>{a}</p>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Логотип (SVG из public/logo.svg)
   ============================================================ */
function BrandLogo() {
  return (
    <a className="rs-brand" href="/" aria-label="Радуга Улыбок — на главную">
      <img className="rs-brand__logo" src="/logo-mark.svg" alt="" aria-hidden="true" />
      <span className="rs-brand__name">Радуга&nbsp;Улыбок</span>
    </a>
  );
}

/* ============================================================
   Главный компонент
   ============================================================ */
export default function LandingPage() {
  const rootRef = useReveal();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const scrollTo = (e, id) => {
    e.preventDefault();
    setOpen(false);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="rs-root" ref={rootRef}>
      {/* ---------- Шапка ---------- */}
      <header
        className={
          "rs-header" +
          (scrolled ? " rs-header--scrolled" : "") +
          (open ? " rs-header--open" : "")
        }
      >
        <nav className="rs-nav">
          <BrandLogo />
          <div className="rs-nav__links">
            <a className="rs-btn rs-btn--link" href="#how"
              onClick={(e) => scrollTo(e, "how")}>
              Как это работает
            </a>
            <a className="rs-btn rs-btn--link" href="#features"
              onClick={(e) => scrollTo(e, "features")}>
              Возможности
            </a>
            <a className="rs-btn rs-btn--ghost" href="/login">Войти</a>
            <a className="rs-btn rs-btn--colorful" href="/register">
              <span className="rs-btn__c">Начать бесплатно {Icon.arrow()}</span>
            </a>
          </div>
          <button
            className="rs-burger"
            aria-label={open ? "Закрыть меню" : "Открыть меню"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <span />
            <span />
            <span />
          </button>
        </nav>

        <div className={"rs-mobile" + (open ? " is-open" : "")}>
          <div className="rs-mobile__inner">
            <div className="rs-mobile__links">
              <a href="#how" onClick={(e) => scrollTo(e, "how")}>
                Как это работает
              </a>
              <a href="#features" onClick={(e) => scrollTo(e, "features")}>
                Возможности
              </a>
              <a href="#security" onClick={(e) => scrollTo(e, "security")}>
                Безопасность
              </a>
            </div>
            <div className="rs-mobile__cta">
              <a className="rs-btn rs-btn--ghost rs-btn--lg" href="/login">
                Войти
              </a>
              <a className="rs-btn rs-btn--colorful rs-btn--lg" href="/register">
                <span className="rs-btn__c">Начать бесплатно {Icon.arrow()}</span>
              </a>
            </div>
          </div>
        </div>
      </header>

      <main>
        {/* ---------- HERO ---------- */}
        <section className="rs-hero">
          <div className="rs-container rs-hero__grid">
            <div className="rs-hero__copy rs-reveal">
              <h1 className="rs-hero__title">
                Узнайте, как вы чистите зубы&nbsp;
                <span className="rs-accent-text">на&nbsp;самом деле</span>
              </h1>
              <p className="rs-hero__lead">
                ИИ оценит ваш зубной налёт и подскажет, что улучшить.
              </p>
              <div className="rs-hero__cta">
                <a className="rs-btn rs-btn--colorful rs-btn--lg" href="/register">
                  <span className="rs-btn__c">Попробовать бесплатно {Icon.arrow()}</span>
                </a>
                <a className="rs-btn rs-btn--ghost rs-btn--lg" href="#how"
                  onClick={(e) => scrollTo(e, "how")}>
                  Как это работает
                </a>
              </div>
              <div className="rs-hero__meta">
                <span className="rs-hero__meta-item">
                  <span className="rs-check">{Icon.check()}</span>
                  Бесплатные попытки при регистрации
                </span>
                <span className="rs-hero__meta-item">
                  <span className="rs-check">{Icon.check()}</span>
                  Работает в браузере
                </span>
              </div>
              <p className="rs-hero__disclaimer">
                <span className="rs-hero__disclaimer-ico" aria-hidden="true">
                  {Icon.info()}
                </span>
                <span>
                  Сервис носит информационно-образовательный характер и не
                  является медицинской услугой.
                </span>
              </p>
            </div>

            <div className="rs-reveal">
              <BeforeAfter />
            </div>
          </div>
        </section>

        {/* ---------- Как это работает ---------- */}
        <section className="rs-section rs-section--wash" id="how">
          <div className="rs-container">
            <div className="rs-section__head rs-reveal">
              <span className="rs-eyebrow">Как это работает</span>
              <h2 className="rs-h2">Всё просто — 4 шага</h2>
            </div>
            <div className="rs-steps">
              {STEPS.map((s, i) => (
                <div className="rs-step rs-reveal" key={i}
                  style={{ transitionDelay: `${i * 70}ms` }}>
                  <span className="rs-step__num">ШАГ {i + 1}</span>
                  <div className="rs-step__art">
                    <Lottie animationData={s.art} loop autoplay />
                  </div>
                  <h3 className="rs-step__title">{s.title}</h3>
                  <p className="rs-step__text">{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------- Что такое индикаторы налёта ---------- */}
        <section className="rs-section" id="indicators">
          <div className="rs-container">
            <div className="rs-section__head rs-reveal">
              <span className="rs-eyebrow">Что такое индикаторы налёта</span>
              <h2 className="rs-h2">Простой способ увидеть зубной налёт</h2>
              <p className="rs-sub">
                Индикаторы налёта — безопасный продукт, который применяют в стоматологии
                по всему миру.
              </p>
            </div>

            <div className="rs-indi rs-reveal">
              <div className="rs-indi__media">
                <figure className="rs-indi__fig">
                  <img src="/indicator-teeth.jpg" alt="Зубы, окрашенные индикатором налёта" />
                  <figcaption>Так выглядит налёт после окрашивания индикатором</figcaption>
                </figure>
                <figure className="rs-indi__fig rs-indi__fig--diagram">
                  <img src="/indicator-diagram.jpg?v=2" alt="Расшифровка цветов индикатора налёта" />
                  <figcaption>Розовый — мягкий налёт, синий — зрелый налёт</figcaption>
                </figure>
              </div>

              <div className="rs-indi__body">
                <p className="rs-indi__lead">
                  Индикаторы зубного налёта — это безопасные пищевые красители, которые
                  окрашивают зубной налёт в яркие цвета. Существуют разные формы выпуска:
                  таблетки, растворы, палочки для индикации. Применяются в стоматологии по
                  всему миру уже много лет.
                </p>

                <ul className="rs-indi__facts">
                  {INDICATOR_FACTS.map((t, i) => (
                    <li key={i}>
                      <span className="rs-indi__check">{Icon.check()}</span>
                      {t}
                    </li>
                  ))}
                </ul>

                <p className="rs-indi__brands">
                  <strong>Примеры:</strong> Mira-2-Ton (Miradent), Curaprox, DENNEO.
                </p>

                <figure className="rs-indi__products">
                  <img
                    src="/indicator-products.jpg"
                    alt="Примеры индикаторов налёта: Plaque Indicator, Blueberry Plaque Test (DENNEO), mira-2-ton (Miradent)"
                  />
                </figure>

                <div className="rs-indi__note">
                  <span className="rs-indi__noteIco">{Icon.info()}</span>
                  <p>
                    <strong>Важно:</strong> для корректного анализа используйте
                    двухцветные индикаторы, окрашивающие налёт в два цвета —
                    <span className="rs-indi__pink"> розовый</span> (мягкий налёт) и
                    <span className="rs-indi__blue"> синий</span> (зрелый налёт).
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------- Экспресс-оценка ---------- */}
        {/* Стоит сразу после блока про индикаторы: отвечает на возражение,
            которое там же и возникает — «а если индикатора нет под рукой». */}
        <section className="rs-section" id="express">
          <div className="rs-container">
            <div className="rs-express rs-reveal">
              <div className="rs-express__body">
                <span className="rs-eyebrow">Экспресс-оценка</span>
                <h2 className="rs-h2">
                  Нет индикатора налёта под&nbsp;рукой? Начните с&nbsp;экспресс-оценки
                </h2>
                <p className="rs-sub rs-express__sub">
                  Сразу после регистрации вам будет доступна базовая оценка гигиены полости
                  рта. Узнайте результат за пару минут!
                </p>
                <div className="rs-express__cta">
                  <a className="rs-btn rs-btn--colorful rs-btn--lg" href="/register">
                    <span className="rs-btn__c">Пройти экспресс-оценку {Icon.arrow()}</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------- Почему удобно ---------- */}
        <section className="rs-section rs-section--wash" id="features">
          <div className="rs-container">
            <div className="rs-section__head rs-reveal">
              <span className="rs-eyebrow">Почему удобно</span>
              <h2 className="rs-h2">Удобно и доступно</h2>
              <p className="rs-sub">
                Простая проверка гигиены — без врачей, приложений и ожидания.
              </p>
            </div>
            <div className="rs-benefits rs-benefits--4">
              {BENEFITS.map((b, i) => {
                const sh = BENEFIT_SHADERS[i % BENEFIT_SHADERS.length];
                return (
                  <div className="rs-bcard rs-reveal" key={i}
                    style={{ transitionDelay: `${(i % 2) * 80}ms` }}>
                    <div className="rs-bcard__shader">
                      <Warp
                        style={{ height: "100%", width: "100%" }}
                        proportion={sh.proportion}
                        softness={sh.softness}
                        distortion={sh.distortion}
                        swirl={sh.swirl}
                        swirlIterations={sh.swirlIterations}
                        shape={sh.shape}
                        shapeScale={sh.shapeScale}
                        scale={1}
                        rotation={0}
                        speed={0.6}
                        colors={sh.colors}
                      />
                    </div>
                    <div className="rs-bcard__body">
                      <span className="rs-bcard__ico">{b.ico()}</span>
                      <h3 className="rs-bcard__title">{b.title}</h3>
                      <p className="rs-bcard__text">{b.text}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ---------- Доверие / безопасность ---------- */}
        <section className="rs-section rs-section--wash" id="security">
          <div className="rs-container rs-trust">
            <div className="rs-trust__art rs-reveal">
              <div className="rs-shield">
                <Lottie animationData={dataSecurity} loop autoplay />
              </div>
            </div>
            <div className="rs-reveal">
              <span className="rs-eyebrow">Безопасность</span>
              <h2 className="rs-h2">Ваши данные остаются вашими</h2>
              <p className="rs-sub" style={{ margin: "14px 0 0", maxWidth: 460 }}>
                Мы относимся к фотографиям и персональным данным с особой
                ответственностью.
              </p>
              <ul className="rs-trust__list">
                {TRUST.map((t, i) => (
                  <li className="rs-trust__item" key={i}>
                    <span className="rs-trust__check">{Icon.check()}</span>
                    <div>
                      <h4>{t.title}</h4>
                      <p>{t.text}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ---------- FAQ ---------- */}
        <section className="rs-section rs-section--wash" id="faq">
          <div className="rs-container">
            <div className="rs-section__head rs-reveal">
              <span className="rs-eyebrow">FAQ</span>
              <h2 className="rs-h2">Частые вопросы</h2>
            </div>
            <div className="rs-faq rs-reveal">
              {FAQ.map((f, i) => (
                <FaqItem key={i} q={f.q} a={f.a} />
              ))}
            </div>
            <p className="rs-faq__foot rs-reveal">
              Остались вопросы? Напишите администратору:{" "}
              <a href="mailto:support@radugaulybok-dent.ru">
                support@radugaulybok-dent.ru
              </a>
            </p>
          </div>
        </section>

        {/* ---------- Финальный CTA ---------- */}
        <section className="rs-section">
          <div className="rs-container">
            <div className="rs-finalcta rs-reveal">
              <div className="rs-finalcta__inner">
                <h2>Готовы позаботиться о своей улыбке?</h2>
                <p>
                  Регистрация занимает меньше минуты — и сразу доступны бесплатные
                  проверки. Без приложений и сложностей.
                </p>
                <div className="rs-finalcta__cta">
                  <a className="rs-btn rs-btn--colorful rs-btn--lg" href="/register">
                    <span className="rs-btn__c">Начать бесплатно {Icon.arrow()}</span>
                  </a>
                  <a className="rs-btn rs-btn--ondark rs-btn--lg" href="/login">
                    У меня уже есть аккаунт
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------- Официальный статус проекта ----------
            Контент ведёт админ; если документов нет — компонент ничего не рисует */}
        <OfficialDocs />
      </main>

      {/* ---------- Футер ---------- */}
      <footer className="rs-footer">
        <div className="rs-container">
          <div className="rs-footer__grid">
            <div className="rs-footer__brand">
              <BrandLogo />
              <p className="rs-footer__tagline">
                ИИ-помощник для контроля гигиены полости рта.
              </p>
              <div className="rs-footer__social">
                <a
                  className="rs-footer__soc"
                  href="https://t.me/radugaulybok_dent"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Telegram"
                >
                  {Icon.telegram()}
                </a>
                <a
                  className="rs-footer__soc"
                  href="https://vk.com/club239855392"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="ВКонтакте"
                >
                  {Icon.vk()}
                </a>
              </div>
            </div>

            {FOOTER_MENU.map((section, i) => (
              <div className="rs-footer__col" key={i}>
                <h3>{section.title}</h3>
                <ul>
                  {section.links.map((link, j) => (
                    <li key={j}>
                      {link.id ? (
                        <a href={link.url}
                          onClick={(e) => scrollTo(e, link.id)}>
                          {link.text}
                        </a>
                      ) : (
                        <a href={link.url}>{link.text}</a>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}

            <div className="rs-footer__col rs-footer__col--docs">
              <h3>Документы</h3>
              <ul>
                {FOOTER_DOCS.map((d, i) => (
                  <li key={i}>
                    <a href={d.url} target="_blank" rel="noopener noreferrer">{d.text}</a>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <p className="rs-footer__legal">
            Сервис носит информационно-образовательный характер и не заменяет
            консультацию врача-стоматолога.
          </p>

          <div className="rs-footer__bottom">
            <p>© {new Date().getFullYear()} Радуга Улыбок. Все права защищены.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
