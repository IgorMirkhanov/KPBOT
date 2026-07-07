#!/usr/bin/env bash
# One-time Vercel project link + env sync
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Linking Vercel project (interactive)..."
vercel link

echo "==> Pulling environment variables from Vercel to .env.local..."
vercel env pull .env.local

echo ""
echo "Done. Next steps:"
echo "  1. Add secrets in Vercel Dashboard if missing:"
echo "       BOT_TOKEN, WEBHOOK_SECRET, REDIS_URL"
echo "  2. Run: ./scripts/vercel-deploy.sh"
echo "  3. Register webhook:"
echo "       WEBHOOK_URL=https://YOUR-APP.vercel.app/webhook python scripts/set_webhook.py"
