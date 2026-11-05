@echo off
REM Crea el acceso directo "Conteo de Personas" en el escritorio.
REM Solo hace falta ejecutarlo una vez (o si mueves la carpeta del proyecto).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\crear_acceso_directo.ps1"
pause
