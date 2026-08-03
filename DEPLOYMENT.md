# Развёртывание сервиса «Радуга Улыбок» 

Документ описывает, как развернуть проект на сервере с нуля. Все значения паролей,
ключей и доменов задаются в файле `.env` и в этот репозиторий не входят — в архиве
есть только шаблон `.env.example`.

## 1. Что это за проект

- **Backend** — Django 4.2 + Django REST Framework (Python 3.11), запускается под gunicorn.
- **Frontend** — React 18 + Vite (одностраничное приложение, SPA).
- **База данных** — PostgreSQL 15.
- **Кэш / rate-limit** — Redis 7.
- **Веб-сервер** — nginx 1.25 (отдаёт собранный фронт, статику, медиа и проксирует API/админку на backend).
- **ИИ-анализ** — Google Gemini (через API или Vertex AI) и/или Qwen3-VL через OpenRouter.
- **Хранилище фото** — локальный диск или объектное хранилище MinIO/S3 (для размещения
  персональных данных на сервере в РФ по 152-ФЗ).

Всё упаковано в Docker. Для запуска нужен только сервер с Docker и Docker Compose.

## 2. Требования к серверу

- ОС: Linux (Ubuntu LTS рекомендуется).
- Docker Engine 24+ и Docker Compose v2.
- Открытые порты 80 и 443.
- Доменное имя, направленное A-записью на IP сервера (для HTTPS-сертификата).
- Для писем (восстановление пароля) — почтовый ящик с доступом по SMTP.

## 3. Структура архива

```
backend/            исходный код Django (приложения users, analysis, core)
frontend/           исходный код React (Vite)
nginx/              конфиг nginx + Dockerfile (внутри собирается фронт)
docker-compose.yml  оркестрация: db, redis, backend, nginx
.env.example        шаблон переменных окружения (скопировать в .env и заполнить)
DEPLOYMENT.md       этот файл
README.md           краткое описание проекта
```

## 4. Быстрый старт

```bash
# 1. Распаковать архив на сервере, например в /opt/teledent
mkdir -p /opt/teledent && tar -xzf raduga-ulybok-source.tar.gz -C /opt/teledent
cd /opt/teledent

# 2. Создать .env из шаблона и заполнить реальными значениями (см. раздел 5)
cp .env.example .env
nano .env

# 3. Собрать и запустить
docker compose up -d --build
```

При старте контейнер backend автоматически:
1. применяет миграции базы данных (`migrate`);
2. собирает статику Django-админки (`collectstatic`);
3. создаёт стартовые настройки и слоты правовых документов (`init_settings`);
4. запускает gunicorn.

Фронт собирается на этапе сборки образа nginx (`npm run build`) и кладётся внутрь
образа — отдельная сборка не нужна.

## 5. Переменные окружения (.env)

Полный список с комментариями — в файле `.env.example`. Ключевые группы:

- **Django**: `SECRET_KEY` (сгенерировать случайную строку 50+ символов), `DEBUG=False`,
  `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` — подставить свой домен.
- **База данных**: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`,
  `POSTGRES_PORT`. По умолчанию хост — `db` (имя контейнера).
- **Почта (SMTP)**: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
  `DEFAULT_FROM_EMAIL`, `FRONTEND_URL`. Нужны для восстановления пароля. Если оставить
  значения по умолчанию — письма печатаются в консоль (для разработки).
- **ИИ**: один из вариантов —
  - `GEMINI_API_KEY` (прямой доступ к Gemini API), либо
  - `USE_VERTEX_AI=true` + `GCP_PROJECT_ID` + сервис-аккаунт в `secrets/vertex-key.json`
    (обход региональных ограничений Gemini через Google Cloud), либо
  - `OPENROUTER_API_KEY` (доступ к Qwen3-VL).
- **Хранилище фото (152-ФЗ)**: `USE_S3_PHOTOS=true` + `AWS_*` для записи фото в MinIO/S3.
  При `false` фото лежат на локальном диске сервера.

Активную нейросеть, модель, число попыток для новых пользователей и тексты промптов
можно менять прямо в админке (Настройки системы) без перезапуска.

## 6. HTTPS-сертификат

nginx настроен на работу по HTTPS и ожидает сертификат Let's Encrypt по пути
`/etc/letsencrypt/live/<домен>/`. Получить сертификат можно:

- стандартным `certbot` (HTTP-01), если сервер доступен для проверок Let's Encrypt; либо
- через DNS-01 (например `acme.sh` с плагином вашего DNS-провайдера), если входящие
  проверки фильтруются. В `docker-compose.yml` каталог `/etc/letsencrypt` пробрасывается
  в контейнер nginx только на чтение.

После выпуска сертификата пропишите домен в `nginx/default.conf` (директивы `server_name`
и пути `ssl_certificate`).

## 7. Создание администратора

```bash
docker compose exec backend python manage.py createsuperuser
```

Затем войдите в админку по адресу `https://<домен>/admin/`.

## 8. Обновление кода

```bash
cd /opt/teledent
# обновить файлы исходников (распаковать новый архив поверх, сохранив .env)
docker compose up -d --build backend nginx
```

Миграции применятся автоматически при старте backend. Файл `.env`, база данных
(`postgres_data`) и медиа при пересборке не затрагиваются.

## 9. Полезные команды

```bash
# статус контейнеров
docker compose ps

# логи backend
docker compose logs backend --tail=50

# запустить автотесты (на отдельных настройках с SQLite, без боевой БД)
docker compose exec backend python manage.py test --settings=config.settings.test

# применить миграции вручную
docker compose exec backend python manage.py migrate
```

## 10. Резервное копирование

- **База данных**: `docker compose exec db pg_dump -U <user> <db> > backup.sql`
- **Медиа** (если фото на локальном диске): каталог `media/`.
- **Хранилище MinIO/S3** (если включено): средствами вашего S3-провайдера.

---

Сервис «Радуга Улыбок». Документ для технической передачи проекта.
