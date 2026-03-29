#!/usr/bin/env bash
# =============================================================================
# setup.sh — Cài đặt đầy đủ Auto Test Dashboard (macOS / Linux)
#
# Cách dùng:
#   chmod +x setup.sh && ./setup.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()     { echo -e "${GREEN}✓${NC}  $*"; }
fail()   { echo -e "${RED}✗${NC}  $*" >&2; exit 1; }
info()   { echo -e "${CYAN}→${NC}  $*"; }
warn()   { echo -e "${YELLOW}⚠${NC}  $*"; }
header() { echo -e "\n${BOLD}━━━  $*  ━━━${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

echo -e "\n${BOLD}╔══════════════════════════════════════════╗"
echo -e "║   Auto Test Dashboard — Cài đặt (macOS)  ║"
echo -e "╚══════════════════════════════════════════╝${NC}"
echo -e "  Thư mục: ${CYAN}$SCRIPT_DIR${NC}\n"

# ── OS ────────────────────────────────────────────────────────────────────────
header "Hệ điều hành"
OS="$(uname -s)"
if [[ "$OS" == "Darwin" ]]; then
  ok "macOS $(sw_vers -productVersion)"
elif [[ "$OS" == "Linux" ]]; then
  . /etc/os-release 2>/dev/null || true
  ok "Linux (${PRETTY_NAME:-unknown})"
else
  fail "Không hỗ trợ OS: $OS — dùng setup.bat trên Windows"
fi

# ── Homebrew (macOS only) ─────────────────────────────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
  header "Homebrew"
  if command -v brew &>/dev/null; then
    ok "Homebrew $(brew --version | head -1)"
  else
    info "Đang cài Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    ok "Homebrew đã cài xong"
  fi
fi

# ── Python 3.10+ ──────────────────────────────────────────────────────────────
header "Python 3.10+"
PYTHON=""
for py in python3.13 python3.12 python3.11 python3.10 python3; do
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
  if [[ "$OS" == "Darwin" ]]; then
    brew install python@3.11
    PYTHON="python3.11"
  else
    sudo apt-get update -qq
    sudo apt-get install -y python3.11 python3.11-venv python3-pip
    PYTHON="python3.11"
  fi
  ok "Python 3.11 đã cài xong"
fi

# ── Node.js ───────────────────────────────────────────────────────────────────
header "Node.js"
if command -v node &>/dev/null; then
  ok "Node.js $(node --version)"
else
  info "Đang cài Node.js LTS..."
  if [[ "$OS" == "Darwin" ]]; then
    brew install node
  else
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    sudo apt-get install -y nodejs
  fi
  ok "Node.js $(node --version) đã cài xong"
fi

# ── Java 17 ───────────────────────────────────────────────────────────────────
header "Java (JDK 17)"
if command -v java &>/dev/null; then
  ok "$(java -version 2>&1 | head -1)"
else
  info "Đang cài OpenJDK 17..."
  if [[ "$OS" == "Darwin" ]]; then
    brew install openjdk@17
    JAVA_PREFIX="$(brew --prefix openjdk@17)"
    if ! command -v java &>/dev/null; then
      sudo ln -sfn "$JAVA_PREFIX/libexec/openjdk.jdk" /Library/Java/JavaVirtualMachines/openjdk-17.jdk
    fi
    [[ ":$PATH:" != *":$JAVA_PREFIX/bin:"* ]] && export PATH="$JAVA_PREFIX/bin:$PATH"
    echo "export PATH=\"$JAVA_PREFIX/bin:\$PATH\"" >> "$HOME/.zprofile" 2>/dev/null || true
  else
    sudo apt-get install -y openjdk-17-jdk
  fi
  ok "Java đã cài xong"
fi

# ── Android SDK ───────────────────────────────────────────────────────────────
header "Android SDK (adb + aapt2)"
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK_ROOT" ]]; then
  [[ "$OS" == "Darwin" ]] && SDK_ROOT="$HOME/Library/Android/sdk" || SDK_ROOT="$HOME/Android/Sdk"
fi

ADB_OK=false; AAPT2_OK=false

if command -v adb &>/dev/null; then
  ok "adb $(adb version | head -1)"; ADB_OK=true
elif [[ -f "$SDK_ROOT/platform-tools/adb" ]]; then
  export PATH="$PATH:$SDK_ROOT/platform-tools"
  ok "adb (từ SDK: $SDK_ROOT/platform-tools)"; ADB_OK=true
fi

AAPT2_PATH="$(find "$SDK_ROOT/build-tools" -name "aapt2" 2>/dev/null | sort -rV | head -1 || true)"
if [[ -n "$AAPT2_PATH" ]]; then
  ok "aapt2: $AAPT2_PATH"; AAPT2_OK=true
fi

if [[ "$ADB_OK" == false || "$AAPT2_OK" == false ]]; then
  warn "Android SDK chưa đủ — cần Android Studio hoặc command-line tools"
  warn "Tải tại: https://developer.android.com/tools"
  warn "Một số tính năng sẽ không hoạt động cho đến khi cài xong"
fi

# ── Appium ────────────────────────────────────────────────────────────────────
header "Appium"
if command -v appium &>/dev/null; then
  ok "Appium $(appium --version)"
else
  info "Đang cài Appium..."
  npm install -g appium
  ok "Appium $(appium --version) đã cài xong"
fi

info "Kiểm tra UIAutomator2 driver..."
if appium driver list --installed 2>/dev/null | grep -q "uiautomator2"; then
  ok "UIAutomator2 driver đã có"
else
  info "Đang cài UIAutomator2 driver..."
  appium driver install uiautomator2
  ok "UIAutomator2 driver đã cài xong"
fi

# ── Python venv + packages ────────────────────────────────────────────────────
header "Python Virtual Environment"
if [[ -d "$VENV_DIR" ]]; then
  ok ".venv đã tồn tại"
else
  info "Đang tạo .venv..."
  "$PYTHON" -m venv "$VENV_DIR"
  ok ".venv đã tạo xong"
fi

header "Python Dependencies"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
info "Đang cài packages từ requirements.txt..."
"$VENV_DIR/bin/pip" install --quiet -r "$REQUIREMENTS"
ok "Tất cả packages đã cài xong"

# ── Xong ─────────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}✓ Cài đặt hoàn tất!${NC}"
echo -e "\n  Để chạy dashboard:"
echo -e "  ${CYAN}./run.sh${NC}\n"
