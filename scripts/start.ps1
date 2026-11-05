# ============================================================
# start.ps1 - Prepara e inicia todo el sistema (Windows)
# ============================================================
# Lo llama start.bat (doble clic) o el acceso directo del escritorio.
# Cada vez que arranca:
#   1. Busca Python 3.9+ (ofrece instalarlo con winget si no hay)
#   2. Crea el entorno virtual e instala dependencias si cambiaron
#   3. Instala dependencias del frontend y lo compila si cambio el codigo
#   4. Crea backend\.env desde la plantilla si no existe
#   5. Inicia el servidor y abre el dashboard en el navegador
# Cerrar esta ventana detiene el sistema.
# Solo ASCII en este archivo: PowerShell 5.1 lo lee como ANSI.
# ============================================================

$ErrorActionPreference = 'Stop'
$Root      = Split-Path -Parent $PSScriptRoot
$Backend   = Join-Path $Root 'backend'
$Frontend  = Join-Path $Root 'frontend'
$Venv      = Join-Path $Root 'venv'
$VenvPy    = Join-Path $Venv 'Scripts\python.exe'
$Port      = 8000
$Url       = "http://localhost:$Port"
# Las comprobaciones van a 127.0.0.1: "localhost" resuelve primero a ::1 (IPv6),
# el servidor solo escucha en IPv4 y .NET agota el timeout antes de reintentar.
$Health    = "http://127.0.0.1:$Port/api/v1/settings"

$Host.UI.RawUI.WindowTitle = 'Conteo de Personas'

function Info($msg)  { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "[AVISO] $msg" -ForegroundColor Yellow }
function Fail($msg) {
    Write-Host ""
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    Write-Host ""
    Read-Host 'Presiona Enter para cerrar'
    exit 1
}

function Ask($question) {
    $answer = Read-Host "$question [S/n]"
    return ($answer -eq '' -or $answer -match '^(s|si|y|yes)$')
}

# Recarga el PATH del registro (tras instalar algo con winget en esta sesion).
function Update-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Test-Python($exe, $prefix) {
    try {
        $out = & $exe @prefix -c "import sys; print('%d.%d' % sys.version_info[:2]); print(sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
        $ver = [version]$out[0]
        if ($ver -lt [version]'3.9') { return $null }
        return $out[1]
    } catch { return $null }
}

function Find-Python {
    $candidates = @(
        @{ exe = 'py';      prefix = @('-3') },
        @{ exe = 'python';  prefix = @() },
        @{ exe = 'python3'; prefix = @() }
    )
    $dirs = @("$env:LOCALAPPDATA\Programs\Python", "$env:ProgramFiles", "${env:ProgramFiles(x86)}")
    foreach ($d in $dirs) {
        if ($d -and (Test-Path $d)) {
            Get-ChildItem -Path $d -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                ForEach-Object { $candidates += @{ exe = (Join-Path $_.FullName 'python.exe'); prefix = @() } }
        }
    }
    foreach ($c in $candidates) {
        if ($c.exe -notmatch '\\' -and -not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
        if ($c.exe -match '\\' -and -not (Test-Path $c.exe)) { continue }
        $found = Test-Python $c.exe $c.prefix
        if ($found) { return $found }
    }
    return $null
}

function Install-WithWinget($id, $name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "$name no esta instalado y winget no esta disponible. Instalalo manualmente y vuelve a abrir."
    }
    if (-not (Ask "$name no esta instalado. Instalarlo ahora con winget?")) {
        Fail "$name es necesario. Instalalo y vuelve a abrir."
    }
    Info "Instalando $name (puede tardar unos minutos)..."
    winget install -e --id $id --scope user --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        # Algunos paquetes no admiten --scope user
        winget install -e --id $id --silent --accept-package-agreements --accept-source-agreements
    }
    Update-Path
}

# Ejecuta $action solo si el hash de $file cambio desde la ultima vez ($stamp).
function Invoke-IfChanged($file, $stamp, [scriptblock]$action) {
    $hash = (Get-FileHash $file -Algorithm SHA256).Hash
    if ((Test-Path $stamp) -and ((Get-Content $stamp -Raw).Trim() -eq $hash)) { return $false }
    & $action
    Set-Content -Path $stamp -Value $hash -Encoding ascii
    return $true
}

# Cualquier error no previsto: mostrarlo y esperar, en vez de cerrar la ventana.
trap {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "        en: $($_.InvocationInfo.PositionMessage)" -ForegroundColor DarkGray
    Write-Host ""
    Read-Host 'Presiona Enter para cerrar'
    exit 1
}

Write-Host ""
Write-Host "  Sistema de Conteo de Personas" -ForegroundColor White
Write-Host "  ============================================" -ForegroundColor DarkGray
Write-Host ""

# -- 0. Ya esta corriendo? ---------------------------------------
try {
    $r = Invoke-WebRequest $Health -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) {
        Ok "El sistema ya esta en marcha. Abriendo el dashboard..."
        Start-Process $Url
        Start-Sleep -Seconds 2
        exit 0
    }
} catch { }

# Puerto ocupado por otro programa (no responde como este sistema)
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($busy) {
    $owner = (Get-Process -Id $busy.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Fail "El puerto $Port esta ocupado por otro programa ($owner, PID $($busy.OwningProcess)). Cierralo y vuelve a abrir."
}

# -- 1. Python y entorno virtual ----------------------------------
if (-not (Test-Path $VenvPy) -or -not (Test-Python $VenvPy @())) {
    $py = Find-Python
    if (-not $py) {
        Install-WithWinget 'Python.Python.3.13' 'Python 3'
        $py = Find-Python
        if (-not $py) { Fail 'No se encontro Python despues de instalarlo. Cierra y vuelve a abrir.' }
    }
    Info "Creando entorno virtual con $py ..."
    if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
    & $py -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Fail 'No se pudo crear el entorno virtual.' }
}
Ok "Python: $(& $VenvPy --version)"

$null = Invoke-IfChanged (Join-Path $Backend 'requirements.txt') (Join-Path $Venv '.requirements.sha256') {
    Info 'Instalando dependencias del backend...'
    & $VenvPy -m pip install --disable-pip-version-check -q -r (Join-Path $Backend 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { Fail 'Fallo la instalacion de dependencias de Python.' }
}
Ok 'Dependencias del backend al dia'

# -- 2. Frontend --------------------------------------------------
$Dist      = Join-Path $Frontend 'dist'
$DistIndex = Join-Path $Dist 'index.html'
$hasNpm    = [bool](Get-Command npm -ErrorAction SilentlyContinue)

if (-not $hasNpm -and -not (Test-Path $DistIndex)) {
    Install-WithWinget 'OpenJS.NodeJS.LTS' 'Node.js'
    $hasNpm = [bool](Get-Command npm -ErrorAction SilentlyContinue)
    if (-not $hasNpm) { Fail 'No se encontro npm despues de instalar Node.js. Cierra y vuelve a abrir.' }
}

if ($hasNpm) {
    Push-Location $Frontend
    try {
        $lock = Join-Path $Frontend 'package-lock.json'
        $nodeModules = Join-Path $Frontend 'node_modules'
        if (-not (Test-Path $nodeModules)) { New-Item -ItemType Directory $nodeModules | Out-Null }
        $null = Invoke-IfChanged $lock (Join-Path $nodeModules '.lock.sha256') {
            Info 'Instalando dependencias del frontend...'
            npm install --no-audit --no-fund --loglevel=error
            if ($LASTEXITCODE -ne 0) { Fail 'Fallo npm install.' }
        }
        Ok 'Dependencias del frontend al dia'

        # Recompilar solo si algun archivo fuente es mas nuevo que la ultima compilacion
        $sources = @('src', 'public', 'index.html', 'vite.config.js', 'tailwind.config.js',
                     'postcss.config.js', 'package-lock.json') |
            ForEach-Object { Join-Path $Frontend $_ } | Where-Object { Test-Path $_ }
        $newest = Get-ChildItem $sources -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $needsBuild = -not (Test-Path $DistIndex) -or ($newest.LastWriteTime -gt (Get-Item $DistIndex).LastWriteTime)
        if ($needsBuild) {
            Info 'Compilando el dashboard (solo cuando cambia el codigo)...'
            npm run build --silent
            if ($LASTEXITCODE -ne 0) { Fail 'Fallo la compilacion del frontend.' }
        }
        Ok 'Dashboard compilado'
    } finally { Pop-Location }
} else {
    Warn 'npm no esta instalado: se usa el dashboard ya compilado.'
}

# -- 3. Configuracion ---------------------------------------------
$EnvFile = Join-Path $Backend '.env'
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Backend '.env.example') $EnvFile
    Warn 'Se creo backend\.env desde la plantilla.'
    Warn 'Completa CAMERA_USER, CAMERA_PASS y la IP de la camara, guarda y cierra el Bloc de notas.'
    Start-Process notepad.exe -ArgumentList "`"$EnvFile`"" -Wait
}
Ok 'Configuracion: backend\.env'

# -- 4. Abrir el navegador cuando el servidor responda ------------
$opener = @"
for (`$i = 0; `$i -lt 90; `$i++) {
    try { if ((Invoke-WebRequest '$Health' -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { Start-Process '$Url'; break } } catch { }
    Start-Sleep -Seconds 1
}
"@
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', $opener

# -- 5. Servidor (en esta ventana) --------------------------------
Write-Host ""
Write-Host "  Dashboard: $Url" -ForegroundColor White
Write-Host "  NO cierres esta ventana: al cerrarla se detiene el sistema." -ForegroundColor Yellow
Write-Host ""

Set-Location $Backend
& $VenvPy main.py --port $Port
$code = $LASTEXITCODE
if ($code -ne 0) { Fail "El servidor se detuvo con un error (codigo $code). Revisa los mensajes de arriba." }
