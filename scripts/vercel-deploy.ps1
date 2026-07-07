# Production deploy via Vercel CLI (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

Write-Host "==> Pulling latest env from Vercel..."
vercel env pull .env.local --yes

Write-Host "==> Deploying to production..."
vercel deploy --prod --yes

Write-Host ""
Write-Host "==> Production deploy complete."
Write-Host "    Health check: https://YOUR-APP.vercel.app/webhook"
Write-Host "    Register Telegram webhook if URL changed:"
Write-Host "      `$env:WEBHOOK_URL='https://YOUR-APP.vercel.app/webhook'; python scripts/set_webhook.py"
