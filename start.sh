#!/usr/bin/env bash
# ============================================================
# start.sh - Script de inicio para Linux / macOS
# ============================================================
# Uso:
#   chmod +x start.sh   (solo la primera vez)
#   ./start.sh
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

# ── 1. Crear entorno virtual si no existe ───────────────────
if [ ! -f "$PYTHON_BIN" ]; then
    echo "[INFO] Creando entorno virtual..."
    python3 -m venv "$VENV_DIR"
fi

# ── 2. Instalar dependencias ────────────────────────────────
echo "[INFO] Instalando/verificando dependencias..."
"$PIP_BIN" install -q -r "$BACKEND_DIR/requirements.txt"

# ── 3. Verificar que existe el .env ─────────────────────────
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "[ERROR] No se encontró backend/.env"
    echo "        Copia backend/.env.example a backend/.env y configura tus credenciales."
    exit 1
fi

# ── 4. Iniciar Frontend en segundo plano ────────────────────
echo "[INFO] Iniciando servidor de Frontend en http://localhost:3001 ..."
cd "$FRONTEND_DIR"
"$PYTHON_BIN" -m http.server 3001 &
FRONTEND_PID=$!
cd "$PROJECT_DIR"

# ── 5. Iniciar Backend ──────────────────────────────────────
echo "[INFO] Iniciando Backend FastAPI en http://localhost:8000 ..."
echo "[INFO] Dashboard disponible en: http://localhost:3001"
echo "       Presiona Ctrl+C para detener ambos servidores."

trap "echo ''; echo '[INFO] Deteniendo servidores...'; kill $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

cd "$BACKEND_DIR"
"$PYTHON_BIN" main.py
