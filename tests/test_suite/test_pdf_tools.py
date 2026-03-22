"""
Test PDF Tools - Kiểm tra các tính năng PDF: Split, Merge, Sign, Scanner.
Tập trung vào việc mở được màn hình tool và không crash.
"""
import time
import pytest
from appium.webdriver.common.appiumby import AppiumBy

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from tests.helpers import (
    find, find_all, is_visible, rid,
    go_to_home, dismiss_onboarding, dismiss_ads, _is_ad_showing,
    open_fab_menu, close_fab_menu,
)


class TestPDFTools:

    @pytest.fixture(autouse=True)
    def setup(self, driver, cfg):
        """Đảm bảo đang ở Home và FAB menu đóng trước mỗi test."""
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)
        dismiss_onboarding(driver, cfg)
        go_to_home(driver, cfg)

    # ── FAB Menu ─────────────────────────────────────────────────────────────

    def test_fab_menu_opens(self, driver):
        """Bấm FAB (+) → bottom sheet tool menu xuất hiện."""
        result = open_fab_menu(driver)
        assert result, "FAB menu không mở được"
        close_fab_menu(driver)

    def test_fab_menu_has_all_tools(self, driver):
        """Tool menu có đủ các nút: Split, Merge, Sign, Scanner, Image to PDF."""
        open_fab_menu(driver)

        tools = {
            "btn_split_file":        "Split File",
            "btn_merge_file":        "Merge File",
            "btn_sign_pdf":          "Sign PDF",
            "btn_create_pdf_scanner":"PDF Scanner",
            "btn_create_image_to_pdf":"Image to PDF",
        }
        missing = []
        for tool_id, tool_name in tools.items():
            if not is_visible(driver, tool_id, timeout=5):
                missing.append(tool_name)

        close_fab_menu(driver)
        assert not missing, f"Không tìm thấy các tool: {missing}"

    # ── Split PDF ────────────────────────────────────────────────────────────

    def test_split_pdf_screen_opens(self, driver):
        """Mở màn hình Split PDF không crash."""
        open_fab_menu(driver)
        find(driver, "btn_split_file").click()
        time.sleep(3)

        # Màn hình split phải hiển thị (không còn ở home)
        assert not is_visible(driver, "btn_action_create_file", timeout=2), \
            "Vẫn đang ở home sau khi click Split"

        # Verify không crash
        source = driver.page_source
        assert len(source) > 200, "Màn hình Split trống/crash"
        print(f"\n  Activity: {driver.current_activity}")

        driver.back()
        time.sleep(1)

    def test_split_pdf_file_list_visible(self, driver):
        """Màn hình Split PDF hiển thị danh sách file để chọn."""
        open_fab_menu(driver)
        find(driver, "btn_split_file").click()
        time.sleep(3)

        # Tìm RecyclerView danh sách file trong màn hình split
        found = (
            is_visible(driver, "rcv_split_file", timeout=5) or
            is_visible(driver, "rcv_all_file", timeout=5) or
            is_visible(driver, "rvFiles", timeout=5)
        )
        # Fallback: tìm bất kỳ RecyclerView nào
        if not found:
            rvs = driver.find_elements(AppiumBy.CLASS_NAME, "androidx.recyclerview.widget.RecyclerView")
            found = len(rvs) > 0

        driver.back()
        time.sleep(1)
        assert found, "Màn hình Split không có danh sách file"

    # ── Merge PDF ────────────────────────────────────────────────────────────

    def test_merge_pdf_screen_opens(self, driver):
        """Mở màn hình Merge PDF không crash."""
        open_fab_menu(driver)
        find(driver, "btn_merge_file").click()
        time.sleep(3)

        source = driver.page_source
        assert len(source) > 200, "Màn hình Merge crash"
        print(f"\n  Activity: {driver.current_activity}")

        driver.back()
        time.sleep(1)

    # ── PDF Scanner ──────────────────────────────────────────────────────────

    def test_scanner_screen_opens(self, driver):
        """Mở màn hình PDF Scanner không crash."""
        open_fab_menu(driver)
        find(driver, "btn_create_pdf_scanner").click()
        time.sleep(3)

        source = driver.page_source
        assert len(source) > 200, "Màn hình Scanner crash"
        print(f"\n  Activity: {driver.current_activity}")

        driver.back()
        time.sleep(1)

    # ── Sign PDF ─────────────────────────────────────────────────────────────

    def test_sign_pdf_screen_opens(self, driver):
        """Mở màn hình Sign PDF không crash."""
        open_fab_menu(driver)
        find(driver, "btn_sign_pdf").click()
        time.sleep(3)

        source = driver.page_source
        assert len(source) > 200, "Màn hình Sign PDF crash"

        driver.back()
        time.sleep(1)
