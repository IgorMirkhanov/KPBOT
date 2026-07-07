# One-time Vercel project link + env sync (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

Write-Host "==> Linking Vercel project (interactive)..."
vercel link

Write-Host "==> Pulling environment variables from Vercel to .env.local..."
vercel env pull .env.local

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  1. Add secrets in Vercel Dashboard if missing: BOT_TOKEN, WEBHOOK_SECRET, REDIS_URL"
Write-Host "  2. Run: .\scripts\vercel-deploy.ps1"
Write-Host "  3. Register webhook:"
Write-Host "       `$env:WEBHOOK_URL='https://YOUR-APP.vercel.app/webhook'; python scripts/set_webhook.py"
