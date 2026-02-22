# 🐱 Cat Viral Curator (Reddit → Telegram)

Веб-приложение на FastAPI для поиска вирусных фото/видео с котами с Reddit **без Reddit API ключей** и ручной отправки в Telegram.

## Что умеет
- Загружает посты из публичных Reddit JSON-лент:
  - `https://www.reddit.com/r/cats/top.json?t=day&limit=50`
  - `https://www.reddit.com/r/cats/top.json?t=week&limit=50`
  - `https://www.reddit.com/r/aww/top.json?t=day&limit=50`
  - `https://www.reddit.com/r/CatVideos/top.json?t=day&limit=50`
  - `https://www.reddit.com/r/funnycats/top.json?t=week&limit=50`
- Все запросы идут с `User-Agent: cat-content-curator/1.0`
- Фильтрация: только image/video, NSFW исключается, дубликаты убираются
- Режимы: «Лучшее за 24 часа» и «Лучшее за 7 дней»
- Сортировка: апвоуты + свежесть, с приоритетом видео
- Русский UI: карточки, тёмная тема, адаптивность
- Автоперевод заголовков на русский
- SQLite-хранилище + защита от дублей
- Кэш ленты на 30 минут
- Ручная отправка в Telegram канал из карточки поста

## Быстрый запуск (в 1 клик)

### Локально (даже для новичка)
1. Установите Python 3.11+
2. Скачайте проект и откройте папку
3. Скопируйте `.env.example` в `.env`
4. Запустите:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

5. Откройте в браузере: `http://localhost:8000`

### Как отправлять в Telegram
1. В приложении откройте блок **Настройки**
2. Вставьте Bot Token и Channel ID
3. Нажмите «Сохранить настройки»
4. В карточке поста нажмите «Отправить в Telegram»

## Запуск на Replit
1. Импортируйте репозиторий в Replit
2. Нажмите **Run**
3. Приложение запустится автоматически на порту 8000
4. При необходимости задайте переменные в Secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`)

## Технически
- Backend: FastAPI + httpx
- База: SQLite (`cats.db`)
- Шаблоны: Jinja2
- Статика: CSS + JS

