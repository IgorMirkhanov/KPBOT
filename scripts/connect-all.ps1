# Full connect + deploy script for KPBOT on Vercel
# Run: .\scripts\connect-all.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ProductionUrl = "https://kpbot-eight.vercel.app"
$WebhookUrl = "$ProductionUrl/webhook"

Write-Host "=== KPBOT Connect All ==="

$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Host "Created .env from .env.example - fill BOT_TOKEN and rerun."
    exit 1
}

Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split("=", 2)
        Set-Item -Path ("env:" + $parts[0].Trim()) -Value $parts[1].Trim()
    }
}

if (-not $env:BOT_TOKEN) {
    Write-Host "Error: BOT_TOKEN missing in .env"
    exit 1
}

$env:WEBHOOK_URL = $WebhookUrl

vercel link --yes --project kpbot | Out-Null
vercel env rm WEBHOOK_SECRET production --yes 2>$null

function Set-VercelEnv($Name, $Value) {
    if ($Value) {
        Write-Host "  env: $Name"
        $Value | vercel env add $Name production --force
    }
}

Write-Host "--- Upload env to Vercel ---"
Set-VercelEnv "BOT_TOKEN" $env:BOT_TOKEN
Set-VercelEnv "WEBHOOK_URL" $WebhookUrl
Set-VercelEnv "UPSTASH_REDIS_REST_URL" $env:UPSTASH_REDIS_REST_URL
Set-VercelEnv "UPSTASH_REDIS_REST_TOKEN" $env:UPSTASH_REDIS_REST_TOKEN

Write-Host "--- Deploy ---"
vercel deploy --prod --yes

Start-Sleep -Seconds 10
try {
    $r = Invoke-WebRequest -Uri $WebhookUrl -UseBasicParsing -TimeoutSec 20
    Write-Host "Health: $($r.Content)"
} catch {
    Write-Host "Health check pending..."
}

python scripts/set_webhook.py
Write-Host "=== Done: $WebhookUrl ==="
