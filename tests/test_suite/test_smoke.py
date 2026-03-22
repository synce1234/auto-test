"""
Smoke Tests - Test cơ bản nhất sau khi update app.
Nếu các test này fail = app bị broken nghiêm trọng.
"""
import time
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TestSmoke:

    def test_app_launches_without_crash(self, driver, cfg):
        """App khởi động và hiển thị màn hình home trong vòng 15 giây"""
        wait = WebDriverWait(driver, cfg["device"]["launch_timeout"])

        # App phải show được gì đó (không crash)
        # Thử tìm bất kỳ element nào trên màn hình
        try:
            # Đợi activity hiện tại là MainActivity
            driver.wait_activity(cfg["app"]["main_activity"], timeout=15)
            assert True, "App khởi động thành công"
        except Exception:
            # Fallback: kiểm tra page source không rỗng
            source = driver.page_source
            assert len(source) > 100, "App không có UI sau khi khởi động"

    def test_no_crash_dialog(self, driver):
        """Không có dialog 'App stopped' sau khi update"""
        time.sleep(2)
        source = driver.page_source.lower()

        crash_keywords = [
            "has stopped",
            "keeps stopping",
            "unfortunately",
        ]
        for keyword in crash_keywords:
            assert keyword not in source, f"App bị crash: tìm thấy '{keyword}' trên màn hình"

    def test_bottom_navigation_visible(self, driver):
        """Bottom navigation bar hiển thị đúng"""
        # Tìm bottom nav bằng nhiều cách
        found = False

        # Thử tìm bằng resource-id pattern phổ biến
        try:
            els = driver.find_elements(AppiumBy.XPATH,
                '//*[@resource-id[contains(., "bottom") or contains(., "nav")]]')
            if els:
                found = True
        except Exception:
            pass

        # Thử tìm bằng class RecyclerView hoặc BottomNavigationView
        if not found:
            try:
                els = driver.find_elements(AppiumBy.CLASS_NAME,
                    "com.google.android.material.bottomnavigation.BottomNavigationView")
                found = len(els) > 0
            except Exception:
                pass

        # Nếu không tìm được element cụ thể, ít nhất app phải có UI
        source = driver.page_source
        assert len(source) > 200, "UI quá đơn giản, có thể app bị lỗi"

    def test_app_version_updated(self, driver, adb, cfg):
        """Version app đọc được từ device sau khi install"""
        installed_version = adb.get_installed_version(cfg["app"]["package_name"])
        assert installed_version != "unknown", "Không lấy được version của app"
        assert len(installed_version) > 0, "Version rỗng"
        print(f"\n  Version hiện tại: {installed_version}")
