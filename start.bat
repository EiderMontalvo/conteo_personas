@echo off
REM ============================================================
REM start.bat - Inicia el Sistema de Conteo de Personas (Windows)
REM ============================================================
REM Doble clic aqui o en el acceso directo del escritorio.
REM Instala lo que falte, compila el dashboard si cambio y abre
REM http://localhost:8000 en el navegador.
REM Para crear el acceso directo: crear_acceso_directo.bat
REM ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
