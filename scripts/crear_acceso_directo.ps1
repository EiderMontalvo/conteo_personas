# Crea "Conteo de Personas" en el escritorio, apuntando a start.bat.
# Solo ASCII en este archivo: PowerShell 5.1 lo lee como ANSI.
$ErrorActionPreference = 'Stop'
$Root    = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath('Desktop')   # respeta OneDrive
$Link    = Join-Path $Desktop 'Conteo de Personas.lnk'

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($Link)
$sc.TargetPath       = Join-Path $Root 'start.bat'
$sc.WorkingDirectory = $Root
$sc.IconLocation     = (Join-Path $PSScriptRoot 'conteo.ico') + ',0'
$sc.Description      = 'Inicia el sistema de conteo de personas y abre el dashboard'
$sc.WindowStyle      = 1
$sc.Save()

Write-Host ""
Write-Host "[ OK ] Acceso directo creado: $Link" -ForegroundColor Green
Write-Host "       Doble clic para iniciar el sistema. Cerrar su ventana lo detiene."
Write-Host ""
