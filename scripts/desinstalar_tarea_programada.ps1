<#
.SYNOPSIS
    Desinstala y elimina la Tarea Programada de Windows 'BitacoraVigilanteCopiasSG'.
.DESCRIPTION
    Detiene y elimina la tarea programada que vigilaba la carpeta de copias
    de Software Ganadero en segundo plano, liberando el computador de procesos
    automáticos de sincronización.
#>
param(
    [string[]]$NombresTareas = @("VigilarCopiasSG", "BitacoraVigilanteCopiasSG")
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  DESINSTALADOR: Vigilante de Copias Software Ganadero     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verificar si las tareas programadas existen y eliminarlas
foreach ($nombre in $NombresTareas) {
    try {
        $tarea = Get-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue
    } catch {
        $tarea = $null
    }

    if ($tarea) {
        Write-Host "[1/2] Deteniendo y eliminando tarea programada '$nombre'..." -ForegroundColor Yellow
        try {
            Stop-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue
        } catch {}
        Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
        Write-Host "  -> Tarea programada '$nombre' eliminada correctamente." -ForegroundColor Green
    } else {
        Write-Host "[1/2] La tarea programada '$nombre' no esta registrada en Windows." -ForegroundColor Gray
    }
}

# 2. Verificar si hay procesos residuales de PowerShell ejecutando vigilar_copias
Write-Host "[2/2] Verificando procesos residuales en ejecucion..." -ForegroundColor Yellow
$procesos = Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%vigilar_copias%'" -ErrorAction SilentlyContinue | Where-Object { $_.ProcessId -ne $PID }

if ($procesos) {
    foreach ($p in $procesos) {
        Write-Host "  -> Deteniendo proceso PID $($p.ProcessId)..." -ForegroundColor Yellow
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  -> Procesos residuales detenidos." -ForegroundColor Green
} else {
    Write-Host "  -> No hay procesos en segundo plano activos." -ForegroundColor Green
}

Write-Host "`n[OK] El computador ha quedado libre del vigilante automatico de Software Ganadero." -ForegroundColor Green
