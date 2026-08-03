// Сжатие фото в браузере перед отправкой на сервер.
// Телефоны отдают снимки по 5-10 МБ; 5 таких фото = 30-40 МБ аплоада с мобильного,
// из-за чего анализ «висел» по 3 минуты. Сервер всё равно ужимает фото
// (max 2048px, JPEG, ~1 МБ) — поэтому жмём до тех же параметров ещё на клиенте,
// качество для нейросети не меняется, а загрузка падает с минут до секунд.

const MAX_DIM = 2048
const JPEG_QUALITY = 0.85
// Файлы меньше этого порога не трогаем — выигрыш не окупит перекодирование
const SKIP_BELOW_BYTES = 700_000

export async function compressImage(file) {
  if (!file.type.startsWith('image/') || file.size < SKIP_BELOW_BYTES) return file
  try {
    // imageOrientation: 'from-image' запекает EXIF-поворот в пиксели —
    // canvas.toBlob теряет EXIF, без этого вертикальные фото легли бы набок
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
    const scale = Math.min(1, MAX_DIM / Math.max(bitmap.width, bitmap.height))
    const w = Math.max(1, Math.round(bitmap.width * scale))
    const h = Math.max(1, Math.round(bitmap.height * scale))

    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    canvas.getContext('2d').drawImage(bitmap, 0, 0, w, h)
    bitmap.close()

    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY))
    if (!blob || blob.size >= file.size) return file

    const name = file.name.replace(/\.[^.]+$/, '') + '.jpg'
    return new File([blob], name, { type: 'image/jpeg' })
  } catch {
    // HEIC без поддержки декода, битый файл и т.п. — отправляем оригинал,
    // сервер обработает как раньше
    return file
  }
}
