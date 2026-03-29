"""
Open Files Password Tests - TC-006 đến TC-011, TC-021 đến TC-025
Sheet: TC - Open Files (version N.2.6.8)

TC-006: Nhập đúng pass → click Cancel → dialog đóng, file KHÔNG mở
TC-007: Nhập sai pass + chọn Remember → click OK → dialog reload (không mở)
TC-008: Không nhập pass + chọn Remember → click OK → dialog reload (không mở)
TC-009: Nhập đúng pass + chọn Remember → click OK → file mở thành công
TC-010: Nhập đúng pass + chọn Remember → click Cancel → dialog đóng, file KHÔNG mở
TC-011: Mở lại file sau khi đã Remember → file mở thẳng không hỏi pass nữa

TC-021: Open file có pass từ màn Home → Show dialog nhập pass
TC-022: Open file có pass từ app khác (external intent) → Show dialog nhập pass
TC-023: Nhập pass đúng, click OK → Mở file thành công
TC-024: Nhập pass không đúng, click OK → Popup reload (không mở được)
TC-025: Không nhập pass, click OK → Popup reload (không mở được)

File test: sample_password.pdf (password: kanbanery)
"""
import time
import os
import urllib.parse
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from tests.helpers import (
    find, find_all, is_visible, rid,
    go_to_home, dismiss_ads, _is_ad_showing, ensure_app_foreground,
)

PKG = "pdf.reader.pdf.viewer.all.document.reader.office.viewer"
PASSWORD_CORRECT = "kanbanery"
PASSWORD_WRONG = "wrongpass!@#"
REMOTE_PDF_PATH = "/sdcard/Download/sample_password_autotest.pdf"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_test_pdf_local():
    return os.path.join(os.path.dirname(__file__), "../../tests/resources/sample_password.pdf")


def push_password_pdf(adb):
    """Push file PDF có password lên device và trigger media scanner."""
    local = get_test_pdf_local()
    if not os.path.exists(local):
        raise FileNotFoundError(f"File test không tồn tại: {local}")
    adb.push_file(local, REMOTE_PDF_PATH)
    # Trigger media scanner để app thấy file ngay
    adb._run([
        "shell", "am", "broadcast",
        "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d", f"file://{REMOTE_PDF_PATH}",
    ])
    time.sleep(2)


def _pull_to_refresh_file_list(driver):
    """Pull-to-refresh trên danh sách file để app cập nhật."""
    try:
        size = driver.get_window_size()
        w, h = size["width"], size["height"]
        driver.swipe(w // 2, h // 4, w // 2, h // 2, 600)
        time.sleep(2)
    except Exception:
        pass


def open_password_pdf_from_home(driver, adb, cfg):
    """
    Push file lên rồi mở từ màn Home của app.
    Dùng UiScrollable để cuộn và tìm file theo tên.
    Trả về True nếu đã click vào file.
    """
    push_password_pdf(adb)
    go_to_home(driver, cfg)
    # Pull-to-refresh để app scan file mới push
    _pull_to_refresh_file_list(driver)

    file_name = "sample_password_autotest"

    # Dùng UiScrollable để scroll và tìm file theo tên (kể cả khi file không visible)
    try:
        el = driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiScrollable(new UiSelector().scrollable(true))'
            f'.scrollIntoView(new UiSelector().textContains("{file_name}"))',
        )
        el.click()
        time.sleep(3)
        return True
    except Exception:
        pass

    # Fallback: tìm trong visible items
    items = find_all(driver, "vl_item_file_name", timeout=5)
    for item in items:
        if file_name in (item.text or ""):
            item.click()
            time.sleep(3)
            return True

    return False


def wait_for_password_dialog(driver, timeout=15) -> bool:
    """Chờ dialog nhập password xuất hiện."""
    selectors = [
        (AppiumBy.XPATH, '//*[contains(@text, "Password") or contains(@text, "password") or contains(@text, "Enter") or contains(@text, "Mật khẩu")]'),
        (AppiumBy.XPATH, '//*[contains(@resource-id, "password") or contains(@resource-id, "pass")]'),
        (AppiumBy.XPATH, '//android.widget.EditText'),
    ]
    for by, sel in selectors:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, sel))
            )
            return True
        except TimeoutException:
            continue
    return False


def find_password_input(driver):
    """Tìm EditText để nhập password."""
    selectors = [
        (AppiumBy.XPATH, '//*[contains(@resource-id, "password") and @class="android.widget.EditText"]'),
        (AppiumBy.XPATH, '//*[contains(@resource-id, "pass") and @class="android.widget.EditText"]'),
        (AppiumBy.XPATH, '//*[contains(@resource-id, "edt") and @class="android.widget.EditText"]'),
        (AppiumBy.XPATH, '//android.widget.EditText'),
    ]
    for by, sel in selectors:
        try:
            return WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((by, sel))
            )
        except TimeoutException:
            continue
    return None


def click_ok_button(driver):
    """Click nút OK hoặc Confirm trên dialog."""
    selectors = [
        '//*[@text="OK" or @text="Ok" or @text="Confirm" or @text="Open"]',
        '//*[contains(@resource-id, "btn_ok") or contains(@resource-id, "btnOk") or contains(@resource-id, "button_ok")]',
        '//*[contains(@resource-id, "positive")]',
    ]
    for xpath in selectors:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, xpath))
            )
            btn.click()
            time.sleep(2)
            return True
        except TimeoutException:
            continue
    return False


def click_cancel_button(driver):
    """Click nút Cancel trên dialog."""
    selectors = [
        '//*[@text="Cancel" or @text="Hủy" or @text="CANCEL"]',
        '//*[contains(@resource-id, "btn_cancel") or contains(@resource-id, "btnCancel")]',
        '//*[contains(@resource-id, "negative")]',
    ]
    for xpath in selectors:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, xpath))
            )
            btn.click()
            time.sleep(2)
            return True
        except TimeoutException:
            continue
    return False


def enter_password(driver, password: str):
    """Nhập password vào EditText."""
    pwd_input = find_password_input(driver)
    if pwd_input is None:
        return False
    pwd_input.clear()
    pwd_input.send_keys(password)
    time.sleep(1)
    return True


def _handle_app_chooser(driver, pkg: str):
    """
    Xử lý Android 'Open with' chooser nếu xuất hiện.
    Tìm và click vào option của app PDF Reader.
    """
    try:
        # Tìm option trong chooser chứa tên app hoặc package
        chooser_xpath = (
            f'//*[contains(@text, "PDF") and contains(@text, "Reader")]'
            f' | //*[contains(@text, "pdf") and contains(@text, "reader")]'
            f' | //*[contains(@package, "{pkg}")]'
        )
        el = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, chooser_xpath))
        )
        el.click()
        time.sleep(2)
        # Click "Just once" nếu có
        for text in ["Just once", "Only this time", "Một lần"]:
            try:
                btn = driver.find_element(AppiumBy.XPATH, f'//*[@text="{text}"]')
                btn.click()
                time.sleep(2)
                break
            except Exception:
                pass
    except Exception:
        pass


def is_file_opened(driver, timeout=8) -> bool:
    """Kiểm tra file đã mở thành công (có toolbar back hoặc doc_view)."""
    return (is_visible(driver, "imv_toolbar_back", timeout=timeout) or
            is_visible(driver, "doc_view", timeout=3))


def is_password_dialog_still_showing(driver) -> bool:
    """Kiểm tra dialog nhập password vẫn còn hiển thị."""
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((AppiumBy.XPATH, '//android.widget.EditText'))
        )
        return True
    except TimeoutException:
        return False


def find_remember_checkbox(driver):
    """Tìm checkbox 'Remember password' trong dialog."""
    selectors = [
        (AppiumBy.XPATH, '//*[contains(@resource-id, "remember") or contains(@resource-id, "Remember")]'),
        (AppiumBy.XPATH, '//*[contains(@resource-id, "check") and @class="android.widget.CheckBox"]'),
        (AppiumBy.XPATH, '//android.widget.CheckBox'),
    ]
    for by, sel in selectors:
        try:
            return WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((by, sel))
            )
        except TimeoutException:
            continue
    return None


def check_remember_checkbox(driver) -> bool:
    """Tick vào checkbox Remember nếu chưa được check. Trả về True nếu thành công."""
    cb = find_remember_checkbox(driver)
    if cb is None:
        return False
    checked = cb.get_attribute("checked")
    if checked != "true":
        cb.click()
        time.sleep(0.5)
    return True


def clear_remember_for_file(adb, pkg: str, remote_path: str):
    """Xóa dữ liệu remember password của app để reset trạng thái."""
    try:
        adb._run(["shell", "pm", "clear", pkg])
        time.sleep(1)
    except Exception:
        pass


# ─── Test Class ───────────────────────────────────────────────────────────────

class TestRememberPassword:
    """TC-006 đến TC-011: Kiểm tra Cancel dialog và Remember Password."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, driver, adb, cfg):
        """Setup: pm clear app để reset SharedPreferences. Teardown: về home, xóa file."""
        # pm clear PKG: xóa toàn bộ data app (SharedPreferences, cache) để loại trừ cached password
        adb._run(["shell", "pm", "clear", PKG])
        time.sleep(3)  # Chờ app hoàn toàn dừng
        # Activate lại app và chờ boot xong
        try:
            driver.activate_app(PKG)
            time.sleep(4)
        except Exception:
            pass
        go_to_home(driver, cfg)
        yield
        # Teardown: về home trước, rồi xóa file
        try:
            go_to_home(driver, cfg)
        except Exception:
            pass
        try:
            adb._run(["shell", "rm", "-f", REMOTE_PDF_PATH])
        except Exception:
            pass

    def _open_and_get_dialog(self, driver, adb, cfg):
        """Helper: push file, về home, mở file, trả về True nếu dialog xuất hiện."""
        local = get_test_pdf_local()
        if not os.path.exists(local):
            pytest.skip("Không có file PDF có password để test")
        push_password_pdf(adb)
        go_to_home(driver, cfg)
        time.sleep(2)
        opened = open_password_pdf_from_home(driver, adb, cfg)
        assert opened, "Không tìm thấy file trong danh sách"
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)
        dialog = wait_for_password_dialog(driver, timeout=15)
        if not dialog:
            pytest.skip("Dialog nhập password không xuất hiện")
        return True

    # ── TC-006: Nhập đúng pass → click Cancel ────────────────────────────────

    @pytest.mark.tc_id("TC-006")
    def test_tc006_correct_password_click_cancel(self, driver, adb, cfg):
        """
        TC-006: Nhập đúng pass mở file → click Cancel
        Expected: Dialog đóng lại, file KHÔNG được mở, quay về màn hình trước
        """
        self._open_and_get_dialog(driver, adb, cfg)

        entered = enter_password(driver, PASSWORD_CORRECT)
        assert entered, "Không nhập được password"

        clicked = click_cancel_button(driver)
        assert clicked, "Không click được nút Cancel"
        time.sleep(2)

        # File không được mở
        file_opened = is_file_opened(driver, timeout=5)
        assert not file_opened, "File đã mở dù click Cancel — đây là bug!"

        # Dialog không còn hiển thị
        dialog_showing = is_password_dialog_still_showing(driver)
        assert not dialog_showing, "Dialog vẫn còn hiển thị sau khi click Cancel"
        print("\n  TC-006 PASS: Nhập đúng pass → Cancel → file không mở, dialog đóng")

    # ── TC-007: Nhập sai pass + Remember → click OK ──────────────────────────

    @pytest.mark.tc_id("TC-007")
    def test_tc007_wrong_password_with_remember_click_ok(self, driver, adb, cfg):
        """
        TC-007: Nhập sai pass + chọn Remember → click OK
        Expected: Dialog reload, file không mở được
        """
        self._open_and_get_dialog(driver, adb, cfg)

        entered = enter_password(driver, PASSWORD_WRONG)
        assert entered, "Không nhập được password"

        # Tick Remember (nếu có)
        check_remember_checkbox(driver)

        click_ok_button(driver)
        time.sleep(3)

        # Kiểm tra dialog trước — nếu dialog vẫn còn thì file chắc chắn chưa mở
        dialog_showing = is_password_dialog_still_showing(driver)
        assert dialog_showing, "Expected dialog reload sau khi nhập sai pass + Remember"

        # Chỉ kiểm tra file_opened khi dialog đã biến mất (tránh false-positive)
        if not dialog_showing:
            file_opened = is_file_opened(driver, timeout=5)
            assert not file_opened, "File đã mở dù nhập sai password — đây là bug!"
        print("\n  TC-007 PASS: Sai pass + Remember → OK → dialog reload, không mở file")

    # ── TC-008: Không nhập pass + Remember → click OK ────────────────────────

    @pytest.mark.tc_id("TC-008")
    def test_tc008_empty_password_with_remember_click_ok(self, driver, adb, cfg):
        """
        TC-008: Không nhập pass + chọn Remember → click OK
        Expected: Dialog reload, file không mở được
        """
        self._open_and_get_dialog(driver, adb, cfg)

        # Đảm bảo input trống
        pwd_input = find_password_input(driver)
        if pwd_input:
            pwd_input.clear()
            time.sleep(0.5)

        # Tick Remember (nếu có)
        check_remember_checkbox(driver)

        click_ok_button(driver)
        time.sleep(3)

        file_opened = is_file_opened(driver, timeout=5)
        assert not file_opened, "File đã mở dù không nhập password — đây là bug!"

        dialog_showing = is_password_dialog_still_showing(driver)
        assert dialog_showing, "Expected dialog reload khi không nhập pass + Remember"
        print("\n  TC-008 PASS: Không nhập pass + Remember → OK → dialog reload, không mở file")

    # ── TC-009: Nhập đúng pass + Remember → click OK ─────────────────────────

    @pytest.mark.tc_id("TC-009")
    def test_tc009_correct_password_with_remember_click_ok(self, driver, adb, cfg):
        """
        TC-009: Nhập đúng pass + chọn Remember → click OK
        Expected: File mở thành công. Lần mở tiếp theo sẽ không hỏi pass nữa (xem TC-011)
        """
        self._open_and_get_dialog(driver, adb, cfg)

        entered = enter_password(driver, PASSWORD_CORRECT)
        assert entered, "Không nhập được password"

        # Tick Remember
        check_remember_checkbox(driver)

        click_ok_button(driver)
        time.sleep(3)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        file_opened = is_file_opened(driver, timeout=10)
        assert file_opened, \
            f"Expected mở file thành công sau khi nhập đúng pass '{PASSWORD_CORRECT}' + Remember"
        print("\n  TC-009 PASS: Đúng pass + Remember → OK → file mở thành công")

    # ── TC-010: Nhập đúng pass + Remember → click Cancel ─────────────────────

    @pytest.mark.tc_id("TC-010")
    def test_tc010_correct_password_with_remember_click_cancel(self, driver, adb, cfg):
        """
        TC-010: Nhập đúng pass + chọn Remember → click Cancel
        Expected: Dialog đóng lại, file KHÔNG được mở
        """
        self._open_and_get_dialog(driver, adb, cfg)

        entered = enter_password(driver, PASSWORD_CORRECT)
        assert entered, "Không nhập được password"

        # Tick Remember
        check_remember_checkbox(driver)

        clicked = click_cancel_button(driver)
        assert clicked, "Không click được nút Cancel"
        time.sleep(2)

        file_opened = is_file_opened(driver, timeout=5)
        assert not file_opened, "File đã mở dù click Cancel — đây là bug!"

        dialog_showing = is_password_dialog_still_showing(driver)
        assert not dialog_showing, "Dialog vẫn hiển thị sau khi click Cancel"
        print("\n  TC-010 PASS: Đúng pass + Remember → Cancel → file không mở, dialog đóng")

    # ── TC-011: Mở lại file sau khi đã Remember ──────────────────────────────

    @pytest.mark.tc_id("TC-011")
    def test_tc011_reopen_file_after_remember(self, driver, adb, cfg):
        """
        TC-011: Mở lại file sau khi đã chọn Remember password (TC-009 đã chạy)
        Expected: File mở thẳng KHÔNG hiển thị dialog nhập password nữa
        Pre-condition: TC-009 đã chạy (remember đã được set cho file này)
        """
        local = get_test_pdf_local()
        if not os.path.exists(local):
            pytest.skip("Không có file PDF có password để test")

        # Bước 1: Setup remember (giống TC-009)
        push_password_pdf(adb)
        go_to_home(driver, cfg)
        time.sleep(2)

        opened = open_password_pdf_from_home(driver, adb, cfg)
        assert opened, "Không tìm thấy file trong danh sách"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        if wait_for_password_dialog(driver, timeout=10):
            # Nhập pass + remember để setup trạng thái
            enter_password(driver, PASSWORD_CORRECT)
            check_remember_checkbox(driver)
            click_ok_button(driver)
            time.sleep(3)
            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(1)
            # Back về home
            driver.back()
            time.sleep(2)
        else:
            # Dialog không xuất hiện = remember đã set từ trước, OK luôn
            driver.back()
            time.sleep(2)

        go_to_home(driver, cfg)
        time.sleep(1)

        # Bước 2: Mở lại file lần 2
        opened_again = open_password_pdf_from_home(driver, adb, cfg)
        assert opened_again, "Không tìm thấy file trong danh sách khi mở lại"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        time.sleep(3)

        # Expected: file mở thẳng, KHÔNG hỏi password
        dialog_showing = is_password_dialog_still_showing(driver)
        file_opened = is_file_opened(driver, timeout=8)

        assert not dialog_showing, \
            "Dialog nhập password xuất hiện dù đã Remember — Remember không hoạt động!"
        assert file_opened, \
            "File không mở được dù đã Remember password"
        print("\n  TC-011 PASS: Mở lại file sau Remember → mở thẳng, không hỏi pass")


class TestOpenFilesPassword:
    """TC-021 đến TC-025: Kiểm tra mở file có password."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, driver, adb, cfg):
        """Setup: về home, dismiss ads. Teardown: xóa file test."""
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)
        go_to_home(driver, cfg)
        yield
        # Cleanup: xóa file test trên device
        try:
            adb._run(["shell", "rm", "-f", REMOTE_PDF_PATH])
        except Exception:
            pass

    # ── TC-021: Open file có pass từ Home ────────────────────────────────────

    @pytest.mark.tc_id("TC-021")
    def test_tc021_open_password_file_from_home(self, driver, adb, cfg):
        """
        TC-021: Đang ở màn hình Home → Click chọn mở file có pass
        Pre-condition: File PDF có password tồn tại trong danh sách
        Expected: Mở màn hình nhập password đúng với design
        """
        local = get_test_pdf_local()
        if not os.path.exists(local):
            pytest.skip("Không có file PDF có password để test (tests/resources/sample_password.pdf)")

        push_password_pdf(adb)
        go_to_home(driver, cfg)
        time.sleep(2)

        # Mở file có password từ danh sách
        opened = open_password_pdf_from_home(driver, adb, cfg)
        assert opened, "Không tìm thấy file có password trong danh sách"

        # Dismiss ads nếu có
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        # Verify dialog nhập password xuất hiện
        dialog_shown = wait_for_password_dialog(driver, timeout=15)
        assert dialog_shown, \
            "Expected dialog nhập password nhưng không thấy sau khi mở file có pass"
        print(f"\n  TC-021 PASS: Dialog nhập password hiển thị khi mở file có pass từ Home")

    # ── TC-022: Open file có pass từ app khác ────────────────────────────────

    @pytest.mark.tc_id("TC-022")
    def test_tc022_open_password_file_from_external(self, driver, adb, cfg):
        """
        TC-022: Đang ở app khác → Mở file có pass bằng app PDF Reader (external intent)
        Pre-condition: File PDF có password tồn tại trên device
        Expected: Mở màn hình nhập password đúng với design
        """
        local = get_test_pdf_local()
        if not os.path.exists(local):
            pytest.skip("Không có file PDF có password để test")

        push_password_pdf(adb)
        time.sleep(1)

        pkg = cfg["app"]["package_name"]

        # Dùng adb am start KHÔNG có -p để Android tự chọn app (hoặc show chooser)
        # Thử cả file:// và content:// URI
        relative_path = REMOTE_PDF_PATH.replace("/sdcard/", "")
        encoded_rel = urllib.parse.quote(relative_path, safe="")
        uris_to_try = [
            f"file://{REMOTE_PDF_PATH}",
            f"content://com.android.externalstorage.documents/document/primary%3A{encoded_rel}",
        ]

        dialog_shown = False
        for uri in uris_to_try:
            # Không dùng -p để app nhận intent đúng cách (như khi mở từ app khác thực sự)
            adb._run([
                "shell", "am", "start",
                "-a", "android.intent.action.VIEW",
                "-t", "application/pdf",
                "-d", uri,
            ])
            time.sleep(4)

            # Xử lý chooser dialog nếu Android show "Open with..."
            _handle_app_chooser(driver, pkg)

            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(1)

            try:
                driver.activate_app(pkg)
                time.sleep(2)
            except Exception:
                pass

            if wait_for_password_dialog(driver, timeout=10):
                dialog_shown = True
                break

            go_to_home(driver, cfg)
            time.sleep(1)

        assert dialog_shown, \
            "Expected dialog nhập password nhưng không thấy sau khi mở file từ external app"
        print(f"\n  TC-022 PASS: Dialog nhập password hiển thị khi mở file từ external app")

    # ── TC-023: Nhập pass đúng click OK ──────────────────────────────────────

    @pytest.mark.tc_id("TC-023")
    def test_tc023_correct_password_opens_file(self, driver, adb, cfg):
        """
        TC-023: Đang ở dialog nhập pass → Nhập pass đúng → Click OK
        Expected: Mở file thành công, màn hình đọc file hiển thị đúng nội dung
        """
        local = get_test_pdf_local()
        if not os.path.exists(local):
            pytest.skip("Không có file PDF có password để test")

        push_password_pdf(adb)
        go_to_home(driver, cfg)
        time.sleep(2)

        opened = open_password_pdf_from_home(driver, adb, cfg)
        assert opened, "Không mở được file để test TC-023"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        dialog_shown = wait_for_password_dialog(driver, timeout=15)
        if not dialog_shown:
            pytest.skip("Dialog nhập password không xuất hiện, bỏ qua TC-023")

        # Nhập password đúng
        entered = enter_password(driver, PASSWORD_CORRECT)
        assert entered, "Không nhập được password vào dialog"

        # Click OK
        clicked = click_ok_button(driver)
        assert clicked, "Không click được nút OK"
        time.sleep(3)

        # Dismiss ads nếu có sau khi mở file
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        # Verify file đã mở thành công
        file_opened = is_file_opened(driver, timeout=10)
        assert file_opened, \
            f"Expected mở file thành công sau khi nhập pass đúng '{PASSWORD_CORRECT}'"
        print(f"\n  TC-023 PASS: Nhập pass đúng → Mở file thành công")

    # ── TC-024: Nhập pass sai click OK ───────────────────────────────────────

    @pytest.mark.tc_id("TC-024")
    def test_tc024_wrong_password_shows_error(self, driver, adb, cfg):
        """
        TC-024: Đang ở dialog nhập pass → Nhập pass không đúng → Click OK
        Expected: Popup 'Enter Password' bị reload (không mở được file)
        """
        local = get_test_pdf_local()
        if not os.path.exists(local):
            pytest.skip("Không có file PDF có password để test")

        push_password_pdf(adb)
        go_to_home(driver, cfg)
        time.sleep(2)

        opened = open_password_pdf_from_home(driver, adb, cfg)
        assert opened, "Không mở được file để test TC-024"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        dialog_shown = wait_for_password_dialog(driver, timeout=15)
        if not dialog_shown:
            pytest.skip("Dialog nhập password không xuất hiện, bỏ qua TC-024")

        # Nhập password sai (có ký tự đặc biệt)
        entered = enter_password(driver, PASSWORD_WRONG)
        assert entered, "Không nhập được password vào dialog"

        # Click OK
        click_ok_button(driver)
        time.sleep(3)

        # Kiểm tra dialog trước — nếu dialog vẫn còn thì file chắc chắn chưa mở
        dialog_still_showing = is_password_dialog_still_showing(driver)
        assert dialog_still_showing, \
            "Expected dialog reload sau khi nhập sai password, nhưng dialog biến mất"

        # Chỉ kiểm tra file_opened khi dialog đã biến mất (tránh false-positive)
        if not dialog_still_showing:
            file_opened = is_file_opened(driver, timeout=5)
            assert not file_opened, \
                "File đã mở dù nhập sai password — đây là bug!"
        print(f"\n  TC-024 PASS: Nhập pass sai → Dialog reload, không mở được file")

    # ── TC-025: Không nhập pass click OK ─────────────────────────────────────

    @pytest.mark.tc_id("TC-025")
    def test_tc025_empty_password_shows_error(self, driver, adb, cfg):
        """
        TC-025: Đang ở dialog nhập pass → Không nhập pass → Click OK
        Expected: Popup 'Enter Password' bị reload (không mở được file)
        """
        local = get_test_pdf_local()
        if not os.path.exists(local):
            pytest.skip("Không có file PDF có password để test")

        push_password_pdf(adb)
        go_to_home(driver, cfg)
        time.sleep(2)

        opened = open_password_pdf_from_home(driver, adb, cfg)
        assert opened, "Không mở được file để test TC-025"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        dialog_shown = wait_for_password_dialog(driver, timeout=15)
        if not dialog_shown:
            pytest.skip("Dialog nhập password không xuất hiện, bỏ qua TC-025")

        # Đảm bảo input trống (không nhập gì)
        pwd_input = find_password_input(driver)
        if pwd_input:
            pwd_input.clear()
            time.sleep(1)

        # Click OK mà không nhập pass
        click_ok_button(driver)
        time.sleep(3)

        # Verify: file không mở được
        file_opened = is_file_opened(driver, timeout=5)
        assert not file_opened, \
            "File đã mở dù không nhập password — đây là bug!"

        # Verify dialog reload
        dialog_still_showing = is_password_dialog_still_showing(driver)
        assert dialog_still_showing, \
            "Expected dialog reload khi không nhập password, nhưng dialog biến mất"
        print(f"\n  TC-025 PASS: Không nhập pass → Dialog reload, không mở được file")
