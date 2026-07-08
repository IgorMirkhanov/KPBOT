# Full production deploy: env vars + deploy + webhook
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ProductionUrl = "https://kpbot-eight.vercel.app"
$WebhookUrl = "$ProductionUrl/webhook"

Write-Host "=== KPBOT Full Deploy ==="

$EnvFile = Join-Path $Root ".env"
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split("=", 2)
        Set-Item -Path ("env:" + $parts[0].Trim()) -Value $parts[1].Trim()
    }
}

vercel link --yes --project kpbot | Out-Null

vercel env rm WEBHOOK_SECRET production --yes 2>$null

function Set-VercelEnv($Name, $Value) {
    if ($Value) {
        Write-Host "  env: $Name"
        $Value | vercel env add $Name production --force
    }
}

Write-Host "--- Upload env ---"
Set-VercelEnv "BOT_TOKEN" $env:BOT_TOKEN
Set-VercelEnv "WEBHOOK_URL" $WebhookUrl
Set-VercelEnv "UPSTASH_REDIS_REST_URL" $env:UPSTASH_REDIS_REST_URL
Set-VercelEnv "UPSTASH_REDIS_REST_TOKEN" $env:UPSTASH_REDIS_REST_TOKEN

Write-Host "--- Deploy production ---"
vercel deploy --prod --yes

Start-Sleep -Seconds 12
$r = Invoke-WebRequest -Uri $WebhookUrl -UseBasicParsing -TimeoutSec 20
Write-Host "Health: $($r.Content)"

$env:WEBHOOK_URL = $WebhookUrl
python scripts/set_webhook.py

Write-Host "=== Deploy complete ==="
Write-Host "Bot: $WebhookUrl"
