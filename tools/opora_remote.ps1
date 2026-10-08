<#
.SYNOPSIS
Vzdálený přístup k Opora Control Center: aplikace zůstává tady, ven vede Cloudflare quick tunnel.

.DESCRIPTION
Aplikace se nedá hostovat jinde (SQLite, data na disku, asistent, lokální modely), proto běží
dál na tomhle počítači a veřejnou adresu jí dá tunel. Skript je návod, který se dá spustit:

  1. ověří `cloudflared`,
  2. vyrobí (nebo znovu použije) přístupový token v .data\remote-access.token,
  3. spustí backend s OPORA_PUBLIC_HOSTS a OPORA_ACCESS_TOKEN, pokud ještě neběží,
  4. spustí `cloudflared tunnel --url http://127.0.0.1:<port>` a najde veřejnou adresu,
  5. vypíše dva řádky, které si uživatel pustí na vzdáleném počítači.

Je idempotentní: druhé spuštění nezaloží druhý tunel, jen znovu vypíše platnou adresu.
Token se nikdy nezapisuje do logu tunelu ani nikam do repozitáře (.data je v .gitignore);
na obrazovku se vypíše jednou, protože ho uživatel musí přenést.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File tools\opora_remote.ps1
#>
[CmdletBinding()]
param(
    [int]$Port = 8740,
    [string]$PublicHosts = "*.trycloudflare.com",
    [switch]$Stop,
    # Ukončí backend, který na portu běží bez vzdáleného režimu, a spustí ho znovu s proměnnými.
    [switch]$RestartBackend
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root ".data"
$tokenFile = Join-Path $dataDir "remote-access.token"
$tunnelLog = Join-Path $dataDir "remote-tunnel.log"
$tunnelPid = Join-Path $dataDir "remote-tunnel.pid"
$urlPattern = 'https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com'

function Write-Step([string]$text) { Write-Host "[opora-remote] $text" }

function Test-Listening([int]$p) {
    $client = New-Object System.Net.Sockets.TcpClient
    try { $client.Connect("127.0.0.1", $p); return $true }
    catch { return $false }
    finally { $client.Dispose() }
}

# Zjistí, jestli backend běží ve vzdáleném režimu: požadavek s cizím Host hlavičkou
# vrátí 401 (režim zapnutý, chybí token) nebo 403 (režim vypnutý, cizí Host se zamítá).
function Get-BoundaryCode([int]$p) {
    Add-Type -AssemblyName System.Net.Http | Out-Null
    $client = New-Object System.Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromSeconds(5)
    $request = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Get, "http://127.0.0.1:$p/api/bootstrap")
    $request.Headers.Host = "probe.trycloudflare.com"
    try { return [int]$client.SendAsync($request).GetAwaiter().GetResult().StatusCode }
    catch { return 0 }
    finally { $client.Dispose() }
}

function Get-TunnelProcess {
    if (-not (Test-Path $tunnelPid)) { return $null }
    $id = 0
    if (-not [int]::TryParse((Get-Content $tunnelPid -Raw).Trim(), [ref]$id)) { return $null }
    try { $process = Get-Process -Id $id -ErrorAction Stop } catch { return $null }
    if ($process.ProcessName -ne "cloudflared") { return $null }
    return $process
}

function Get-TunnelUrl {
    if (-not (Test-Path $tunnelLog)) { return $null }
    $found = [regex]::Matches((Get-Content $tunnelLog -Raw), $urlPattern)
    if ($found.Count -eq 0) { return $null }
    return $found[$found.Count - 1].Value
}

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

if ($Stop) {
    $running = Get-TunnelProcess
    if ($running) { Stop-Process -Id $running.Id -Force; Write-Step "Tunel zastaven." }
    else { Write-Step "Žádný tunel z tohoto skriptu neběží." }
    if (Test-Path $tunnelPid) { Remove-Item $tunnelPid -Force }
    Write-Step "Backend běží dál; zastavte ho v jeho vlastním okně."
    return
}

# 1. cloudflared (na PATH, nebo stažený binár v %LOCALAPPDATA%\Opora\bin)
$localCloudflared = Join-Path $env:LOCALAPPDATA "Opora\bin\cloudflared.exe"
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue) -and (Test-Path $localCloudflared)) {
    $env:PATH = (Split-Path -Parent $localCloudflared) + ";" + $env:PATH
}
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Step "cloudflared není nainstalovaný. Nainstalujte ho a skript spusťte znovu:"
    Write-Host ""
    Write-Host "    winget install --id Cloudflare.cloudflared"
    Write-Host ""
    exit 1
}
Write-Step "cloudflared: $((Get-Command cloudflared).Source)"

# 2. token
$fresh = $false
$token = ""
if (Test-Path $tokenFile) { $token = (Get-Content $tokenFile -Raw).Trim() }
if ($token.Length -lt 24) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $token = [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')
    Set-Content -Path $tokenFile -Value $token -Encoding ascii -NoNewline
    $fresh = $true
}
if ($fresh) { Write-Step "Nový token uložen do .data\remote-access.token (mimo git)." }
else { Write-Step "Použit existující token z .data\remote-access.token." }
Write-Warning "Token je jediný klíč od celé aplikace. Kdo má adresu i token, může i zapisovat. Neposílejte ho nezabezpečeným kanálem a nevkládejte ho do příkazů v historii ani do logů. Výměna tokenu = smazat .data\remote-access.token a spustit skript znovu."

# 3. backend
$env:OPORA_PUBLIC_HOSTS = $PublicHosts
$env:OPORA_ACCESS_TOKEN = $token
# Paměť rolí (OpenViking) na tomto počítači: adresa a správcovský klíč z ~/.openviking/ov.conf,
# pokud existuje. Klíč se nikde nevypisuje; bez souboru zůstane paměť vypnutá/nedostupná.
$ovConf = Join-Path $env:USERPROFILE ".openviking\ov.conf"
if (Test-Path $ovConf) {
    try {
        $ov = Get-Content $ovConf -Raw | ConvertFrom-Json
        if ($ov.server -and $ov.server.root_api_key) {
            $env:OPORA_OPENVIKING_URL = "http://127.0.0.1:$($ov.server.port)"
            $env:OPORA_OPENVIKING_ADMIN_API_KEY = [string]$ov.server.root_api_key
            Write-Step "OpenViking: správcovský klíč načten z ov.conf (do prostředí backendu, ne na obrazovku)."
        }
    } catch { Write-Step "OpenViking: ov.conf nejde přečíst; paměť rolí zůstane bez správcovského klíče." }
}
if (Test-Listening $Port) {
    $code = Get-BoundaryCode $Port
    if ($code -eq 401) {
        Write-Step "Backend na portu $Port už běží ve vzdáleném režimu."
    }
    elseif ($RestartBackend) {
        Write-Step "Backend na portu $Port běží bez vzdáleného režimu; na přání ho ukončím a spustím znovu."
        $owner = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
        if ($owner) {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$owner"
            $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)" -ErrorAction SilentlyContinue
            Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
            if ($parent -and $parent.CommandLine -like "*tools.opora*") { Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue }
            $deadline = (Get-Date).AddSeconds(20)
            while ((Test-Listening $Port) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
        }
        Write-Step "Spouštím backend znovu s proměnnými vzdáleného režimu (vlastní okno)."
        Start-Process -FilePath "uv" -ArgumentList "run", "opora", "--no-open", "--no-build" -WorkingDirectory $root | Out-Null
        $deadline = (Get-Date).AddSeconds(180)
        while (-not (Test-Listening $Port) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
        if (-not (Test-Listening $Port)) { Write-Step "Backend se nerozeběhl; zkontrolujte jeho okno."; exit 1 }
        Write-Step "Backend poslouchá na http://127.0.0.1:$Port"
    }
    else {
        Write-Step "Backend na portu $Port běží, ale BEZ vzdáleného režimu (hranice odpověděla $code)."
        Write-Host ""
        Write-Host "    Zastavte ho v jeho okně a spusťte znovu takto:"
        Write-Host "    `$env:OPORA_PUBLIC_HOSTS = '$PublicHosts'"
        Write-Host "    `$env:OPORA_ACCESS_TOKEN = (Get-Content .data\remote-access.token -Raw).Trim()"
        Write-Host "    uv run opora --no-open"
        Write-Host ""
        Write-Step "Tunel se přesto spustí; dokud backend nepřepnete, vrátí veřejná adresa 403."
    }
}
else {
    Write-Step "Spouštím backend s proměnnými vzdáleného režimu (vlastní okno)."
    Start-Process -FilePath "uv" -ArgumentList "run", "opora", "--no-open" -WorkingDirectory $root | Out-Null
    $deadline = (Get-Date).AddSeconds(180)
    while (-not (Test-Listening $Port) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
    if (-not (Test-Listening $Port)) {
        Write-Step "Backend se do 3 minut nerozeběhl (sestavuje se frontend?). Zkontrolujte jeho okno a spusťte skript znovu."
        exit 1
    }
    Write-Step "Backend poslouchá na http://127.0.0.1:$Port"
}

# 4. tunel
$existing = Get-TunnelProcess
$url = $null
if ($existing) {
    $url = Get-TunnelUrl
    if ($url) { Write-Step "Tunel už běží (PID $($existing.Id)), nezakládám druhý." }
    else { Write-Step "Tunel běží (PID $($existing.Id)), ale adresa v logu není; zastavte ho přes -Stop a spusťte znovu." }
}
if (-not $url) {
    if (-not $existing) {
        Set-Content -Path $tunnelLog -Value "" -Encoding utf8
        # cloudflared píše banner s adresou na stderr; log drží jen adresu a stav, nikdy token.
        $process = Start-Process -FilePath "cloudflared" -ArgumentList "tunnel", "--url", "http://127.0.0.1:$Port" `
            -RedirectStandardError $tunnelLog -RedirectStandardOutput "$tunnelLog.out" -WindowStyle Hidden -PassThru
        Set-Content -Path $tunnelPid -Value $process.Id -Encoding ascii -NoNewline
        Write-Step "cloudflared spuštěn (PID $($process.Id)), čekám na veřejnou adresu…"
    }
    $deadline = (Get-Date).AddSeconds(60)
    while (-not $url -and (Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        $url = Get-TunnelUrl
    }
}
if (-not $url) {
    Write-Step "Adresa tunelu se neobjevila. Podívejte se do .data\remote-tunnel.log."
    exit 1
}

# 5. co má uživatel udělat na druhém počítači
Write-Host ""
Write-Step "Veřejná adresa: $url"
Write-Host ""
Write-Host "  V prohlížeči otevřete $url a vložte token do přihlašovací obrazovky."
Write-Host ""
Write-Host "  Terminálový agent na vzdáleném počítači (PowerShell):"
Write-Host ""
Write-Host "    `$env:OPORA_ACCESS_TOKEN = '$token'"
Write-Host "    python opora_read.py --api-base $url status"
Write-Host ""
Write-Step "Adresa quick tunelu platí jen do zastavení tunelu; příště bude jiná. Zastavení: tools\opora_remote.ps1 -Stop"
