#!/usr/bin/env bash
# ============================================================
# start.sh - Prepara e inicia todo el sistema (Linux / macOS)
# ============================================================
# Uso:
#   chmod +x start.sh   (solo la primera vez)
#   ./start.sh
# Cada vez que arranca:
#   1. Crea el entorno virtual e instala dependencias si cambiaron
#   2. Instala dependencias del frontend y lo compila si cambio el codigo
#   3. Crea backend/.env desde la plantilla si no existe
#   4. Inicia el servidor y abre http://localhost:8000
# Ctrl+C detiene el sistema.
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PYTHON_BIN="$VENV_DIR/bin/python"
PORT=8000
URL="http://localhost:$PORT"

info() { printf '\033[36m[INFO]\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m[ OK ]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[AVISO]\033[0m %s\n' "$*"; }
fail() { printf '\033[31m[ERROR]\033[0m %s\n' "$*"; exit 1; }

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

# Ejecuta el resto de argumentos solo si el hash de $1 cambio (guardado en $2).
run_if_changed() {
    local file="$1" stamp="$2"; shift 2
    local hash; hash="$(sha "$file")"
    if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$hash" ]; then return 0; fi
    "$@"
    echo "$hash" > "$stamp"
}

open_url() {
    if command -v xdg-open >/dev/null; then xdg-open "$1" >/dev/null 2>&1 || true
    elif command -v open >/dev/null; then open "$1" || true
    fi
}

echo
echo "  Sistema de Conteo de Personas"
echo "  ============================================"
echo

# -- 0. Ya esta corriendo? ---------------------------------------
if curl -fs -m 3 "http://127.0.0.1:$PORT/api/v1/settings" >/dev/null 2>&1; then
    ok "El sistema ya esta en marcha. Abriendo el dashboard..."
    open_url "$URL"
    exit 0
fi

# -- 1. Python y entorno virtual ----------------------------------
command -v python3 >/dev/null || fail "Python 3.9+ no esta instalado (Debian/Ubuntu: sudo apt install python3 python3-venv)."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || fail "Se necesita Python 3.9 o superior."
if [ ! -x "$PYTHON_BIN" ]; then
    info "Creando entorno virtual..."
    python3 -m venv "$VENV_DIR" || fail "No se pudo crear el entorno virtual (Debian/Ubuntu: sudo apt install python3-venv)."
fi
install_backend() {
    info "Instalando dependencias del backend..."
    "$PYTHON_BIN" -m pip install --disable-pip-version-check -q -r "$BACKEND_DIR/requirements.txt"
}
run_if_changed "$BACKEND_DIR/requirements.txt" "$VENV_DIR/.requirements.sha256" install_backend
ok "Dependencias del backend al dia"

# -- 2. Frontend --------------------------------------------------
DIST_INDEX="$FRONTEND_DIR/dist/index.html"
if command -v npm >/dev/null; then
    cd "$FRONTEND_DIR"
    mkdir -p node_modules
    install_frontend() {
        info "Instalando dependencias del frontend..."
        npm install --no-audit --no-fund --loglevel=error
    }
    run_if_changed package-lock.json node_modules/.lock.sha256 install_frontend
    ok "Dependencias del frontend al dia"

    # Recompilar solo si algun archivo fuente es mas nuevo que la ultima compilacion
    if [ ! -f "$DIST_INDEX" ] || [ -n "$(find src public index.html vite.config.js tailwind.config.js \
            postcss.config.js package-lock.json -type f -newer "$DIST_INDEX" 2>/dev/null | head -1)" ]; then
        info "Compilando el dashboard (solo cuando cambia el codigo)..."
        npm run build --silent
    fi
    ok "Dashboard compilado"
    cd "$PROJECT_DIR"
elif [ -f "$DIST_INDEX" ]; then
    warn "npm no esta instalado: se usa el dashboard ya compilado."
else
    fail "Node.js 18+ no esta instalado y el dashboard no esta compilado. Instala Node.js y vuelve a ejecutar."
fi

# -- 3. Configuracion ---------------------------------------------
if [ ! -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    warn "Se creo backend/.env desde la plantilla."
    warn "Completa CAMERA_USER, CAMERA_PASS y la IP de la camara en backend/.env y vuelve a ejecutar."
    exit 1
fi
ok "Configuracion: backend/.env"

# -- 4. Abrir el navegador cuando el servidor responda ------------
(
    for _ in $(seq 1 90); do
        if curl -fs -m 3 "http://127.0.0.1:$PORT/api/v1/settings" >/dev/null 2>&1; then open_url "$URL"; break; fi
        sleep 1
    done
) &

# -- 5. Servidor --------------------------------------------------
echo
echo "  Dashboard: $URL"
echo "  Ctrl+C detiene el sistema."
echo

cd "$BACKEND_DIR"
exec "$PYTHON_BIN" main.py --port "$PORT"
