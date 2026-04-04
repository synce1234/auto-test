"""
Standalone test: verify open_password_pdf_from_home() hoạt động đúng.

Mục tiêu: push file PDF có password lên device, tìm và click file từ màn Home,
dialog nhập password phải xuất hiện.

Chạy:
  TEST_DEVICE_SERIAL=emulator-5554 pytest test_open_password_pdf.py -v -s
"""
import os
import sys
import subprocess
import time
import re

import pytest
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

with open(os.path.join(ROOT, "config.yaml")) as _f:
    CFG = yaml.safe_load(_f)

PKG    = CFG["app"]["package_name"]
SERIAL = os.environ.get("TEST_DEVICE_SERIAL", "")
ADB    = ["adb", "-s", SERIAL] if SERIAL else ["adb"]

REMOTE_PDF = "/sdcard/Download/sample_password_autotest.pdf"
FILE_NAME  = "sample_password_autotest"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _adb(cmd, timeout=30):
    return subprocess.run(ADB + cmd, capture_output=True, text=True, timeout=timeout)


def _dump_xml() -> str:
    try:
        fname = f"/sdcard/pw_test_{int(time.time()*1000)}.xml"
        _adb(["shell", "uiautomator", "dump", fname], timeout=10)
        r = _adb(["pull", fname, "/tmp/pw_test.xml"], timeout=8)
        _adb(["shell", "rm", "-f", fname], timeout=5)
        if r.returncode != 0:
            return ""
        with open("/tmp/pw_test.xml", "r", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def _current_focus():
    r = _adb(["shell", "dumpsys", "activity", "activities"])
    for line in (r.stdout or "").splitlines():
        if "mCurrentFocus" in line:
            return line.strip()
    return ""


def _scroll_to_top():
    """Scroll về đầu danh sách bằng cách swipe nhanh từ trên xuống nhiều lần."""
    r = _adb(["shell", "wm", "size"])
    m = re.search(r"(\d+)x(\d+)", r.stdout or "")
    sw, sh = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
    # Swipe xuống (scroll list lên đầu) 5 lần
    for _ in range(5):
        _adb(["shell", "input", "swipe",
              str(sw // 2), str(int(sh * 0.30)),
              str(sw // 2), str(int(sh * 0.75)),
              "300"])
        time.sleep(0.4)
    time.sleep(0.5)


def _find_file_in_dump(xml: str):
    """Tìm file theo tên trong XML dump. Trả về (cx, cy) nếu tìm thấy, None nếu không."""
    m = re.search(
        rf'resource-id="[^"]*vl_item_file_name"[^>]*text="[^"]*{re.escape(FILE_NAME)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        xml,
    )
    if m:
        cx = (int(m.group(1)) + int(m.group(3))) // 2
        cy = (int(m.group(2)) + int(m.group(4))) // 2
        return cx, cy
    return None


def _visible_file_names_in_dump(xml: str) -> list:
    """Lấy tất cả tên file đang visible trong dump (để debug)."""
    return re.findall(r'resource-id="[^"]*vl_item_file_name"[^>]*text="([^"]*)"', xml)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def drv_adb():
    from appium import webdriver
    from appium.options.android.uiautomator2.base import UiAutomator2Options
    from core.adb_controller import ADBController

    options = UiAutomator2Options()
    options.platform_name                       = "Android"
    options.app_package                         = PKG
    options.app_activity                        = CFG["app"]["main_activity"]
    options.no_reset                            = True
    options.auto_grant_permissions              = True
    options.new_command_timeout                 = 120
    options.uiautomator2_server_install_timeout = 60000
    if SERIAL:
        options.udid = SERIAL

    driver = webdriver.Remote(
        f"http://{CFG['appium']['host']}:{CFG['appium']['port']}",
        options=options,
    )
    driver.implicitly_wait(CFG["device"]["ui_timeout"])
    adb = ADBController(SERIAL)
    yield driver, adb
    try:
        driver.quit()
    except Exception:
        pass


# ─── Test ─────────────────────────────────────────────────────────────────────

def test_open_password_pdf_from_home(drv_adb):
    """
    Verify open_password_pdf_from_home():
      1. Push file lên device
      2. go_to_home → màn Home hiện list file
      3. Scroll về đầu list, tìm file theo tên (có scroll xuống nếu cần)
      4. Click file → dialog nhập password xuất hiện
    """
    from tests.helpers import go_to_home, _is_home_screen
    from tests.test_suite.test_open_files_password import (
        push_password_pdf, open_password_pdf_from_home, wait_for_password_dialog,
    )

    driver, adb = drv_adb

    print("\n[STEP 1] Push password PDF lên device...")
    push_password_pdf(adb)
    print(f"[STEP 1] File tại: {REMOTE_PDF}")

    print("\n[STEP 2] go_to_home...")
    home_ok = go_to_home(driver, CFG)
    print(f"[STEP 2] go_to_home() = {home_ok}")
    assert home_ok, "Không vào được màn Home"

    print("\n[STEP 3] Chờ list file load...")
    time.sleep(3)
    print("[STEP 3] Scroll về đầu list trước khi tìm file...")
    _scroll_to_top()

    # Debug: dump ngay sau khi về Home
    xml0 = _dump_xml()
    visible0 = _visible_file_names_in_dump(xml0)
    print(f"[STEP 3] Files visible sau go_to_home ({len(visible0)}):")
    for fn in visible0:
        print(f"    '{fn}'")

    coord0 = _find_file_in_dump(xml0)
    print(f"[STEP 3] '{FILE_NAME}' trong dump: {coord0}")

    print("\n[STEP 4] Tìm và click file (có scroll nếu cần)...")
    clicked = open_password_pdf_from_home(driver, adb, CFG)
    print(f"[STEP 4] open_password_pdf_from_home() = {clicked}")

    if not clicked:
        # Debug dump sau khi fail
        xml_fail = _dump_xml()
        visible_fail = _visible_file_names_in_dump(xml_fail)
        print(f"[DEBUG] Files visible khi fail ({len(visible_fail)}):")
        for fn in visible_fail:
            print(f"    '{fn}'")
        print(f"[DEBUG] mCurrentFocus: {_current_focus()}")

    assert clicked, f"Không tìm/click được file '{FILE_NAME}' trong danh sách"

    print("\n[STEP 5] Chờ dialog nhập password...")
    dialog_ok = wait_for_password_dialog(driver, adb, timeout=15)
    print(f"[STEP 5] Dialog password xuất hiện: {dialog_ok}")

    if not dialog_ok:
        xml_dlg = _dump_xml()
        print(f"[DEBUG] Focus khi dialog fail: {_current_focus()}")
        ids = re.findall(r'resource-id="([^"]*)"', xml_dlg)
        print(f"[DEBUG] resource-ids on screen: {sorted(set(ids))[:20]}")

    assert dialog_ok, "Dialog nhập password không xuất hiện sau khi click file"
    print("\n[RESULT] ✓ open_password_pdf_from_home hoạt động đúng")
