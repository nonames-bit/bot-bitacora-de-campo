<#
.SYNOPSIS
    Vigilante automatico para la carpeta de copias de Software Ganadero en Windows.
.DESCRIPTION
    Monitorea la carpeta local donde Software Ganadero genera los backups (.Zip) por fecha.
    Al detectar un archivo nuevo o modificado (comparando fecha de modificacion, tamano y hash MD5),
    lo envia automaticamente via SCP al servidor VPS (DigitalOcean) y ejecuta el script de importacion
    remota sin intervencion manual.
.PARAMETER CopiasDir
    Ruta de la carpeta donde SG exporta las copias (por defecto C:\Copias).
.PARAMETER VpsHost
    Direccion IP publica o host del droplet VPS (por defecto 206.189.188.183).
.PARAMETER VpsUser
    Usuario SSH para conectarse al VPS (por defecto root).
.PARAMETER VpsDestDir
    Directorio temporal en el VPS para transferir el Zip (por defecto /tmp).
.PARAMETER VpsProjectPath
    Directorio del proyecto bitacora en el VPS (por defecto /root/bitacora).
.PARAMETER IntervaloSegundos
    Intervalo de sondeo en segundos para revisar la carpeta (por defecto 60).
.PARAMETER UnaVez
    Si se especifica, ejecuta una sola verificacion y termina.
.EXAMPLE
    .\scripts\vigilar_copias_windows.ps1
.EXAMPLE
    .\scripts\vigilar_copias_windows.ps1 -CopiasDir "D:\SoftwareGanadero\Copias" -UnaVez
#>
param(
    [string]$CopiasDir = "C:\Usati\Copias",
    [string]$VpsHost = "206.189.188.183",
    [string]$VpsUser = "root",
    [string]$VpsDestDir = "/tmp",
    [string]$VpsProjectPath = "/root/bitacora",
    [int]$IntervaloSegundos = 60,
    [switch]$UnaVez
)

# Asegurar que el directorio de copias existe
if (-not (Test-Path -Path $CopiasDir)) {
    New-Item -ItemType Directory -Path $CopiasDir -Force | Out-Null
    Write-Host "[DIR] Directorio creado: $CopiasDir" -ForegroundColor Cyan
}

$EstadoFile = Join-Path $CopiasDir ".ultimo_sincronizado.json"
$LogFile = Join-Path $CopiasDir "copias_sync.log"
$SshKey = Join-Path $env:USERPROFILE ".ssh\id_ed25519_bitacora"
$SshOpts = @("-i", $SshKey, "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3")

# Reintenta una escritura de archivo varias veces: en Windows, el antivirus u OneDrive
# suelen bloquear momentaneamente un archivo recien creado/modificado (IOException
# transitoria), y sin reintento la escritura fallaba en silencio dejando el estado
# de sincronizacion sin persistir (ver docs: bug detectado 2026-08-29).
function Invoke-EscrituraConReintento {
    param(
        [scriptblock]$Accion,
        [int]$Intentos = 5,
        [int]$EsperaMs = 400
    )
    for ($i = 1; $i -le $Intentos; $i++) {
        try {
            & $Accion
            return $true
        } catch {
            if ($i -eq $Intentos) {
                Write-Host "[ERROR] Escritura fallo tras $Intentos intentos: $_" -ForegroundColor Red
                return $false
            }
            Start-Sleep -Milliseconds $EsperaMs
        }
    }
    return $false
}

function Write-Log {
    param([string]$Mensaje, [string]$Nivel = "INFO")
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $linea = "[$timestamp] [$Nivel] $Mensaje"
    Write-Host $linea
    Invoke-EscrituraConReintento -Accion { Add-Content -Path $LogFile -Value $linea -Encoding UTF8 } | Out-Null
}

function Leer-Estado {
    if (Test-Path -Path $EstadoFile) {
        try {
            $raw = Get-Content -Path $EstadoFile -Raw -Encoding UTF8
            $obj = ConvertFrom-Json $raw
            if ($null -eq $obj.procesados) {
                $obj | Add-Member -MemberType NoteProperty -Name "procesados" -Value @{} -Force
            }
            return $obj
        } catch {
            Write-Log "Error al leer archivo de estado, creando nuevo." "WARN"
        }
    }
    return [PSCustomObject]@{
        ultimo_archivo = ""
        ultimo_hash = ""
        # PSCustomObject vacio, no Hashtable: iterar .PSObject.Properties sobre un
        # [hashtable] devuelve tambien sus miembros .NET (IsReadOnly, Keys, Count...)
        # como si fueran archivos procesados, contaminando el JSON guardado.
        procesados = [PSCustomObject]@{}
    }
}

function Guardar-Estado {
    param($Nombre, $HashVal, $Length, $LastWriteTime)
    $estado = Leer-Estado
    $props = @{}
    if ($null -ne $estado.procesados) {
        $estado.procesados.PSObject.Properties | ForEach-Object {
            $props[$_.Name] = $_.Value
        }
    }

    $props[$Nombre] = @{
        hash = $HashVal
        size = $Length
        mtime = $LastWriteTime
        fecha_sync = (Get-Date).ToString("o")
    }

    $nuevoEstado = [PSCustomObject]@{
        ultimo_archivo = $Nombre
        ultimo_hash = $HashVal
        fecha_actualizacion = (Get-Date).ToString("o")
        procesados = $props
    }

    $json = $nuevoEstado | ConvertTo-Json -Depth 5
    $ok = Invoke-EscrituraConReintento -Accion { Set-Content -Path $EstadoFile -Value $json -Encoding UTF8 }
    if (-not $ok) {
        Write-Log "No se pudo persistir el estado de sincronizacion para $Nombre en $EstadoFile (quedara pendiente de reintento en la proxima corrida)." "ERROR"
    }
}

function Test-ArchivoListo {
    param([string]$Ruta)
    try {
        $stream = [System.IO.File]::Open($Ruta, 'Open', 'Read', 'Read')
        $stream.Close()
        $stream.Dispose()
        return $true
    } catch {
        return $false
    }
}

function Sincronizar-Copias {
    Write-Log "Revisando carpeta de copias: $CopiasDir..." "INFO"
    $archivosZip = Get-ChildItem -Path $CopiasDir -File | Where-Object { $_.Extension -match '^\.zip$' } | Sort-Object LastWriteTime

    if ($archivosZip.Count -eq 0) {
        Write-Log "No hay archivos .Zip en $CopiasDir." "INFO"
        return
    }

    $estado = Leer-Estado
    $nEnviados = 0
    $nFallidos = 0
    $nOmitidos = 0

    foreach ($archivo in $archivosZip) {
        $nombre = $archivo.Name

        # Verificar si el archivo esta listo para lectura (no bloqueado por SG)
        if (-not (Test-ArchivoListo -Ruta $archivo.FullName)) {
            Write-Log "El archivo $nombre esta en uso o siendo escrito. Se omitira en este ciclo." "WARN"
            continue
        }

        # Calcular hash MD5 del archivo
        $fileHash = (Get-FileHash -Path $archivo.FullName -Algorithm MD5).Hash

        # Comprobar si ya fue sincronizado
        $yaSincronizado = $false
        if ($null -ne $estado.procesados) {
            $reg = $estado.procesados.$nombre
            if ($null -ne $reg -and $reg.hash -eq $fileHash) {
                $yaSincronizado = $true
            }
        }

        if ($yaSincronizado) {
            $nOmitidos++
            continue
        }

        Write-Log "Nuevo backup detectado: $nombre ($([math]::Round($archivo.Length/1MB, 2)) MB). Iniciando transferencia..." "INFO"

        # 1. Enviar via SCP al VPS
        $scpTarget = "${VpsUser}@${VpsHost}:${VpsDestDir}/$nombre"
        Write-Log "Ejecutando SCP a $scpTarget..." "INFO"
        & scp @SshOpts "$($archivo.FullName)" "$scpTarget"

        if ($LASTEXITCODE -ne 0) {
            Write-Log "Error en la transferencia SCP de $nombre (codigo: $LASTEXITCODE)." "ERROR"
            $nFallidos++
            Start-Sleep -Seconds 2
            continue
        }

        Write-Log "Transferencia SCP completada. Disparando importacion remota en VPS..." "INFO"

        # 2. Ejecutar script de importacion remota por SSH
        $sshCmd = "bash ${VpsProjectPath}/scripts/importar_backup.sh ${VpsDestDir}/$nombre"
        & ssh @SshOpts "${VpsUser}@${VpsHost}" "$sshCmd"

        if ($LASTEXITCODE -eq 0) {
            Write-Log "[OK] Importacion remota completada exitosamente para $nombre." "INFO"
            Guardar-Estado -Nombre $nombre -HashVal $fileHash -Length $archivo.Length -LastWriteTime $archivo.LastWriteTimeUtc.ToString("o")
            $nEnviados++
        } else {
            Write-Log "[WARN] Error al ejecutar importacion remota para $nombre (codigo: $LASTEXITCODE)." "ERROR"
            $nFallidos++
            Start-Sleep -Seconds 2
        }
    }

    Write-Log "Resumen del ciclo: $nEnviados enviados, $nFallidos fallidos, $nOmitidos ya sincronizados (de $($archivosZip.Count) backups en carpeta)." "INFO"
}

Write-Log ">> Iniciando vigilante de copias SG (Windows -> VPS $VpsHost)" "INFO"
Write-Log "Carpeta vigilada: $CopiasDir | Intervalo: ${IntervaloSegundos}s" "INFO"

if ($UnaVez) {
    Sincronizar-Copias
    exit 0
}

while ($true) {
    try {
        Sincronizar-Copias
    } catch {
        Write-Log "Excepcion durante la sincronizacion: $_" "ERROR"
    }
    Start-Sleep -Seconds $IntervaloSegundos
}
