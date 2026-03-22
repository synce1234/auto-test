#!/bin/bash
# Helper script để chạy auto-test với đúng PATH

# Load Android SDK path
export ANDROID_SDK_ROOT="$HOME/Library/Android/sdk"
export PATH="$PATH:$ANDROID_SDK_ROOT/platform-tools"

# Đi đến thư mục auto-test
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Chạy orchestrator với các arguments được truyền vào
python3 orchestrator.py "$@"
