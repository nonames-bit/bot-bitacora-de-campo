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

function Write-Log {
    param([string]$Mensaje, [string]$Nivel = "INFO")
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $linea = "[$timestamp] [$Nivel] $Mensaje"
    Write-Host $linea
    try {
        Add-Content -Path $LogFile -Value $linea -Encoding UTF8
    } catch { }
}

function Leer-Estado {
    if (Test-Path -Path $EstadoFile) {
        try {
            $raw = Get-Content -Path $EstadoFile -Raw -Encoding UTF8
            $obj = ConvertFrom-Json $raw
            if ($obj.procesados -eq $null) {
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
        procesados = @{}
    }
}

function Guardar-Estado {
    param($Nombre, $HashVal, $Length, $LastWriteTime)
    $estado = Leer-Estado
    $props = @{}
    if ($estado.procesados -ne $null) {
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

    try {
        $nuevoEstado | ConvertTo-Json -Depth 5 | Set-Content -Path $EstadoFile -Encoding UTF8
    } catch {
        Write-Log "Error al guardar estado en $EstadoFile : $_" "ERROR"
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
        if ($estado.procesados -ne $null) {
            $reg = $estado.procesados.$nombre
            if ($reg -ne $null -and $reg.hash -eq $fileHash) {
                $yaSincronizado = $true
            }
        }

        if (-not $yaSincronizado) {
            Write-Log "Nuevo backup detectado: $nombre ($([math]::Round($archivo.Length/1MB, 2)) MB). Iniciando transferencia..." "INFO"

            # 1. Enviar via SCP al VPS
            $scpTarget = "${VpsUser}@${VpsHost}:${VpsDestDir}/$nombre"
            Write-Log "Ejecutando SCP a $scpTarget..." "INFO"
            & scp -i "$env:USERPROFILE\.ssh\id_ed25519_bitacora" -o StrictHostKeyChecking=accept-new "$($archivo.FullName)" "$scpTarget"

            if ($LASTEXITCODE -ne 0) {
                Write-Log "Error en la transferencia SCP de $nombre (codigo: $LASTEXITCODE)." "ERROR"
                continue
            }

            Write-Log "Transferencia SCP completada. Disparando importacion remota en VPS..." "INFO"

            # 2. Ejecutar script de importacion remota por SSH
            $sshCmd = "bash ${VpsProjectPath}/scripts/importar_backup.sh ${VpsDestDir}/$nombre"
            & ssh -i "$env:USERPROFILE\.ssh\id_ed25519_bitacora" -o StrictHostKeyChecking=accept-new "${VpsUser}@${VpsHost}" "$sshCmd"

            if ($LASTEXITCODE -eq 0) {
                Write-Log "[OK] Importacion remota completada exitosamente para $nombre." "INFO"
                Guardar-Estado -Nombre $nombre -HashVal $fileHash -Length $archivo.Length -LastWriteTime $archivo.LastWriteTimeUtc.ToString("o")
            } else {
                Write-Log "[WARN] Error al ejecutar importacion remota para $nombre (codigo: $LASTEXITCODE)." "ERROR"
            }
        }
    }
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
