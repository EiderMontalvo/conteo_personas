@echo off
REM ============================================================
REM start.bat - Script de inicio para Windows
REM ============================================================
REM Uso: Doble clic en start.bat, o ejecutar desde CMD/PowerShell
REM ============================================================

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%venv"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "PYTHON_BIN=%VENV_DIR%\Scripts\python.exe"
set "PIP_BIN=%VENV_DIR%\Scripts\pip.exe"

echo.
echo  Sistema de Conteo de Personas
echo  ====================================================

REM ── 1. Verificar que Python esté instalado ──────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python 3.9+ desde https://python.org
    echo         Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

REM ── 2. Crear entorno virtual si no existe ───────────────────
if not exist "%PYTHON_BIN%" (
    echo [INFO] Creando entorno virtual...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

REM ── 3. Instalar dependencias ────────────────────────────────
echo [INFO] Instalando/verificando dependencias...
"%PIP_BIN%" install -q -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Fallo al instalar dependencias.
    pause
    exit /b 1
)

REM ── 3.1. Dependencias del Frontend ──────────────────────────
echo [INFO] Verificando dependencias del Frontend...
cd /d "%FRONTEND_DIR%"
where npm >nul 2>&1
if not errorlevel 1 (
    if not exist "node_modules\" (
        echo [INFO] Descargando dependencias de Node ^(npm install^)...
        call npm install
    )
) else (
    echo [WARNING] npm no encontrado. No se puede compilar el frontend automaticamente.
)
cd /d "%PROJECT_DIR%"

REM ── 4. Verificar que existe el .env ─────────────────────────
if not exist "%BACKEND_DIR%\.env" (
    echo [ERROR] No se encontro backend\.env
    echo         Copia backend\.env.example a backend\.env y configura tus credenciales.
    pause
    exit /b 1
)

REM ── 5. Iniciar Frontend en segundo plano ────────────────────
echo [INFO] Iniciando servidor de Frontend en http://localhost:3001 ...
cd /d "%FRONTEND_DIR%"
start "BI Frontend" /min cmd /c "npm run dev -- --port 3001"
cd /d "%PROJECT_DIR%"

REM ── 6. Iniciar Backend ──────────────────────────────────────
echo [INFO] Iniciando Backend FastAPI en http://localhost:8000 ...
echo [INFO] Dashboard disponible en: http://localhost:3001
echo        Cierra esta ventana para detener el sistema.
echo.

cd /d "%BACKEND_DIR%"
"%PYTHON_BIN%" main.py

pause
