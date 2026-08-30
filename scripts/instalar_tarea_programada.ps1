<#
.SYNOPSIS
    Instala una Tarea Programada de Windows que corre el vigilante de copias
    de Software Ganadero (vigilar_copias_windows.ps1) cada N minutos, para
    siempre, sin necesidad de dejar una ventana abierta.

.DESCRIPTION
    El problema que resuelve: ejecutar vigilar_copias_windows.ps1 a mano
    (o dejarlo corriendo en una consola) funciona mientras esa ventana sigue
    abierta, pero apenas se cierra la ventana, se apaga o reinicia el
    computador, el vigilante deja de correr y los backups nuevos de Software
    Ganadero dejan de subir al VPS sin que nadie se dé cuenta (justo lo que
    pasó el 2026-08-30: corrió una vez el día anterior y no volvió a correr).

    Este script registra una Tarea Programada de Windows que ejecuta
    "vigilar_copias_windows.ps1 -UnaVez" cada N minutos de forma indefinida,
    incluso después de reiniciar el computador (siempre que el usuario haya
    iniciado sesión). Usar -UnaVez en cada corrida es más robusto que dejar
    el modo de bucle continuo corriendo: si una corrida falla o se cuelga,
    la siguiente igual se dispara sola a los N minutos.

.PARAMETER IntervaloMinutos
    Cada cuántos minutos se revisa la carpeta de copias (por defecto 5).

.PARAMETER CopiasDir
    Carpeta donde Software Ganadero guarda sus backups .Zip (por defecto
    C:\Usati\Copias, igual que vigilar_copias_windows.ps1).

.EXAMPLE
    .\scripts\instalar_tarea_programada.ps1
.EXAMPLE
    .\scripts\instalar_tarea_programada.ps1 -IntervaloMinutos 10 -CopiasDir "D:\SoftwareGanadero\Copias"

.NOTES
    Ejecutar UNA sola vez para instalar. Para quitarla despues:
        Unregister-ScheduledTask -TaskName "BitacoraVigilanteCopiasSG" -Confirm:$false
#>
param(
    [int]$IntervaloMinutos = 5,
    [string]$CopiasDir = "C:\Usati\Copias",
    [string]$NombreTarea = "BitacoraVigilanteCopiasSG"
)

$ErrorActionPreference = "Stop"

$rutaScript = Join-Path $PSScriptRoot "vigilar_copias_windows.ps1"
if (-not (Test-Path $rutaScript)) {
    Write-Host "[ERROR] No se encontro $rutaScript" -ForegroundColor Red
    exit 1
}
$rutaScript = (Resolve-Path $rutaScript).Path

try {
    $tareaExistente = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
} catch {
    $tareaExistente = $null
}
if ($tareaExistente) {
    Write-Host "[INFO] Ya existe una tarea '$NombreTarea'. Se va a reemplazar con la nueva configuracion." -ForegroundColor Yellow
}

$argumentos = "-NoProfile -ExecutionPolicy Bypass -File `"$rutaScript`" -CopiasDir `"$CopiasDir`" -UnaVez"
$accion = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argumentos -WorkingDirectory (Split-Path $rutaScript -Parent)

# Dispara ya mismo y se repite cada N minutos indefinidamente.
$disparador = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervaloMinutos) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

$configuracion = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $NombreTarea `
    -Action $accion -Trigger $disparador -Settings $configuracion `
    -Description "Revisa cada $IntervaloMinutos minutos si hay un backup nuevo de Software Ganadero en $CopiasDir y lo sube al bot en el VPS." `
    -Force | Out-Null

Write-Host ""
Write-Host "[OK] Tarea '$NombreTarea' instalada. Correra sola cada $IntervaloMinutos minutos," -ForegroundColor Green
Write-Host "     aunque cierres esta ventana o reinicies el computador (con sesion iniciada)." -ForegroundColor Green
Write-Host ""
Write-Host "Para verla en Windows: abre 'Programador de tareas' y busca '$NombreTarea'." -ForegroundColor Cyan
Write-Host "Para forzar una corrida ahora mismo:  Start-ScheduledTask -TaskName '$NombreTarea'" -ForegroundColor Cyan
Write-Host "Para quitarla:  Unregister-ScheduledTask -TaskName '$NombreTarea' -Confirm:`$false" -ForegroundColor Cyan
Write-Host "Log de cada corrida: $CopiasDir\copias_sync.log" -ForegroundColor Cyan

# Dispara una corrida inmediata para no esperar el primer intervalo.
Start-ScheduledTask -TaskName $NombreTarea
Write-Host ""
Write-Host "Corrida inicial disparada. Revisa $CopiasDir\copias_sync.log en unos segundos." -ForegroundColor Green
