"""
Test Data Migration - Kiểm tra dữ liệu người dùng còn nguyên sau khi update app.
Đây là test quan trọng nhất của update flow.
"""
import time  # noqa: F401 (used in setup fixture)
import pytest
from appium.webdriver.common.appiumby import AppiumBy

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from tests.helpers import (
    find, find_all, find_text_contains, is_visible, rid,
    go_to_home, dismiss_onboarding, dismiss_ads, _is_ad_showing,
)


class TestDataMigration:
    """
    Test suite này chạy SAU KHI update app từ version cũ lên mới.
    Mục tiêu: đảm bảo dữ liệu người dùng không bị mất khi update.
    """

    @pytest.fixture(autouse=True)
    def setup(self, driver, cfg):
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)
        dismiss_onboarding(driver, cfg)
        go_to_home(driver, cfg)

    # ── 1. File list còn nguyên ──────────────────────────────────────────────

    def test_file_list_preserved_after_update(self, driver):
        """
        Danh sách file vẫn còn sau khi update.
        (App không xóa index file của user)
        """
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert len(items) > 0, \
            "Danh sách file bị mất sau khi update! (Expected: có file từ version cũ)"
        print(f"\n  Số file còn lại sau update: {len(items)}")

    def test_file_names_readable(self, driver):
        """Tên file hiển thị đúng (không bị corrupt encoding)."""
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert items, "Không có file để test"

        for item in items[:5]:
            name = item.text
            assert len(name) > 0, "Tên file rỗng"
            # Kiểm tra không có ký tự lạ (replacement character)
            assert "▯" not in name and "\ufffd" not in name, \
                f"Tên file bị corrupt: '{name}'"
            print(f"    ✓ {name}")

    def test_file_size_readable(self, driver):
        """Kích thước file hiển thị đúng (không phải 0 hoặc rỗng)."""
        sizes = find_all(driver, "vl_item_file_size", timeout=10)
        assert sizes, "Không có thông tin kích thước file"

        for size_el in sizes[:5]:
            size_text = size_el.text
            assert len(size_text) > 0, "Kích thước file rỗng"
            # Phải có đơn vị KB hoặc MB
            has_unit = any(u in size_text.upper() for u in ["KB", "MB", "GB", "B"])
            assert has_unit, f"Kích thước file không hợp lệ: '{size_text}'"

    # ── 2. File có thể mở được sau update ────────────────────────────────────

    def test_first_pdf_still_openable(self, driver):
        """File PDF đầu tiên vẫn mở được sau khi update."""
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert items, "Không có file để test"

        file_name = items[0].text
        items[0].click()
        time.sleep(4)

        # Phải mở được viewer
        assert is_visible(driver, "textView_title", timeout=10), \
            f"Không mở được file '{file_name}' sau khi update"

        # Không có crash dialog
        source = driver.page_source.lower()
        assert "has stopped" not in source, "App crash khi mở file sau update"

        title = find(driver, "textView_title").text
        print(f"\n  Đã mở: {title}")

        driver.back()
        time.sleep(1)

    # ── 3. Tab Favorites còn data ────────────────────────────────────────────

    def test_favorites_tab_accessible(self, driver):
        """Tab Favorites vào được và không crash sau update."""
        find(driver, "layoutStar").click()
        time.sleep(2)

        # Không crash
        source = driver.page_source
        assert len(source) > 200, "App crash khi vào tab Favorites sau update"

        # Quay lại
        find(driver, "layoutAll").click()
        time.sleep(1)

    # ── 4. Toolbar Search hoạt động ──────────────────────────────────────────

    def test_search_toolbar_accessible(self, driver):
        """Nút search trên toolbar hoạt động sau update."""
        assert is_visible(driver, "imv_home_toolbar_search", timeout=5), \
            "Nút search không còn sau update"

        find(driver, "imv_home_toolbar_search").click()
        time.sleep(2)

        # Phải mở màn hình search (có search input)
        source = driver.page_source
        assert len(source) > 200, "Màn hình search crash"

        driver.back()
        time.sleep(1)

    # ── 5. App không show crash sau cold start ────────────────────────────────

    def test_cold_start_after_update(self, driver, adb, cfg):
        """
        Force stop app → restart → kiểm tra home load bình thường.
        Simulate cold start sau khi user update xong và mở lại.
        """
        pkg = cfg["app"]["package_name"]
        activity = cfg["app"]["main_activity"]

        # Force stop
        adb.force_stop_app(pkg)
        time.sleep(2)

        # Restart
        adb.launch_app(pkg, activity)
        time.sleep(cfg["device"]["launch_timeout"])

        # Dismiss onboarding nếu có
        dismiss_onboarding(driver, cfg)

        # Home phải load được
        assert is_visible(driver, "rcv_all_file", timeout=15), \
            "Home không load được sau cold start"

        # Không có crash dialog
        source = driver.page_source.lower()
        assert "has stopped" not in source and "keeps stopping" not in source, \
            "App crash khi cold start sau update"
