"""
Test Open PDF - Mở file PDF và kiểm tra viewer hoạt động đúng.
"""
import time
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from tests.helpers import (
    find, find_all, is_visible, rid,
    go_to_home, dismiss_onboarding2, _is_ad_showing, _safe_dismiss_open_app_ad,
    close_exit_dialog,
)


class TestOpenPDF:

    @pytest.fixture(autouse=True)
    def setup(self, driver, cfg, tc_manager):
        """Đảm bảo đang ở màn hình Home trước mỗi test."""
        if _is_ad_showing(driver):
            _safe_dismiss_open_app_ad(driver)
            time.sleep(1)
        dismiss_onboarding2(driver, cfg)
        go_to_home(driver, cfg)

    # ── 1. Home screen có file list ──────────────────────────────────────────

    @pytest.mark.tc_id("TC_PDF_001")
    def test_file_list_visible(self, driver):
        """Màn hình home hiển thị danh sách file PDF."""
        rcv = find(driver, "rcv_all_file")
        assert rcv.is_displayed(), "RecyclerView danh sách file không hiển thị"

    @pytest.mark.tc_id("TC_PDF_002")
    def test_file_list_not_empty(self, driver):
        """Danh sách file có ít nhất 1 item."""
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert len(items) > 0, "Không có file nào trong danh sách"
        print(f"\n  Số file tìm thấy: {len(items)}")
        for item in items[:3]:
            print(f"    - {item.text}")

    # ── 2. Mở file PDF ───────────────────────────────────────────────────────

    @pytest.mark.tc_id("TC_PDF_003")
    def test_open_pdf_opens_viewer(self, driver):
        """Click vào file PDF → mở PDF viewer."""
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert items, "Không có file để test"

        first_file = items[0].text
        items[0].click()
        time.sleep(3)

        # Kiểm tra viewer đã mở: có title bar với tên file
        assert is_visible(driver, "textView_title", timeout=10), \
            "PDF viewer không mở (không thấy title bar)"
        print(f"\n  Đã mở file: {first_file}")

    @pytest.mark.tc_id("TC_PDF_004")
    def test_viewer_shows_page_number(self, driver):
        """PDF viewer hiển thị số trang."""
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert items
        items[0].click()
        time.sleep(3)

        page_text_el = find(driver, "pageNumberText", timeout=8)
        page_text = page_text_el.text
        assert "/" in page_text, f"Số trang hiển thị sai: '{page_text}'"
        print(f"\n  Số trang: {page_text}")

    @pytest.mark.tc_id("TC_PDF_005")
    def test_viewer_bottom_toolbar_visible(self, driver):
        """Bottom toolbar trong viewer (Search, Favorite, Mode, More) hiển thị."""
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert items
        items[0].click()
        time.sleep(3)

        assert is_visible(driver, "frToolbarBottom", timeout=8), \
            "Bottom toolbar không hiển thị trong viewer"
        assert is_visible(driver, "imv_toolbar_search"), "Nút Search không có"
        assert is_visible(driver, "imv_toolbar_more"), "Nút More không có"

    @pytest.mark.tc_id("TC_PDF_006")
    def test_viewer_back_returns_to_home(self, driver):
        """Bấm Back trong viewer → quay về màn hình Home."""
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert items
        items[0].click()
        time.sleep(3)

        assert is_visible(driver, "imv_toolbar_back", timeout=8)
        find(driver, "imv_toolbar_back").click()
        time.sleep(2)
        close_exit_dialog(driver)
        time.sleep(2)
        assert is_visible(driver, "rcv_all_file", timeout=8), \
            "Không về được Home sau khi bấm Back"

    # ── 3. Navigate pages ────────────────────────────────────────────────────

    @pytest.mark.tc_id("TC_PDF_007")
    def test_scroll_down_in_viewer(self, driver):
        """Scroll xuống trong viewer không crash."""
        items = find_all(driver, "vl_item_file_name", timeout=10)
        assert items
        items[0].click()
        time.sleep(3)

        assert is_visible(driver, "doc_view", timeout=8)

        # Scroll xuống 3 lần
        size = driver.get_window_size()
        w, h = size["width"], size["height"]
        for _ in range(3):
            driver.swipe(w // 2, int(h * 0.6), w // 2, int(h * 0.3), 500)
            time.sleep(0.5)

        # Kiểm tra viewer vẫn còn (không crash)
        assert is_visible(driver, "doc_view", timeout=5), \
            "Viewer bị đóng hoặc crash sau khi scroll"

    # ── 4. Tab navigation ────────────────────────────────────────────────────

    @pytest.mark.tc_id("TC_PDF_008")
    def test_tab_files_visible(self, driver):
        """Tab 'Files' hiển thị ở home screen."""
        assert is_visible(driver, "layoutAll", timeout=5), "Tab Files không hiển thị"

    @pytest.mark.tc_id("TC_PDF_009")
    def test_tab_favorites_clickable(self, driver):
        """Click tab Favorites không crash."""
        find(driver, "layoutStar").click()
        time.sleep(1)
        assert is_visible(driver, "ll_home_tab", timeout=5), "App crash sau khi click tab"
        # Quay lại tab Files
        find(driver, "layoutAll").click()
        time.sleep(1)
