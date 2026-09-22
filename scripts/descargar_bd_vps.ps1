<#
.SYNOPSIS
    Descarga una copia de la base de datos de producción desde el VPS hacia el entorno local de pruebas.
.DESCRIPTION
    Conecta vía SCP al VPS (DigitalOcean) y descarga /root/bitacora/data/bitacora.db
    hacia data/bitacora.db (creando un backup previo data/bitacora_local_backup.db).
    Permite tener en la máquina local la información viva y exacta de producción para pruebas.
.PARAMETER VpsHost
    Host o IP del VPS (por defecto 206.189.188.183).
.PARAMETER VpsUser
    Usuario SSH (por defecto root).
#>
param(
    [string]$VpsHost = "206.189.188.183",
    [string]$VpsUser = "root",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519_bitacora"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  DESCARGAR BASE DE DATOS DE PRODUCCION (VPS -> LOCAL)    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$localDb = "data\bitacora.db"
$backupLocal = "data\bitacora_local_antes_sync.db"

# 1. Respaldo previo de la base local
if (Test-Path $localDb) {
    Write-Host "[1/3] Creando respaldo de la base local en '$backupLocal'..." -ForegroundColor Yellow
    Copy-Item $localDb $backupLocal -Force
}

# 2. Descargar con SCP
Write-Host "[2/3] Descargando '/root/bitacora/data/bitacora.db' desde $VpsHost..." -ForegroundColor Yellow

$keyArg = ""
if (Test-Path $KeyPath) {
    $keyArg = "-i `"$KeyPath`""
}

$scpCmd = "scp $keyArg ${VpsUser}@${VpsHost}:/root/bitacora/data/bitacora.db `"$localDb`""
Write-Host "  -> Ejecutando: $scpCmd" -ForegroundColor Gray

try {
    Invoke-Expression $scpCmd
    Write-Host "[3/3] Base de datos de produccion descargada con exito en '$localDb'." -ForegroundColor Green
    Write-Host "`n[OK] Tu entorno local de pruebas ahora tiene exactamente los mismos datos del VPS." -ForegroundColor Green
} catch {
    Write-Host "[ERROR] No se pudo descargar la base de datos: $_" -ForegroundColor Red
}
