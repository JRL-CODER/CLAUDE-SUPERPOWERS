# refresh-token.ps1 - Amazon Ads (Che Mate + FCX/Icarus en un solo token)
# -----------------------------------------------------------------------------
# Credentials: fill in your own values or set as environment variables.
# Do NOT commit real secrets to git.

$client = @{
    ClientId     = $env:AMZN_ADS_CLIENT_ID     ?? "<YOUR_CLIENT_ID>"
    ClientSecret = $env:AMZN_ADS_CLIENT_SECRET  ?? "<YOUR_CLIENT_SECRET>"
    RefreshToken = $env:AMZN_ADS_REFRESH_TOKEN  ?? "<YOUR_REFRESH_TOKEN>"
    Label        = "Todos los clientes"
}

$configFiles = @(
    "C:\Users\Julian\AppData\Roaming\Claude\claude_desktop_config.json",
    "C:\Users\Julian\.zcode\cli\config.json"
)

function Get-AccessToken($c) {
    $body = "grant_type=refresh_token&refresh_token=$($c.RefreshToken)&client_id=$($c.ClientId)&client_secret=$($c.ClientSecret)"
    try {
        $r = Invoke-WebRequest -Uri "https://api.amazon.com/auth/o2/token" `
            -Method POST -ContentType "application/x-www-form-urlencoded" -Body $body -UseBasicParsing
        return ($r.Content | ConvertFrom-Json).access_token
    } catch {
        Write-Host "  FAILED: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

Write-Host "`nObteniendo token fresco..." -ForegroundColor Cyan
Write-Host "  Refreshing $($client.Label)..." -NoNewline
$token = Get-AccessToken $client
if (-not $token) { exit 1 }
Write-Host " OK ($($token.Substring(0,20))...)" -ForegroundColor Green

foreach ($path in $configFiles) {
    $name = Split-Path $path -Leaf
    if (-not (Test-Path $path)) {
        Write-Host "`n[$name] No encontrado - saltando" -ForegroundColor Yellow
        continue
    }
    Write-Host "`nActualizando $name..." -ForegroundColor Cyan
    $content = Get-Content $path -Raw
    $newContent = $content -replace 'Authorization: Bearer Atza\|[^"]+', "Authorization: Bearer $token"
    if ($newContent -eq $content) {
        Write-Host "  Bearer token no encontrado en $name" -ForegroundColor Yellow
        continue
    }
    Set-Content $path $newContent -NoNewline
    Write-Host "  Token actualizado" -ForegroundColor Green
}

Write-Host "`nListo. Reinicia Claude Desktop y ZCode para que tomen efecto." -ForegroundColor Cyan
