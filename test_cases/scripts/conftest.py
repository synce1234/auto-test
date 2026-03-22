"""
conftest.py cho test_cases/scripts/
Cung cấp driver, adb, cfg fixtures và đăng ký tc_pytest_plugin.
"""
import os
import sys
import base64
import pytest
import yaml

# Import SESSION_TIMESTAMP từ plugin để dùng chung đường dẫn assets
from test_cases.tc_pytest_plugin import SESSION_TIMESTAMP

# Thêm auto-test root vào path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from appium import webdriver
from appium.options.android.uiautomator2.base import UiAutomator2Options
from core.adb_controller import ADBController

# Đăng ký plugin TC Manager — cung cấp tc_manager + tc_result fixtures
# và tự động save report Excel khi session kết thúc
pytest_plugins = ["test_cases.tc_pytest_plugin"]


# ─── Load config ──────────────────────────────────────────────────────────────

def _load_config():
    config_path = os.path.join(os.path.dirname(__file__), "../../config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


CFG = _load_config()

# Thư mục assets riêng cho session này
_REPORTS_ROOT  = os.path.join(os.path.dirname(__file__), "../../reports")
_SCREENSHOT_DIR = os.path.join(_REPORTS_ROOT, "screenshots", SESSION_TIMESTAMP)
_VIDEO_DIR      = os.path.join(_REPORTS_ROOT, "videos",      SESSION_TIMESTAMP)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def cfg():
    return CFG


@pytest.fixture(scope="session")
def adb():
    """ADB controller — serial từ env var."""
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    return ADBController(serial)


@pytest.fixture(scope="session")
def driver():
    """Appium driver dùng chung cả session."""
    options = UiAutomator2Options()
    options.platform_name          = "Android"
    options.app_package            = CFG["app"]["package_name"]
    options.app_activity           = CFG["app"]["main_activity"]
    options.no_reset               = True
    options.auto_grant_permissions = True
    options.new_command_timeout    = 120

    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    if serial:
        options.udid = serial

    host = CFG["appium"]["host"]
    port = CFG["appium"]["port"]

    drv = webdriver.Remote(f"http://{host}:{port}", options=options)
    drv.implicitly_wait(CFG["device"]["ui_timeout"])

    yield drv
    drv.quit()


# ─── Video recording ──────────────────────────────────────────────────────────

def _video_enabled() -> bool:
    return CFG.get("test", {}).get("record_video", False)


def _video_quality() -> str:
    return CFG.get("test", {}).get("video_quality", "medium")


def _video_save_mode() -> str:
    """'on_failure' hoặc 'always'"""
    return CFG.get("test", {}).get("video_save_mode", "on_failure")


def _tc_id_from_item(item) -> str | None:
    """
    Lấy TC ID từ test item.
    Ưu tiên: tc_result.tc_id → tên class (TestTC001 → TC_001).
    """
    import re
    # 1. Thử từ tc_result fixture
    funcargs = getattr(item, "funcargs", None) or (
        getattr(item, "node", None) and getattr(item.node, "funcargs", None)
    )
    if funcargs:
        tc_result_obj = funcargs.get("tc_result")
        tc_id = getattr(tc_result_obj, "tc_id", None) if tc_result_obj else None
        if tc_id:
            return tc_id
    # 2. Thử từ tên class (TestTC001 → TC_001)
    cls = getattr(item, "cls", None)
    if cls:
        m = re.match(r"TestTC(\d+)", cls.__name__)
        if m:
            return f"TC_{m.group(1).zfill(3)}"
    return None


def _save_video(drv, test_name: str) -> str | None:
    """Stop recording và lưu video ra file MP4. Trả về đường dẫn file hoặc None."""
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


@pytest.fixture(autouse=True)
def video_recorder(driver, request):
    """
    Tự động quay video màn hình cho mỗi test.
    Lưu video theo video_save_mode trong config:
      - 'on_failure': chỉ lưu khi test FAIL
      - 'always'    : lưu tất cả
    """
    if not _video_enabled():
        yield
        return

    # Bắt đầu quay
    quality_map = {"high": 8000000, "medium": 4000000, "low": 1000000}
    bit_rate = quality_map.get(_video_quality(), 4000000)
    try:
        driver.start_recording_screen(
            video_size="1080x1920",
            time_limit="600",     # tối đa 10 phút / test
            bit_rate=bit_rate,
        )
    except Exception as e:
        print(f"\n  [VIDEO START FAILED] {e}")

    yield  # ← test chạy ở đây

    # Dừng quay và quyết định có lưu không
    save_mode = _video_save_mode()
    tc_id     = _tc_id_from_item(request.node)
    fname     = f"{tc_id}_{request.node.name}" if tc_id else request.node.name

    if save_mode == "always":
        path = _save_video(driver, fname)
        if path:
            print(f"\n  [VIDEO] {path}")
    else:
        # Lưu tạm vào bộ nhớ, hook makereport quyết định có ghi file không
        try:
            request.node._video_b64  = driver.stop_recording_screen()
            request.node._video_fname = fname
        except Exception:
            request.node._video_b64  = None
            request.node._video_fname = fname


# ─── Screenshot + Video khi fail ──────────────────────────────────────────────

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    drv = item.funcargs.get("driver") if hasattr(item, "funcargs") and item.funcargs else None
    if not drv:
        return

    test_cfg = CFG.get("test", {})

    # Lấy tc_id để prefix tên file
    tc_id = _tc_id_from_item(item)
    fname = f"{tc_id}_{item.name}" if tc_id else item.name

    # Screenshot — chụp luôn nếu video_save_mode=always, hoặc chỉ khi fail
    save_ss = test_cfg.get("screenshot_on_failure") and (
        report.failed or test_cfg.get("video_save_mode") == "always"
    )
    if save_ss:
        try:
            os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
            path = os.path.join(_SCREENSHOT_DIR, f"{fname}.png")
            drv.save_screenshot(path)
            print(f"\n  [SCREENSHOT] {path}")
        except Exception as e:
            print(f"\n  [SCREENSHOT FAILED] {e}")

    if report.failed:
        # Video on_failure: lấy video đã stop trong fixture, ghi file
        if test_cfg.get("record_video") and test_cfg.get("video_save_mode") == "on_failure":
            video_b64  = getattr(item, "_video_b64", None)
            video_fname = getattr(item, "_video_fname", fname)
            if video_b64:
                try:
                    os.makedirs(_VIDEO_DIR, exist_ok=True)
                    path = os.path.join(_VIDEO_DIR, f"{video_fname}.mp4")
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(video_b64))
                    print(f"\n  [VIDEO] {path}")
                except Exception as e:
                    print(f"\n  [VIDEO SAVE FAILED] {e}")
