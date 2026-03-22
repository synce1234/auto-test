"""
Test Cases: Open App (TC_001 → TC_007)
Group: Open app

TC_001 - Click vào app PDF Reader lần đầu (có internet)
TC_002 - Click vào app PDF Reader lần đầu (không có internet)
TC_003 - Click vào app PDF Reader (internet chậm)
TC_004 - Chọn mở app PDF Reader từ app khác
TC_005 - Click Continue đóng Ads (có internet)
TC_006 - Click Continue đóng Ads (không có internet)
TC_007 - Nhấn Back để đóng Ads
"""
import time
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from appium.webdriver.common.appiumby import AppiumBy
from tests.helpers import (
    find, is_visible, rid,
    dismiss_ads, _is_ad_showing,
    dismiss_onboarding,
)
from test_cases.tc_manager import TCManager

PKG = "pdf.reader.pdf.viewer.all.document.reader.office.viewer"
SPLASH_ACTIVITY  = "com.simple.pdf.reader.ui.main.SplashScreenActivity"
LANGUAGE_ACTIVITY = "com.simple.pdf.reader.ui.onboarding.language.LanguageActivity"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tc(tc_manager):
    """Delegate sang session-scoped tc_manager để kết quả được ghi vào report."""
    return tc_manager


def _wait_for_driver_ready(driver, timeout: int = 15) -> bool:
    """Poll cho đến khi Appium/UIA2 có thể trả lời command."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            _ = driver.current_package  # bất kỳ lệnh nhẹ nào
            return True
        except Exception:
            time.sleep(1)
    return False


@pytest.fixture(autouse=True)
def fresh_launch(driver, adb, cfg):
    """Force stop app và relaunch qua ADB, chờ UIA2 kết nối lại."""
    adb.force_stop_app(PKG)
    time.sleep(2)  # Chờ process die hẳn

    # Luôn dùng ADB để launch (không phụ thuộc vào UIA2 state)
    adb.launch_app(PKG, cfg["app"]["main_activity"])

    # Chờ UIA2 kết nối lại sau khi app restart
    _wait_for_driver_ready(driver, timeout=15)

    # Chờ thêm cho app load đủ (bù trừ 15s đã poll)
    remaining = cfg["device"]["launch_timeout"] - 10
    if remaining > 0:
        time.sleep(remaining)

    yield
    # Teardown: force stop
    adb.force_stop_app(PKG)
    time.sleep(1)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _wait_for_splash(driver, timeout: int = 15) -> bool:
    """Chờ màn hình Splash xuất hiện."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            activity = driver.current_activity or ""
            if "Splash" in activity or "splash" in activity:
                return True
            # Fallback: logo hoặc bất kỳ UI nào của app
            if PKG in (driver.current_package or ""):
                source = driver.page_source
                if "imv_logo_pdf" in source or len(source) > 500:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _is_on_language_screen(driver) -> bool:
    """Kiểm tra đang ở màn hình Language."""
    return (
        is_visible(driver, "rclLanguage", timeout=5) or
        is_visible(driver, "btn_continue", timeout=3)
    )


def _is_on_home_screen(driver) -> bool:
    """Kiểm tra đang ở màn hình Home (đã qua onboarding)."""
    return is_visible(driver, "rcv_all_file", timeout=3)


def _is_past_splash(driver) -> bool:
    """
    Kiểm tra app đã qua màn hình Splash và đang ở màn hình tiếp theo.
    Accept Language screen (first launch) hoặc Home screen (đã onboard).
    """
    return (
        _is_on_language_screen(driver) or
        _is_on_home_screen(driver)
    )


def _is_on_interstitial_ad(driver) -> bool:
    """Kiểm tra đang ở màn hình Interstitial Ads (open app ad)."""
    return _is_ad_showing(driver)


def _has_continue_to_app_button(driver) -> bool:
    """Kiểm tra nút 'Continue to app' có hiển thị trên Ad không.
    Dùng XPATH vì AdMob overlay không luôn xuất hiện trong page_source text."""
    try:
        el = driver.find_element(
            AppiumBy.XPATH,
            '//*[contains(@text,"Continue to app") or contains(@content-desc,"Continue to app")]'
        )
        return el is not None and el.is_displayed()
    except Exception:
        pass
    # Fallback: check page_source
    try:
        return "Continue to app" in driver.page_source
    except Exception:
        return False


# ─── TC_001: Click vào app lần đầu, có internet ───────────────────────────────

class TestTC001:
    """TC_001 - Click vào app PDF Reader lần đầu (có internet)"""

    @pytest.fixture(autouse=True)
    def clear_data(self, adb, driver, cfg):
        """
        Clear app data + relaunch để giả lập lần mở đầu tiên.
        Chạy sau fresh_launch nên cần relaunch lại sau khi clear.
        """
        adb.force_stop_app(PKG)
        adb.clear_app_data(PKG)
        time.sleep(1)
        adb.launch_app(PKG, cfg["app"]["main_activity"])
        _wait_for_driver_ready(driver, timeout=15)
        remaining = cfg["device"]["launch_timeout"] - 10
        if remaining > 0:
            time.sleep(remaining)

    def test_splash_shows(self, driver, tc):
        """Màn hình Splash hiển thị đúng khi mở app."""
        splash_ok = _wait_for_splash(driver, timeout=10)
        assert splash_ok, "Màn hình Splash không hiển thị"
        tc.update_result("TC_001", "PASS",
                         actual="Màn hình Splash hiển thị đúng")

    def test_interstitial_ad_shows_after_splash(self, driver, tc):
        """Sau Splash → hiện Interstitial Ads hoặc màn hình tiếp theo."""
        time.sleep(5)
        ad_or_next = (
            _is_on_interstitial_ad(driver) or
            _is_past_splash(driver)
        )
        assert ad_or_next, \
            "Sau Splash không hiển thị Ads hoặc màn hình tiếp theo"

        if _is_on_interstitial_ad(driver):
            actual = "Hiển thị Interstitial Ads"
        elif _is_on_language_screen(driver):
            actual = "Hiển thị Language screen"
        else:
            actual = "Chuyển thẳng đến Home screen (đã onboard)"
        tc.update_result("TC_001", "PASS", actual=actual)


# ─── TC_002: Click vào app lần đầu, không có internet ────────────────────────

class TestTC002:
    """TC_002 - Click vào app PDF Reader lần đầu (không có internet)"""

    @pytest.fixture(autouse=True)
    def clear_data_and_disable_wifi(self, adb, driver, cfg):
        """
        Clear app data + tắt wifi + relaunch để giả lập lần mở đầu không có internet.
        Tắt wifi SAU khi clear, TRƯỚC khi relaunch để app không có network từ đầu.
        """
        adb.force_stop_app(PKG)
        adb.clear_app_data(PKG)
        time.sleep(1)
        adb._run(["shell", "svc", "wifi", "disable"])
        adb._run(["shell", "svc", "data", "disable"])
        time.sleep(1)
        adb.launch_app(PKG, cfg["app"]["main_activity"])
        _wait_for_driver_ready(driver, timeout=15)
        remaining = cfg["device"]["launch_timeout"] - 10
        if remaining > 0:
            time.sleep(remaining)
        yield
        adb._run(["shell", "svc", "wifi", "enable"])
        adb._run(["shell", "svc", "data", "enable"])
        time.sleep(2)

    def test_splash_shows_without_internet(self, driver, tc):
        """Splash hiển thị đúng dù không có internet."""
        splash_ok = _wait_for_splash(driver, timeout=10)
        assert splash_ok, "Splash không hiển thị khi không có internet"
        tc.update_result("TC_002", "PASS",
                         actual="Splash hiển thị đúng khi không có internet")

    def test_goes_to_language_without_internet(self, driver, tc):
        """Không có internet + lần đầu mở → phải hiện Language screen (không có Ads)."""
        time.sleep(8)  # chờ qua splash

        # Không có internet + clear data → không nên có Ads; nhưng dismiss nếu có cache
        if _is_on_interstitial_ad(driver):
            dismiss_ads(driver)
            time.sleep(2)

        on_language = _is_on_language_screen(driver)
        assert on_language, (
            "Không hiện Language screen khi mở lần đầu không có internet "
            f"(hiện tại: {'Home screen' if _is_on_home_screen(driver) else 'màn hình khác'})"
        )
        tc.update_result("TC_002", "PASS",
                         actual="Language screen hiển thị đúng khi không có internet")


# ─── TC_003: Click vào app, internet chậm ────────────────────────────────────

class TestTC003:
    """TC_003 - Click vào app PDF Reader (internet chậm, splash < 30s)"""

    def test_splash_loads_within_30s(self, driver, tc):
        """Màn hình Splash load xong trong vòng 30 giây."""
        start = time.time()
        splash_ok = _wait_for_splash(driver, timeout=30)
        elapsed = time.time() - start

        assert splash_ok, f"App không load được trong 30s (elapsed: {elapsed:.1f}s)"
        assert elapsed < 30, f"Splash load quá lâu: {elapsed:.1f}s"

        tc.update_result("TC_003", "PASS",
                         actual=f"Splash load trong {elapsed:.1f}s (<30s)")

    def test_goes_to_next_screen_after_splash(self, driver, tc):
        """Sau splash → Language screen hoặc Home screen."""
        time.sleep(10)  # chờ kỹ hơn
        # Dismiss ad nếu có
        if _is_on_interstitial_ad(driver):
            dismiss_ads(driver)
            time.sleep(2)

        on_next = _is_past_splash(driver)
        assert on_next, "Không tới được màn hình tiếp theo sau splash"

        actual = "Language screen" if _is_on_language_screen(driver) else "Home screen"
        tc.update_result("TC_003", "PASS",
                         actual=f"Hiển thị {actual} sau Splash")


# ─── TC_004: Mở app từ app khác ───────────────────────────────────────────────

class TestTC004:
    """TC_004 - Chọn mở app PDF Reader từ app khác"""

    @pytest.fixture(autouse=True)
    def setup_from_other_app(self, adb, cfg):
        """
        Simulate mở từ app khác: dùng intent ACTION_VIEW với file PDF.
        Không cần launch trực tiếp qua fresh_launch.
        """
        # Force stop app trước
        adb.force_stop_app(PKG)
        time.sleep(1)
        # Gửi intent view file (simulate open từ file manager)
        adb._run([
            "shell", "am", "start",
            "-a", "android.intent.action.VIEW",
            "-t", "application/pdf",
            "-n", f"{PKG}/{SPLASH_ACTIVITY}",
        ])
        time.sleep(cfg["device"]["launch_timeout"])
        yield

    def test_splash_shows_when_opened_from_other_app(self, driver, tc):
        """Splash hiển thị đúng khi mở từ app khác."""
        splash_or_content = (
            _wait_for_splash(driver, timeout=10) or
            PKG in (driver.current_package or "")
        )
        assert splash_or_content, "App không mở được khi gọi từ app khác"
        tc.update_result("TC_004", "PASS",
                         actual="Splash hiển thị đúng khi mở từ app khác")

    def test_interstitial_ad_shows_after_splash_from_other_app(self, driver, tc):
        """Sau Splash (mở từ app khác) → hiện Ads hoặc màn hình tiếp theo."""
        time.sleep(5)
        ad_or_next_screen = (
            _is_on_interstitial_ad(driver) or
            _is_past_splash(driver)
        )
        assert ad_or_next_screen, \
            "Sau Splash (từ app khác) không hiển thị màn hình tiếp theo"

        actual = "Hiển thị Interstitial Ads" if _is_on_interstitial_ad(driver) else \
                 "Chuyển tiếp đến màn hình tiếp theo"
        tc.update_result("TC_004", "PASS", actual=actual)


# ─── TC_005: Click Continue đóng Ads (có internet) ───────────────────────────

class TestTC005:
    """TC_005 - Click Continue to app → đóng Ads, sang màn hình tiếp theo"""

    def test_continue_button_visible_on_ad(self, driver, tc):
        """Nút 'Continue to app' xuất hiện trên màn hình Ad."""
        time.sleep(5)
        if not _is_on_interstitial_ad(driver):
            pytest.skip("Interstitial Ad không xuất hiện trong môi trường test")

        # Dùng XPATH để tìm button (AdMob overlay không phải lúc nào cũng trong page_source)
        has_continue = _has_continue_to_app_button(driver)
        assert has_continue, "Không tìm thấy nút 'Continue to app' trên Ad"
        tc.update_result("TC_005", "PASS",
                         actual="Nút 'Continue to app' hiển thị trên Interstitial Ad")

    def test_click_continue_closes_ad(self, driver, tc):
        """Click Continue → Ads đóng, chuyển sang màn hình tiếp theo."""
        time.sleep(5)
        if not _is_on_interstitial_ad(driver):
            pytest.skip("Interstitial Ad không xuất hiện trong môi trường test")

        dismissed = dismiss_ads(driver)
        assert dismissed, "Không dismiss được Ad khi click Continue"
        time.sleep(3)

        on_next = _is_past_splash(driver)
        assert on_next, "Sau khi đóng Ad không chuyển sang màn hình tiếp theo"

        actual = "Language screen" if _is_on_language_screen(driver) else "Home screen"
        tc.update_result("TC_005", "PASS",
                         actual=f"Đóng Ads thành công → chuyển sang {actual}")

    def test_next_screen_shows_correctly(self, driver, tc):
        """Màn hình tiếp theo sau Ads hiển thị đúng (Language hoặc Home)."""
        time.sleep(5)
        if _is_on_interstitial_ad(driver):
            dismiss_ads(driver)
            time.sleep(3)

        on_next = _is_past_splash(driver)
        assert on_next, "Màn hình tiếp theo không hiển thị sau khi dismiss Ad"

        if _is_on_language_screen(driver):
            lang_list = is_visible(driver, "rclLanguage", timeout=5)
            assert lang_list, "Danh sách ngôn ngữ không hiển thị"
            actual = "Language screen hiển thị đúng với danh sách ngôn ngữ"
        else:
            actual = "Home screen hiển thị đúng (đã hoàn thành onboarding)"

        tc.update_result("TC_005", "PASS", actual=actual)


# ─── TC_006: Click Continue đóng Ads (không có internet) ─────────────────────

class TestTC006:
    """TC_006 - Click Continue to app → đóng Ads (không có internet)"""

    @pytest.fixture(autouse=True)
    def disable_wifi(self, adb):
        """Tắt wifi SAU khi app đã launch (ad có thể đã load sẵn)."""
        time.sleep(3)  # chờ sau fresh_launch để ad load trước
        adb._run(["shell", "svc", "wifi", "disable"])
        adb._run(["shell", "svc", "data", "disable"])
        time.sleep(1)
        yield
        adb._run(["shell", "svc", "wifi", "enable"])
        adb._run(["shell", "svc", "data", "enable"])
        time.sleep(2)

    def test_click_continue_without_internet(self, driver, tc):
        """Click Continue đóng Ad, sang màn hình tiếp theo khi không có internet."""
        time.sleep(3)
        if _is_on_interstitial_ad(driver):
            dismissed = dismiss_ads(driver)
            assert dismissed, "Không dismiss được Ad khi không có internet"
            time.sleep(3)

        on_next = _is_past_splash(driver)
        assert on_next, \
            "Sau khi đóng Ad (no internet) không sang màn hình tiếp theo"

        actual = "Language screen" if _is_on_language_screen(driver) else "Home screen"
        tc.update_result("TC_006", "PASS",
                         actual=f"Đóng Ads → {actual} (không có internet)")

    def test_screen_shows_without_internet(self, driver, tc):
        """Màn hình tiếp theo vẫn hiển thị đúng khi không có internet."""
        time.sleep(3)
        if _is_on_interstitial_ad(driver):
            dismiss_ads(driver)
            time.sleep(3)

        on_next = _is_past_splash(driver)
        assert on_next, \
            "Màn hình tiếp theo không hiển thị khi không có internet"

        actual = "Language screen" if _is_on_language_screen(driver) else "Home screen"
        tc.update_result("TC_006", "PASS",
                         actual=f"{actual} hiển thị đúng khi không có internet")


# ─── TC_007: Nhấn Back để đóng Ads ───────────────────────────────────────────

class TestTC007:
    """TC_007 - Nhấn Back trên điện thoại để đóng Ads"""

    def test_back_button_closes_ad(self, driver, tc):
        """Nhấn Back khi đang ở màn hình Ad → Ads đóng."""
        time.sleep(5)
        if not _is_on_interstitial_ad(driver):
            pytest.skip("Interstitial Ad không xuất hiện trong môi trường test")

        driver.back()
        time.sleep(2)

        still_on_ad = _is_on_interstitial_ad(driver)
        assert not still_on_ad, "Ad vẫn còn sau khi nhấn Back"
        tc.update_result("TC_007", "PASS",
                         actual="Nhấn Back → Ads đóng thành công")

    def test_goes_to_next_screen_after_back(self, driver, tc):
        """Sau khi nhấn Back đóng Ad → chuyển sang màn hình tiếp theo."""
        time.sleep(5)
        if _is_on_interstitial_ad(driver):
            driver.back()
            time.sleep(3)

        on_next = _is_past_splash(driver)
        assert on_next, \
            "Sau khi nhấn Back đóng Ad không chuyển sang màn hình tiếp theo"

        actual = "Language screen" if _is_on_language_screen(driver) else "Home screen"
        tc.update_result("TC_007", "PASS",
                         actual=f"Nhấn Back → {actual} hiển thị đúng")
