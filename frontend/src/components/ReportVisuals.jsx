// Визуальные элементы отчёта анализа с индикатором. Вынесены отдельно, потому что
// их показывает и настоящий отчёт (ResultPage), и демо-пример после экспресс-оценки
// (SampleReportPreview) — пример должен выглядеть ровно так же, как реальный отчёт.

export function ScoreGauge({ score }) {
  const pct = ((score || 0) / 10) * 100
  const color = score >= 7 ? '#006971' : score >= 4 ? '#FDCB12' : '#ba1a1a'
  const circumference = 2 * Math.PI * 40
  const offset = circumference - (pct / 100) * circumference

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-28 h-28">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#E2E8F0" strokeWidth="10" />
          <circle
            cx="50" cy="50" r="40" fill="none"
            stroke={color} strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 1s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold" style={{ fontFamily: "'Geist', 'Inter', system-ui", color }}>
            {score ?? '—'}
          </span>
          <span className="text-xs text-on-surface-variant">из 10</span>
        </div>
      </div>
      <p className="text-xs text-on-surface-variant mt-2">
        {score >= 8 ? 'Отличная гигиена' : score >= 6 ? 'Хорошая гигиена' : score >= 4 ? 'Требует внимания' : 'Плохая гигиена'}
      </p>
    </div>
  )
}

export function PlaqueBar({ label, value, color }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-on-surface-variant">{label}</span>
        <span className="font-medium text-on-surface" style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>{value ?? 0}%</span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: '#E2E8F0' }}>
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${value ?? 0}%`, background: color }}
        />
      </div>
    </div>
  )
}
