#!/usr/bin/env bash
# Production deploy via Vercel CLI
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Pulling latest env from Vercel..."
vercel env pull .env.local --yes

echo "==> Deploying to production..."
vercel deploy --prod --yes

echo ""
echo "==> Production deploy complete."
echo "    Health check: https://YOUR-APP.vercel.app/webhook"
echo "    Register Telegram webhook if URL changed:"
echo "      WEBHOOK_URL=https://YOUR-APP.vercel.app/webhook python scripts/set_webhook.py"
