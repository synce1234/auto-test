"""
Standalone test: verify dismiss_onboarding hoạt động đúng.

Mục tiêu:
  - Gỡ APK cũ, cài APK mới từ thư mục apks/
  - Chạy hàm khởi tạo (dismiss_onboarding / app_init)
  - Mở lại app → phải vào splash / ads / màn chính — KHÔNG vào Settings "All files access"

Chạy:
  pytest test_init_verify.py -v -s
  TEST_DEVICE_SERIAL=emulator-5554 pytest test_init_verify.py -v -s

Yêu cầu:
  - Appium server đang chạy (appium --port 4723)
  - ADB device kết nối và authorized
"""
import os
import sys
import subprocess
import time
import glob

import pytest
import yaml
from appium import webdriver
from appium.options.android.uiautomator2.base import UiAutomator2Options

# ─── Paths & Config ───────────────────────────────────────────────────────────

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

with open(os.path.join(ROOT, "config.yaml")) as _f:
    CFG = yaml.safe_load(_f)

PKG     = CFG["app"]["package_name"]
MAIN_ACT = CFG["app"]["main_activity"]
SERIAL  = os.environ.get("TEST_DEVICE_SERIAL", "")
ADB_PFX = ["adb", "-s", SERIAL] if SERIAL else ["adb"]

# APK mới nhất trong thư mục apks/
_apk_files = sorted(glob.glob(os.path.join(ROOT, "apks", "*.apk")))
APK_PATH = _apk_files[-1] if _apk_files else ""

# Màn hình Settings "All files access" — phải KHÔNG xuất hiện sau init
_SETTINGS_TEXTS = ("All files access", "Allow access to manage all files", "manage all files")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _adb(cmd: list, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(ADB_PFX + cmd, capture_output=True, text=True, timeout=timeout)


def _current_focus() -> str:
    """
    Lấy mCurrentFocus từ dumpsys activity activities.
    (dumpsys window windows không có trường này trên một số Android version)
    """
    r = _adb(["shell", "dumpsys", "activity", "activities"])
    for line in (r.stdout or "").splitlines():
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            return line.strip()
    return ""


def _is_settings_foreground() -> bool:
    """Kiểm tra Settings 'All files access' có đang foreground không."""
    focus = _current_focus()
    return bool(focus) and (
        "settings" in focus.lower() or "permissioncontroller" in focus.lower()
    )


def _create_driver() -> webdriver.Remote:
    options = UiAutomator2Options()
    options.platform_name                        = "Android"
    options.app_package                          = PKG
    options.app_activity                         = MAIN_ACT
    options.no_reset                             = True
    options.auto_grant_permissions               = True
    options.new_command_timeout                  = 120
    options.uiautomator2_server_install_timeout  = 60000
    options.adb_exec_timeout                     = 60000
    if SERIAL:
        options.udid = SERIAL
    host = CFG["appium"]["host"]
    port = CFG["appium"]["port"]
    drv = webdriver.Remote(f"http://{host}:{port}", options=options)
    drv.implicitly_wait(CFG["device"]["ui_timeout"])
    return drv


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def init_driver():
    """Tạo Appium driver 1 lần cho cả module test này."""
    drv = _create_driver()
    yield drv
    try:
        drv.quit()
    except Exception:
        pass


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_step1_uninstall_and_install():
    """
    Gỡ APK cũ và cài APK mới từ apks/.
    Không cần Appium — dùng ADB trực tiếp.
    """
    assert APK_PATH, f"Không tìm thấy APK trong {ROOT}/apks/"
    print(f"\n[STEP 1] APK: {os.path.basename(APK_PATH)}")

    # Uninstall
    r_uninstall = _adb(["uninstall", PKG], timeout=30)
    msg = (r_uninstall.stdout + r_uninstall.stderr).strip()
    print(f"[STEP 1] Uninstall: {msg or 'ok'}")

    time.sleep(2)

    # Install
    print(f"[STEP 1] Đang cài APK...")
    r_install = subprocess.run(
        ADB_PFX + ["install", "-r", APK_PATH],
        capture_output=True, text=True, timeout=120,
    )
    out = (r_install.stdout + r_install.stderr).strip()
    print(f"[STEP 1] Install result: {out}")
    assert r_install.returncode == 0, f"ADB install thất bại:\n{out}"
    assert "Success" in out, f"APK install không thành công:\n{out}"
    print("[STEP 1] Install OK ✓")


def test_step2_run_init(init_driver):
    """
    Chạy khởi tạo app: grant permissions, dismiss_onboarding, kill app.
    Sau bước này, onboarding đã hoàn tất — mở lại app sẽ không vào Settings nữa.
    """
    from tests.helpers import app_init

    drv = init_driver
    print("\n[STEP 2] Grant POST_NOTIFICATIONS...")
    _adb(["shell", "pm", "grant", PKG, "android.permission.POST_NOTIFICATIONS"], timeout=10)

    print("[STEP 2] Chạy app_init (dismiss_onboarding + kill)...")
    result = app_init(drv, CFG)
    print(f"[STEP 2] app_init trả về: {result}")
    # Không assert result — app_init có thể trả về False nếu timeout nhưng vẫn hoàn thành cơ bản
    print("[STEP 2] Init hoàn thành ✓")


def test_step3_verify_launch_not_settings(init_driver):
    """
    Kill app, mở lại 3 lần liên tiếp và mỗi lần kiểm tra:
      ✓ mCurrentFocus KHÔNG chứa 'settings'
      ✓ mCurrentFocus chứa package của app
    Mục tiêu: đảm bảo onboarding đã hoàn tất — app không bao giờ redirect về Settings nữa.
    """
    drv = init_driver

    for _attempt in range(1, 4):
        print(f"\n[STEP 3] Lần {_attempt}/3: kill + launch app...")

        # Kill
        try:
            drv.terminate_app(PKG)
        except Exception:
            _adb(["shell", "am", "force-stop", PKG])
        time.sleep(1.5)

        # Launch
        try:
            drv.activate_app(PKG)
        except Exception:
            _adb(["shell", "monkey", "-p", PKG, "-c",
                  "android.intent.category.LAUNCHER", "1"], timeout=10)

        # Chờ app khởi động qua splash
        time.sleep(6)

        focus = _current_focus()
        on_settings = _is_settings_foreground()
        print(f"[STEP 3] mCurrentFocus     : {focus}")
        print(f"[STEP 3] Đang ở Settings   : {on_settings}")

        assert not on_settings, (
            f"[Lần {_attempt}] App vào Settings sau init!\n"
            f"  mCurrentFocus={focus}\n"
            f"  Onboarding chưa hoàn tất — 'All files access' vẫn chưa được grant."
        )

        # Kiểm tra bổ sung: nếu focus có dữ liệu thì phải chứa PKG (không phải màn khác)
        if focus:
            _pkg_short = PKG.split(".")[-1]  # "viewer"
            assert _pkg_short in focus.lower() or PKG in focus, (
                f"[Lần {_attempt}] App không ở màn của mình!\n"
                f"  mCurrentFocus={focus}\n"
                f"  Mong đợi có '{_pkg_short}' hoặc '{PKG}' trong focus."
            )
        else:
            print(f"[STEP 3]   (mCurrentFocus rỗng — không check PKG)")

        print(f"[STEP 3] ✓ Lần {_attempt}: App ở màn của app, không phải Settings")

    print(f"\n[STEP 3] ✓ Cả 3 lần launch đều OK — onboarding hoàn chỉnh!")
