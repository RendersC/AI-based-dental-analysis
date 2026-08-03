/**
 * График динамики оценок гигиены — чистый SVG без сторонних библиотек.
 * Шкала Y фиксированная 0..10 (оценка модели). По X — анализы в порядке дат.
 * Принимает { points: [{id, date, score}], summary } из /analysis/dynamics/.
 */

const BRAND = '#00548d'

// В динамике участвуют только анализы с индикатором: балл выводится из измеренной
// площади налёта, а в экспресс-оценке баллов нет вообще. Без этой подписи человек,
// сделавший экспресс, не понимает, почему график не сдвинулся.
const EXPRESS_NOTE = 'Экспресс-оценки в графике не учитываются: в них нет балла. В динамику попадают только анализы с индикатором.'

function formatDate(iso) {
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function TrendBadge({ change, trend }) {
  if (change === null || trend === 'none') return null
  const up = trend === 'up'
  const flat = trend === 'flat'
  const color = flat ? '#6E7785' : up ? '#1f8a4c' : '#ba1a1a'
  const sign = change > 0 ? '+' : ''
  const label = flat ? 'без изменений' : `${sign}${change} балла`
  const arrow = flat ? '→' : up ? '↑' : '↓'
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded"
      style={{ color, background: `${color}14` }}>
      {arrow} {label}
    </span>
  )
}

export default function DynamicsChart({ data }) {
  if (!data) return null
  const { points = [], summary = {} } = data

  // Нужно минимум 2 валидных анализа, чтобы линия имела смысл.
  if (points.length < 2) {
    return (
      <div className="ds-card">
        <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase mb-3"
          style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Динамика гигиены</h3>
        <p className="text-sm text-on-surface-variant">
          {points.length === 0
            ? 'Здесь появится график динамики после первых анализов с индикатором.'
            : 'Нужен ещё хотя бы один анализ с индикатором, чтобы построить динамику. Сделайте следующий анализ — и увидите, как меняется оценка.'}
        </p>
        <p className="text-[11px] text-on-surface-variant mt-2">
          {EXPRESS_NOTE}
        </p>
      </div>
    )
  }

  // Геометрия viewBox: рисуем в координатах 0..W x 0..H, SVG масштабируется по ширине.
  const W = 320
  const H = 180
  const padL = 26   // место под подписи оси Y
  const padR = 10
  const padT = 12
  const padB = 26   // место под подписи оси X
  const plotW = W - padL - padR
  const plotH = H - padT - padB

  const n = points.length
  const x = (i) => padL + (n === 1 ? plotW / 2 : (plotW * i) / (n - 1))
  const y = (score) => padT + plotH * (1 - score / 10)

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(p.score)}`).join(' ')
  // Заливка под линией: замыкаем путь по нижней границе.
  const areaPath = `${linePath} L ${x(n - 1)} ${padT + plotH} L ${x(0)} ${padT + plotH} Z`

  const yTicks = [0, 2, 4, 6, 8, 10]

  return (
    <div className="ds-card">
      <div className="flex items-center justify-between gap-2 mb-3">
        <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
          style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>Динамика гигиены</h3>
        <TrendBadge change={summary.change} trend={summary.trend} />
      </div>

      {/* Сводка */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        {[
          { label: 'Сейчас', value: summary.last },
          { label: 'Лучший', value: summary.best },
          { label: 'Средний', value: summary.average },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg px-2 py-2 text-center"
            style={{ background: '#f2f4f6', border: '1px solid #E2E8F0' }}>
            <p className="text-[10px] font-semibold tracking-wider text-on-surface-variant uppercase"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>{label}</p>
            <p className="text-lg font-bold mt-0.5" style={{ fontFamily: "'Geist', 'Inter', system-ui", color: BRAND }}>
              {value ?? '—'}
            </p>
          </div>
        ))}
      </div>

      {/* График */}
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ overflow: 'visible' }}
        role="img" aria-label="График динамики оценок гигиены">
        <defs>
          <linearGradient id="dynArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={BRAND} stopOpacity="0.22" />
            <stop offset="100%" stopColor={BRAND} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Сетка + подписи Y */}
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={padL} y1={y(t)} x2={W - padR} y2={y(t)}
              stroke="#E2E8F0" strokeWidth="1" />
            <text x={padL - 6} y={y(t) + 3} textAnchor="end"
              fontSize="9" fill="#9aa3b2" fontFamily="system-ui">{t}</text>
          </g>
        ))}

        {/* Заливка и линия */}
        <path d={areaPath} fill="url(#dynArea)" />
        <path d={linePath} fill="none" stroke={BRAND} strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" />

        {/* Точки + подписи X (дату показываем у первой, последней и при <=5 точках у всех) */}
        {points.map((p, i) => {
          const showDate = n <= 5 || i === 0 || i === n - 1
          return (
            <g key={p.id}>
              <circle cx={x(i)} cy={y(p.score)} r="3" fill="#fff" stroke={BRAND} strokeWidth="2" />
              {showDate && (
                <text x={x(i)} y={H - 8} textAnchor="middle"
                  fontSize="8" fill="#9aa3b2" fontFamily="system-ui">{formatDate(p.date)}</text>
              )}
            </g>
          )
        })}
      </svg>

      <p className="text-[11px] text-on-surface-variant mt-2">
        Оценка по 10-балльной шкале. {EXPRESS_NOTE}
      </p>
    </div>
  )
}
