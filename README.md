# KPBOT — Конструктор коммерческих предложений MediaPeace

Telegram-бот для автоматической генерации PDF коммерческих предложений на базе готового шаблона. Таблица бюджета не перерисовывается — невыбранные строки маскируются прямо в оригинальном PDF через PyMuPDF.

## Возможности

- Мультивыбор услуг через inline-кнопки
- Стандартные цены или кастомная стоимость
- Автоматический пересчёт итогов (1 / 3 / 6 месяцев)
- Вставка названия компании и срока действия КП
- Удаление лишних страниц услуг из PDF

## Стек

- Python 3.11+
- [aiogram 3](https://docs.aiogram.dev/)
- [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/)
- [Vercel](https://vercel.com) — serverless webhook
- [Upstash Redis](https://upstash.com) — хранение FSM-состояния на Vercel

## Структура

```
├── api/webhook.py          # Serverless endpoint для Vercel
├── bot_setup.py            # Инициализация Bot + Dispatcher
├── config.py               # Конфигурация через env
├── document_generator.py   # Генерация PDF (маскирование строк)
├── handlers.py             # FSM-логика бота
├── main.py                 # Локальный запуск (polling)
├── scripts/set_webhook.py  # Регистрация webhook в Telegram
├── templates/
│   └── commercial_proposal.pdf
├── vercel.json
└── requirements.txt
```

## Локальный запуск

```bash
pip install -r requirements.txt
cp .env.example .env
# Заполните BOT_TOKEN в .env

python main.py
```

## Деплой на GitHub

Репозиторий: [github.com/IgorMirkhanov/KPBOT](https://github.com/IgorMirkhanov/KPBOT)

```bash
git init
git add .
git commit -m "Initial commit: Telegram KP bot"
git branch -M main
git remote add origin https://github.com/IgorMirkhanov/KPBOT.git
git push -u origin main
```

> **Важно:** файл `.env` с токеном не попадает в git (см. `.gitignore`).

## Деплой на Vercel

Telegram-бот на Vercel работает через **webhook**, не polling.

### 1. Импорт проекта

1. Зайдите на [vercel.com](https://vercel.com) → **Add New Project**
2. Импортируйте репозиторий `IgorMirkhanov/KPBOT`
3. Framework Preset: **Other**
4. Root Directory: `/` (корень)

### 2. Переменные окружения

В **Settings → Environment Variables** добавьте:

| Переменная       | Описание                                      |
|------------------|-----------------------------------------------|
| `BOT_TOKEN`      | Токен от @BotFather                           |
| `WEBHOOK_SECRET` | Случайная строка (защита webhook)             |
| `REDIS_URL`      | URL Redis (Upstash) — **обязательно** для FSM |

> Без Redis многошаговый диалог (выбор услуг → компания → цена → срок) не сохранится между запросами на serverless.

### 3. Деплой

После деплоя URL будет вида: `https://kpbot-xxx.vercel.app`

Проверка: откройте `https://kpbot-xxx.vercel.app/api/webhook` — должно показать `KPBOT webhook is running`.

### 4. Регистрация webhook в Telegram

```bash
# Локально или в CI
set BOT_TOKEN=your_token
set WEBHOOK_URL=https://kpbot-xxx.vercel.app/api/webhook
set WEBHOOK_SECRET=your_secret
python scripts/set_webhook.py
```

Или вручную:

```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://kpbot-xxx.vercel.app/api/webhook&secret_token=<WEBHOOK_SECRET>
```

### 5. Upstash Redis (бесплатно)

1. [upstash.com](https://upstash.com) → Create Database
2. Скопируйте **Redis URL**
3. Вставьте в `REDIS_URL` на Vercel
4. Redeploy проект

## Переключение polling ↔ webhook

| Режим    | Где использовать | Команда / endpoint        |
|----------|------------------|---------------------------|
| Polling  | Локально         | `python main.py`          |
| Webhook  | Vercel           | `api/webhook.py`          |

Перед локальным polling удалите webhook:

```
https://api.telegram.org/bot<TOKEN>/deleteWebhook
```

## Лицензия

Private / MediaPeace internal use.
