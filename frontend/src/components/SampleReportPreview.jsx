import { useNavigate } from 'react-router-dom'
import { ScoreGauge, PlaqueBar } from './ReportVisuals'

// Демо-пример полного отчёта, который показываем после экспресс-оценки.
//
// ВАЖНО: это ОБРАЗЕЦ, а не результат по фото пользователя, и он честно так подписан.
// Построить настоящий отчёт по фото из экспресс-оценки невозможно: без индикатора
// налёт не окрашен, измерять нечего. Цифры ниже — вымышленные, они лишь показывают,
// как выглядит отчёт после анализа с индикатором.
const SAMPLE = {
  score: 6,
  fresh: 22,
  old: 12,
  zones: [
    'межзубные промежутки нижних резцов',
    'пришеечная область верхних моляров',
  ],
  recommendations: [
    'Чистите межзубные промежутки зубной нитью каждый вечер',
    'Уделяйте жевательным зубам по 10 секунд с каждой стороны',
    'Используйте технику Басса: щётка под углом 45° к линии дёсен',
  ],
}

export default function SampleReportPreview() {
  const navigate = useNavigate()

  return (
    <div className="ds-card" style={{ borderColor: '#c1c7d2' }}>
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <h3 className="text-xs font-semibold tracking-widest text-on-surface-variant uppercase"
          style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
          Как выглядит полный отчёт
        </h3>
        <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
          style={{ background: '#fff8e1', color: '#8a6100', border: '1px solid #f6cf6c' }}>
          ПРИМЕР
        </span>
      </div>
      <p className="text-xs text-on-surface-variant mb-4">
        Это образец, а не оценка вашего фото. Такой отчёт вы получите после анализа
        с индикатором налёта — с точными цифрами, проблемными зонами и динамикой.
      </p>

      {/* Сам образец приглушён, чтобы его нельзя было принять за свой результат */}
      <div style={{ opacity: 0.75, pointerEvents: 'none', userSelect: 'none' }} aria-hidden="true">
        <div className="rounded-lg p-3" style={{ background: '#f7f9fb', border: '1px solid #E2E8F0' }}>
          <div className="flex flex-col sm:flex-row items-center gap-4">
            <ScoreGauge score={SAMPLE.score} />
            <div className="flex-1 w-full space-y-3">
              <PlaqueBar label="Мягкий налёт (розовый)" value={SAMPLE.fresh} color="#F45EAC" />
              <PlaqueBar label="Зрелый налёт (синий)" value={SAMPLE.old} color="#00548d" />
            </div>
          </div>

          <div className="mt-4">
            <p className="text-[10px] font-semibold tracking-widest text-on-surface-variant uppercase mb-2"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              Проблемные зоны
            </p>
            <div className="flex flex-wrap gap-2">
              {SAMPLE.zones.map((zone, i) => (
                <span key={i} className="px-2.5 py-1 rounded-full text-xs font-medium"
                  style={{ background: '#ffdad6', color: '#ba1a1a', fontFamily: "'Geist', 'Inter', system-ui" }}>
                  {zone}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <p className="text-[10px] font-semibold tracking-widest text-on-surface-variant uppercase mb-2"
              style={{ fontFamily: "'Geist', 'Inter', system-ui" }}>
              Рекомендации
            </p>
            <div className="space-y-2">
              {SAMPLE.recommendations.map((rec, i) => (
                <div key={i} className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded flex items-center justify-center text-white font-bold flex-shrink-0 mt-0.5"
                    style={{ background: '#00548d', fontFamily: "'Geist', 'Inter', system-ui", fontSize: '10px' }}>
                    {i + 1}
                  </span>
                  <p className="text-xs text-on-surface leading-relaxed">{rec}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <button onClick={() => navigate('/analysis')} className="ds-btn-primary w-full py-3 mt-4">
        Пройти анализ с индикатором
      </button>
    </div>
  )
}
