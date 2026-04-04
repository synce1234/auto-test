"""
Standalone test: verify go_to_home() hoạt động đúng.

Mục tiêu: sau khi gọi go_to_home(), app phải đang hiển thị màn Home
(rcv_all_file — danh sách file).

Các tình huống test:
  1. App đang ở Home → vẫn trả về True
  2. App đang ở reader (mở 1 file) → go_to_home đưa về Home
  3. App bị kill → go_to_home relaunch và về Home

Chạy:
  TEST_DEVICE_SERIAL=emulator-5554 pytest test_go_to_home.py -v -s
"""
import os
import sys
import subprocess
import time

import pytest
import yaml
from appium import webdriver
from appium.options.android.uiautomator2.base import UiAutomator2Options

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

with open(os.path.join(ROOT, "config.yaml")) as _f:
    CFG = yaml.safe_load(_f)

PKG    = CFG["app"]["package_name"]
SERIAL = os.environ.get("TEST_DEVICE_SERIAL", "")
ADB    = ["adb", "-s", SERIAL] if SERIAL else ["adb"]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _adb(cmd, timeout=30):
    return subprocess.run(ADB + cmd, capture_output=True, text=True, timeout=timeout)


def _current_focus() -> str:
    r = _adb(["shell", "dumpsys", "activity", "activities"])
    for line in (r.stdout or "").splitlines():
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            return line.strip()
    return ""


def _create_driver():
    options = UiAutomator2Options()
    options.platform_name                       = "Android"
    options.app_package                         = PKG
    options.app_activity                        = CFG["app"]["main_activity"]
    options.no_reset                            = True
    options.auto_grant_permissions              = True
    options.new_command_timeout                 = 120
    options.uiautomator2_server_install_timeout = 60000
    options.adb_exec_timeout                    = 60000
    if SERIAL:
        options.udid = SERIAL
    drv = webdriver.Remote(
        f"http://{CFG['appium']['host']}:{CFG['appium']['port']}",
        options=options,
    )
    drv.implicitly_wait(CFG["device"]["ui_timeout"])
    return drv


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def drv():
    driver = _create_driver()
    # Đảm bảo app đang chạy trước khi test
    try:
        driver.activate_app(PKG)
        time.sleep(3)
    except Exception:
        pass
    yield driver
    try:
        driver.quit()
    except Exception:
        pass


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_go_to_home_from_home(drv):
    """
    Tình huống 1: App đang ở Home.
    go_to_home() phải trả về True ngay.
    """
    from tests.helpers import go_to_home, _is_home_screen

    print("\n[T1] Đảm bảo đang ở Home trước...")
    result_pre = go_to_home(drv, CFG)
    assert result_pre, "Không thể về Home để setup cho T1"

    print("[T1] Gọi go_to_home() khi đã ở Home...")
    result = go_to_home(drv, CFG)

    focus = _current_focus()
    home_adb = _is_home_screen(drv, SERIAL)
    print(f"[T1] go_to_home() = {result}")
    print(f"[T1] _is_home_screen (ADB) = {home_adb}")
    print(f"[T1] mCurrentFocus = {focus}")

    assert result, "go_to_home() trả về False khi đã ở Home"
    assert home_adb, "ADB dump không thấy rcv_all_file khi đang ở Home"


def test_go_to_home_from_reader(drv):
    """
    Tình huống 2: App đang mở file (reader view).
    go_to_home() phải đưa về Home (rcv_all_file).
    """
    from tests.helpers import go_to_home, _is_home_screen

    print("\n[T2] Setup: mở file trong reader...")
    # Tìm file PDF đầu tiên trên device và mở bằng am start intent
    _r_ls = _adb(["shell", "find", "/sdcard/Download", "-name", "*.pdf", "-maxdepth", "2"])
    _pdf = (_r_ls.stdout or "").strip().splitlines()
    _pdf = [p for p in _pdf if p.strip()]

    if _pdf:
        _file = _pdf[0].strip()
        print(f"[T2] Mở file: {_file}")
        _adb([
            "shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"file://{_file}",
            "-n", f"{PKG}/com.simple.pdf.reader.ui.office.DocReaderActivity",
        ], timeout=15)
        time.sleep(5)
    else:
        print("[T2] Không có PDF trên device — dùng monkey để mở app + navigate")
        _adb(["shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1"])
        time.sleep(3)

    focus_before = _current_focus()
    print(f"[T2] Trước go_to_home: {focus_before}")

    result = go_to_home(drv, CFG)

    focus_after = _current_focus()
    home_adb = _is_home_screen(drv, SERIAL)
    print(f"[T2] go_to_home() = {result}")
    print(f"[T2] _is_home_screen (ADB) = {home_adb}")
    print(f"[T2] Sau go_to_home: {focus_after}")

    assert result, "go_to_home() trả về False sau khi từ reader"
    assert home_adb, "ADB dump không thấy rcv_all_file sau go_to_home từ reader"


def test_go_to_home_from_killed(drv):
    """
    Tình huống 3: App bị kill.
    go_to_home() phải relaunch và về Home.
    """
    from tests.helpers import go_to_home, _is_home_screen

    print("\n[T3] Kill app...")
    try:
        drv.terminate_app(PKG)
    except Exception:
        _adb(["shell", "am", "force-stop", PKG])
    time.sleep(2)

    focus_before = _current_focus()
    print(f"[T3] Sau kill: {focus_before}")

    result = go_to_home(drv, CFG)

    focus_after = _current_focus()
    home_adb = _is_home_screen(drv, SERIAL)
    print(f"[T3] go_to_home() = {result}")
    print(f"[T3] _is_home_screen (ADB) = {home_adb}")
    print(f"[T3] Sau go_to_home: {focus_after}")

    assert result, "go_to_home() trả về False sau khi app bị kill"
    assert home_adb, "ADB dump không thấy rcv_all_file sau go_to_home từ killed state"
