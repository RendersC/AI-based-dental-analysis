"""Измерение налёта по цвету индикатора: детерминированный CV-скрипт (OpenCV, HSV).

Зачем: нейросети оценивают проценты налёта «на глаз», и цифры плавают от запуска
к запуску (GigaChat вообще их выдумывает). Скрипт считает пиксели красителя внутри
области зубов — одно и то же фото всегда даёт один и тот же результат. Балл дальше
выводит derive_score() из ai_router, текст пишет активная нейросеть по готовым цифрам.

Принцип: скрипт ищет НЕ зубы вообще, а краситель. Двухцветный индикатор
(Mira-2-Ton и аналоги) даёт насыщенный розово-малиновый (свежий налёт, 1-3 дня)
и сине-фиолетовый (зрелый, 3+ дня) — такой насыщенности во рту больше нет ничего.
Кариес и потемнения эмали тёмные и в диапазоны красителя не попадают, поэтому
налётом не считаются.

HSV в OpenCV: H = 0..179 (не 0..359!), S и V = 0..255. Красный «оборачивается»
через 0, поэтому красно-розовые оттенки требуют двух диапазонов по Hue.

Область зубов ищем классическим CV без нейросети: зубы — крупная светлая
слабонасыщенная область в кадре, плюс сами окрашенные участки (окрашенный зуб
уже не белый). Дёсны/губы/кожа отсекаются по оттенку (красно-оранжевый Hue
с заметной насыщенностью) и по насыщенности.

Все пороги собраны в константах ниже — калибруются на реальных фото
с индикатором, менять в одном месте.
"""
import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Пороги (калибровка) ──────────────────────────────────────────────────────

# Свежий налёт — розовый/малиновый краситель (маджента, H 140..179).
# Узкий «переваливший» через 0 красно-розовый диапазон оставлен с жёсткими
# порогами: здоровые дёсны и межзубные сосочки живут ровно в этих оттенках,
# и отличить их от красителя можно только по высокой насыщенности и яркости.
FRESH_HUE_MAIN = (140, 179)
FRESH_HUE_WRAP = (0, 4)
FRESH_SAT_MIN = 70
FRESH_VAL_MIN = 80
FRESH_WRAP_SAT_MIN = 120
FRESH_WRAP_VAL_MIN = 140

# Зрелый налёт — синий/фиолетовый краситель. Яркость не ниже 80: тени полости
# рта на телефонных фото имеют синеватый оттенок и при низких порогах
# засчитываются как «зрелый налёт» (проверено на реальном фото).
OLD_HUE = (95, 139)
OLD_SAT_MIN = 80
OLD_VAL_MIN = 80

# Эмаль в два уровня строгости.
# ЯКОРЬ — строгий: по-настоящему белая эмаль. Замеры на реальных фото:
# эмаль S=18-25, бледная кожа при розоватом балансе белого S=43-92 — порог 40
# отделяет одно от другого. Если на фото нет ни одного строгого якоря (всё
# закрашено целиком), измерение честно падает в фолбэк на нейросеть.
ANCHOR_SAT_MAX = 40
ANCHOR_VAL_MIN = 140
# РОСТ — мягкий: эмаль рядом с красителем ловит розовый отсвет (замер: «белый»
# резец рядом с пятном имел S≈79), поэтому область дорастает через S до 90.
# Кожа сюда тоже проходит, но путь роста от зубов к коже перекрыт губами
# и дёснами (их S>90) — утечки нет.
ENAMEL_SAT_MAX = 90
ENAMEL_VAL_MIN = 130

# Якорные компоненты эмали: минимальная площадь (доля кадра) и центральное окно,
# в котором должен лежать центроид компоненты. Отсекает светлую одежду у нижнего
# края, лоб/кожу у верхнего и блики на губах.
MIN_COMPONENT_FRAC = 0.002
ANCHOR_CENTER_BOX = (0.12, 0.88)   # допустимый диапазон центроида по обеим осям

# Минимальная суммарная площадь зубов, чтобы измерению можно было верить.
# Меньше — считаем, что зубы не нашлись, и честно отдаём None (фолбэк на LLM).
MIN_TOOTH_FRAC = 0.015

# Цвета подсветки на оверлее (BGR) и прозрачность заливки.
OVERLAY_FRESH_BGR = (180, 60, 255)   # ярко-розовый
OVERLAY_OLD_BGR = (255, 120, 0)      # ярко-синий
OVERLAY_ALPHA = 0.55


@dataclass
class PlaqueMeasurement:
    """Результат измерения по ОДНОМУ фото."""
    ok: bool                      # нашлась ли область зубов достаточного размера
    tooth_pixels: int = 0
    fresh_pixels: int = 0
    old_pixels: int = 0
    overlay_jpeg: Optional[bytes] = None

    @property
    def fresh_percent(self) -> Optional[float]:
        if not self.ok:
            return None
        return round(100.0 * self.fresh_pixels / self.tooth_pixels, 1)

    @property
    def old_percent(self) -> Optional[float]:
        if not self.ok:
            return None
        return round(100.0 * self.old_pixels / self.tooth_pixels, 1)


@dataclass
class PlaqueTotals:
    """Агрегат по набору фото одного анализа: пиксели суммируются, чтобы фото
    крупным планом весило больше, чем снятое издалека (у него больше пикселей зубов)."""
    ok: bool
    fresh_percent: Optional[float] = None
    old_percent: Optional[float] = None
    measurements: List[PlaqueMeasurement] = field(default_factory=list)


def _hue_mask(hsv, hue_range, sat_min, val_min):
    lo = np.array([hue_range[0], sat_min, val_min], dtype=np.uint8)
    hi = np.array([hue_range[1], 255, 255], dtype=np.uint8)
    return cv2.inRange(hsv, lo, hi)


def _dye_masks(hsv):
    """Маски красителя: (свежий розовый, зрелый синий)."""
    fresh = _hue_mask(hsv, FRESH_HUE_MAIN, FRESH_SAT_MIN, FRESH_VAL_MIN)
    fresh |= _hue_mask(hsv, FRESH_HUE_WRAP, FRESH_WRAP_SAT_MIN, FRESH_WRAP_VAL_MIN)
    old = _hue_mask(hsv, OLD_HUE, OLD_SAT_MIN, OLD_VAL_MIN)
    # Пиксель не может быть и свежим и зрелым: на границе диапазонов (H≈140)
    # отдаём приоритет зрелому — фиолетовый ближе к синему красителю.
    fresh &= cv2.bitwise_not(old)
    return fresh, old


def _tooth_mask(hsv, fresh, old):
    """Область зубов через якорь по эмали.

    Цветом отличить окрашенный зуб от окрашенной губы или блестящей десны нельзя —
    краситель одинаковый. Поэтому сначала ищем то, что бывает ТОЛЬКО у зубов:
    светлую слабонасыщенную эмаль (якорные компоненты, крупные и не у края кадра).
    Зубной ряд — выпуклая оболочка якорей; краситель учитывается только внутри неё.
    Губы, кожа, перчатки и фон остаются снаружи, даже если совпали по цвету."""
    h, w = hsv.shape[:2]
    enamel = cv2.inRange(
        hsv,
        np.array([0, 0, ENAMEL_VAL_MIN], dtype=np.uint8),
        np.array([179, ENAMEL_SAT_MAX, 255], dtype=np.uint8),
    )
    anchor_src = cv2.inRange(
        hsv,
        np.array([0, 0, ANCHOR_VAL_MIN], dtype=np.uint8),
        np.array([179, ANCHOR_SAT_MAX, 255], dtype=np.uint8),
    )

    k = max(3, int(min(h, w) * 0.008) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    enamel = cv2.morphologyEx(enamel, cv2.MORPH_OPEN, kernel)
    enamel = cv2.morphologyEx(enamel, cv2.MORPH_CLOSE, kernel)
    anchor_src = cv2.morphologyEx(anchor_src, cv2.MORPH_OPEN, kernel)
    anchor_src = cv2.morphologyEx(anchor_src, cv2.MORPH_CLOSE, kernel)

    # Якоря: крупные компоненты строгой эмали с центроидом не у самого края
    # кадра (светлая одежда, лоб и блики на губах живут у краёв).
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(anchor_src, connectivity=8)
    min_area = int(h * w * MIN_COMPONENT_FRAC)
    lo, hi = ANCHOR_CENTER_BOX
    anchor = np.zeros((h, w), dtype=np.uint8)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        cx, cy = centroids[i]
        if not (lo * w <= cx <= hi * w and lo * h <= cy <= hi * h):
            continue
        anchor[labels == i] = 255
    if not cv2.countNonZero(anchor):
        return anchor

    # Выпуклая оболочка якорей — ядро зубного ряда. Зубы, закрашенные целиком
    # (у них нет якорной эмали), в неё могут не попасть, поэтому дальше область
    # дорастает через пиксели эмали/красителя ОГРАНИЧЕННО по расстоянию:
    # соседние окрашенные зубы достижимы, а губы и кожа — уже нет.
    pts = cv2.findNonZero(anchor)
    hull = cv2.convexHull(pts)
    region = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(region, hull, 255)
    region = cv2.dilate(region, kernel, iterations=2)

    # Рост ТОЛЬКО через эмаль и синий краситель. Через розовое расти нельзя:
    # здоровые дёсны по цвету неотличимы от розового красителя (проверено на
    # реальных фото — hue обоих 167..179, LAB не разделяет, бренды красителя
    # разные), и рост через розовое утаскивает область на дёсны и губы.
    # Синий во рту не встречается — по нему расти безопасно.
    # Цена компромисса: полностью розовый зуб ВНЕ оболочки якорей не попадёт
    # в область. Внутри зубного ряда всё покрыто оболочкой, страдают только
    # крайние в кадре целиком закрашенные зубы — приемлемо для v1.
    allowed_growth = enamel | old
    # Каждая итерация растит область примерно на радиус ядра. Предел суммарного
    # роста привязан к высоте якорного блока (масштаб зубного ряда на ЭТОМ фото,
    # а не кадра): соседние зубы достижимы, губы и кожа — нет.
    ys = np.where(anchor.any(axis=1))[0]
    anchor_height = int(ys[-1] - ys[0] + 1)
    grow_px = max(k, int(0.6 * anchor_height))
    grow_iters = max(2, grow_px // max(1, k // 2))
    for _ in range(grow_iters):
        grown = cv2.dilate(region, kernel) & allowed_growth | region
        if cv2.countNonZero(grown) == cv2.countNonZero(region):
            break
        region = grown

    # Зуб = эмаль или краситель, и только внутри области. Неокрашенная десна
    # (насыщенный красный, не эмаль и не краситель) в знаменатель не попадает.
    tooth = (enamel | fresh | old) & region
    tooth = cv2.morphologyEx(tooth, cv2.MORPH_CLOSE, kernel)
    return tooth


def _build_overlay(bgr, fresh, old, tooth):
    """Фото с полупрозрачной подсветкой зон налёта + контурами. Возвращает JPEG-байты."""
    out = bgr.copy()
    color_layer = bgr.copy()
    color_layer[fresh > 0] = OVERLAY_FRESH_BGR
    color_layer[old > 0] = OVERLAY_OLD_BGR
    cv2.addWeighted(color_layer, OVERLAY_ALPHA, out, 1 - OVERLAY_ALPHA, 0, dst=out)

    # Контуры пятен, чтобы зоны читались и на маленьком экране.
    for mask, color in ((fresh, OVERLAY_FRESH_BGR), (old, OVERLAY_OLD_BGR)):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, contours, -1, color, 1)

    ok, buf = cv2.imencode('.jpg', out, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return buf.tobytes() if ok else None


def measure_photo(jpeg_bytes: bytes, with_overlay: bool = True) -> PlaqueMeasurement:
    """Измеряет налёт по одному фото (JPEG/PNG байты после process_photo).

    Никогда не бросает исключений наружу: любая ошибка = «измерить не удалось»
    (ok=False), выше по стеку это означает фолбэк на оценку нейросетью."""
    try:
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            return PlaqueMeasurement(ok=False)

        # Лёгкое сглаживание убирает шум сенсора, не размывая границы пятен.
        blurred = cv2.GaussianBlur(bgr, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        fresh, old = _dye_masks(hsv)
        tooth = _tooth_mask(hsv, fresh, old)

        h, w = hsv.shape[:2]
        tooth_px = int(cv2.countNonZero(tooth))
        if tooth_px < h * w * MIN_TOOTH_FRAC:
            return PlaqueMeasurement(ok=False)

        fresh_in = fresh & tooth
        old_in = old & tooth
        m = PlaqueMeasurement(
            ok=True,
            tooth_pixels=tooth_px,
            fresh_pixels=int(cv2.countNonZero(fresh_in)),
            old_pixels=int(cv2.countNonZero(old_in)),
        )
        if with_overlay:
            m.overlay_jpeg = _build_overlay(bgr, fresh_in, old_in, tooth)
        return m
    except Exception:
        logger.exception('plaque_cv: ошибка измерения — фолбэк на оценку нейросетью')
        return PlaqueMeasurement(ok=False)


def measure_photos(blobs: List[bytes], with_overlay: bool = True) -> PlaqueTotals:
    """Меряет набор фото одного анализа и агрегирует проценты по суммам пикселей.

    ok=True только если зубы нашлись на КАЖДОМ фото: если хотя бы одно фото
    скрипт не понял, честнее целиком отдать анализ нейросети, чем смешивать
    измеренную и угаданную части."""
    measurements = [measure_photo(b, with_overlay=with_overlay) for b in blobs]
    if not measurements or not all(m.ok for m in measurements):
        return PlaqueTotals(ok=False, measurements=measurements)

    tooth = sum(m.tooth_pixels for m in measurements)
    fresh = sum(m.fresh_pixels for m in measurements)
    old = sum(m.old_pixels for m in measurements)
    return PlaqueTotals(
        ok=True,
        fresh_percent=round(100.0 * fresh / tooth, 1),
        old_percent=round(100.0 * old / tooth, 1),
        measurements=measurements,
    )


def build_measured_block(fresh_percent: float, old_percent: float) -> str:
    """Блок с измеренными цифрами для промпта нейросети: модель пишет текст
    по готовым числам и не оценивает проценты сама."""
    return (
        'ИЗМЕРЕННЫЕ ДАННЫЕ (детерминированный CV-скрипт посчитал пиксели красителя '
        'внутри области зубов на этом фото):\n'
        f'- свежий налёт (розовый краситель): {fresh_percent}% площади зубов\n'
        f'- зрелый налёт (синий краситель): {old_percent}% площади зубов\n\n'
        'Эти проценты уже измерены и будут показаны пациенту. В полях '
        'fresh_plaque_percent и old_plaque_percent верни РОВНО эти числа, не '
        'переоценивай их по фото. Балл система рассчитает сама. Твоя задача: '
        'проверить валидность фото (правила ниже), определить проблемные зоны и '
        'дать рекомендации, согласованные с этими цифрами.\n\n'
    )
