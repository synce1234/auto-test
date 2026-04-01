"""
init_app.py — Chạy bước khởi tạo app (onboarding) trước khi test suite bắt đầu.

Dùng cùng Appium session config với conftest.py nhưng chạy độc lập qua subprocess.
Server gọi: python init_app.py --device <serial>

Exit code:
  0 = thành công
  1 = lỗi
"""
import sys
import os
import time
import argparse
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from appium import webdriver
from appium.options.android.uiautomator2.base import UiAutomator2Options
from tests.helpers import app_init


def _load_cfg():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="", help="ADB serial của device")
    args = parser.parse_args()

    cfg = _load_cfg()

    options = UiAutomator2Options()
    options.platform_name          = "Android"
    options.app_package            = cfg["app"]["package_name"]
    options.app_activity           = cfg["app"]["main_activity"]
    options.no_reset               = True
    options.auto_grant_permissions = True
    options.new_command_timeout    = 120
    options.uiautomator2_server_install_timeout = 60000
    options.adb_exec_timeout                    = 60000

    if args.device:
        options.udid = args.device

    host = cfg["appium"]["host"]
    port = cfg["appium"]["port"]

    driver = None
    try:
        print(f"[INIT] Kết nối Appium {host}:{port}...")
        driver = webdriver.Remote(f"http://{host}:{port}", options=options)
        driver.implicitly_wait(cfg["device"]["ui_timeout"])
        print("[INIT] Kết nối thành công")

        ok = app_init(driver, cfg)
        print(f"[INIT] Kết quả: {'OK ✓' if ok else 'WARNING - onboarding chưa hoàn thành'}")
        sys.exit(0)

    except Exception as e:
        print(f"[INIT] LỖI: {e}", file=sys.stderr)
        sys.exit(1)

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
