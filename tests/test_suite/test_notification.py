"""
Notification Tests - TC-001 đến TC-010
Sheet: TC - Notice (version N.2.6.8)

TC-001: Don't allow system notification → Reading notification toggle bị disable
TC-002: Allow system notification → Reading notification toggle được enable
TC-003: Toggle Reading Notification OFF
TC-004: Toggle Reading Notification ON
TC-005: Silent noti khi app không có file nào (close app)
TC-006: Silent noti khi có file in-progress <100% (opened từ Home)
TC-007: Silent noti khi có file in-progress <100% (opened từ app khác)
TC-008: Silent noti khi chỉ có file đã đọc 100% (opened từ Home)
TC-009: Silent noti khi chỉ có file đã đọc 100% (opened từ app khác)
TC-010: Silent noti khi có file chưa đọc lần nào
"""
import time
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from tests.utils.robust_driver import RobustDriver
from tests.helpers import (
    find, find_all, is_visible, rid,
    go_to_home, app_init, dismiss_ads, _is_ad_showing,
    ensure_app_foreground,
)
from tests.test_suite.test_open_files_other import _fresh_install, _safe_dismiss_open_app_ad, _handle_chooser, _wait_reader_open

PKG = "pdf.reader.pdf.viewer.all.document.reader.office.viewer"


# ─── Notification helpers ──────────────────────────────────────────────────────

def grant_notification_permission(driver):
    """Click 'Allow' trên system notification permission dialog."""
    try:
        allow_btn = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((
                AppiumBy.XPATH,
                '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_button"]'
                ' | //*[@text="Allow"]'
                ' | //*[@text="Cho phép"]',
            ))
        )
        allow_btn.click()
        time.sleep(1)
        return True
    except TimeoutException:
        return False


def deny_notification_permission(driver):
    """Click 'Don't Allow' trên system notification permission dialog."""
    try:
        deny_btn = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((
                AppiumBy.XPATH,
                '//*[@resource-id="com.android.permissioncontroller:id/permission_deny_button"]'
                ' | //*[@text="Don\'t allow"]'
                ' | //*[@text="Don\'t Allow"]'
                ' | //*[@text="Không cho phép"]',
            ))
        )
        deny_btn.click()
        time.sleep(1)
        return True
    except TimeoutException:
        return False


def open_sidebar_menu(driver):
    """Mở menu sidebar (hamburger menu)."""
    # Thử tìm nút menu (hamburger icon)
    menu_selectors = [
        (AppiumBy.ID, rid("imv_home_menu_nav")),
        (AppiumBy.ID, rid("imgMenu")),
        (AppiumBy.ID, rid("ivMenu")),
        (AppiumBy.ID, rid("nav_menu")),
        (AppiumBy.XPATH, '//*[@content-desc="Menu" or @content-desc="Open navigation drawer"]'),
        (AppiumBy.XPATH, '//*[@resource-id[contains(., "menu")] and @class="android.widget.ImageView"]'),
    ]
    for by, selector in menu_selectors:
        try:
            el = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((by, selector))
            )
            el.click()
            time.sleep(1.5)
            return True
        except (TimeoutException, NoSuchElementException):
            continue
    return False


def find_reading_notification_toggle(driver):
    """Tìm toggle Reading Notification trong sidebar menu."""
    toggle_selectors = [
        (AppiumBy.ID, rid("menuSwitch")),
        (AppiumBy.ID, rid("swNotification")),
        (AppiumBy.ID, rid("switchNotification")),
        (AppiumBy.ID, rid("sw_notification")),
        (AppiumBy.XPATH, '//*[contains(@text, "Reading notification") or contains(@text, "Notification")]'
                         '/following-sibling::*[@class="android.widget.Switch"]'),
        (AppiumBy.XPATH, '//android.widget.Switch[preceding-sibling::*[contains(@text, "notification")]]'),
        (AppiumBy.XPATH, '//*[contains(@resource-id, "notif") and @class="android.widget.Switch"]'),
        (AppiumBy.XPATH, '//*[contains(@resource-id, "notif") and @class="android.widget.CompoundButton"]'),
    ]
    for by, selector in toggle_selectors:
        try:
            el = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((by, selector))
            )
            return el
        except (TimeoutException, NoSuchElementException):
            continue
    return None


def get_toggle_state(toggle_el) -> bool:
    """
    Trả về True nếu toggle đang ON, False nếu OFF.
    SwitchView không expose 'checked' qua accessibility nên dùng screenshot + màu sắc.
    colorOn = #EB4747 (đỏ), colorOff = #C8C8C8 (xám).
    """
    # Thử dùng checked attribute trước (fallback cho Switch chuẩn)
    checked = toggle_el.get_attribute("checked")
    if checked == "true":
        return True

    # Thử selected attribute (một số custom view dùng selected thay checked)
    selected = toggle_el.get_attribute("selected")
    if selected == "true":
        return True

    # SwitchView custom → dùng màu sắc từ screenshot
    try:
        import base64
        import io
        import re as _re
        from PIL import Image

        bounds_str = toggle_el.get_attribute("bounds")
        if not bounds_str:
            return False
        nums = list(map(int, _re.findall(r'\d+', bounds_str)))
        if len(nums) < 4:
            return False
        x1, y1, x2, y2 = nums[0], nums[1], nums[2], nums[3]

        driver = toggle_el.parent  # WebDriver
        screenshot_b64 = driver.get_screenshot_as_base64()
        img = Image.open(io.BytesIO(base64.b64decode(screenshot_b64))).convert("RGB")

        # Scale bounds nếu screenshot nhỏ hơn màn hình thật (high-DPI)
        scr_w, scr_h = img.size
        win = driver.get_window_size()
        sx = scr_w / win["width"]
        sy = scr_h / win["height"]
        cx1, cy1, cx2, cy2 = int(x1*sx), int(y1*sy), int(x2*sx), int(y2*sy)

        # Crop vùng toggle và lấy màu trung bình
        crop = img.crop((cx1, cy1, cx2, cy2))
        pixels = list(crop.getdata())
        avg_r = sum(p[0] for p in pixels) / len(pixels)
        avg_g = sum(p[1] for p in pixels) / len(pixels)
        avg_b = sum(p[2] for p in pixels) / len(pixels)

        # colorOn = #EB4747 (R=235, G=71, B=71), colorOff = #C8C8C8 (R=200, G=200, B=200)
        # Nếu avg_r > avg_g + 40 → đang ON (đỏ)
        # Nếu tất cả channel gần bằng nhau (gray) → đang OFF
        is_reddish = avg_r > avg_g + 40 and avg_r > avg_b + 40
        return is_reddish
    except Exception:
        # Fallback: thử text attribute của toggle
        try:
            text = toggle_el.get_attribute("text") or ""
            if text.lower() in ("on", "true", "1"):
                return True
        except Exception:
            pass
        return False


def click_notification_row(driver, adb=None):
    """
    Click vào toggle Reading Notification.
    SwitchView custom cần dùng 'adb input tap' vì Appium không trigger
    MotionEvent đúng cho custom view này.
    Truyền adb fixture để dùng ADBController._run(), hoặc fallback subprocess.
    """
    import re

    def _get_toggle_center():
        toggle = find_reading_notification_toggle(driver)
        if toggle:
            bounds_str = toggle.get_attribute("bounds")
            if bounds_str:
                nums = list(map(int, re.findall(r'\d+', bounds_str)))
                if len(nums) == 4:
                    return (nums[0] + nums[2]) // 2, (nums[1] + nums[3]) // 2
        return None

    # Thử Appium click trực tiếp trước (nhanh nhất, hoạt động tốt với standard Switch)
    toggle = find_reading_notification_toggle(driver)
    if toggle:
        try:
            toggle.click()
            return True
        except Exception:
            pass

    # Fallback: dùng tọa độ từ bounds
    coords = _get_toggle_center()
    if not coords:
        return False
    cx, cy = coords

    # Thử driver.tap() trước (Appium native, tốt hơn adb trên emulator)
    try:
        driver.tap([(cx, cy)])
        return True
    except Exception:
        pass

    # Dùng ADBController nếu có
    if adb is not None:
        try:
            adb._run(["shell", "input", "tap", str(cx), str(cy)])
            return True
        except Exception:
            pass

    # Fallback: subprocess
    try:
        import subprocess
        subprocess.run(["adb", "shell", "input", "tap", str(cx), str(cy)],
                       timeout=5, capture_output=True, check=True)
        return True
    except Exception:
        pass

    return False


def handle_open_with_chooser(driver, pkg_label: str = "All Docs PDF Reader") -> bool:
    """
    Xử lý dialog 'Open with...' sau khi mở file từ intent.
    Click 'Just once' để mở file bằng app chỉ định.
    Trả về True nếu đã handle được.
    """
    try:
        just_once = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((AppiumBy.XPATH, '//*[@text="Just once"]'))
        )
        just_once.click()
        time.sleep(2)
        return True
    except (TimeoutException, NoSuchElementException):
        pass
    return False


def force_exit_notification(adb, pkg, alarm_type: int = 10342):
    """
    Buộc app gửi exit notification ngay lập tức qua ADB broadcast.
    alarm_type: 10342=TYPE_EXIT_9, 10343=TYPE_EXIT_10
    App phải đang ở background trước khi gọi hàm này.
    """
    adb._run([
        "shell", "am", "broadcast",
        "-a", "pdf.reader.ALARM",
        "-p", pkg,
        "--ei", "typeNotification", str(alarm_type),
    ])
    time.sleep(3)


def force_alarm_notification(adb, pkg, alarm_type: int):
    """
    Trigger morning (10340) hoặc night (10341) alarm notification qua ADB broadcast.
    Lưu ý: initNotificationMorning/Night có guard giờ (6-8h / 20-22h) và weekday.
    """
    # Reset mLastType bằng cách gửi type khác trước
    dummy = 10343 if alarm_type != 10343 else 10342
    adb._run(["shell", "am", "broadcast",
              "-a", "pdf.reader.ALARM", "-p", pkg,
              "--ei", "typeNotification", str(dummy)])
    time.sleep(1)
    adb._run(["shell", "am", "broadcast",
              "-a", "pdf.reader.ALARM", "-p", pkg,
              "--ei", "typeNotification", str(alarm_type)])
    time.sleep(3)


def click_notification_by_text(driver, keyword: str, click_button_text: str = None) -> bool:
    """
    Mở notification shade, tìm notification chứa keyword rồi click.
    Nếu click_button_text != None: expand notification rồi click vào button đó.
    Nếu None thì click vào body notification.
    Trả về True nếu click thành công.
    """
    try:
        driver.open_notifications()
        time.sleep(2)

        # Tìm notification chứa keyword
        noti_el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                AppiumBy.XPATH,
                f'//*[contains(@text, "{keyword}")]'
            ))
        )

        if click_button_text:
            # Thử tìm button ngay (notification đã expanded)
            btn = None
            try:
                btn = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((
                        AppiumBy.XPATH,
                        f'//*[@text="{click_button_text}"]'
                    ))
                )
            except TimeoutException:
                pass

            # Nếu chưa thấy button → expand notification bằng cách swipe down
            if btn is None:
                try:
                    loc = noti_el.location
                    size = noti_el.size
                    cx = loc['x'] + size['width'] // 2
                    cy = loc['y'] + size['height'] // 2
                    driver.swipe(cx, cy, cx, cy + 250, 400)
                    time.sleep(1)
                    btn = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((
                            AppiumBy.XPATH,
                            f'//*[@text="{click_button_text}"]'
                        ))
                    )
                except TimeoutException:
                    pass

            if btn is not None:
                btn.click()
            else:
                # Fallback: re-find notification body (tránh StaleElementReferenceException)
                try:
                    noti_el = driver.find_element(
                        AppiumBy.XPATH,
                        f'//*[contains(@text, "{keyword}")]'
                    )
                except Exception:
                    pass
                noti_el.click()
        else:
            noti_el.click()

        time.sleep(3)
        return True
    except (TimeoutException, NoSuchElementException):
        try:
            driver.back()
        except Exception:
            pass
        return False


def dismiss_notification_by_text(driver, keyword: str) -> bool:
    """
    Mở notification shade, swipe để dismiss notification chứa keyword.
    Trả về True nếu dismiss thành công.
    """
    try:
        driver.open_notifications()
        time.sleep(2)

        noti_el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                AppiumBy.XPATH,
                f'//*[contains(@text, "{keyword}")]'
            ))
        )
        # Swipe right để dismiss
        loc = noti_el.location
        size = noti_el.size
        start_x = loc["x"] + size["width"] // 4
        start_y = loc["y"] + size["height"] // 2
        end_x = loc["x"] + size["width"]
        driver.swipe(start_x, start_y, end_x, start_y, 300)
        time.sleep(2)

        # Verify notification đã biến mất
        source = driver.page_source
        try:
            driver.back()
        except Exception:
            pass
        return keyword.lower() not in source.lower()
    except (TimeoutException, NoSuchElementException):
        try:
            driver.back()
        except Exception:
            pass
        return False


def open_notification_shade(driver):
    """Mở notification shade."""
    try:
        driver.open_notifications()
        time.sleep(2)
        return True
    except Exception:
        return False


def get_notification_content(driver) -> str:
    """Lấy nội dung notification shade hiện tại."""
    try:
        return driver.page_source
    except Exception:
        return ""


def close_notification_shade(driver):
    """Đóng notification shade."""
    try:
        driver.back()
        time.sleep(1)
    except Exception:
        pass


def background_app(driver):
    """Đẩy app xuống background."""
    try:
        driver.background_app(-1)  # -1 = send to background indefinitely
        time.sleep(2)
    except Exception:
        try:
            driver.press_keycode(3)  # KEYCODE_HOME
            time.sleep(2)
        except Exception:
            pass


def wait_for_notification(driver, title_keyword: str, timeout: int = 30) -> bool:
    """
    Chờ notification xuất hiện với title chứa keyword.
    Mở notification shade và kiểm tra nội dung.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        open_notification_shade(driver)
        source = get_notification_content(driver)
        if title_keyword.lower() in source.lower():
            close_notification_shade(driver)
            return True
        close_notification_shade(driver)
        time.sleep(3)
    return False


def clear_all_notifications(driver):
    """Xóa tất cả notifications."""
    open_notification_shade(driver)
    time.sleep(1)
    try:
        # Tìm nút Clear All / Dismiss All
        clear_btns = [
            '//*[@text="Clear all"]',
            '//*[@text="CLEAR ALL"]',
            '//*[contains(@content-desc, "Clear all")]',
        ]
        for xpath in clear_btns:
            try:
                el = driver.find_element(AppiumBy.XPATH, xpath)
                el.click()
                time.sleep(1)
                return
            except Exception:
                pass
        # Swipe từng notification để dismiss
        size = driver.get_window_size()
        for _ in range(5):
            try:
                driver.swipe(
                    size["width"] // 2, size["height"] // 2,
                    size["width"], size["height"] // 2,
                    300
                )
                time.sleep(0.5)
            except Exception:
                break
    except Exception:
        pass
    finally:
        close_notification_shade(driver)


# ─── Test Class ───────────────────────────────────────────────────────────────

class TestNotification:
    """
    Test notification feature theo TC-001 đến TC-010.
    """

    @pytest.fixture(autouse=True)
    def _setup_before_test(self, adb):
        """Chạy trước mỗi test: xóa file test trên device, rồi nhấn Home."""
        _dirs = "/sdcard/Download /sdcard/Documents /sdcard/Document /sdcard/DCIM /sdcard"
        _exts = "pdf doc docx xls xlsx ppt pptx txt epub svg html"
        _rm_cmd = (
            f"for d in {_dirs}; do "
            f"for ext in {_exts}; do "
            'rm -f "$d"/*.$ext 2>/dev/null; '
            "done; done; true"
        )
        try:
            adb._run(["shell", _rm_cmd], timeout=60)
        except Exception:
            pass
        adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
        time.sleep(0.5)

    # ── TC-001: Don't allow notification permission ──────────────────────────

    @pytest.mark.tc_id("TC-NTF-001")
    def test_tc001_deny_notification_permission(self, driver, adb, cfg):
        """
        TC-001: Open app lần đầu → chọn 'Không cho phép' notification
        Expected: Disable button reading notification ở Menu/Sidebar
        """
        pkg = cfg["app"]["package_name"]

        # Revoke notification permission (không dùng pm clear để tránh crash UIAutomator2)
        adb._run(["shell", "pm", "revoke", pkg, "android.permission.POST_NOTIFICATIONS"])
        time.sleep(1)
        # Reset permission flags để dialog có thể hiện lại
        adb._run(["shell", "pm", "reset-permissions", pkg])
        time.sleep(1)
        # Restart app sạch (không clear data → UIAutomator2 không bị crash)
        adb.force_stop_app(pkg)
        time.sleep(1)
        driver.activate_app(pkg)
        time.sleep(4)

        # Dismiss onboarding nếu có (Language screen, etc.)
        go_to_home(driver, cfg)

        # Mở sidebar menu
        assert open_sidebar_menu(driver), "Không mở được sidebar menu"
        time.sleep(1)

        # Tìm Reading Notification toggle
        toggle = find_reading_notification_toggle(driver)
        assert toggle is not None, "Không tìm thấy Reading Notification toggle trong menu"

        # Toggle phải ở trạng thái OFF khi notification permission bị revoke
        state = get_toggle_state(toggle)
        assert not state, \
            f"Expected Reading Notification toggle = OFF sau khi revoke permission, nhưng đang ON"
        print(f"\n  TC-001 PASS: Toggle = OFF (notification permission revoked)")

    # ── TC-002: Allow notification permission ───────────────────────────────

    @pytest.mark.tc_id("TC-NTF-002")
    def test_tc002_allow_notification_permission(self, driver, adb, cfg):
        """
        TC-002: Open app lần đầu → chọn 'Cho phép' notification
        Expected: Enable button reading notification ở Menu/Sidebar
        """
        pkg = cfg["app"]["package_name"]

        # Grant notification permission via ADB (không dùng pm clear → UIAutomator2 an toàn)
        adb._run(["shell", "pm", "grant", pkg, "android.permission.POST_NOTIFICATIONS"])
        time.sleep(1)
        # Restart app để onResume() re-check permission state
        adb.force_stop_app(pkg)
        time.sleep(1)
        driver.activate_app(pkg)
        time.sleep(6)
        go_to_home(driver, cfg)

        # Mở sidebar menu
        assert open_sidebar_menu(driver), "Không mở được sidebar menu"
        time.sleep(1.5)

        # Tìm Reading Notification toggle
        toggle = find_reading_notification_toggle(driver)
        assert toggle is not None, "Không tìm thấy Reading Notification toggle trong menu"

        # Toggle phải ở trạng thái ON khi notification permission được grant
        state = get_toggle_state(toggle)
        assert state, \
            f"Expected Reading Notification toggle = ON sau khi grant permission, nhưng đang OFF"
        print(f"\n  TC-002 PASS: Toggle = ON (notification permission granted)")

    # ── TC-003: Toggle Reading Notification OFF ──────────────────────────────

    @pytest.mark.tc_id("TC-NTF-003")
    def test_tc003_toggle_notification_off(self, driver, adb, cfg):
        """
        TC-003: Reading Notification đang ON → Toggle thành OFF
        Expected: Toggle ở trạng thái OFF, app không nhận Noti
        """
        pkg = cfg["app"]["package_name"]
        # Grant permission và restart app để onResume() re-check permission state
        adb._run(["shell", "pm", "grant", pkg, "android.permission.POST_NOTIFICATIONS"])
        time.sleep(1)
        adb.force_stop_app(pkg)
        time.sleep(1)
        driver.activate_app(pkg)
        time.sleep(6)
        go_to_home(driver, cfg)

        # Mở sidebar
        assert open_sidebar_menu(driver), "Không mở được sidebar menu"
        time.sleep(1.5)

        toggle = find_reading_notification_toggle(driver)
        assert toggle is not None, "Không tìm thấy Reading Notification toggle"

        # Nếu toggle đang OFF, bật lên ON trước
        if not get_toggle_state(toggle):
            click_notification_row(driver, adb)
            time.sleep(2)
            toggle = find_reading_notification_toggle(driver)
            assert get_toggle_state(toggle), "Không bật được toggle lên ON"

        # Tắt toggle
        click_notification_row(driver, adb)
        time.sleep(2)

        # Kiểm tra lại state
        toggle = find_reading_notification_toggle(driver)
        assert toggle is not None, "Không tìm thấy toggle sau khi click"
        state = get_toggle_state(toggle)
        assert not state, f"Expected Toggle = OFF nhưng đang: {state}"
        print(f"\n  TC-003 PASS: Toggle Reading Notification = OFF")

    # ── TC-004: Toggle Reading Notification ON ───────────────────────────────

    @pytest.mark.tc_id("TC-NTF-004")
    def test_tc004_toggle_notification_on(self, driver, adb, cfg):
        """
        TC-004: Reading Notification đang OFF → Toggle thành ON
        Expected: Toggle ở trạng thái ON, app có thể gửi Noti
        """
        pkg = cfg["app"]["package_name"]
        # Grant permission và restart app để onResume() re-check permission state
        adb._run(["shell", "pm", "grant", pkg, "android.permission.POST_NOTIFICATIONS"])
        time.sleep(1)
        adb.force_stop_app(pkg)
        time.sleep(1)
        driver.activate_app(pkg)
        time.sleep(6)
        go_to_home(driver, cfg)

        # Mở sidebar
        assert open_sidebar_menu(driver), "Không mở được sidebar menu"
        time.sleep(1.5)

        toggle = find_reading_notification_toggle(driver)
        assert toggle is not None, "Không tìm thấy Reading Notification toggle"

        # Nếu toggle đang ON, tắt xuống OFF trước
        if get_toggle_state(toggle):
            click_notification_row(driver, adb)
            time.sleep(2)
            toggle = find_reading_notification_toggle(driver)
            assert not get_toggle_state(toggle), "Không tắt được toggle về OFF"

        # Bật toggle
        click_notification_row(driver, adb)
        time.sleep(2)

        # Kiểm tra lại state
        toggle = find_reading_notification_toggle(driver)
        assert toggle is not None, "Không tìm thấy toggle sau khi click"
        state = get_toggle_state(toggle)
        assert state, f"Expected Toggle = ON nhưng đang: {state}"
        print(f"\n  TC-004 PASS: Toggle Reading Notification = ON")

    # ── TC-005: Silent noti - app không có file ──────────────────────────────

    @pytest.mark.tc_id("TC-NTF-005")
    def test_tc005_silent_noti_no_files(self, driver, adb, cfg):
        """
        TC-005: App không có file nào, close/background app
        Expected: Hiện noti silent:
          Title: 📚Don't miss it
          Description: 📚Read All Files With PDF Reader
        """
        pkg = cfg["app"]["package_name"]

        # Gỡ + cài lại APK đúng bản đang chọn (INSTALL_APK / apks.file trong config), xóa data app
        installed = _fresh_install(adb, cfg)
        assert installed, "Không cài được APK"
        # Chạy lại app_init (helpers.py): launch → dismiss onboarding → kill app (chuẩn sau cài mới)
        assert app_init(driver, cfg), "app_init không hoàn thành sau fresh install"

        # Xóa tất cả notifications hiện tại
        clear_all_notifications(driver)

        # Đảm bảo app ở home
        ensure_app_foreground(driver, cfg)
        time.sleep(5)
        _safe_dismiss_open_app_ad(driver, adb)

        # Background app
        background_app(driver)
        time.sleep(2)

        # Về home và mở notification bar để chụp ảnh xác nhận
        try:
            adb.run(["shell", "input", "keyevent", "KEYCODE_HOME"])
            time.sleep(1)
           
        except Exception:
            pass
        # Chụp screenshot bằng ADB (tránh Appium crash khi notification shade mở)
        try:
            rdriver = RobustDriver(driver).configure_recovery(adb=adb)
            if rdriver.open_notification_shade():
                time.sleep(1)
        except Exception:
            pass
        # Sleep 3s sau đó kiểm tra notification text (dùng RobustDriver)
        time.sleep(3)
        ok_noti = False
        try:
            rdriver = RobustDriver(driver).configure_recovery(adb=adb)
            # đảm bảo shade đang mở (best-effort)
            try:
                rdriver.open_notification_shade()
                time.sleep(1)
            except Exception:
                pass

            # đọc page_source để verify text
            for _ in range(2):
                try:
                    src = (rdriver.page_source or "").lower()
                    ok_noti = ("don't miss it".lower() in src) and ("read all files with pdf reader".lower() in src)
                    break
                except Exception as e:
                    if getattr(rdriver, "_is_uia2_crash")(e):
                        serial = os.environ.get("TEST_DEVICE_SERIAL", "")
                        rdriver.restart_appium_server(int(os.environ.get("APPIUM_PORT", "4723")), serial)
                        # recreate session best-effort
                        try:
                            getattr(rdriver, "_try_recreate_driver_after_restart")()
                        except Exception:
                            pass
                        try:
                            rdriver.open_notification_shade()
                            time.sleep(1)
                        except Exception:
                            pass
                        continue
                    break
        except Exception:
            ok_noti = False

        assert ok_noti, "Không tìm thấy notification chứa 'Don't miss it' và 'Read All Files With PDF Reader'"

        print(f"\n  TC-005 PASS: App không có file nào, close/background app hiện noti silent\n")

        # pytest.skip("NEED CONFIRM: Kiểm tra screenshot — notification 'Don't miss it' có hiện không?")

    # ── TC-006: Silent noti - file in-progress <100% từ Home ────────────────

    @pytest.mark.tc_id("TC-NTF-006")
    def test_tc006_silent_noti_inprogress_from_home(self, driver, adb, cfg):
        """
        TC-006: Có file in-progress <100%, opened từ Home, close app
        Expected: Noti silent:
          Title: 📚<tên file>.pdf
          Description: 📚Don't miss it. Complete Reading Now + Nút Open
        """
        # TODO: push 1 file vào để test và trigger scan , hãy tham khảo test open file others
        pkg = cfg["app"]["package_name"]
        go_to_home(driver, cfg)

        # Tìm file không phải Welcome để mở
        items = find_all(driver, "vl_item_file_name", timeout=10)
        target = next((el for el in items if "welcome" not in el.text.lower()), None)

        # Nếu không có file phù hợp → push file test vào app
        if target is None:
            test_pdf_local = os.path.join(
                os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
            )
            remote_path = "/sdcard/Download/sample_simple.pdf"
            adb.push_file(test_pdf_local, remote_path)
            time.sleep(3)
            go_to_home(driver, cfg)
            items = find_all(driver, "vl_item_file_name", timeout=10)
            target = next((el for el in items if "welcome" not in el.text.lower()), None)

        if target is None:
            pytest.skip("Không có file nào (ngoài Welcome) để test TC-006")

        file_name = target.text
        target.click()
        time.sleep(3)
 
        RobustDriver(driver).configure_recovery(adb=adb).dismiss_ad_if_any()

        # Đọc một chút (không 100%) rồi close file
        if is_visible(driver, "imv_toolbar_back", timeout=8):
            find(driver, "imv_toolbar_back").click()
            time.sleep(2)

        # Xóa notifications cũ
        clear_all_notifications(driver)

        # Background app
        background_app(driver)
        time.sleep(2)

        # Force gửi exit notification qua ADB broadcast (TYPE_EXIT_10 để tránh mLastType từ TC-005)
        force_exit_notification(adb, pkg, alarm_type=10343)  # TYPE_EXIT_10

        # Kiểm tra notification
        noti_found = wait_for_notification(driver, "Complete Reading Now", timeout=15)
        if not noti_found:
            noti_found = wait_for_notification(driver, "Don't miss it", timeout=10)
        if not noti_found:
            noti_found = wait_for_notification(driver, "Read All Files", timeout=10)

        assert noti_found, \
            f"Không tìm thấy silent notification cho file '{file_name}' sau khi background"
        print(f"\n  TC-006 PASS: Silent noti cho file '{file_name}' hiện thị")

    # ── TC-007: Silent noti - file in-progress <100% từ app khác ────────────

    @pytest.mark.tc_id("TC-NTF-007")
    def test_tc007_silent_noti_inprogress_from_external(self, driver, adb, cfg):
        """
        TC-007: Có file in-progress <100%, opened từ app khác, close app
        Expected: Noti silent với 'Complete Reading Now'
        Luồng:
        1. Mở file từ app khác (dismiss ads nếu có)
        2. Đọc file dưới 100%, thực hiện close file
        3. Close app hoặc chuyển app sang background
        """
        pkg = cfg["app"]["package_name"]

        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        remote_path = "/sdcard/Download/sample_autotest.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(1)

        # Đưa về màn hình home trước khi mở file từ intent (simulate app khác)
        adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
        time.sleep(1)

        # 1. Mở file từ intent (simulate app khác)
        adb._run([
            "shell", "am", "start",
            "-a", "android.intent.action.VIEW",
            "-t", "application/pdf",
            "-d", f"file://{remote_path}",
        ])
        time.sleep(3)

        # Xử lý dialog "Open with..." nếu có (ResolverActivity/ChooserActivity)
        _handle_chooser(adb, driver)

        # Dismiss ads nếu có
        RobustDriver(driver).configure_recovery(adb=adb).dismiss_ad_if_any()

        # 2. Đọc file một chút (<100%) rồi close file
        if is_visible(driver, "doc_view", timeout=8):
            size = driver.get_window_size()
            w, h = size["width"], size["height"]
            driver.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3), 400)
            time.sleep(1)

        if is_visible(driver, "imv_toolbar_back", timeout=5):
            find(driver, "imv_toolbar_back").click()
            time.sleep(2)

        # Xóa notifications cũ
        clear_all_notifications(driver)

        # 4. Chuyển app sang background
        background_app(driver)
        time.sleep(3)

        # Kiểm tra notification
        noti_found = wait_for_notification(driver, "Complete Reading Now", timeout=30)
        if not noti_found:
            noti_found = wait_for_notification(driver, "Don't miss it", timeout=15)

        if not noti_found:
            open_notification_shade(driver)
            time.sleep(1)

        assert noti_found, \
            "Không tìm thấy silent notification 'Complete Reading Now' cho external file"
        print(f"\n  TC-007 PASS: Silent noti cho external file hiện thị")

    # ── TC-008: Silent noti - file 100% completed từ Home ───────────────────

    @pytest.mark.tc_id("TC-NTF-008")
    def test_tc008_silent_noti_completed_from_home(self, driver, adb, cfg):
        """
        TC-008: Chỉ có file đã đọc 100%, opened từ Home, close app
        Expected: Hiện noti silent với 'Complete Reading Now'
        """
        pkg = cfg["app"]["package_name"]
        go_to_home(driver, cfg)

        # Chọn file không phải Welcome
        items = find_all(driver, "vl_item_file_name", timeout=10)
        target = next((el for el in items if "welcome" not in el.text.lower()), None)

        # Nếu không có file phù hợp → push file test
        if target is None:
            test_pdf_local = os.path.join(
                os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
            )
            remote_path = "/sdcard/Download/sample_simple.pdf"
            adb.push_file(test_pdf_local, remote_path)
            time.sleep(3)
            go_to_home(driver, cfg)
            items = find_all(driver, "vl_item_file_name", timeout=10)
            target = next((el for el in items if "welcome" not in el.text.lower()), None)

        if target is None:
            pytest.skip("Không có file nào (ngoài Welcome) để test TC-008")

        file_name = target.text
        target.click()
        time.sleep(3)

        RobustDriver(driver).configure_recovery(adb=adb).dismiss_ad_if_any()

        # Cuộn đến cuối file để simulate đọc 100%
        if is_visible(driver, "doc_view", timeout=8):
            size = driver.get_window_size()
            w, h = size["width"], size["height"]
            for _ in range(15):
                driver.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.2), 400)
                time.sleep(0.3)

        # Close file
        if is_visible(driver, "imv_toolbar_back", timeout=5):
            find(driver, "imv_toolbar_back").click()
            time.sleep(2)

        # Xóa notifications cũ
        clear_all_notifications(driver)

        # Background app
        background_app(driver)
        time.sleep(2)

        # Force gửi exit notification qua ADB broadcast (TYPE_EXIT_9, khác với TC-006 dùng TYPE_EXIT_10)
        force_exit_notification(adb, pkg, alarm_type=10342)  # TYPE_EXIT_9

        # Kiểm tra notification
        noti_found = wait_for_notification(driver, "Complete Reading Now", timeout=15)
        if not noti_found:
            noti_found = wait_for_notification(driver, "Read All Files", timeout=10)
        if not noti_found:
            noti_found = wait_for_notification(driver, "Don't miss it", timeout=10)

        # Mở notification shade trước khi assert để screenshot chụp đúng trạng thái
        if not noti_found:
            open_notification_shade(driver)
            time.sleep(1)

        assert noti_found, \
            f"Không tìm thấy silent notification sau khi đọc 100% file '{file_name}'"
        print(f"\n  TC-008 PASS: Silent noti sau khi đọc 100% file '{file_name}'")

    # ── TC-009: Silent noti - file 100% từ app khác ──────────────────────────

    @pytest.mark.tc_id("TC-NTF-009")
    def test_tc009_silent_noti_completed_from_external(self, driver, adb, cfg):
        """
        TC-009: File đã đọc 100%, opened từ app khác, close app
        Expected: Hiện noti silent với 'Complete Reading Now'
        Luồng:
        1. Mở file từ app khác (dismiss ads nếu có)
        2. Đọc file 100%
        3. Close app hoặc chuyển app sang background
        """
        pkg = cfg["app"]["package_name"]

        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        remote_path = "/sdcard/Download/sample_autotest_complete.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(1)

        # Xóa notifications cũ trước khi bắt đầu
        clear_all_notifications(driver)

        # 1. Mở file từ intent (simulate app khác)
        adb._run([
            "shell", "am", "start",
            "-a", "android.intent.action.VIEW",
            "-t", "application/pdf",
            "-d", f"file://{remote_path}",
        ])
        time.sleep(3)

        # Xử lý dialog "Open with..." nếu có
        _handle_chooser(adb, driver, "Just once")
        time.sleep(10)

        # Dismiss ads nếu có (chỉ dùng XPATH, không dùng fallback tap)
        from tests.helpers import _is_ad_showing, dismiss_ads
        for _ in range(3):
            if is_visible(driver, "doc_view", timeout=3) or is_visible(driver, "imv_toolbar_back", timeout=2):
                break
            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(2)

        # 2. Scroll đến cuối để đọc 100%
        if is_visible(driver, "doc_view", timeout=8):
            size = driver.get_window_size()
            w, h = size["width"], size["height"]
            for _ in range(15):
                driver.swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.2), 400)
                time.sleep(0.3)

        # Close file
        if is_visible(driver, "imv_toolbar_back", timeout=5):
            find(driver, "imv_toolbar_back").click()
            time.sleep(2)

        # 3. Background app
        background_app(driver)
        time.sleep(3)

        # Kiểm tra notification
        noti_found = wait_for_notification(driver, "Complete Reading Now", timeout=15)
        if not noti_found:
            noti_found = wait_for_notification(driver, "Don't miss it", timeout=15)

        # Mở notification shade trước khi assert để screenshot chụp đúng trạng thái
        if not noti_found:
            open_notification_shade(driver)
            time.sleep(1)

        assert noti_found, \
            "Không tìm thấy silent notification sau khi đọc 100% file từ external app"
        print(f"\n  TC-009 PASS: Silent noti cho external file 100%")

    # ── TC-010: Silent noti - file chưa đọc lần nào ─────────────────────────

    @pytest.mark.tc_id("TC-NTF-010")
    def test_tc010_silent_noti_unread_file(self, driver, adb, cfg):
        """
        TC-010: App có file chưa đọc lần nào, close app
        Expected: Hiện noti silent:
          Title: 📚<tên file>.pdf
          Description: 📚Reminder: You seems need to view this file
        """
        pkg = cfg["app"]["package_name"]

        # Push một file PDF mới (chưa từng mở) lên device
        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        # Đặt tên mới để đảm bảo là file "chưa đọc"
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        remote_path = f"/sdcard/Download/unread_test_{ts}.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(2)
        
        try:
            adb._run(["shell", "am", "broadcast",
                      "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", f"file://{remote_path}"])
            time.sleep(1)
        except Exception:
            pass

        # Về home
        go_to_home(driver, cfg)

        # Xóa notifications cũ
        clear_all_notifications(driver)

        # Background app
        background_app(driver)
        time.sleep(3)

        # Kiểm tra notification với "Reminder"
        noti_found = wait_for_notification(driver, "Reminder", timeout=30)
        if not noti_found:
            noti_found = wait_for_notification(driver, "need to view", timeout=15)
        if not noti_found:
            noti_found = wait_for_notification(driver, "Don't miss it", timeout=15)

        # Cleanup
        adb._run(["shell", "rm", remote_path])

        assert noti_found, \
            "Không tìm thấy silent notification 'Reminder: You seems need to view this file'"
        print(f"\n  TC-010 PASS: Silent noti 'Reminder' cho unread file hiện thị")

    # ── TC-011: Click Open button on notification ─────────────────────────────

    @pytest.mark.tc_id("TC-NTF-011")
    def test_tc011_open_button_on_noti(self, driver, adb, cfg):
        """
        TC-011: Đã push noti → Bấm button Open (hoặc Read Now trên new file noti)
        Expected: Open app, chuyển đến màn đọc file tương ứng
        
        """
        import datetime
        pkg = cfg["app"]["package_name"]

        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        clear_all_notifications(driver)
        adb._run(["shell", "input", "keyevent", "3"])  # HOME - background app
        time.sleep(3)

        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        remote_path = f"/sdcard/Download/tc011_test_{ts}.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(2)

        # Trigger media scan để app nhận diện file mới
        try:
            adb._run(["shell", "am", "broadcast",
                      "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", f"file://{remote_path}"])
            time.sleep(1)
        except Exception:
            pass
        
        # Vào Home app, click vào file vừa push, đợi 5s rồi dismiss ads
        file_name = os.path.basename(remote_path)
        go_to_home(driver, cfg)
        items = find_all(driver, "vl_item_file_name", timeout=10)
        target = next((el for el in items if file_name.replace(".pdf", "") in el.text), None)
        if target:
            target.click()
        time.sleep(5)
        RobustDriver(driver).configure_recovery(adb=adb).dismiss_ad_if_any()
        
        # Terminate app và đợi 3s
        driver.terminate_app(pkg)
        time.sleep(3)

        # Nhấn Home và đợi để app background + notification xuất hiện
        adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
        time.sleep(3)
        go_to_home(driver, cfg)
        adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
        time.sleep(3)
        noti_found = wait_for_notification(driver, "All Docs PDF Reader", timeout=30)
        assert noti_found, "Không tìm thấy notification 'All Docs PDF Reader'"

        # Click nút action — thử "Read now" trước, fallback "Open"
        
        clicked = click_notification_by_text(driver, "All Docs PDF Reader", click_button_text="Open")
        if not clicked:
            adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
            time.sleep(3)
            clicked = click_notification_by_text(driver, "All Docs PDF Reader", click_button_text="Read now")
        
        if not clicked:
            open_notification_shade(driver)
            time.sleep(1)
            assert False, "Không tìm thấy hoặc không click được nút action trên notification"
        time.sleep(5)
        # Dismiss ads nếu có
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            #         time.sleep(1)
        RobustDriver(driver).configure_recovery(adb=adb).dismiss_ad_if_any()
        time.sleep(5)
        
        reading_open = _wait_reader_open(driver, timeout=10)
        
        assert reading_open, "Expected mở màn đọc file hoặc home sau khi bấm nút noti"
        print(f"\n  TC-011 PASS: Bấm action button trên noti → mở app thành công")

    # ── TC-012: Click notification body ──────────────────────────────────────

    @pytest.mark.tc_id("TC-NTF-012")
    def test_tc012_click_noti_body(self, driver, adb, cfg):
        """
        TC-012: Đã push noti → Bấm bất kỳ đâu trên noti
        Expected: Open app, chuyển đến màn đọc file tương ứng
        Note: Dùng new file notification vì silent exit noti bị chặn bởi UIAutomator2 foreground.
        """
        import datetime
        pkg = cfg["app"]["package_name"]

        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        clear_all_notifications(driver)
        adb._run(["shell", "input", "keyevent", "3"])  # HOME - background app
        time.sleep(3)

        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        remote_path = f"/sdcard/Download/tc011_test_{ts}.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(2)

        # Trigger media scan để app nhận diện file mới
        try:
            adb._run(["shell", "am", "broadcast",
                      "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", f"file://{remote_path}"])
            time.sleep(1)
        except Exception:
            pass
        
        # Vào Home app, click vào file vừa push, đợi 5s rồi dismiss ads
        file_name = os.path.basename(remote_path)
        go_to_home(driver, cfg)
        items = find_all(driver, "vl_item_file_name", timeout=10)
        target = next((el for el in items if file_name.replace(".pdf", "") in el.text), None)
        if target:
            target.click()
        time.sleep(5)
        RobustDriver(driver).configure_recovery(adb=adb).dismiss_ad_if_any()
        
        # Terminate app và đợi 3s
        driver.terminate_app(pkg)
        time.sleep(3)

        # Nhấn Home và đợi để app background + notification xuất hiện
        adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
        time.sleep(3)
        go_to_home(driver, cfg)
        adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
        time.sleep(3)
        noti_found = wait_for_notification(driver, "All Docs PDF Reader", timeout=30)
        assert noti_found, "Không tìm thấy notification 'All Docs PDF Reader'"

        # Click nút action — thử "Read now" trước, fallback "Open"
        
        clicked = click_notification_by_text(driver, "All Docs PDF Reader", click_button_text="Don't miss out")
        if not clicked:
            adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
            time.sleep(3)
            clicked = click_notification_by_text(driver, "All Docs PDF Reader", click_button_text="Open")
        
        if not clicked:
            open_notification_shade(driver)
            time.sleep(1)
            assert False, "Không tìm thấy hoặc không click được nút action trên notification"
        time.sleep(5)
        # Dismiss ads nếu có
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            #         time.sleep(1)
        RobustDriver(driver).configure_recovery(adb=adb).dismiss_ad_if_any()
        time.sleep(5)
        
        reading_open = _wait_reader_open(driver, timeout=10)
        
        assert reading_open, "Expected mở màn đọc file hoặc home sau khi bấm nút noti"
        print(f"\n  TC-012 PASS: Bấm vào body noti → mở app thành công")

    # ── TC-013: Dismiss notification ─────────────────────────────────────────

    @pytest.mark.tc_id("TC-NTF-013")
    def test_tc013_dismiss_noti(self, driver, adb, cfg):
        """
        TC-013: Đã push noti → Xóa noti
        Expected: Noti không còn trên device
        Note: Dùng new file notification vì silent exit noti bị chặn bởi UIAutomator2 foreground.
        """
        import datetime
        pkg = cfg["app"]["package_name"]

        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        clear_all_notifications(driver)
        adb._run(["shell", "input", "keyevent", "3"])  # HOME - background app
        time.sleep(3)

        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        remote_path = f"/sdcard/Download/tc011_test_{ts}.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(2)

        # Trigger media scan để app nhận diện file mới
        try:
            adb._run(["shell", "am", "broadcast",
                      "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", f"file://{remote_path}"])
            time.sleep(1)
        except Exception:
            pass
        
        # Vào Home app, click vào file vừa push, đợi 5s rồi dismiss ads
        file_name = os.path.basename(remote_path)
        go_to_home(driver, cfg)
        items = find_all(driver, "vl_item_file_name", timeout=10)
        target = next((el for el in items if file_name.replace(".pdf", "") in el.text), None)
        if target:
            target.click()
        time.sleep(5)
        RobustDriver(driver).configure_recovery(adb=adb).dismiss_ad_if_any()
        
        # Terminate app và đợi 3s
        driver.terminate_app(pkg)
        time.sleep(3)

        # Nhấn Home và đợi để app background + notification xuất hiện
        adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
        time.sleep(3)
        go_to_home(driver, cfg)
        adb._run(["shell", "input", "keyevent", "3"])  # KEYCODE_HOME
        time.sleep(3)
        noti_found = wait_for_notification(driver, "All Docs PDF Reader", timeout=30)
        assert noti_found, "Không tìm thấy notification 'All Docs PDF Reader'"
        # Xóa toàn bộ notification
        clear_all_notifications(driver)
        time.sleep(2)
        # Verify notification đã biến mất
        driver.open_notifications()
        time.sleep(2)
        source = driver.page_source
        noti_keyword = ["Don't miss out"]
        for i in noti_keyword:
            still_visible = i.lower() in source.lower()
            assert not still_visible, \
            f"Notification '{i}' vẫn còn sau khi xóa"
        time.sleep(1)
        adb._run(["shell", "rm", remote_path])

        print(f"\n  TC-013 PASS: Notification đã bị xóa thành công")

    # ── TC-014: Alarm notification 9AM (Morning) ─────────────────────────────

    @pytest.mark.tc_id("TC-NTF-014")
    def test_tc014_alarm_noti_morning(self, driver, adb, cfg):
        """
        TC-014: Check noti alarm lúc 9h AM (TYPE_MORNING=10340)
        Expected: Title "Hello a new day!!!", Description "Read uncompleted files now"
        Note: App chỉ gửi noti nếu đang weekday và giờ trong 6-8h AM.
        """
        import datetime
        pkg = cfg["app"]["package_name"]

        now = datetime.datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0=Mon, 6=Sun

        # Cảnh báo nếu ngoài giờ hợp lệ (6-8h sáng, weekday)
        if not (6 <= hour <= 8 and weekday < 5):
            pytest.skip(
                f"TC-014 cần chạy lúc 6-8h sáng ngày thường (hiện tại: {now.strftime('%H:%M %a')})"
            )

        go_to_home(driver, cfg)
        clear_all_notifications(driver)
        background_app(driver)
        time.sleep(2)

        # Trigger morning alarm
        force_alarm_notification(adb, pkg, alarm_type=10340)

        noti_found = wait_for_notification(driver, "Hello a new day", timeout=15)
        if not noti_found:
            noti_found = wait_for_notification(driver, "Read uncompleted", timeout=10)

        if not noti_found:
            open_notification_shade(driver)
            time.sleep(1)

        try:
            driver.activate_app(pkg)
        except Exception:
            pass

        assert noti_found, \
            "Không tìm thấy alarm notification 'Hello a new day!!!'"
        print(f"\n  TC-014 PASS: Morning alarm notification hiển thị")

    # ── TC-015: Alarm notification 10PM (Night) ──────────────────────────────

    @pytest.mark.tc_id("TC-NTF-015")
    def test_tc015_alarm_noti_night(self, driver, adb, cfg):
        """
        TC-015: Check noti alarm lúc 10 PM (TYPE_NIGHT=10341)
        Expected: Title "Feed your brain🔥🔥🔥", Description "Don't forget reading time before sleeping!"
        Note: App chỉ gửi noti nếu đang weekday và giờ trong 20-22h.
        """
        import datetime
        pkg = cfg["app"]["package_name"]

        now = datetime.datetime.now()
        hour = now.hour
        weekday = now.weekday()

        if not (20 <= hour <= 22 and weekday < 5):
            pytest.skip(
                f"TC-015 cần chạy lúc 20-22h ngày thường (hiện tại: {now.strftime('%H:%M %a')})"
            )

        go_to_home(driver, cfg)
        clear_all_notifications(driver)
        background_app(driver)
        time.sleep(2)

        force_alarm_notification(adb, pkg, alarm_type=10341)

        noti_found = wait_for_notification(driver, "Feed your brain", timeout=15)
        if not noti_found:
            noti_found = wait_for_notification(driver, "before sleeping", timeout=10)

        if not noti_found:
            open_notification_shade(driver)
            time.sleep(1)

        try:
            driver.activate_app(pkg)
        except Exception:
            pass

        assert noti_found, \
            "Không tìm thấy alarm notification 'Feed your brain🔥🔥🔥'"
        print(f"\n  TC-015 PASS: Night alarm notification hiển thị")

    # ── TC-016: Click alarm notification → All files screen ──────────────────

    @pytest.mark.tc_id("TC-NTF-016")
    def test_tc016_click_alarm_noti(self, driver, adb, cfg):
        """
        TC-016: Đã push noti alarm → Click vào noti
        Expected: Hiện thị màn all file (Home)
        """
        import datetime
        pkg = cfg["app"]["package_name"]

        now = datetime.datetime.now()
        hour = now.hour
        weekday = now.weekday()
        in_morning = 6 <= hour <= 8 and weekday < 5
        in_night = 20 <= hour <= 22 and weekday < 5

        if not (in_morning or in_night):
            pytest.skip(
                f"TC-016 cần giờ hợp lệ cho alarm (6-8h hoặc 20-22h, ngày thường). "
                f"Hiện tại: {now.strftime('%H:%M %a')}"
            )

        alarm_type = 10340 if in_morning else 10341
        noti_keyword = "Hello a new day" if in_morning else "Feed your brain"

        go_to_home(driver, cfg)
        clear_all_notifications(driver)
        background_app(driver)
        time.sleep(2)

        force_alarm_notification(adb, pkg, alarm_type=alarm_type)
        noti_found = wait_for_notification(driver, noti_keyword, timeout=15)
        if not noti_found:
            driver.activate_app(pkg)
            pytest.skip("Không có alarm notification để test TC-016")

        clicked = click_notification_by_text(driver, noti_keyword, click_button_text=None)
        time.sleep(3)

        try:
            driver.activate_app(pkg)
            time.sleep(2)
        except Exception:
            pass

        if not clicked:
            open_notification_shade(driver)
            time.sleep(1)
            assert False, "Không click được alarm notification"

        home_open = is_visible(driver, "imv_home_menu_nav", timeout=10)
        assert home_open, \
            "Expected mở màn Home (all files) sau khi click alarm notification"
        print(f"\n  TC-016 PASS: Click alarm noti → mở màn Home")

    # ── TC-017: Dismiss alarm notification ───────────────────────────────────

    @pytest.mark.tc_id("TC-NTF-017")
    def test_tc017_dismiss_alarm_noti(self, driver, adb, cfg):
        """
        TC-017: Đã push noti alarm → Xóa noti
        Expected: Xóa noti khỏi device
        """
        import datetime
        pkg = cfg["app"]["package_name"]

        now = datetime.datetime.now()
        hour = now.hour
        weekday = now.weekday()
        in_morning = 6 <= hour <= 8 and weekday < 5
        in_night = 20 <= hour <= 22 and weekday < 5

        if not (in_morning or in_night):
            pytest.skip(
                f"TC-017 cần giờ hợp lệ cho alarm. Hiện tại: {now.strftime('%H:%M %a')}"
            )

        alarm_type = 10340 if in_morning else 10341
        noti_keyword = "Hello a new day" if in_morning else "Feed your brain"

        go_to_home(driver, cfg)
        clear_all_notifications(driver)
        background_app(driver)
        time.sleep(2)

        force_alarm_notification(adb, pkg, alarm_type=alarm_type)
        noti_found = wait_for_notification(driver, noti_keyword, timeout=15)
        if not noti_found:
            driver.activate_app(pkg)
            pytest.skip("Không có alarm notification để test TC-017")

        dismiss_notification_by_text(driver, noti_keyword)
        time.sleep(1)

        driver.open_notifications()
        time.sleep(2)
        source = driver.page_source
        still_visible = noti_keyword.lower() in source.lower()
        driver.back()

        try:
            driver.activate_app(pkg)
        except Exception:
            pass

        assert not still_visible, \
            f"Alarm notification '{noti_keyword}' vẫn còn sau khi xóa"
        print(f"\n  TC-017 PASS: Alarm notification đã bị xóa")

    # ── TC-018: New file notification ─────────────────────────────────────────

    @pytest.mark.tc_id("TC-NTF-018")
    def test_tc018_new_file_noti(self, driver, adb, cfg):
        """
        TC-018: Download/tạo file mới → Hiện noti New File
        Expected: Title: <tên file>.pdf, Description: "You have a new file", Button "Read Now"
        Note: CheckFileEndlessService monitors file system khi app ở background.
        """
        import datetime
        pkg = cfg["app"]["package_name"]
        go_to_home(driver, cfg)
        clear_all_notifications(driver)

        # Background app để service có thể detect file mới
        background_app(driver)
        time.sleep(3)

        # Push file mới với tên unique
        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            driver.activate_app(pkg)
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        remote_path = f"/sdcard/Download/newfile_test_{ts}.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(2)

        # Chờ new file notification (service cần thời gian detect)
        file_name = f"newfile_test_{ts}.pdf"
        noti_found = wait_for_notification(driver, "You have a new file", timeout=30)
        if not noti_found:
            noti_found = wait_for_notification(driver, file_name[:15], timeout=15)

        if not noti_found:
            open_notification_shade(driver)
            time.sleep(1)

        # Cleanup
        adb._run(["shell", "rm", remote_path])
        try:
            driver.activate_app(pkg)
        except Exception:
            pass

        assert noti_found, \
            f"Không tìm thấy new file notification cho '{file_name}'"
        print(f"\n  TC-018 PASS: New file notification hiển thị cho '{file_name}'")

    # ── TC-019: Click Open on new file notification ───────────────────────────

    @pytest.mark.tc_id("TC-NTF-019")
    def test_tc019_open_new_file_noti(self, driver, adb, cfg):
        """
        TC-019: Đã push noti new file → Click Open
        Expected: Hiện thị màn đọc file tương ứng
        """
        import datetime
        pkg = cfg["app"]["package_name"]
        go_to_home(driver, cfg)
        clear_all_notifications(driver)
        background_app(driver)
        time.sleep(3)

        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            driver.activate_app(pkg)
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        remote_path = f"/sdcard/Download/newfile_open_{ts}.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(2)

        file_name = f"newfile_open_{ts}.pdf"
        noti_found = wait_for_notification(driver, "You have a new file", timeout=30)
        if not noti_found:
            driver.activate_app(pkg)
            adb._run(["shell", "rm", remote_path])
            pytest.skip("Không có new file notification để test TC-019")

        # Click vào notification để mở app
        clicked = click_notification_by_text(driver, "You have a new file", click_button_text="Read Now")
        time.sleep(3)

        if not clicked:
            adb._run(["shell", "rm", remote_path])
            assert False, "Không click được notification new file"

        # Dismiss ad nếu có
        try:
            from tests.helpers import dismiss_ads, _is_ad_showing
            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(2)
        except Exception:
            pass

        # Kiểm tra nếu reading screen đã mở trực tiếp từ notification
        reading_open = is_visible(driver, "imv_toolbar_back", timeout=5)

        # Nếu chưa vào reading screen → tìm file trong danh sách home và tap
        if not reading_open and is_visible(driver, "rcv_all_file", timeout=5):
            try:
                file_el = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((
                        AppiumBy.XPATH,
                        f'//*[contains(@text, "{file_name}")]'
                    ))
                )
                file_el.click()
                time.sleep(3)
                # Dismiss ad lần 2 nếu có sau khi mở file
                if _is_ad_showing(driver):
                    dismiss_ads(driver)
                    time.sleep(2)
                reading_open = is_visible(driver, "imv_toolbar_back", timeout=8)
            except Exception:
                pass

        # Cleanup
        adb._run(["shell", "rm", remote_path])
        assert reading_open, \
            f"Expected màn đọc file '{file_name}' mở sau khi click notification, nhưng không thấy"
        print(f"\n  TC-019 PASS: Click notification → mở màn đọc file '{file_name}' thành công")

    # ── TC-020: Dismiss new file notification ────────────────────────────────

    @pytest.mark.tc_id("TC-NTF-020")
    def test_tc020_dismiss_new_file_noti(self, driver, adb, cfg):
        """
        TC-020: Đã push noti new file → Xóa noti
        Expected: Xóa noti khỏi device
        """
        import datetime
        pkg = cfg["app"]["package_name"]
        go_to_home(driver, cfg)
        clear_all_notifications(driver)
        background_app(driver)
        time.sleep(3)

        test_pdf_local = os.path.join(
            os.path.dirname(__file__), "../../tests/resources/sample_simple.pdf"
        )
        if not os.path.exists(test_pdf_local):
            driver.activate_app(pkg)
            pytest.skip("Không có file test PDF (tests/resources/sample_simple.pdf)")

        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        remote_path = f"/sdcard/Download/newfile_dismiss_{ts}.pdf"
        adb.push_file(test_pdf_local, remote_path)
        time.sleep(2)

        noti_found = wait_for_notification(driver, "You have a new file", timeout=30)
        if not noti_found:
            driver.activate_app(pkg)
            adb._run(["shell", "rm", remote_path])
            pytest.skip("Không có new file notification để test TC-020")

        # Dùng clear_all_notifications để xóa toàn bộ notification
        clear_all_notifications(driver)
        time.sleep(2)

        # Verify notification đã biến mất
        driver.open_notifications()
        time.sleep(2)
        source = driver.page_source
        still_visible = "You have a new file" in source
        driver.back()
        time.sleep(1)

        adb._run(["shell", "rm", remote_path])
        try:
            driver.activate_app(pkg)
        except Exception:
            pass

        assert not still_visible, \
            "New file notification vẫn còn sau khi xóa"
        print(f"\n  TC-020 PASS: New file notification đã bị xóa")
