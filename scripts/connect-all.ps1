# Полное подключение KPBOT к Vercel + Telegram
# Запуск: .\scripts\connect-all.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ProductionUrl = "https://kpbot-eight.vercel.app"
$WebhookPath   = "/webhook"
$WebhookUrl    = "$ProductionUrl$WebhookPath"

Write-Host "=== KPBOT Connect All ===" -ForegroundColor Cyan
Write-Host "Production URL: $ProductionUrl"

$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Создан .env — заполните BOT_TOKEN и перезапустите." -ForegroundColor Yellow
    exit 1
}

Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}

if (-not $env:BOT_TOKEN) {
    Write-Host "Ошибка: BOT_TOKEN не задан в .env" -ForegroundColor Red
    exit 1
}

if (-not $env:WEBHOOK_SECRET) {
    $env:WEBHOOK_SECRET = python -c "import secrets; print(secrets.token_urlsafe(32))"
    Add-Content $EnvFile "`nWEBHOOK_SECRET=$($env:WEBHOOK_SECRET)"
}

$env:WEBHOOK_URL = $WebhookUrl
if (-not (Select-String -Path $EnvFile -Pattern "^WEBHOOK_URL=" -Quiet)) {
    Add-Content $EnvFile "`nWEBHOOK_URL=$WebhookUrl"
} else {
    (Get-Content $EnvFile) -replace '^WEBHOOK_URL=.*', "WEBHOOK_URL=$WebhookUrl" | Set-Content $EnvFile
}

Write-Host "`n--- Vercel CLI ---" -ForegroundColor Cyan
$vercelOk = $false
try {
    vercel whoami | Out-Null
    $vercelOk = $true
} catch {
    Write-Host "Выполните: vercel login" -ForegroundColor Yellow
}

if ($vercelOk) {
    if (-not (Test-Path (Join-Path $Root ".vercel\project.json"))) {
        vercel link --yes --project kpbot
    }

    Write-Host "`n--- Upload env to Vercel ---" -ForegroundColor Cyan
    foreach ($pair in @(
        @("BOT_TOKEN", $env:BOT_TOKEN),
        @("WEBHOOK_SECRET", $env:WEBHOOK_SECRET),
        @("WEBHOOK_URL", $env:WEBHOOK_URL),
        @("REDIS_URL", $env:REDIS_URL)
    )) {
        if ($pair[1]) {
            Write-Host "  -> $($pair[0])"
            $pair[1] | vercel env add $pair[0] production --force
        }
    }

    Write-Host "`n--- Deploy ---" -ForegroundColor Cyan
    vercel deploy --prod --yes
}

Write-Host "`n--- Health Check ---" -ForegroundColor Cyan
Start-Sleep -Seconds 8
foreach ($url in @("$ProductionUrl/webhook", "$ProductionUrl/api/webhook")) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15
        Write-Host "OK $url -> $($r.Content)"
        break
    } catch { }
}

Write-Host "`n--- Telegram setWebhook ---" -ForegroundColor Cyan
python scripts/set_webhook.py

Write-Host "`n=== Готово ===" -ForegroundColor Green
Write-Host "Webhook: $WebhookUrl"
if (-not $env:REDIS_URL) {
    Write-Host "ВАЖНО: добавьте REDIS_URL (Upstash) в Vercel env для FSM!" -ForegroundColor Yellow
}
