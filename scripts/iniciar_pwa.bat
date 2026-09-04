@echo off
REM ==========================================================================
REM  Arranque del Dashboard PWA con doble clic (Windows).
REM  Equivalente a scripts\iniciar_pwa.ps1 pero interactivo: valida entorno,
REM  arranca la PWA y abre el navegador en http://localhost:8080.
REM  No toca Etapas B/C ni el bot de Telegram.
REM ==========================================================================
cd /d "%~dp0.."
if not defined BITACORA_DB set BITACORA_DB=data\bitacora.db
if not defined PWA_PORT set PWA_PORT=8080
if not defined PWA_HOST set PWA_HOST=0.0.0.0

if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activando entorno virtual (.venv)...
    call ".venv\Scripts\activate.bat"
)

if not exist "%BITACORA_DB%" (
    echo [ERROR] No se encontro la base de datos: %BITACORA_DB%
    echo         Verifique data\bitacora.db o defina BITACORA_DB con la ruta correcta.
    pause
    exit /b 1
)

python -c "import flask" 2>nul
if errorlevel 1 (
    echo [ERROR] Flask no esta instalado.
    echo         Instalelo con:  pip install flask
    pause
    exit /b 2
)

echo Iniciando PWA Bitacora JA en http://localhost:%PWA_PORT% ...
start "PWA Bitacora JA" /min python src\pwa\app.py
timeout /t 3 /nobreak >nul
echo Abriendo navegador en http://localhost:%PWA_PORT% ...
start "" "http://localhost:%PWA_PORT%"
echo.
echo PWA corriendo. No cierre la ventana "PWA Bitacora JA".
echo Para detenerla: cierre esa ventana o pulse Ctrl+C en ella.
pause
