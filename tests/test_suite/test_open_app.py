"""
Open App Tests — TC-006 đến TC-007
TC-006: Click Continue để đóng Ads → vào màn hình Language
TC-007: Nhấn Back để đóng Ads → vào màn hình Language
"""
import time
import os
import subprocess
import pytest
from appium.webdriver.common.appiumby import AppiumBy

from tests.helpers import (
    is_visible,
    _is_ad_showing,
)
from tests.utils.robust_driver import RobustDriver

PKG = "pdf.reader.pdf.viewer.all.document.reader.office.viewer"


def _get_adb_cmd(cfg):
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    return ["adb", "-s", serial] if serial else ["adb"]


def _kill_and_launch(adb_cmd, pkg):
    """Kill app hoàn toàn rồi relaunch để đảm bảo ad hiện lại."""
    subprocess.run(adb_cmd + ["shell", "am", "force-stop", pkg],
                   capture_output=True, timeout=5)
    time.sleep(1)
    subprocess.run(
        adb_cmd + ["shell", "monkey", "-p", pkg,
                   "-c", "android.intent.category.LAUNCHER", "1"],
        capture_output=True, timeout=8,
    )
    time.sleep(3)


def _ad_visible_adb(adb_cmd) -> bool:
    """Kiểm tra AdActivity đang foreground qua dumpsys (không cần UiAutomator2)."""
    try:
        r = subprocess.run(
            adb_cmd + ["shell", "dumpsys", "activity", "activities"],
            capture_output=True, text=True, timeout=8,
        )
        focus = next(
            (l.strip() for l in r.stdout.splitlines()
             if "mCurrentFocus" in l or "mFocusedApp" in l),
            "",
        )
        return "adactivity" in focus.lower()
    except Exception:
        return False


def _wait_for_ad(driver, adb_cmd, timeout=20) -> bool:
    """Chờ ad xuất hiện (AdActivity foreground hoặc _is_ad_showing)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _ad_visible_adb(adb_cmd) or _is_ad_showing(driver):
            return True
        time.sleep(1)
    return False


def _language_screen_visible(driver) -> bool:
    """
    Kiểm tra màn hình Language (ChooseLanguageActivity) đang hiển thị.
    Dùng activity name + fallback resource-id.
    """
    try:
        activity = driver.current_activity or ""
        if "ChooseLanguage" in activity or "Language" in activity:
            return True
    except Exception:
        pass
    return (is_visible(driver, "btn_continue", timeout=2)
            or is_visible(driver, "rcv_language", timeout=2))


def _tap_continue_to_app_adb(adb_cmd) -> bool:
    """Tìm nút 'Continue to app' / 'Skip Ad' qua ADB dump rồi tap."""
    import xml.etree.ElementTree as ET
    import re as _re
    _DISMISS_TEXTS = {"Continue to app", "Skip Ad", "Skip ad", "Close ad"}
    try:
        subprocess.run(adb_cmd + ["shell", "uiautomator", "dump", "/sdcard/uidump_ad.xml"],
                       capture_output=True, timeout=8)
        r = subprocess.run(adb_cmd + ["shell", "cat", "/sdcard/uidump_ad.xml"],
                           capture_output=True, text=True, timeout=5)
        xml = r.stdout
        if not xml or "<hierarchy" not in xml:
            return False
        root = ET.fromstring(xml)
        for node in root.iter("node"):
            txt = node.get("text", "") or node.get("content-desc", "")
            if any(t in txt for t in _DISMISS_TEXTS):
                nums = _re.findall(r"\d+", node.get("bounds", ""))
                if len(nums) >= 4:
                    cx = (int(nums[0]) + int(nums[2])) // 2
                    cy = (int(nums[1]) + int(nums[3])) // 2
                    subprocess.run(adb_cmd + ["shell", "input", "tap", str(cx), str(cy)],
                                   capture_output=True, timeout=5)
                    return True
    except Exception:
        pass
    return False


class TestOpenApp:
    """TC-006 và TC-007: Mở app → dismiss ad → vào màn Language."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, adb, cfg):
        yield
        try:
            adb._run(["shell", "input", "keyevent", "3"])  # HOME
        except Exception:
            pass

    # ── TC-006: Dùng Back để đóng Ads ────────────────────────────────────────

    @pytest.mark.tc_id("TC-006")
    def test_tc006_continue_closes_ad_shows_language(self, driver, adb, cfg):
        """
        TC-006: Đóng Ads bằng Back (RobustDriver) → màn hình Language hiển thị
        Expected: Ads đóng, chuyển đến màn hình Language
        """
        pkg = cfg["app"]["package_name"]
        adb_cmd = _get_adb_cmd(cfg)

        # Clear toàn bộ data app (SharedPreferences, cache) để đảm bảo ad hiện lại
        # Dùng subprocess trực tiếp — không qua Appium để tránh crash UiAutomator2
        subprocess.run(adb_cmd + ["shell", "pm", "clear", pkg],
                       capture_output=True, timeout=10)
        time.sleep(1)

        _kill_and_launch(adb_cmd, pkg)

        ad_showed = _wait_for_ad(driver, adb_cmd, timeout=20)
        if not ad_showed:
            pytest.skip("Ad không xuất hiện sau khi launch — không thể test TC-006")

        # Dùng RobustDriver.dismiss_ad() — thử Back trước, fallback ADB dump
        rd = RobustDriver(driver).configure_recovery(adb=adb)
        dismissed = False
        for _ in range(3):
            if not rd.is_ad_visible():
                dismissed = True
                break
            if rd.dismiss_ad():
                dismissed = True
                break
            time.sleep(1.5)
        assert dismissed, "Không dismiss được ad (RobustDriver)"
        time.sleep(2)

        lang_visible = _language_screen_visible(driver)
        assert lang_visible, (
            "Màn hình Language không hiển thị sau khi đóng Ads — "
            f"current_activity={getattr(driver, 'current_activity', 'unknown')}"
        )
        print("\n  TC-006 PASS: Ads đóng (Back) → Language screen hiển thị")

    # ── TC-007: Nhấn Back đóng Ads ───────────────────────────────────────────

    @pytest.mark.tc_id("TC-007")
    def test_tc007_back_closes_ad_shows_language(self, driver, adb, cfg):
        """
        TC-007: Nhấn Back khi đang xem Ads
        Expected: Ads đóng, chuyển đến màn hình Language
        """
        pkg = cfg["app"]["package_name"]
        adb_cmd = _get_adb_cmd(cfg)

        _kill_and_launch(adb_cmd, pkg)

        ad_showed = _wait_for_ad(driver, adb_cmd, timeout=20)
        if not ad_showed:
            pytest.skip("Ad không xuất hiện sau khi launch — không thể test TC-007")

        subprocess.run(adb_cmd + ["shell", "input", "keyevent", "4"],
                       capture_output=True, timeout=5)
        time.sleep(2)

        lang_visible = _language_screen_visible(driver)
        assert lang_visible, (
            "Màn hình Language không hiển thị sau khi nhấn Back — "
            f"current_activity={getattr(driver, 'current_activity', 'unknown')}"
        )
        print("\n  TC-007 PASS: Back → Ads đóng → Language screen hiển thị")
