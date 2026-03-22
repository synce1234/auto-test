#!/usr/bin/env bash
# =============================================================================
# setup.sh — Cài đặt và chạy Auto Test Dashboard
#
# Cách dùng:
#   ./setup.sh            # Cài đặt đầy đủ rồi start server
#   ./setup.sh --install  # Chỉ cài đặt, không start server
#   ./setup.sh --start    # Chỉ start server (bỏ qua bước cài đặt)
#   ./setup.sh --port 9090 --dir /path/to/auto-test
# =============================================================================
set -euo pipefail

# ── Màu sắc ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()     { echo -e "${GREEN}✓${NC}  $*"; }
fail()   { echo -e "${RED}✗${NC}  $*" >&2; exit 1; }
info()   { echo -e "${CYAN}→${NC}  $*"; }
warn()   { echo -e "${YELLOW}⚠${NC}  $*"; }
header() { echo -e "\n${BOLD}━━━  $*  ━━━${NC}"; }
skip()   { echo -e "   ${YELLOW}(đã có, bỏ qua)${NC}"; }

# ── Parse args ────────────────────────────────────────────────────────────────
MODE="all"   # all | install | start
PORT=8080
DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) MODE="install" ;;
    --start)   MODE="start" ;;
    --port)    PORT="$2"; shift ;;
    --dir)     DIR="$2"; shift ;;
    -h|--help)
      echo "Cách dùng: $0 [--install|--start] [--port PORT] [--dir PATH]"
      exit 0 ;;
    *) warn "Bỏ qua tham số không rõ: $1" ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${DIR:-$SCRIPT_DIR}"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
SERVER="$SCRIPT_DIR/server.py"

echo -e "\n${BOLD}╔══════════════════════════════════════════╗"
echo -e "║      Auto Test Dashboard — Setup         ║"
echo -e "╚══════════════════════════════════════════╝${NC}"
echo -e "  Project dir : ${CYAN}$BASE_DIR${NC}"
echo -e "  Port        : ${CYAN}$PORT${NC}"
echo -e "  Mode        : ${CYAN}$MODE${NC}"

# =============================================================================
# PHẦN 1: CÀI ĐẶT
# =============================================================================
if [[ "$MODE" != "start" ]]; then

  # ── Phát hiện OS ───────────────────────────────────────────────────────────
  header "Phát hiện hệ điều hành"
  OS="$(uname -s)"
  if [[ "$OS" == "Darwin" ]]; then
    ok "macOS $(sw_vers -productVersion)"
    PKG_MANAGER="brew"
  elif [[ "$OS" == "Linux" ]]; then
    . /etc/os-release 2>/dev/null || true
    ok "Linux ($NAME)"
    PKG_MANAGER="apt"
  else
    fail "Hệ điều hành không được hỗ trợ: $OS"
  fi

  # ── Homebrew (macOS) ───────────────────────────────────────────────────────
  if [[ "$PKG_MANAGER" == "brew" ]]; then
    header "Homebrew"
    if command -v brew &>/dev/null; then
      ok "Homebrew $(brew --version | head -1)"
    else
      info "Đang cài Homebrew..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      ok "Homebrew đã cài xong"
    fi
  fi

  # ── Python 3.10+ ──────────────────────────────────────────────────────────
  header "Python"
  PYTHON=""
  for py in python3.12 python3.11 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
      VER="$("$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
      MAJOR="${VER%%.*}"; MINOR="${VER##*.}"
      if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 10 ]]; then
        PYTHON="$py"; ok "Python $VER ($py)"; break
      fi
    fi
  done

  if [[ -z "$PYTHON" ]]; then
    info "Đang cài Python 3.11..."
    if [[ "$PKG_MANAGER" == "brew" ]]; then
      brew install python@3.11
      PYTHON="python3.11"
    else
      sudo apt-get update -qq
      sudo apt-get install -y python3.11 python3.11-venv python3-pip
      PYTHON="python3.11"
    fi
    ok "Python đã cài xong"
  fi

  # ── Node.js ───────────────────────────────────────────────────────────────
  header "Node.js"
  if command -v node &>/dev/null; then
    ok "Node.js $(node --version)"
  else
    info "Đang cài Node.js..."
    if [[ "$PKG_MANAGER" == "brew" ]]; then
      brew install node
    else
      curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
      sudo apt-get install -y nodejs
    fi
    ok "Node.js $(node --version) đã cài xong"
  fi

  # ── Java (JDK) ────────────────────────────────────────────────────────────
  header "Java (JDK)"
  if command -v java &>/dev/null; then
    ok "$(java -version 2>&1 | head -1)"
  else
    info "Đang cài Java 17..."
    if [[ "$PKG_MANAGER" == "brew" ]]; then
      brew install openjdk@17
      # Thêm vào PATH nếu chưa có
      JAVA_HOME_CANDIDATE="$(brew --prefix openjdk@17)"
      if [[ ":$PATH:" != *":$JAVA_HOME_CANDIDATE/bin:"* ]]; then
        echo "export PATH=\"$JAVA_HOME_CANDIDATE/bin:\$PATH\"" >> "$HOME/.zprofile"
        export PATH="$JAVA_HOME_CANDIDATE/bin:$PATH"
      fi
    else
      sudo apt-get install -y openjdk-17-jdk
    fi
    ok "Java đã cài xong"
  fi

  # ── Android SDK (adb + aapt2) ──────────────────────────────────────────────
  header "Android SDK (adb, aapt2)"
  ADB_OK=false; AAPT2_OK=false

  if command -v adb &>/dev/null; then
    ok "adb $(adb --version | head -1)"; ADB_OK=true
  fi

  # Tìm aapt2 trong SDK build-tools
  SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}"
  if [[ ! -d "$SDK_ROOT" ]]; then
    SDK_ROOT="$HOME/Android/Sdk"  # Linux default
  fi
  AAPT2_PATH="$(find "$SDK_ROOT/build-tools" -name "aapt2" 2>/dev/null | sort -rV | head -1 || true)"
  if [[ -n "$AAPT2_PATH" ]]; then
    ok "aapt2: $AAPT2_PATH"; AAPT2_OK=true
  fi

  if [[ "$ADB_OK" == false || "$AAPT2_OK" == false ]]; then
    warn "Android SDK chưa đủ:"
    [[ "$ADB_OK" == false ]]   && warn "  • adb không tìm thấy"
    [[ "$AAPT2_OK" == false ]] && warn "  • aapt2 không tìm thấy"
    echo ""
    echo "  Cài Android command-line tools:"
    if [[ "$OS" == "Darwin" ]]; then
      echo "    brew install --cask android-studio"
      echo "  Hoặc tải SDK tools tại:"
      echo "    https://developer.android.com/tools"
    else
      echo "    sudo apt-get install android-sdk"
      echo "  Hoặc tải SDK tools tại:"
      echo "    https://developer.android.com/tools"
    fi
    echo ""
    warn "Bỏ qua Android SDK — một số tính năng có thể không hoạt động"
  fi

  # ── Appium ────────────────────────────────────────────────────────────────
  header "Appium"
  if command -v appium &>/dev/null; then
    ok "Appium $(appium --version)"
  else
    info "Đang cài Appium..."
    npm install -g appium
    ok "Appium $(appium --version) đã cài xong"
  fi

  # Appium UIAutomator2 driver
  info "Kiểm tra UIAutomator2 driver..."
  if appium driver list --installed 2>/dev/null | grep -q "uiautomator2"; then
    ok "UIAutomator2 driver đã có"
  else
    info "Đang cài UIAutomator2 driver..."
    appium driver install uiautomator2
    ok "UIAutomator2 driver đã cài xong"
  fi

  # ── Python virtual environment ────────────────────────────────────────────
  header "Python Virtual Environment"
  if [[ -d "$VENV_DIR" ]]; then
    ok ".venv đã tồn tại tại $VENV_DIR"
  else
    info "Đang tạo .venv..."
    "$PYTHON" -m venv "$VENV_DIR"
    ok ".venv đã tạo xong"
  fi

  # ── Python dependencies ───────────────────────────────────────────────────
  header "Python Dependencies"
  VENV_PIP="$VENV_DIR/bin/pip"
  "$VENV_PIP" install --quiet --upgrade pip
  info "Đang cài các package từ requirements.txt..."
  "$VENV_PIP" install --quiet -r "$REQUIREMENTS"
  ok "Tất cả Python packages đã cài xong"

  # ── Summary ───────────────────────────────────────────────────────────────
  echo -e "\n${GREEN}${BOLD}✓ Cài đặt hoàn tất!${NC}"

  if [[ "$MODE" == "install" ]]; then
    echo ""
    echo "  Để start server, chạy:"
    echo -e "  ${CYAN}$0 --start${NC}"
    echo ""
    exit 0
  fi
fi

# =============================================================================
# PHẦN 2: KHỞI ĐỘNG SERVER
# =============================================================================
header "Khởi động Auto Test Dashboard"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -f "$VENV_PYTHON" ]]; then
  fail ".venv không tồn tại. Hãy chạy '$0 --install' trước."
fi

# Kiểm tra Appium đang chạy không, nếu không thì start
APPIUM_PORT="${APPIUM_PORT:-4723}"
if ! lsof -i ":$APPIUM_PORT" -sTCP:LISTEN &>/dev/null; then
  info "Đang start Appium server (port $APPIUM_PORT)..."
  appium --port "$APPIUM_PORT" --log-level error &
  APPIUM_PID=$!
  sleep 2
  if kill -0 "$APPIUM_PID" 2>/dev/null; then
    ok "Appium server đang chạy (PID $APPIUM_PID)"
  else
    warn "Không start được Appium — kiểm tra lại nếu cần chạy test trên thiết bị thật"
  fi
else
  ok "Appium server đã chạy trên port $APPIUM_PORT"
fi

# Build server args
SERVER_ARGS=("--port" "$PORT")
if [[ -n "$DIR" ]]; then
  SERVER_ARGS+=("--dir" "$BASE_DIR")
fi

echo ""
echo -e "  ${BOLD}Dashboard:${NC}  ${CYAN}http://localhost:$PORT${NC}"
echo -e "  ${BOLD}Project:${NC}    ${CYAN}$BASE_DIR${NC}"
echo ""
echo "  Nhấn Ctrl+C để dừng."
echo ""

exec "$VENV_PYTHON" "$SERVER" "${SERVER_ARGS[@]}"
