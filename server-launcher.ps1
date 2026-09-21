param([switch]$NoPause, [switch]$SkipDiscord, [switch]$SecureOnly)
$ErrorActionPreference = 'Stop'
$inv = $PSScriptRoot
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
$secureTunnel = Join-Path $env:LOCALAPPDATA 'Inventory\tunnel-client\v0.0.14\tunnel-client.exe'
$profileDir = Join-Path $env:LOCALAPPDATA 'Inventory\tunnel-client\profiles'
$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$run = Join-Path $env:TEMP ('simsimpc-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
try {
    foreach ($path in @((Join-Path $inv 'app.py'), $python, $secureTunnel, (Join-Path $profileDir 'inventory.yaml'))) {
        if (-not (Test-Path -LiteralPath $path)) { throw "File not found: $path" }
    }
    Write-Host '[1/3] Starting FastAPI...'
    $env:CAMERA_AGENT_TOKEN = [Environment]::GetEnvironmentVariable('CAMERA_AGENT_TOKEN', 'User')
    $ready = $false
    try { $ready = (Invoke-WebRequest 'http://127.0.0.1:8000/customer' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
    if (-not $ready) {
        $server = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app:app','--host','0.0.0.0','--port','8000') -WorkingDirectory $inv -WindowStyle Hidden -RedirectStandardOutput "$run-python.out.log" -RedirectStandardError "$run-python.err.log" -PassThru
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if ($server.HasExited) { throw ("FastAPI exited. " + (Get-Content "$run-python.err.log" -Raw)) }
            try { $ready = (Invoke-WebRequest 'http://127.0.0.1:8000/customer' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
            if ($ready) { break }
        }
        if (-not $ready) { throw "FastAPI did not become ready. See $run-python.err.log" }
    }
    Write-Host '[OK] Local customer page: HTTP 200'
    Write-Host '[2/3] Starting OpenAI secure MCP tunnel...'
    $env:CONTROL_PLANE_API_KEY = [Environment]::GetEnvironmentVariable('CONTROL_PLANE_API_KEY', 'User')
    if (-not $env:CONTROL_PLANE_API_KEY) { throw 'Saved tunnel runtime key is missing.' }
    $profile = Get-Content -LiteralPath (Join-Path $profileDir 'inventory.yaml') -Raw | ConvertFrom-Json
    $tunnelId = $profile.control_plane.tunnel_id
    if (-not $tunnelId) { throw 'Saved tunnel ID is missing.' }
    $connectResult = & $secureTunnel runtimes connect --alias inventory --profile inventory --profile-dir $profileDir --tunnel-id $tunnelId --mcp-server-url http://127.0.0.1:8000/mcp/ --runtime-api-key env:CONTROL_PLANE_API_KEY --json 2> "$run-secure.err.log"
    if ($LASTEXITCODE -ne 0) { throw "Secure tunnel startup failed. See $run-secure.err.log" }
    $secureReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        $state = & $secureTunnel runtimes status inventory --json 2> "$run-secure-status.err.log" | ConvertFrom-Json
        if ($LASTEXITCODE -eq 0 -and $state.process_running -and $state.healthy -and $state.ready) { $secureReady = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $secureReady) { throw 'Secure MCP tunnel did not become ready. Check the inventory runtime status.' }
    Write-Host '[OK] OpenAI secure MCP tunnel is healthy and ready.'
    if ($SecureOnly) {
        if (-not $NoPause) { Read-Host 'Server and secure tunnel are running. Press Enter to close' | Out-Null }
        exit 0
    }
    # Keep the existing customer/admin web link separate from the ChatGPT MCP tunnel.
    Write-Host '[2/3] Starting Cloudflare Tunnel...'
    $tunnel = Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--url','http://127.0.0.1:8000','--no-autoupdate') -WindowStyle Hidden -RedirectStandardOutput "$run-tunnel.out.log" -RedirectStandardError "$run-tunnel.err.log" -PassThru
    $publicUrl = $null
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        $logs = [string](Get-Content "$run-tunnel.err.log" -Raw) + [string](Get-Content "$run-tunnel.out.log" -Raw)
        $match = [regex]::Match($logs, 'https://[A-Za-z0-9-]+\.trycloudflare\.com')
        if ($match.Success) { $publicUrl = $match.Value + '/customer'; break }
        if ($tunnel.HasExited) { throw "Cloudflare exited. See $run-tunnel.err.log" }
    }
    if (-not $publicUrl) { throw "No public URL received. See $run-tunnel.err.log" }
    Write-Host "PUBLIC CUSTOMER URL: $publicUrl"
    Write-Host '[3/3] Checking public customer page...'
    $publicReady = $false
    for ($i = 0; $i -lt 20; $i++) {
        try { $publicReady = (Invoke-WebRequest $publicUrl -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 } catch {}
        if ($publicReady) { break }
        Start-Sleep -Seconds 2
    }
    if (-not $publicReady) { throw "Public URL created but HTTP check failed: $publicUrl" }
    Write-Host '[OK] Public customer page: HTTP 200'
    if (-not $SkipDiscord) {
        $match = [regex]::Match([string]$env:DISCORD_WEBHOOK_URL, 'https://(?:discord\.com|discordapp\.com)/api/webhooks/[0-9]+/[A-Za-z0-9_-]+')
        if ($match.Success) {
            try {
                $adminUrl = ([uri]$publicUrl).GetLeftPart([System.UriPartial]::Authority) + '/'
                $body = @{content = "SimsimPC admin page`n$adminUrl"} | ConvertTo-Json
                Invoke-RestMethod -Uri $match.Value -Method Post -ContentType 'application/json' -Body $body | Out-Null
                Write-Host '[OK] Discord notification sent.'
            } catch { Write-Host '[WARNING] Discord notification failed; server is running.' }
        } else { Write-Host '[WARNING] Valid Discord webhook not found; server is running.' }
    } else { Write-Host '[INFO] Discord skipped for verification.' }
    Write-Host "Logs: $run-*.log"
    if (-not $NoPause) { Read-Host 'Server is running. Press Enter to close this launcher' | Out-Null }
    exit 0
} catch {
    Write-Host ('[ERROR] ' + $_.Exception.Message)
    if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
    exit 1
}
