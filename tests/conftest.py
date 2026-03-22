"""
pytest conftest - Setup Appium driver dùng chung cho toàn bộ test suite.
"""
import os
import sys
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from appium import webdriver
from appium.options.android.uiautomator2.base import UiAutomator2Options
from core.adb_controller import ADBController


# ─── Load config ──────────────────────────────────────────────────────────────

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


CFG = load_config()


# ─── Appium driver fixture ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def driver():
    """Tạo Appium driver 1 lần cho cả session test."""
    options = UiAutomator2Options()
    options.platform_name          = "Android"
    options.app_package            = CFG["app"]["package_name"]
    options.app_activity           = CFG["app"]["main_activity"]
    options.no_reset               = True
    options.auto_grant_permissions = True
    options.new_command_timeout    = 120

    # Đọc serial từ env var (orchestrator truyền vào khi chạy multi-device)
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    if serial:
        options.udid = serial

    host = CFG["appium"]["host"]
    port = CFG["appium"]["port"]

    drv = webdriver.Remote(f"http://{host}:{port}", options=options)
    drv.implicitly_wait(CFG["device"]["ui_timeout"])

    # Chờ app khởi động, dismiss onboarding + ad 1 lần cho cả session
    import time
    time.sleep(CFG["device"]["launch_timeout"])
    from tests.helpers import dismiss_onboarding, dismiss_ads, _is_ad_showing
    # Dismiss ad nếu có ngay khi mở
    if _is_ad_showing(drv):
        dismiss_ads(drv)
        time.sleep(1)
    dismiss_onboarding(drv, CFG)

    yield drv
    drv.quit()


@pytest.fixture(scope="session")
def adb():
    """ADB controller dùng chung — serial lấy từ env var"""
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    return ADBController(serial)


@pytest.fixture(scope="session")
def cfg():
    return CFG


# ─── Screenshot khi fail ──────────────────────────────────────────────────────

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        driver = item.funcargs.get("driver")
        if driver and CFG["test"].get("screenshot_on_failure"):
            screenshot_dir = os.path.join(
                os.path.dirname(__file__), "..", "reports", "screenshots"
            )
            os.makedirs(screenshot_dir, exist_ok=True)
            path = os.path.join(screenshot_dir, f"{item.name}.png")
            driver.save_screenshot(path)
            print(f"\n  [SCREENSHOT] {path}")
