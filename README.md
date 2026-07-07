# KPBOT — Конструктор коммерческих предложений MediaPeace

Telegram-бот для автоматической генерации PDF коммерческих предложений на базе готового шаблона.

## Архитектура деплоя

| Среда | Режим | Entry point |
|-------|-------|-------------|
| Локально | `polling` | `main.py` |
| Vercel (prod) | `webhook` | `api/index.py` → `/webhook` |

> **gunicorn / uvicorn не нужны.** Vercel Python Serverless использует `@vercel/python` и класс `handler` в `api/*.py`. ASGI/WSGI-серверы нужны только для VPS/Docker, не для serverless.

## Структура

```
├── api/
│   ├── index.py          # Primary Vercel serverless handler
│   └── webhook.py        # Legacy alias
├── webhook_app.py        # Async aiogram 3 webhook logic
├── bot_setup.py          # Bot + Dispatcher + Redis FSM
├── main.py               # Local polling only
├── vercel.json           # Routes, timeouts, region
├── scripts/
│   ├── vercel-setup.ps1  # vercel link + env pull
│   ├── vercel-deploy.ps1 # vercel deploy --prod
│   └── set_webhook.py    # Register Telegram webhook
└── .github/workflows/
    └── vercel-deploy.yml # Auto-deploy on push to main
```

---

## 1. vercel.json

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "version": 2,
  "framework": null,
  "installCommand": "pip install -r requirements.txt",
  "rewrites": [
    { "source": "/webhook", "destination": "/api/index" },
    { "source": "/api/webhook", "destination": "/api/index" }
  ],
  "functions": {
    "api/**/*.py": {
      "maxDuration": 60,
      "memory": 1024
    }
  },
  "regions": ["fra1"]
}
```

- **`/webhook`** — основной URL для Telegram `setWebhook`
- **`maxDuration: 60`** — до 60 сек на генерацию PDF (Pro plan; Hobby = 10 сек)
- **`regions: fra1`** — Frankfurt, ближе к Telegram EU

---

## 2. Переменные окружения (Vercel Dashboard)

**Settings → Environment Variables → Production:**

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Токен от @BotFather |
| `WEBHOOK_SECRET` | ✅ | Случайная строка (1–256 символов) |
| `REDIS_URL` | ✅ | Upstash Redis URL для FSM |
| `WEBHOOK_URL` | ⚙️ CI only | `https://YOUR-APP.vercel.app/webhook` |

### Безопасное добавление через CLI

```powershell
# Windows — интерактивно, значение не попадает в историю shell
vercel env add BOT_TOKEN production
vercel env add WEBHOOK_SECRET production
vercel env add REDIS_URL production
vercel env add WEBHOOK_URL production
```

Или через Dashboard: **Settings → Environment Variables → Add** → выберите **Production**, **Preview**, **Development**.

> Никогда не коммитьте `.env`, `.env.local` — они в `.gitignore`.

---

## 3. Первичная настройка Vercel CLI

```powershell
npm install -g vercel
cd "c:\Users\Igorm\Desktop\Бот Кп"

# One-time: link project + pull env
.\scripts\vercel-setup.ps1
```

Или вручную:

```powershell
vercel link
vercel env pull .env.local
```

---

## 4. Production deploy

```powershell
.\scripts\vercel-deploy.ps1
```

Или вручную:

```powershell
vercel env pull .env.local --yes
vercel deploy --prod --yes
```

Проверка:

```
GET https://YOUR-APP.vercel.app/webhook
→ "KPBOT webhook is running. POST Telegram updates here."
```

---

## 5. Регистрация Telegram webhook

```powershell
$env:BOT_TOKEN = "your_token"
$env:WEBHOOK_URL = "https://YOUR-APP.vercel.app/webhook"
$env:WEBHOOK_SECRET = "your_secret"
python scripts/set_webhook.py
```

---

## 6. Continuous Deployment (GitHub Actions)

При каждом `push` в `main` автоматически деплоится production.

### GitHub Secrets (Settings → Secrets → Actions)

| Secret | Где взять |
|--------|-----------|
| `VERCEL_TOKEN` | [vercel.com/account/tokens](https://vercel.com/account/tokens) |
| `VERCEL_ORG_ID` | `.vercel/project.json` после `vercel link` |
| `VERCEL_PROJECT_ID` | `.vercel/project.json` после `vercel link` |
| `BOT_TOKEN` | @BotFather |
| `WEBHOOK_SECRET` | ваш секрет |
| `WEBHOOK_URL` | `https://YOUR-APP.vercel.app/webhook` |

После `vercel link` посмотрите IDs:

```powershell
Get-Content .vercel\project.json
```

---

## 7. Локальная разработка (polling)

```powershell
pip install -r requirements.txt
copy .env.example .env
# заполните BOT_TOKEN

# Сначала удалите webhook:
# https://api.telegram.org/bot<TOKEN>/deleteWebhook

python main.py
```

---

## 8. Upstash Redis (обязательно на Vercel)

1. [upstash.com](https://upstash.com) → Create Database
2. Copy **Redis URL** → `REDIS_URL` в Vercel
3. Redeploy

Без Redis FSM-состояние (выбор услуг → компания → цена → срок) теряется между serverless-вызовами.

---

## Репозиторий

[github.com/IgorMirkhanov/KPBOT](https://github.com/IgorMirkhanov/KPBOT)
