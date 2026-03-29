"""
conftest.py gốc — dùng chung cho toàn bộ test suite.
Gộp từ tests/conftest.py và test_cases/scripts/conftest.py.
"""
import os
import re
import sys
import base64
import time
import subprocess
import pytest
import yaml
from datetime import datetime

# Đảm bảo project root luôn trong sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Đăng ký tc_pytest_plugin — tự động generate Excel + HTML dashboard khi session kết thúc
pytest_plugins = ["test_cases.tc_pytest_plugin"]

from appium import webdriver
from appium.options.android.uiautomator2.base import UiAutomator2Options
from core.adb_controller import ADBController
from test_cases.tc_pytest_plugin import SESSION_TIMESTAMP


# ─── Load config ───────────────────────────────────────────────────────────────

def _load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


CFG = _load_config()

_REPORTS_ROOT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
_SCREENSHOT_DIR = os.path.join(_REPORTS_ROOT, "screenshots", SESSION_TIMESTAMP)
_VIDEO_DIR      = os.path.join(_REPORTS_ROOT, "videos",      SESSION_TIMESTAMP)

# Session driver reference — dùng để start recording sớm nhất có thể (trước fixtures)
_session_driver  = None
_recording_active = False  # True khi đang có recording chạy


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def cfg():
    return CFG


@pytest.fixture(scope="session")
def adb():
    """ADB controller dùng chung — serial lấy từ env var."""
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    return ADBController(serial)


def _wait_for_device(serial: str = "", timeout: int = 60) -> bool:
    """Chờ ADB device online và authorized."""
    adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            adb_prefix + ["shell", "echo", "ok"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and "ok" in result.stdout:
            return True
        time.sleep(2)
    return False


def _restart_appium(port: int, serial: str = ""):
    """Restart Appium server, chờ device authorized và Appium sẵn sàng."""
    subprocess.run(["pkill", "-f", "node.*appium"], capture_output=True)
    time.sleep(3)
    subprocess.Popen(
        ["appium", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Chờ device authorized trước
    _wait_for_device(serial)
    # Chờ Appium sẵn sàng
    import urllib.request
    for _ in range(20):
        time.sleep(2)
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/status", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
    return False


@pytest.fixture(scope="session")
def driver():
    """Tạo Appium driver 1 lần cho cả session test. Tự restart Appium nếu gặp Settings timeout."""
    global _session_driver
    options = UiAutomator2Options()
    options.platform_name          = "Android"
    options.app_package            = CFG["app"]["package_name"]
    options.app_activity           = CFG["app"]["main_activity"]
    options.no_reset               = True
    options.auto_grant_permissions = True
    options.new_command_timeout    = 120
    # Tăng timeout để emulator có đủ thời gian settle trước khi Appium cài Settings app
    options.uiautomator2_server_install_timeout = 60000
    options.adb_exec_timeout                    = 60000

    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    if serial:
        options.udid = serial

    host = CFG["appium"]["host"]
    port = CFG["appium"]["port"]

    drv = None
    for attempt in range(3):
        try:
            drv = webdriver.Remote(f"http://{host}:{port}", options=options)
            break
        except Exception as e:
            if "Appium Settings app is not running" in str(e) and attempt < 2:
                print(f"\n  [APPIUM] Settings timeout, restarting Appium (attempt {attempt + 1})...")
                _restart_appium(port, serial)
            else:
                raise

    drv.implicitly_wait(CFG["device"]["ui_timeout"])

    # Lưu reference sớm để pytest_runtest_protocol có thể dùng
    _session_driver = drv

    # Grant media/storage permissions (cần cho các TC liên quan đến file)
    _adb = ADBController(serial)
    pkg  = CFG["app"]["package_name"]
    for perm in [
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
    ]:
        try:
            _adb._run(["shell", "pm", "grant", pkg, perm])
        except Exception:
            pass

    # Chờ app khởi động, dismiss onboarding + ad 1 lần cho cả session
    time.sleep(CFG["device"]["launch_timeout"])
    from tests.helpers import dismiss_onboarding, dismiss_ads, _is_ad_showing
    if _is_ad_showing(drv):
        dismiss_ads(drv)
        time.sleep(1)
    dismiss_onboarding(drv, CFG)

    yield drv
    _session_driver = None
    drv.quit()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _tc_id_from_item(item) -> str | None:
    """
    Lấy TC ID từ test item.
    Ưu tiên: @pytest.mark.tc_id → tc_result.tc_id → tên class (TestTC001 → TC_001).
    """
    # 1. Từ @pytest.mark.tc_id("TC-026")
    marker = item.get_closest_marker("tc_id")
    if marker and marker.args:
        return str(marker.args[0]).replace("-", "_")

    # 2. Từ tc_result fixture
    funcargs = getattr(item, "funcargs", None)
    if funcargs:
        tc_result_obj = funcargs.get("tc_result")
        tc_id = getattr(tc_result_obj, "tc_id", None) if tc_result_obj else None
        if tc_id:
            return tc_id

    # 3. Từ tên class (TestTC001 → TC_001)
    cls = getattr(item, "cls", None)
    if cls:
        m = re.match(r"TestTC(\d+)", cls.__name__)
        if m:
            return f"TC_{m.group(1).zfill(3)}"

    return None


# ─── Video recording ───────────────────────────────────────────────────────────

def _video_enabled() -> bool:
    return CFG.get("test", {}).get("record_video", False)


def _video_quality() -> str:
    return CFG.get("test", {}).get("video_quality", "medium")


def _save_video(drv, test_name: str) -> str | None:
    """Stop recording và lưu video ra file MP4."""
    try:
        video_b64 = drv.stop_recording_screen()
        if not video_b64:
            return None
        os.makedirs(_VIDEO_DIR, exist_ok=True)
        path = os.path.join(_VIDEO_DIR, f"{test_name}.mp4")
        with open(path, "wb") as f:
            f.write(base64.b64decode(video_b64))
        return path
    except Exception as e:
        print(f"\n  [VIDEO SAVE FAILED] {e}")
        return None


def _do_start_recording(drv) -> bool:
    """Gọi start_recording_screen, trả về True nếu thành công."""
    global _recording_active
    if _recording_active:
        return True
    quality_map = {"high": 8000000, "medium": 4000000, "low": 1000000}
    bit_rate = quality_map.get(_video_quality(), 4000000)
    try:
        drv.start_recording_screen(
            video_size="1080x1920",
            time_limit="600",
            bit_rate=bit_rate,
        )
        _recording_active = True
        return True
    except Exception as e:
        print(f"\n  [VIDEO START FAILED] {e}")
        return False


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """
    Start recording TRƯỚC KHI bất kỳ fixture nào chạy.
    Test đầu tiên của session: _session_driver chưa có → video_recorder fixture sẽ xử lý.
    Các test sau: recording bắt đầu ở đây, trước fresh_launch / setup fixtures.
    """
    global _recording_active
    _recording_active = False  # Reset cho mỗi test
    need_confirm = item.get_closest_marker("need_confirm") is not None
    if _session_driver and (_video_enabled() or need_confirm):
        _do_start_recording(_session_driver)
    yield


def _is_uia2_crash(e: Exception) -> bool:
    """Kiểm tra exception có phải do UiAutomator2 instrumentation crash không."""
    return "instrumentation process is not running" in str(e)


def _adb_recover_home(serial: str = ""):
    """
    Dùng ADB thuần (bypass UiAutomator2) để về Home screen.
    Gọi khi UiAutomator2 bị crash và Appium command không dùng được.
    """
    adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
    # Force-stop UiAutomator2 server để Appium restart lại khi cần
    for pkg in ["io.appium.uiautomator2.server", "io.appium.uiautomator2.server.test"]:
        subprocess.run(adb_prefix + ["shell", "am", "force-stop", pkg],
                       capture_output=True)
    # Dùng ADB input để press Home (không cần UiAutomator2)
    subprocess.run(adb_prefix + ["shell", "input", "keyevent", "3"],
                   capture_output=True)
    time.sleep(3)  # Chờ UiAutomator2 restart tự động


@pytest.fixture(autouse=True)
def setup_before_test(driver):
    """Kill app PDF và về home screen trước mỗi test."""
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    # Chờ device sẵn sàng (phòng trường hợp emulator đang authorize sau reboot)
    _wait_for_device(serial, timeout=30)
    pkg = CFG["app"]["package_name"]
    try:
        driver.terminate_app(pkg)
    except Exception:
        # Fallback: dùng ADB force-stop khi Appium không dùng được
        subprocess.run((["adb", "-s", serial] if serial else ["adb"]) +
                       ["shell", "am", "force-stop", pkg], capture_output=True)
    try:
        driver.press_keycode(3)  # KEYCODE_HOME
    except Exception as e:
        if _is_uia2_crash(e):
            print(f"\n  [UIA2 CRASH] UiAutomator2 crashed, recovering via ADB...")
            _adb_recover_home(serial)
        else:
            # Fallback ADB cho mọi lỗi khác
            subprocess.run((["adb", "-s", serial] if serial else ["adb"]) +
                           ["shell", "input", "keyevent", "3"], capture_output=True)
    time.sleep(1)
    yield


@pytest.fixture(autouse=True)
def video_recorder(driver, request):
    """
    Quay video toàn bộ quá trình test từ lúc start đến khi kết thúc.
    Luôn lưu video sau mỗi test (không phân biệt pass/fail).
    Recording khởi động bởi pytest_runtest_protocol hook (trước mọi fixture).
    Fixture này chỉ start nếu hook chưa start (test đầu tiên của session).
    """
    global _recording_active
    need_confirm = request.node.get_closest_marker("need_confirm") is not None
    if not _video_enabled() and not need_confirm:
        yield
        return

    # Chỉ start nếu hook chưa start (thường là test đầu tiên của session)
    if not _recording_active:
        _do_start_recording(driver)

    yield

    # ── Teardown: dừng và lưu video ──
    _recording_active = False

    tc_id = _tc_id_from_item(request.node)
    fname = f"{tc_id}_{request.node.name}" if tc_id else request.node.name
    path  = _save_video(driver, fname)
    if path:
        print(f"\n  [VIDEO] {path}")


# ─── Ghi kết quả từ @pytest.mark.tc_id ────────────────────────────────────────

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """Map @pytest.mark.tc_id marker → TCManager để update Excel/HTML dashboard."""
    start = time.time()
    outcome = yield
    duration = time.time() - start

    # Không xử lý nếu test dùng tc_result fixture (tránh double-write)
    if item.funcargs.get("tc_result"):
        return

    tc_mgr = item.funcargs.get("tc_manager")
    if not tc_mgr:
        return

    marker = item.get_closest_marker("tc_id")
    if not marker or not marker.args:
        return

    tc_id = str(marker.args[0]).replace("-", "_")

    if outcome.excinfo:
        exc_type = outcome.excinfo[0]
        exc_val  = outcome.excinfo[1]
        import _pytest.outcomes as _outcomes
        if exc_type is not None and issubclass(exc_type, _outcomes.Skipped):
            reason = str(exc_val)
            if "NEED CONFIRM" in reason.upper():
                status = "NEED CONFIRM"
            else:
                status = "SKIP"
            actual = reason
        else:
            status = "FAIL"
            actual = str(exc_val)
    else:
        status = "PASS"
        actual = "Test passed"

    tc_mgr.update_result(tc_id=tc_id, status=status, actual=actual, duration=duration)


# ─── Screenshot khi call phase kết thúc ───────────────────────────────────────

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report  = outcome.get_result()

    if report.when != "call":
        return

    drv = item.funcargs.get("driver") if hasattr(item, "funcargs") and item.funcargs else None
    if not drv:
        return

    tc_id = _tc_id_from_item(item)
    fname = f"{tc_id}_{item.name}" if tc_id else item.name

    # Screenshot — chụp cả PASS lẫn FAIL
    if report.passed or report.failed:
        try:
            os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
            suffix = "PASS" if report.passed else "FAIL"
            path   = os.path.join(_SCREENSHOT_DIR, f"{fname}_{suffix}.png")
            drv.save_screenshot(path)
            print(f"\n  [SCREENSHOT] {path}")
        except Exception as e:
            print(f"\n  [SCREENSHOT FAILED] {e}")
