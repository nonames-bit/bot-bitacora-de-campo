<#
.SYNOPSIS
    Arranca el Dashboard PWA (Fase 7 Etapa D) en segundo plano en Windows.
.DESCRIPTION
    Equivalente Windows de scripts/iniciar_pwa.sh. Activa .venv si existe,
    valida Flask y data/bitacora.db con mensajes claros en español, lanza
    "python src/pwa/app.py" en segundo plano (no bloquea la consola),
    guarda el log en data/pwa.log y muestra la URL local y de red.
    No toca Etapas B/C (offline/SOS/RFID) ni el bot de Telegram.
.EXAMPLE
    .\scripts\iniciar_pwa.ps1
.EXAMPLE
    .\scripts\iniciar_pwa.ps1 -Puerto 8081 -AbrirNavegador
#>
param(
    [int]$Puerto = 0,
    [string]$HostPwa = "",
    [switch]$AbrirNavegador
)

$ErrorActionPreference = "Stop"
$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Raiz

if ($Puerto -eq 0) {
    if ($env:PWA_PORT) { $Puerto = [int]$env:PWA_PORT } else { $Puerto = 8080 }
}
if ([string]::IsNullOrWhiteSpace($HostPwa)) {
    if ($env:PWA_HOST) { $HostPwa = $env:PWA_HOST } else { $HostPwa = "0.0.0.0" }
}
$env:PWA_PORT = "$Puerto"
$env:PWA_HOST = $HostPwa
if (-not $env:BITACORA_DB) { $env:BITACORA_DB = "data/bitacora.db" }

# .venv si existe (mismo patrón que iniciar_pwa.sh / iniciar_bot.sh).
$venvAct = Join-Path $Raiz ".venv\Scripts\Activate.ps1"
if (Test-Path $venvAct) {
    Write-Host "[INFO] Activando entorno virtual (.venv)..." -ForegroundColor Cyan
    . $venvAct
}

# Validación previa con mensaje claro (sin traceback): DB y Flask.
if (-not (Test-Path $env:BITACORA_DB)) {
    Write-Host "[ERROR] No se encontró la base de datos: $($env:BITACORA_DB)" -ForegroundColor Red
    Write-Host "        Verifique data\bitacora.db o defina `$env:BITACORA_DB con la ruta correcta." -ForegroundColor Red
    exit 1
}
python -c "import flask" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Flask no está instalado." -ForegroundColor Red
    Write-Host "        Instálelo con:  pip install flask" -ForegroundColor Red
    exit 2
}

$Log = Join-Path $Raiz "data\pwa.log"
$PidFile = Join-Path $Raiz "data\pwa.pid"
# Si ya corre en este puerto, no duplicar: avisar y abrir la URL.
try {
    $tcp = New-Object Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect("127.0.0.1", $Puerto, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne(500) -and $tcp.Connected) {
        Write-Host "[AVISO] El puerto $Puerto ya está ocupado (la PWA quizás ya corre)." -ForegroundColor Yellow
        Write-Host "        Ábrala en:  http://localhost:$Puerto" -ForegroundColor Green
        try { $tcp.Close() } catch {}
        if ($AbrirNavegador) { Start-Process "http://localhost:$Puerto" }
        exit 0
    }
    try { $tcp.Close() } catch {}
} catch {}

Write-Host "Iniciando PWA Bitácora JA en segundo plano (puerto $Puerto, DB=$($env:BITACORA_DB))..." -ForegroundColor Cyan
$proc = Start-Process -FilePath "python" -ArgumentList "src/pwa/app.py" `
    -WorkingDirectory $Raiz -WindowStyle Hidden `
    -RedirectStandardOutput $Log -RedirectStandardError $Log -PassThru
$proc.Id | Out-File -FilePath $PidFile -Encoding utf8 -Force

Start-Sleep -Seconds 3
if ($proc.HasExited) {
    Write-Host "[ERROR] La PWA no arrancó. Revise el log: $Log" -ForegroundColor Red
    Get-Content $Log -Tail 20
    exit 3
}

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host "  PWA lista — abra en el navegador:  http://localhost:$Puerto" -ForegroundColor Green
Write-Host "  Desde celular/otra PC (misma red): pregunte su IP con: ipconfig" -ForegroundColor Green
Write-Host "  Log: $Log  |  PID: $($proc.Id) (guardado en data\pwa.pid)" -ForegroundColor Cyan
Write-Host "  Para detener:  Stop-Process -Id $($proc.Id)" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Green
if ($AbrirNavegador) { Start-Process "http://localhost:$Puerto" }
