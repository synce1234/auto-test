#!/usr/bin/env bash
# Double-click file này trên Mac để khởi động dashboard và mở trình duyệt.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=8080
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
SERVER="$SCRIPT_DIR/server.py"
APPIUM_PORT=4723

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC}  $*"; }
info() { echo -e "${CYAN}→${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
fail() { echo -e "${RED}✗${NC}  $*"; read -p "Nhấn Enter để đóng..."; exit 1; }

echo -e "\n${BOLD}╔══════════════════════════════════════════╗"
echo -e "║      Auto Test Dashboard — Start         ║"
echo -e "╚══════════════════════════════════════════╝${NC}\n"

# Kiểm tra .venv — tự cài nếu chưa có
if [[ ! -f "$VENV_PYTHON" ]]; then
  warn ".venv chưa có — đang chạy setup.sh..."
  bash "$SCRIPT_DIR/setup.sh" || fail "setup.sh thất bại. Kiểm tra lại môi trường."
fi

# Android SDK
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}"
export ANDROID_SDK_ROOT="$SDK_ROOT"
export PATH="$PATH:$SDK_ROOT/platform-tools:$SDK_ROOT/emulator"

# Appium
if lsof -i ":$APPIUM_PORT" -sTCP:LISTEN &>/dev/null 2>&1; then
  ok "Appium đang chạy trên port $APPIUM_PORT"
elif command -v appium &>/dev/null; then
  info "Đang start Appium (port $APPIUM_PORT)..."
  appium --port "$APPIUM_PORT" --log-level error --log /tmp/appium.log &
  sleep 2
  ok "Appium đã start (log: /tmp/appium.log)"
else
  warn "Appium chưa cài — test sẽ không chạy được"
fi

# Mở trình duyệt sau 1.5 giây (chờ server kịp start)
(sleep 1.5 && open "http://localhost:$PORT") &

echo -e "\n  ${BOLD}Dashboard :${NC} ${CYAN}http://localhost:$PORT${NC}"
echo -e "  ${BOLD}Project   :${NC} ${CYAN}$SCRIPT_DIR${NC}"
echo -e "\n  Nhấn ${BOLD}Ctrl+C${NC} để dừng.\n"

"$VENV_PYTHON" "$SERVER" --port "$PORT"

# Giữ cửa sổ Terminal mở nếu server crash
echo -e "\n${RED}Server đã dừng.${NC}"
read -p "Nhấn Enter để đóng..."
