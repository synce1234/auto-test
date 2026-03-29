#!/usr/bin/env bash
# =============================================================================
# run.sh — Khởi động Auto Test Dashboard (macOS / Linux)
#
# Cách dùng:
#   ./run.sh              # Start Appium + Dashboard (port 8080)
#   ./run.sh --port 9090  # Đổi port
#   ./run.sh --no-appium  # Không tự start Appium
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC}  $*"; }
fail() { echo -e "${RED}✗${NC}  $*" >&2; exit 1; }
info() { echo -e "${CYAN}→${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
SERVER="$SCRIPT_DIR/server.py"
PORT=8080
APPIUM_PORT=4723
START_APPIUM=true

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)      PORT="$2"; shift ;;
    --no-appium) START_APPIUM=false ;;
    -h|--help)
      echo "Cách dùng: $0 [--port PORT] [--no-appium]"
      exit 0 ;;
    *) warn "Bỏ qua: $1" ;;
  esac
  shift
done

echo -e "\n${BOLD}╔══════════════════════════════════════════╗"
echo -e "║      Auto Test Dashboard — Start         ║"
echo -e "╚══════════════════════════════════════════╝${NC}"

# ── Kiểm tra .venv ────────────────────────────────────────────────────────────
if [[ ! -f "$VENV_PYTHON" ]]; then
  fail ".venv không tìm thấy. Hãy chạy './setup.sh' trước."
fi

# ── Android SDK path ──────────────────────────────────────────────────────────
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK_ROOT" ]]; then
  [[ "$(uname -s)" == "Darwin" ]] && SDK_ROOT="$HOME/Library/Android/sdk" || SDK_ROOT="$HOME/Android/Sdk"
fi
export ANDROID_SDK_ROOT="$SDK_ROOT"
export PATH="$PATH:$SDK_ROOT/platform-tools:$SDK_ROOT/emulator"

# ── Appium ────────────────────────────────────────────────────────────────────
if [[ "$START_APPIUM" == true ]]; then
  if lsof -i ":$APPIUM_PORT" -sTCP:LISTEN &>/dev/null 2>&1; then
    ok "Appium đang chạy trên port $APPIUM_PORT"
  else
    if command -v appium &>/dev/null; then
      info "Đang start Appium (port $APPIUM_PORT)..."
      appium --port "$APPIUM_PORT" --log-level error --log /tmp/appium.log &
      APPIUM_PID=$!
      sleep 2
      if kill -0 "$APPIUM_PID" 2>/dev/null; then
        ok "Appium đã start (PID $APPIUM_PID, log: /tmp/appium.log)"
      else
        warn "Không start được Appium — kiểm tra lại nếu cần chạy test"
      fi
    else
      warn "Appium chưa cài — chạy './setup.sh' để cài"
    fi
  fi
fi

# ── Start server ──────────────────────────────────────────────────────────────
echo -e "\n  ${BOLD}Dashboard :${NC} ${CYAN}http://localhost:$PORT${NC}"
echo -e "  ${BOLD}Project   :${NC} ${CYAN}$SCRIPT_DIR${NC}"
echo -e "\n  Nhấn ${BOLD}Ctrl+C${NC} để dừng.\n"

exec "$VENV_PYTHON" "$SERVER" --port "$PORT"
