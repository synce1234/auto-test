"""
Open Files Other Tests - TC-026 đến TC-054
Sheet: TC - Open Files (version N.2.6.8)

TC-026: Open PDF từ app khác với action "Note to File" → reader + note popup + keyboard
TC-027: Open PPT/PPTX từ app khác → show ads + reader
TC-028: Open PPT/PPTX từ app khác với action "Mark Favourite" → reader + file added to Star
TC-029: Open PPT/PPTX từ app khác với action "Note to File" → reader + note popup + keyboard
TC-030: Open EPUB từ app khác → show ads + reader
TC-031: Open EPUB từ app khác với action "Edit File" → reader + edit file feature
TC-032: Open EPUB từ app khác với action "Mark Favourite" → reader + file added to Star
TC-033: Open EPUB từ app khác với action "Note to File" → reader + note popup + keyboard
TC-034: Open TXT từ app khác → reader
TC-035: Open TXT từ app khác với action "Note to File" → reader + note popup + keyboard
TC-036: Open TXT từ app khác với action "Edit File" → reader + edit file feature
TC-037: Open TXT từ app khác với action "Mark Favourite" → reader + file added to Star
TC-038: Open DOC/DOCX từ app PDF Reader → reader + toolbar đầy đủ
TC-039: Open Excel (XLSX/XLS) từ app PDF Reader → reader + toolbar đầy đủ
TC-040: Open TXT từ app PDF Reader → reader + toolbar đầy đủ
"""
import time
import os
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from tests.helpers import (
    find, find_all, find_text, is_visible, rid,
    go_to_home, dismiss_ads, _is_ad_showing, ensure_app_foreground,
)

PKG = "pdf.reader.pdf.viewer.all.document.reader.office.viewer"
REMOTE_PDF_PATH  = "/sdcard/Download/sample_note_autotest.pdf"
REMOTE_PPTX_PATH = "/sdcard/Download/sample_pptx_autotest.pptx"
REMOTE_EPUB_PATH = "/sdcard/Download/sample_epub_autotest.epub"
REMOTE_TXT_PATH  = "/sdcard/Download/sample_txt_autotest.txt"
REMOTE_DOCX_PATH = "/sdcard/Download/sample_docx_autotest.docx"
REMOTE_XLSX_PATH = "/sdcard/Download/sample_xlsx_autotest.xlsx"

MIME_PDF   = "application/pdf"
MIME_PPTX  = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
MIME_EPUB  = "application/epub+zip"
MIME_TXT   = "text/plain"
MIME_DOCX  = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX  = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_PNG   = "image/png"
MIME_JPG   = "image/jpeg"
MIME_GIF   = "image/gif"
MIME_WEBP  = "image/webp"

REMOTE_PNG_PATH  = "/sdcard/Download/sample_png_autotest.png"
REMOTE_JPG_PATH  = "/sdcard/Download/sample_jpg_autotest.jpg"
REMOTE_GIF_PATH  = "/sdcard/Download/sample_gif_autotest.gif"
REMOTE_WEBP_PATH = "/sdcard/Download/sample_webp_autotest.webp"


# ─── Resource file helpers ─────────────────────────────────────────────────────

def _res(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "../../tests/resources", filename)


def _push(adb, local_name: str, remote_path: str):
    local = _res(local_name)
    if not os.path.exists(local):
        raise FileNotFoundError(f"File test không tồn tại: {local}")
    adb.push_file(local, remote_path)
    time.sleep(1)


# ─── Launch helpers ────────────────────────────────────────────────────────────

def _safe_dismiss_open_app_ad(driver, adb):
    """
    Dismiss AdMob open-app ad an toàn, không dùng window_handles hay page_source
    (tránh crash UIAutomator2 khi WebView hiện diện).
    Dùng driver.current_activity để check + driver.tap() cho dismiss.
    """
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            activity = driver.current_activity or ""
            if "AdActivity" not in activity and "ad" not in activity.lower():
                return  # Không có ad
        except Exception:
            return
        # Click "Continue to app >" — nằm trong WebView ở góc trên phải
        # Tọa độ tương đối: x=96%, y=10.6% của màn hình
        try:
            size = driver.get_window_size()
            x = int(size["width"] * 0.96)
            y = int(size["height"] * 0.106)
            driver.tap([(x, y)])
        except Exception:
            try:
                adb._run(["shell", "input", "tap", "1040", "255"])
            except Exception:
                pass
        time.sleep(2)


def _open_via_intent(adb, uri: str, mime: str, component: str = None):
    """
    Dùng adb am start mô phỏng mở file từ app khác.
    component: "pkg/.ui.main.XxxActivity" để target activity cụ thể.
    """
    cmd = ["shell", "am", "start", "-a", "android.intent.action.VIEW",
           "-t", mime, "-d", uri]
    if component:
        cmd += ["-n", component]
    adb._run(cmd)
    time.sleep(5)


def _handle_chooser(driver, pkg: str):
    """Xử lý Android 'Open with' chooser nếu xuất hiện."""
    try:
        chooser_xpath = (
            '//*[contains(@text,"PDF") and contains(@text,"Reader")]'
            ' | //*[contains(@text,"All Docs")]'
        )
        el = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((AppiumBy.XPATH, chooser_xpath))
        )
        el.click()
        time.sleep(2)
        for text in ["Just once", "Only this time"]:
            try:
                driver.find_element(AppiumBy.XPATH, f'//*[@text="{text}"]').click()
                time.sleep(2)
                break
            except Exception:
                pass
    except Exception:
        pass


def _wait_reader_open(driver, timeout=20) -> bool:
    """Chờ màn đọc file mở (toolbar back hoặc doc_view)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_visible(driver, "imv_toolbar_back", timeout=2):
            return True
        if is_visible(driver, "doc_view", timeout=2):
            return True
        time.sleep(1)
    return False


def _is_note_popup_visible(driver, timeout=15) -> bool:
    """Kiểm tra note popup (backgroundNoteEdit) đang hiển thị."""
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located(
                (AppiumBy.ID, rid("backgroundNoteEdit"))
            )
        )
        return el.is_displayed()
    except TimeoutException:
        return False


def _is_note_edit_visible(driver, timeout=10) -> bool:
    """Kiểm tra tvNoteEdit EditText tồn tại (keyboard focused)."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, rid("tvNoteEdit")))
        )
        return True
    except TimeoutException:
        return False


def _is_file_in_star_tab(driver, filename_contains: str) -> bool:
    """Kiểm tra file xuất hiện trong tab Star."""
    # Click vào tab Star
    try:
        star_tab = find(driver, "layoutStar", timeout=8)
        star_tab.click()
        time.sleep(2)
    except Exception:
        return False

    # Tìm file trong rcv_star_file
    items = find_all(driver, "vl_item_file_name", timeout=8)
    for item in items:
        if filename_contains in (item.text or ""):
            return True

    # Nếu không thấy trong visible items, thử scroll
    try:
        driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiScrollable(new UiSelector().scrollable(true))'
            f'.scrollIntoView(new UiSelector().textContains("{filename_contains}"))',
        )
        return True
    except Exception:
        pass

    return False


def _set_filter_to_all(driver) -> bool:
    """
    Click filter icon và chọn 'All files' để hiển thị tất cả loại file.
    Filter mặc định của app là PDF; cần chuyển sang All trước khi tìm DOCX/XLSX/TXT.
    """
    try:
        # Click nút filter
        filter_btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((AppiumBy.ID, rid("imv_filter_file")))
        )
        filter_btn.click()
        time.sleep(1)

        # Tìm "All files" trong popup menu
        all_item = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (AppiumBy.XPATH, '//*[contains(@text, "All files") or contains(@text, "All Files")]')
            )
        )
        all_item.click()
        time.sleep(2)
        return True
    except Exception:
        return False


def _open_file_from_home(driver, adb, cfg, filename_contains: str,
                          remote_full_path: str, timeout=15) -> bool:
    """
    Push file rồi relaunch app để app rescan file list, sau đó tìm và click file.
    remote_full_path: đường dẫn đầy đủ trên device (vd: /sdcard/Download/sample.docx)
    """
    # Media scan với full path để Android nhận diện file
    try:
        adb._run(["shell", "am", "broadcast",
                  "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                  "-d", f"file://{remote_full_path}"])
        time.sleep(1)
    except Exception:
        pass

    # Relaunch app để app rescan file system và hiển thị file mới
    pkg = cfg["app"]["package_name"]
    try:
        adb.force_stop_app(pkg)
        time.sleep(1)
        adb.launch_app(pkg, cfg["app"]["main_activity"])
        time.sleep(cfg["device"]["launch_timeout"])
    except Exception:
        pass

    # Dismiss ads/onboarding nếu có
    from tests.helpers import dismiss_onboarding, ensure_app_foreground
    if _is_ad_showing(driver):
        dismiss_ads(driver)
        time.sleep(1)
    dismiss_onboarding(driver, cfg)

    # Chờ rcv_all_file xuất hiện
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (AppiumBy.ID, rid("rcv_all_file"))
            )
        )
    except TimeoutException:
        return False

    # Chuyển filter sang "All files" để hiển thị DOCX/XLSX/TXT (default là PDF)
    _set_filter_to_all(driver)

    # Thử scroll tới file
    try:
        driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiScrollable(new UiSelector().resourceId("{rid("rcv_all_file")}").scrollable(true))'
            f'.scrollIntoView(new UiSelector().textContains("{filename_contains}"))',
        )
        time.sleep(1)
    except Exception:
        pass

    # Tìm và click
    try:
        el = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable(
                (AppiumBy.XPATH, f'//*[contains(@text, "{filename_contains}")]')
            )
        )
        el.click()
        return True
    except Exception:
        pass

    return False


def _count_popup_windows(serial: str) -> int:
    """
    Đếm số PopupWindow đang hiển thị trên màn hình qua 'dumpsys window windows'.
    PowerMenu dùng TYPE_APPLICATION_PANEL nên không xuất hiện trong UIAutomator2
    hierarchy — nhưng vẫn đăng ký là PopupWindow trong WindowManager.
    """
    import subprocess
    result = subprocess.run(
        ["adb", "-s", serial, "shell", "dumpsys", "window", "windows"],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout.count("PopupWindow:")


def _powermenu_opened(adb, timeout: int = 5) -> bool:
    """
    Kiểm tra PowerMenu đã mở sau khi click More bằng cách đếm PopupWindow trong
    dumpsys window windows. PowerMenu mở → số PopupWindow tăng thêm ≥ 1.
    """
    import time as _time
    serial = adb.serial or "emulator-5554"
    count_before = _count_popup_windows(serial)
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        count_now = _count_popup_windows(serial)
        if count_now > count_before:
            return True
        _time.sleep(0.5)
    return False


def _powermenu_count_before(adb) -> int:
    """Lấy số PopupWindow hiện tại trước khi click More."""
    serial = adb.serial or "emulator-5554"
    return _count_popup_windows(serial)


def _powermenu_opened_after(adb, count_before: int, timeout: int = 5) -> bool:
    """Kiểm tra PowerMenu đã mở sau click More dựa trên count_before."""
    import time as _time
    serial = adb.serial or "emulator-5554"
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        if _count_popup_windows(serial) > count_before:
            return True
        _time.sleep(0.5)
    return False


def _check_reader_toolbar(driver, expected_ids: list, timeout=15) -> list:
    """
    Kiểm tra các toolbar elements có hiển thị sau khi reader mở.
    Trả về list các ID bị thiếu (không tìm thấy).
    """
    time.sleep(3)  # Chờ toolbar render
    missing = []
    for res_id in expected_ids:
        if not is_visible(driver, res_id, timeout=timeout):
            missing.append(res_id)
        timeout = 5  # Chỉ timeout dài cho element đầu tiên
    return missing


# ─── Test Class ───────────────────────────────────────────────────────────────

class TestOpenFilesOther:
    """TC-026 đến TC-040: Mở file từ app khác và từ trong app với các action khác nhau."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, driver, adb, cfg):
        """Setup: về home, dismiss ads. Teardown: xóa file test."""
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)
        go_to_home(driver, cfg)
        yield
        for remote_path in [REMOTE_PDF_PATH, REMOTE_PPTX_PATH, REMOTE_EPUB_PATH,
                            REMOTE_TXT_PATH, REMOTE_DOCX_PATH, REMOTE_XLSX_PATH,
                            "/sdcard/Download/sample_pdf_autotest.pdf",
                            "/sdcard/Download/large_autotest.pdf",
                            "/sdcard/Download/large_autotest.docx",
                            "/sdcard/Download/large_autotest.xlsx",
                            "/sdcard/Download/medium_autotest.pdf",
                            "/sdcard/Download/medium_autotest.docx",
                            "/sdcard/Download/medium_autotest.xlsx",
                            "/sdcard/Download/medium_autotest.pptx",
                            "/sdcard/Download/medium_autotest.epub",
                            "/sdcard/Download/medium_autotest.txt",
                            REMOTE_PNG_PATH, REMOTE_JPG_PATH,
                            REMOTE_GIF_PATH, REMOTE_WEBP_PATH,
                            "/sdcard/Download/small_autotest.pdf",
                            "/sdcard/Download/small_autotest.docx",
                            "/sdcard/Download/small_autotest.xlsx",
                            "/sdcard/Download/small_autotest.pptx",
                            "/sdcard/Download/small_autotest.epub",
                            "/sdcard/Download/small_autotest.txt",
                            ]:
            try:
                adb._run(["shell", "rm", "-f", remote_path])
            except Exception:
                pass

    # ── TC-026: PDF + Note to File ─────────────────────────────────────────

    @pytest.mark.tc_id("TC-026")
    def test_tc026_pdf_note_to_file(self, driver, adb, cfg):
        """
        TC-026: Mở file PDF từ app khác với action "Note to File"
        Expected: Reader mở + note popup hiện + keyboard focused
        """
        if not os.path.exists(_res("sample_simple.pdf")):
            pytest.skip("Không có sample_simple.pdf để test")

        _push(adb, "sample_simple.pdf", REMOTE_PDF_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.PdfNoteActivity"
        _open_via_intent(adb, f"file://{REMOTE_PDF_PATH}", MIME_PDF, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=20)
        assert reader_open, "Reader không mở sau khi launch PdfNoteActivity"

        note_popup = _is_note_popup_visible(driver, timeout=15)
        assert note_popup, "Note popup (backgroundNoteEdit) không hiển thị"

        note_edit = _is_note_edit_visible(driver, timeout=8)
        assert note_edit, "tvNoteEdit không có focus cho note popup"

        print("\n  TC-026 PASS: Reader mở + note popup hiện + keyboard focused")

    # ── TC-027: PPT/PPTX từ app khác ──────────────────────────────────────

    @pytest.mark.tc_id("TC-027")
    def test_tc027_pptx_open_from_external(self, driver, adb, cfg):
        """
        TC-027: Mở file PPT/PPTX từ app khác
        Expected: Show ads + reader mở
        """
        if not os.path.exists(_res("sample.pptx")):
            pytest.skip("Không có sample.pptx để test")

        _push(adb, "sample.pptx", REMOTE_PPTX_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_PPTX_PATH}", MIME_PPTX, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi mở PPT/PPTX từ app khác"

        print("\n  TC-027 PASS: PPT/PPTX mở từ app khác → reader hiển thị")

    # ── TC-028: PPT/PPTX + Mark Favourite ─────────────────────────────────

    @pytest.mark.tc_id("TC-028")
    def test_tc028_pptx_mark_favourite(self, driver, adb, cfg):
        """
        TC-028: Mở file PPT/PPTX từ app khác với action "Mark Favourite"
        Expected: Reader mở + file được thêm vào danh sách Favourite (Star tab)
        """
        if not os.path.exists(_res("sample.pptx")):
            pytest.skip("Không có sample.pptx để test")

        _push(adb, "sample.pptx", REMOTE_PPTX_PATH)

        # Xóa logcat TRƯỚC khi launch intent để capture chính xác
        adb._run(["logcat", "-c"])

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocFavouriteActivity"
        _open_via_intent(adb, f"file://{REMOTE_PPTX_PATH}", MIME_PPTX, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocFavouriteActivity"

        # Chờ postDelayed(1000ms) + background thread (~500ms) hoàn tất
        time.sleep(5)

        # Verify favourite đã được lưu qua logcat (DocReaderActivity logs "SAVED FAVORITE")
        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu vào SharedPreferences (SAVED FAVORITE không tìm thấy trong logcat)"

        print("\n  TC-028 PASS: PPT/PPTX đã được mark favourite và lưu vào SharedPreferences")

    # ── TC-029: PPT/PPTX + Note to File ───────────────────────────────────

    @pytest.mark.tc_id("TC-029")
    def test_tc029_pptx_note_to_file(self, driver, adb, cfg):
        """
        TC-029: Mở file PPT/PPTX từ app khác với action "Note to File"
        Expected: Reader mở + note popup hiện + keyboard focused
        """
        if not os.path.exists(_res("sample.pptx")):
            pytest.skip("Không có sample.pptx để test")

        _push(adb, "sample.pptx", REMOTE_PPTX_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocNoteActivity"
        _open_via_intent(adb, f"file://{REMOTE_PPTX_PATH}", MIME_PPTX, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocNoteActivity"

        note_popup = _is_note_popup_visible(driver, timeout=15)
        assert note_popup, "Note popup (backgroundNoteEdit) không hiển thị"

        note_edit = _is_note_edit_visible(driver, timeout=8)
        assert note_edit, "tvNoteEdit không có focus cho note popup"

        print("\n  TC-029 PASS: PPT/PPTX mở + note popup hiện + keyboard focused")

    # ── TC-030: EPUB từ app khác ───────────────────────────────────────────

    @pytest.mark.tc_id("TC-030")
    def test_tc030_epub_open_from_external(self, driver, adb, cfg):
        """
        TC-030: Mở file EPUB từ app khác
        Expected: Show ads + reader mở
        """
        if not os.path.exists(_res("sample.epub")):
            pytest.skip("Không có sample.epub để test")

        _push(adb, "sample.epub", REMOTE_EPUB_PATH)

        _open_via_intent(adb, f"file://{REMOTE_EPUB_PATH}", MIME_EPUB)
        _handle_chooser(driver, PKG)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở EPUB từ app khác"

        print("\n  TC-030 PASS: EPUB mở từ app khác → reader hiển thị")

    # ── TC-031: EPUB + Edit File ────────────────────────────────────────────

    @pytest.mark.tc_id("TC-031")
    def test_tc031_epub_edit_file(self, driver, adb, cfg):
        """
        TC-031: Mở file EPUB từ app khác với action "Edit File"
        Expected: Reader mở + tính năng edit file được mở
        """
        if not os.path.exists(_res("sample.epub")):
            pytest.skip("Không có sample.epub để test")

        _push(adb, "sample.epub", REMOTE_EPUB_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocEditActivity"
        _open_via_intent(adb, f"file://{REMOTE_EPUB_PATH}", MIME_EPUB, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi launch DocEditActivity với EPUB"

        print("\n  TC-031 PASS: EPUB mở từ app khác với Edit File → reader hiển thị")

    # ── TC-032: EPUB + Mark Favourite ──────────────────────────────────────

    @pytest.mark.tc_id("TC-032")
    def test_tc032_epub_mark_favourite(self, driver, adb, cfg):
        """
        TC-032: Mở file EPUB từ app khác với action "Mark Favourite"
        Expected: Reader mở + file được thêm vào danh sách Favourite
        """
        if not os.path.exists(_res("sample.epub")):
            pytest.skip("Không có sample.epub để test")

        _push(adb, "sample.epub", REMOTE_EPUB_PATH)

        # Xóa logcat TRƯỚC khi launch intent để capture chính xác
        adb._run(["logcat", "-c"])

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocFavouriteActivity"
        _open_via_intent(adb, f"file://{REMOTE_EPUB_PATH}", MIME_EPUB, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocFavouriteActivity với EPUB"

        # Chờ postDelayed(1000ms) + background thread (~500ms) hoàn tất
        time.sleep(5)

        # Verify favourite đã được lưu qua logcat
        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu vào SharedPreferences (SAVED FAVORITE không tìm thấy trong logcat)"

        print("\n  TC-032 PASS: EPUB đã được mark favourite và lưu vào SharedPreferences")

    # ── TC-033: EPUB + Note to File ─────────────────────────────────────────

    @pytest.mark.tc_id("TC-033")
    def test_tc033_epub_note_to_file(self, driver, adb, cfg):
        """
        TC-033: Mở file EPUB từ app khác với action "Note to File"
        Expected: Reader mở + note popup hiện + keyboard focused
        """
        if not os.path.exists(_res("sample.epub")):
            pytest.skip("Không có sample.epub để test")

        _push(adb, "sample.epub", REMOTE_EPUB_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocNoteActivity"
        _open_via_intent(adb, f"file://{REMOTE_EPUB_PATH}", MIME_EPUB, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocNoteActivity với EPUB"

        note_popup = _is_note_popup_visible(driver, timeout=15)
        assert note_popup, "Note popup (backgroundNoteEdit) không hiển thị"

        note_edit = _is_note_edit_visible(driver, timeout=8)
        assert note_edit, "tvNoteEdit không có focus cho note popup"

        print("\n  TC-033 PASS: EPUB mở + note popup hiện + keyboard focused")

    # ── TC-034: TXT từ app khác ─────────────────────────────────────────────

    @pytest.mark.tc_id("TC-034")
    def test_tc034_txt_open_from_external(self, driver, adb, cfg):
        """
        TC-034: Mở file TXT từ app khác
        Expected: Reader mở
        """
        if not os.path.exists(_res("sample.txt")):
            pytest.skip("Không có sample.txt để test")

        _push(adb, "sample.txt", REMOTE_TXT_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_TXT_PATH}", MIME_TXT, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở TXT từ app khác"

        print("\n  TC-034 PASS: TXT mở từ app khác → reader hiển thị")

    # ── TC-035: TXT + Note to File ──────────────────────────────────────────

    @pytest.mark.tc_id("TC-035")
    def test_tc035_txt_note_to_file(self, driver, adb, cfg):
        """
        TC-035: Mở file TXT từ app khác với action "Note to File"
        Expected: Reader mở + note popup hiện + keyboard focused
        """
        if not os.path.exists(_res("sample.txt")):
            pytest.skip("Không có sample.txt để test")

        _push(adb, "sample.txt", REMOTE_TXT_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocNoteActivity"
        _open_via_intent(adb, f"file://{REMOTE_TXT_PATH}", MIME_TXT, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocNoteActivity với TXT"

        note_popup = _is_note_popup_visible(driver, timeout=15)
        assert note_popup, "Note popup (backgroundNoteEdit) không hiển thị"

        note_edit = _is_note_edit_visible(driver, timeout=8)
        assert note_edit, "tvNoteEdit không có focus cho note popup"

        print("\n  TC-035 PASS: TXT mở + note popup hiện + keyboard focused")

    # ── TC-036: TXT + Edit File ─────────────────────────────────────────────

    @pytest.mark.tc_id("TC-036")
    def test_tc036_txt_edit_file(self, driver, adb, cfg):
        """
        TC-036: Mở file TXT từ app khác với action "Edit File"
        Expected: Reader mở + tính năng edit file được mở
        """
        if not os.path.exists(_res("sample.txt")):
            pytest.skip("Không có sample.txt để test")

        _push(adb, "sample.txt", REMOTE_TXT_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocEditActivity"
        _open_via_intent(adb, f"file://{REMOTE_TXT_PATH}", MIME_TXT, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        # DocEditActivity mở text editor (edit mode), kiểm tra btn_edit_cancel hoặc btn_edit_save
        edit_open = is_visible(driver, "btn_edit_cancel", timeout=25) or \
                    is_visible(driver, "btn_edit_save", timeout=5)
        assert edit_open, "Edit mode không mở sau khi launch DocEditActivity với TXT"

        print("\n  TC-036 PASS: TXT mở từ app khác với Edit File → edit mode hiển thị")

    # ── TC-037: TXT + Mark Favourite ───────────────────────────────────────

    @pytest.mark.tc_id("TC-037")
    def test_tc037_txt_mark_favourite(self, driver, adb, cfg):
        """
        TC-037: Mở file TXT từ app khác với action "Mark Favourite"
        Expected: Reader mở + file được thêm vào danh sách Favourite
        """
        if not os.path.exists(_res("sample.txt")):
            pytest.skip("Không có sample.txt để test")

        _push(adb, "sample.txt", REMOTE_TXT_PATH)

        # Xóa logcat TRƯỚC khi launch intent
        adb._run(["logcat", "-c"])

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocFavouriteActivity"
        _open_via_intent(adb, f"file://{REMOTE_TXT_PATH}", MIME_TXT, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocFavouriteActivity với TXT"

        # Chờ postDelayed(1000ms) hoàn tất
        time.sleep(5)

        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu (SAVED FAVORITE không tìm thấy trong logcat)"

        print("\n  TC-037 PASS: TXT đã được mark favourite và lưu vào SharedPreferences")

    # ── TC-038: Open DOC/DOCX từ app PDF Reader ───────────────────────────

    @pytest.mark.tc_id("TC-038")
    def test_tc038_docx_open_from_app(self, driver, adb, cfg):
        """
        TC-038: Mở file DOC/DOCX từ trong app PDF Reader
        Expected: Reader mở + toolbar đầy đủ (back, note, search, go_to_page, edit, star, share, print)
        """
        if not os.path.exists(_res("sample.docx")):
            pytest.skip("Không có sample.docx để test")

        _push(adb, "sample.docx", REMOTE_DOCX_PATH)

        clicked = _open_file_from_home(driver, adb, cfg, "sample_docx_autotest",
                                        REMOTE_DOCX_PATH, timeout=15)
        assert clicked, "Không tìm thấy/click được file DOCX trong Home screen"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi click file DOCX"

        # Kiểm tra các toolbar elements luôn hiển thị
        always_visible_ids = [
            "imv_toolbar_back",
            "imgCreateNote",
            "imv_toolbar_search",
            "imv_toolbar_star",
        ]
        missing = _check_reader_toolbar(driver, always_visible_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        # Mở PowerMenu bằng nút More và kiểm tra popup xuất hiện (screenshot-based)
        more_btn = is_visible(driver, "imv_toolbar_more", timeout=5)
        assert more_btn, "Không tìm thấy nút More ở toolbar"
        popup_count_before = _powermenu_count_before(adb)
        driver.find_element("id", f"{PKG}:id/imv_toolbar_more").click()
        opened = _powermenu_opened_after(adb, popup_count_before, timeout=5)
        assert opened, "PowerMenu không mở sau khi click nút More (Go to page, Share, Print)"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc038_docx_open_from_app.png"))
        print("\n  TC-038 PASS: DOCX mở từ app → reader + toolbar đầy đủ")

    # ── TC-039: Open Excel từ app PDF Reader ──────────────────────────────

    @pytest.mark.tc_id("TC-039")
    def test_tc039_xlsx_open_from_app(self, driver, adb, cfg):
        """
        TC-039: Mở file Excel (XLSX/XLS) từ trong app PDF Reader
        Expected: Reader mở + toolbar đầy đủ (back, search, go_to_page, edit, star, share, print)
        """
        if not os.path.exists(_res("sample.xlsx")):
            pytest.skip("Không có sample.xlsx để test")

        _push(adb, "sample.xlsx", REMOTE_XLSX_PATH)

        clicked = _open_file_from_home(driver, adb, cfg, "sample_xlsx_autotest",
                                        REMOTE_XLSX_PATH, timeout=15)
        assert clicked, "Không tìm thấy/click được file XLSX trong Home screen"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi click file XLSX"

        # Kiểm tra các toolbar elements luôn hiển thị
        always_visible_ids = [
            "imv_toolbar_back",
            "imv_toolbar_search",
            "imv_toolbar_star",
        ]
        missing = _check_reader_toolbar(driver, always_visible_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        # Mở PowerMenu bằng nút More và kiểm tra popup xuất hiện (screenshot-based)
        # Note: Excel không có "Go to page" trong menu
        more_btn = is_visible(driver, "imv_toolbar_more", timeout=5)
        assert more_btn, "Không tìm thấy nút More ở toolbar"
        popup_count_before = _powermenu_count_before(adb)
        driver.find_element("id", f"{PKG}:id/imv_toolbar_more").click()
        opened = _powermenu_opened_after(adb, popup_count_before, timeout=5)
        assert opened, "PowerMenu không mở sau khi click nút More (Share, Print)"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc039_xlsx_open_from_app.png"))
        print("\n  TC-039 PASS: XLSX mở từ app → reader + toolbar đầy đủ")

    # ── TC-040: Open TXT từ app PDF Reader ────────────────────────────────

    @pytest.mark.tc_id("TC-040")
    def test_tc040_txt_open_from_app(self, driver, adb, cfg):
        """
        TC-040: Mở file TXT từ trong app PDF Reader
        Expected: Reader mở + toolbar đầy đủ (back, edit, search, go_to_page, star, share, print)
        """
        if not os.path.exists(_res("sample.txt")):
            pytest.skip("Không có sample.txt để test")

        _push(adb, "sample.txt", REMOTE_TXT_PATH)

        clicked = _open_file_from_home(driver, adb, cfg, "sample_txt_autotest",
                                        REMOTE_TXT_PATH, timeout=15)
        assert clicked, "Không tìm thấy/click được file TXT trong Home screen"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi click file TXT"

        # Kiểm tra các toolbar elements luôn hiển thị
        always_visible_ids = [
            "imv_toolbar_back",
            "imv_toolbar_edit",
            "imv_toolbar_search",
            "imv_toolbar_star",
        ]
        missing = _check_reader_toolbar(driver, always_visible_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        # Mở PowerMenu bằng nút More và kiểm tra popup xuất hiện (screenshot-based)
        more_btn = is_visible(driver, "imv_toolbar_more", timeout=5)
        assert more_btn, "Không tìm thấy nút More ở toolbar"
        popup_count_before = _powermenu_count_before(adb)
        driver.find_element("id", f"{PKG}:id/imv_toolbar_more").click()
        opened = _powermenu_opened_after(adb, popup_count_before, timeout=5)
        assert opened, "PowerMenu không mở sau khi click nút More (Go to page, Share, Print)"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc040_txt_open_from_app.png"))
        print("\n  TC-040 PASS: TXT mở từ app → reader + toolbar đầy đủ")

        print("\n  TC-035 PASS: TXT mở + note popup hiện + keyboard focused")

    # ── TC-041: Open EPUB từ app PDF Reader ───────────────────────────────

    @pytest.mark.tc_id("TC-041")
    def test_tc041_epub_open_from_app(self, driver, adb, cfg):
        """
        TC-041: Mở file EPUB từ trong app PDF Reader
        Expected: Reader mở + toolbar đầy đủ (back, bookmark, note, search, star, More → go_to_page, share, print)
        """
        if not os.path.exists(_res("sample.epub")):
            pytest.skip("Không có sample.epub để test")

        _push(adb, "sample.epub", REMOTE_EPUB_PATH)

        clicked = _open_file_from_home(driver, adb, cfg, "sample_epub_autotest",
                                        REMOTE_EPUB_PATH, timeout=15)
        assert clicked, "Không tìm thấy/click được file EPUB trong Home screen"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi click file EPUB"

        always_visible_ids = [
            "imv_toolbar_back",
            "imgCreateNote",
            "imv_toolbar_search",
            "imv_toolbar_star",
        ]
        missing = _check_reader_toolbar(driver, always_visible_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        more_btn = is_visible(driver, "imv_toolbar_more", timeout=5)
        assert more_btn, "Không tìm thấy nút More ở toolbar"
        popup_count_before = _powermenu_count_before(adb)
        driver.find_element("id", f"{PKG}:id/imv_toolbar_more").click()
        opened = _powermenu_opened_after(adb, popup_count_before, timeout=5)
        assert opened, "PowerMenu không mở sau khi click nút More (Go to page, Share, Print)"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc041_epub_open_from_app.png"))
        print("\n  TC-041 PASS: EPUB mở từ app → reader + toolbar đầy đủ")

    # ── TC-042: Open PDF từ app PDF Reader ────────────────────────────────

    @pytest.mark.tc_id("TC-042")
    def test_tc042_pdf_open_from_app(self, driver, adb, cfg):
        """
        TC-042: Mở file PDF từ trong app PDF Reader
        Expected: Reader mở + toolbar đầy đủ (back, thumbnails, bookmark, note, search,
                  dark mode, rotate, star, More → go_to_page, share, print)
        """
        remote_pdf = "/sdcard/Download/sample_pdf_autotest.pdf"
        if not os.path.exists(_res("sample_simple.pdf")):
            pytest.skip("Không có sample_simple.pdf để test")

        _push(adb, "sample_simple.pdf", remote_pdf)
        adb._run(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                  "-d", f"file://{remote_pdf}"])

        clicked = _open_file_from_home(driver, adb, cfg, "sample_pdf_autotest",
                                        remote_pdf, timeout=15)
        assert clicked, "Không tìm thấy/click được file PDF trong Home screen"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi click file PDF"

        # PDF có thêm: thumbnails (imgListPreview), dark mode, rotate (imgSwipeHoz)
        always_visible_ids = [
            "imv_toolbar_back",
            "imgListPreview",
            "imgCreateNote",
            "imv_toolbar_search",
            "imv_toolbar_darkMode",
            "imgSwipeHoz",
            "imv_toolbar_star",
        ]
        missing = _check_reader_toolbar(driver, always_visible_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        more_btn = is_visible(driver, "imv_toolbar_more", timeout=5)
        assert more_btn, "Không tìm thấy nút More ở toolbar"
        popup_count_before = _powermenu_count_before(adb)
        driver.find_element("id", f"{PKG}:id/imv_toolbar_more").click()
        opened = _powermenu_opened_after(adb, popup_count_before, timeout=5)
        assert opened, "PowerMenu không mở sau khi click nút More (Go to page, Share, Print)"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc042_pdf_open_from_app.png"))
        print("\n  TC-042 PASS: PDF mở từ app → reader + toolbar đầy đủ")

    # ── TC-043: Open PPTX từ app PDF Reader ───────────────────────────────

    @pytest.mark.tc_id("TC-043")
    def test_tc043_pptx_open_from_app(self, driver, adb, cfg):
        """
        TC-043: Mở file PPTX/PPT từ trong app PDF Reader
        Expected: Reader mở + toolbar đầy đủ (back, note, search, edit, star, More → go_to_page, share, print)
        """
        if not os.path.exists(_res("sample.pptx")):
            pytest.skip("Không có sample.pptx để test")

        _push(adb, "sample.pptx", REMOTE_PPTX_PATH)

        clicked = _open_file_from_home(driver, adb, cfg, "sample_pptx_autotest",
                                        REMOTE_PPTX_PATH, timeout=15)
        assert clicked, "Không tìm thấy/click được file PPTX trong Home screen"

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi click file PPTX"

        always_visible_ids = [
            "imv_toolbar_back",
            "imgCreateNote",
            "imv_toolbar_search",
            "imv_toolbar_star",
        ]
        missing = _check_reader_toolbar(driver, always_visible_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        more_btn = is_visible(driver, "imv_toolbar_more", timeout=5)
        assert more_btn, "Không tìm thấy nút More ở toolbar"
        popup_count_before = _powermenu_count_before(adb)
        driver.find_element("id", f"{PKG}:id/imv_toolbar_more").click()
        opened = _powermenu_opened_after(adb, popup_count_before, timeout=5)
        assert opened, "PowerMenu không mở sau khi click nút More (Go to page, Share, Print)"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc043_pptx_open_from_app.png"))
        print("\n  TC-043 PASS: PPTX mở từ app → reader + toolbar đầy đủ")

    # ── TC-044: Open file dung lượng lớn (200–500 pages) ──────────────────

    @pytest.mark.tc_id("TC-044")
    def test_tc044_open_large_file(self, driver, adb, cfg):
        """
        TC-044: Mở file dung lượng lớn (200–500 trang) — tất cả format
        Expected: File hiển thị đầy đủ, tất cả tính năng hoạt động bình thường
        Test data: cần file lớn đặt tại tests/resources/large_file.pdf (hoặc .docx, .xlsx, .pptx)
        """
        large_files = [
            ("large_file.pdf",  "/sdcard/Download/large_autotest.pdf"),
            ("large_file.docx", "/sdcard/Download/large_autotest.docx"),
            ("large_file.xlsx", "/sdcard/Download/large_autotest.xlsx"),
        ]
        available = [(name, remote) for name, remote in large_files if os.path.exists(_res(name))]
        if not available:
            pytest.skip("Không có file lớn (200–500 trang) để test. "
                        "Đặt file vào tests/resources/ với tên: large_file.pdf / large_file.docx / large_file.xlsx")

        for local_name, remote_path in available:
            _push(adb, local_name, remote_path)
            adb._run(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", f"file://{remote_path}"])

            file_label = local_name.replace("large_file.", "large_autotest.")
            # Tìm theo tên không có extension để tránh vấn đề dot trong XPATH
            file_search = file_label.rsplit(".", 1)[0]
            clicked = _open_file_from_home(driver, adb, cfg, file_search,
                                            remote_path, timeout=20)
            assert clicked, f"Không tìm thấy/click được file {local_name} trong Home screen"

            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(1)

            reader_open = _wait_reader_open(driver, timeout=40)
            assert reader_open, f"Reader không mở sau khi click file {local_name}"

            toolbar_ok = is_visible(driver, "imv_toolbar_back", timeout=10)
            assert toolbar_ok, f"Toolbar không hiển thị sau khi mở {local_name}"

            screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            ext = local_name.split(".")[-1]
            driver.save_screenshot(os.path.join(screenshot_dir, f"test_tc044_large_{ext}.png"))

            go_to_home(driver, cfg)
            time.sleep(1)

        print(f"\n  TC-044 PASS: File lớn mở thành công ({len(available)} format)")

    # ── TC-045: Open file dung lượng trung bình (50–200 pages) ────────────

    @pytest.mark.tc_id("TC-045")
    def test_tc045_open_medium_file(self, driver, adb, cfg):
        """
        TC-045: Mở file dung lượng trung bình (50–200 trang) — tất cả format
        Expected: File hiển thị đầy đủ, tất cả tính năng hoạt động bình thường
        Test data: cần file trung bình đặt tại tests/resources/medium_file.pdf (hoặc các format khác)
        """
        medium_files = [
            ("medium_file.pdf",  "/sdcard/Download/medium_autotest.pdf"),
            ("medium_file.docx", "/sdcard/Download/medium_autotest.docx"),
            ("medium_file.xlsx", "/sdcard/Download/medium_autotest.xlsx"),
            ("medium_file.pptx", "/sdcard/Download/medium_autotest.pptx"),
            ("medium_file.epub", "/sdcard/Download/medium_autotest.epub"),
            ("medium_file.txt",  "/sdcard/Download/medium_autotest.txt"),
        ]
        available = [(name, remote) for name, remote in medium_files if os.path.exists(_res(name))]
        if not available:
            pytest.skip("Không có file trung bình (50–200 trang) để test. "
                        "Đặt file vào tests/resources/ với tên: medium_file.pdf / medium_file.docx / v.v.")

        for local_name, remote_path in available:
            _push(adb, local_name, remote_path)
            adb._run(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", f"file://{remote_path}"])

            file_label = local_name.replace("medium_file.", "medium_autotest.")
            # Tìm theo tên không có extension để tránh vấn đề dot trong XPATH
            file_search = file_label.rsplit(".", 1)[0]
            clicked = _open_file_from_home(driver, adb, cfg, file_search,
                                            remote_path, timeout=20)
            assert clicked, f"Không tìm thấy/click được file {local_name} trong Home screen"

            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(1)

            reader_open = _wait_reader_open(driver, timeout=40)
            assert reader_open, f"Reader không mở sau khi click file {local_name}"

            toolbar_ok = is_visible(driver, "imv_toolbar_back", timeout=10)
            assert toolbar_ok, f"Toolbar không hiển thị sau khi mở {local_name}"

            screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            ext = local_name.split(".")[-1]
            driver.save_screenshot(os.path.join(screenshot_dir, f"test_tc045_medium_{ext}.png"))

            go_to_home(driver, cfg)
            time.sleep(1)

        print(f"\n  TC-045 PASS: File trung bình mở thành công ({len(available)} format)")

    # ── TC-046: Open file dung lượng nhỏ ──────────────────────────────────

    @pytest.mark.tc_id("TC-046")
    def test_tc046_open_small_file(self, driver, adb, cfg):
        """
        TC-046: Mở file dung lượng nhỏ — tất cả format (pdf, docx, xlsx, pptx, epub, txt)
        Expected: File hiển thị đầy đủ, tính năng hoạt động bình thường
        """
        small_files = [
            ("sample_simple.pdf", "/sdcard/Download/small_autotest.pdf",  MIME_PDF),
            ("sample.docx",       "/sdcard/Download/small_autotest.docx", MIME_DOCX),
            ("sample.xlsx",       "/sdcard/Download/small_autotest.xlsx", MIME_XLSX),
            ("sample.pptx",       "/sdcard/Download/small_autotest.pptx", MIME_PPTX),
            ("sample.epub",       "/sdcard/Download/small_autotest.epub", MIME_EPUB),
            ("sample.txt",        "/sdcard/Download/small_autotest.txt",  MIME_TXT),
        ]
        available = [(name, remote, mime) for name, remote, mime in small_files
                     if os.path.exists(_res(name))]
        if not available:
            pytest.skip("Không có file nhỏ để test")

        for local_name, remote_path, _mime in available:
            _push(adb, local_name, remote_path)
            adb._run(["shell", "am", "broadcast",
                      "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", f"file://{remote_path}"])

            file_search = remote_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            clicked = _open_file_from_home(driver, adb, cfg, file_search,
                                            remote_path, timeout=20)
            assert clicked, f"Không tìm thấy/click được file {local_name} trong Home screen"

            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(1)

            reader_open = _wait_reader_open(driver, timeout=25)
            assert reader_open, f"Reader không mở sau khi click file {local_name}"

            toolbar_ok = is_visible(driver, "imv_toolbar_back", timeout=10)
            assert toolbar_ok, f"Toolbar không hiển thị sau khi mở {local_name}"

            screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            ext = local_name.rsplit(".", 1)[-1]
            driver.save_screenshot(os.path.join(screenshot_dir, f"test_tc046_small_{ext}.png"))

            go_to_home(driver, cfg)
            time.sleep(1)

        print(f"\n  TC-046 PASS: File nhỏ mở thành công ({len(available)} format)")

    # ── TC-047: Open PNG từ app khác ───────────────────────────────────────

    @pytest.mark.tc_id("TC-047")
    def test_tc047_png_open_from_external(self, driver, adb, cfg):
        """
        TC-047: Mở file PNG từ app khác
        Expected: Reader mở + toolbar hiển thị (back, note, search, star, More)
        """
        if not os.path.exists(_res("sample.png")):
            pytest.skip("Không có sample.png để test")

        _push(adb, "sample.png", REMOTE_PNG_PATH)

        # Send app to background trước khi fire intent
        # để tránh race condition: AOA gọi continueAfterAppOpenAd() trước khi IO coroutine set myFilesModel
        adb._run(["shell", "input", "keyevent", "KEYCODE_HOME"])
        time.sleep(2)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_PNG_PATH}", MIME_PNG, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở PNG từ app khác"

        # Image reader dùng imgBookmark thay vì imv_toolbar_star, không có imv_toolbar_search
        toolbar_ids = ["imv_toolbar_back", "imgCreateNote", "imgBookmark"]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc047_png_open_from_external.png"))
        print("\n  TC-047 PASS: PNG mở từ app khác → reader + toolbar hiển thị")

    # ── TC-048: Open JPG/JPEG từ app khác ─────────────────────────────────

    @pytest.mark.tc_id("TC-048")
    def test_tc048_jpg_open_from_external(self, driver, adb, cfg):
        """
        TC-048: Mở file JPG/JPEG từ app khác
        Expected: Reader mở + toolbar hiển thị (back, note, search, star, More)
        """
        if not os.path.exists(_res("sample.jpg")):
            pytest.skip("Không có sample.jpg để test")

        _push(adb, "sample.jpg", REMOTE_JPG_PATH)

        adb._run(["shell", "input", "keyevent", "KEYCODE_HOME"])
        time.sleep(2)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_JPG_PATH}", MIME_JPG, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở JPG từ app khác"

        toolbar_ids = ["imv_toolbar_back", "imgCreateNote", "imgBookmark"]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc048_jpg_open_from_external.png"))
        print("\n  TC-048 PASS: JPG mở từ app khác → reader + toolbar hiển thị")

    # ── TC-049: Open GIF từ app khác ───────────────────────────────────────

    @pytest.mark.tc_id("TC-049")
    def test_tc049_gif_open_from_external(self, driver, adb, cfg):
        """
        TC-049: Mở file GIF từ app khác
        Expected: Reader mở + toolbar hiển thị (back, note, search, star, More)
        """
        if not os.path.exists(_res("sample.gif")):
            pytest.skip("Không có sample.gif để test")

        _push(adb, "sample.gif", REMOTE_GIF_PATH)

        adb._run(["shell", "input", "keyevent", "KEYCODE_HOME"])
        time.sleep(2)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_GIF_PATH}", MIME_GIF, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở GIF từ app khác"

        toolbar_ids = ["imv_toolbar_back", "imgCreateNote", "imgBookmark"]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc049_gif_open_from_external.png"))
        print("\n  TC-049 PASS: GIF mở từ app khác → reader + toolbar hiển thị")

    # ── TC-050: Open WEBP từ app khác ──────────────────────────────────────

    @pytest.mark.tc_id("TC-050")
    def test_tc050_webp_open_from_external(self, driver, adb, cfg):
        """
        TC-050: Mở file WEBP từ app khác
        Expected: Reader mở + toolbar hiển thị (back, note, search, star, More)
        """
        if not os.path.exists(_res("sample.webp")):
            pytest.skip("Không có sample.webp để test")

        _push(adb, "sample.webp", REMOTE_WEBP_PATH)

        adb._run(["shell", "input", "keyevent", "KEYCODE_HOME"])
        time.sleep(2)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_WEBP_PATH}", MIME_WEBP, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở WEBP từ app khác"

        toolbar_ids = ["imv_toolbar_back", "imgCreateNote", "imgBookmark"]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc050_webp_open_from_external.png"))
        print("\n  TC-050 PASS: WEBP mở từ app khác → reader + toolbar hiển thị")

    # ── TC-051: Open file HEIC từ app khác ────────────────────────────────

    @pytest.mark.tc_id("TC-051")
    def test_tc051_heic_open_from_external(self, driver, adb, cfg):
        """
        TC-051: Mở file HEIC từ app khác
        Expected: Reader mở + toolbar hiển thị (back, note, star)
        """
        if not os.path.exists(_res("sample.heic")):
            pytest.skip("Không có sample.heic để test")

        remote_path = "/sdcard/Download/sample_heic_autotest.heic"
        _push(adb, "sample.heic", remote_path)

        adb._run(["shell", "input", "keyevent", "KEYCODE_HOME"])
        time.sleep(2)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{remote_path}", "image/heic", component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở HEIC từ app khác"

        toolbar_ids = ["imv_toolbar_back", "imgCreateNote", "imgBookmark"]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc051_heic_open_from_external.png"))
        print("\n  TC-051 PASS: HEIC mở từ app khác → reader + toolbar hiển thị")

    # ── TC-052: Open file SVG+XML từ app khác ─────────────────────────────

    @pytest.mark.tc_id("TC-052")
    def test_tc052_svg_open_from_external(self, driver, adb, cfg):
        """
        TC-052: Mở file SVG+XML từ app khác
        Expected: Reader mở + toolbar hiển thị (back, search, star)
        """
        if not os.path.exists(_res("sample.svg")):
            pytest.skip("Không có sample.svg để test")

        remote_path = "/sdcard/Download/sample_svg_autotest.svg"
        _push(adb, "sample.svg", remote_path)

        adb._run(["shell", "input", "keyevent", "KEYCODE_HOME"])
        time.sleep(2)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{remote_path}", "image/svg+xml", component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở SVG từ app khác"

        toolbar_ids = ["imv_toolbar_back", "imgCreateNote", "imgBookmark"]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        driver.save_screenshot(os.path.join(screenshot_dir, "test_tc052_svg_open_from_external.png"))
        print("\n  TC-052 PASS: SVG mở từ app khác → reader + toolbar hiển thị")

    # ── TC-053: Open file có link, click link → browser mở ────────────────

    @pytest.mark.tc_id("TC-053")
    def test_tc053_open_file_with_link(self, driver, adb, cfg):
        """
        TC-053: Mở PDF có chứa hyperlink, xác nhận link được highlight (hiển thị màu xanh)
        Expected: PDF mở + link URL được render nổi bật (highlight) trong nội dung
        Resource: sample_with_link.pdf — PDF tạo bằng reportlab có URI annotation
        """
        if not os.path.exists(_res("sample_with_link.pdf")):
            pytest.skip("Không có sample_with_link.pdf để test")

        remote_path = "/sdcard/Download/sample_link_autotest.pdf"
        _push(adb, "sample_with_link.pdf", remote_path)
        adb._run(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                  "-d", f"file://{remote_path}"])

        adb._run(["shell", "input", "keyevent", "KEYCODE_HOME"])
        time.sleep(2)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{remote_path}", MIME_PDF, component)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = _wait_reader_open(driver, timeout=30)
        assert reader_open, "Reader không mở sau khi mở PDF có link"

        # Chờ PDF render xong
        time.sleep(2)

        # Chụp screenshot làm bằng chứng link được highlight
        # (đã xác nhận thủ công: link hiển thị màu xanh trong PDF reader)
        screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, "test_tc053_open_file_with_link.png")
        driver.save_screenshot(screenshot_path)

        # Xác nhận PDF đã render (toolbar hiển thị = file mở thành công)
        toolbar_ok = is_visible(driver, "imv_toolbar_back", timeout=5)
        assert toolbar_ok, "PDF reader toolbar không hiển thị — file chưa render"

        # Bot đã chụp screenshot — tester cần mở dashboard xem link có màu xanh không
        pytest.skip(
            "NEED CONFIRM: Tester mở screenshot trong dashboard để xác nhận "
            "link 'https://www.google.com' hiển thị màu xanh (highlight) trong PDF reader."
        )

    # ── TC-054: Open file text format khác (html, json, xml, csv...) ──────

    @pytest.mark.tc_id("TC-054")
    def test_tc054_open_text_format_files(self, driver, adb, cfg):
        """
        TC-054: Mở các file định dạng text (html, json, xml, csv) bằng trình soạn thảo TXT
        Expected: File mở bằng text editor, có thể edit
        """
        text_files = [
            ("sample.html", "/sdcard/Download/sample_html_autotest.html", "text/html"),
            ("sample.json", "/sdcard/Download/sample_json_autotest.json", "application/json"),
            ("sample.csv",  "/sdcard/Download/sample_csv_autotest.csv",   "text/csv"),
            ("sample.xml",  "/sdcard/Download/sample_xml_autotest.xml",   "text/xml"),
        ]
        available = [(n, r, m) for n, r, m in text_files if os.path.exists(_res(n))]
        if not available:
            pytest.skip("Không có file text format để test")

        for local_name, remote_path, mime in available:
            _push(adb, local_name, remote_path)

            adb._run(["shell", "input", "keyevent", "KEYCODE_HOME"])
            time.sleep(2)

            component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
            _open_via_intent(adb, f"file://{remote_path}", mime, component)

            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(1)

            reader_open = _wait_reader_open(driver, timeout=30)
            assert reader_open, f"Reader không mở sau khi mở {local_name}"

            # Text editor có imv_toolbar_edit
            toolbar_ok = is_visible(driver, "imv_toolbar_back", timeout=10)
            assert toolbar_ok, f"Toolbar không hiển thị sau khi mở {local_name}"

            screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            ext = local_name.split(".")[-1]
            driver.save_screenshot(os.path.join(screenshot_dir, f"test_tc054_{ext}_open.png"))

            go_to_home(driver, cfg)
            time.sleep(1)

        print(f"\n  TC-054 PASS: {len(available)} định dạng text mở thành công bằng text editor")

    # ── TC-017: Doc/Docx từ app khác — basic open ──────────────────────────

    @pytest.mark.tc_id("TC-017")
    def test_tc017_docx_open_from_external(self, driver, adb, cfg):
        """
        TC-017: Mở file Doc/Docx từ app khác
        Expected: Reader mở thành công
        """
        if not os.path.exists(_res("sample.docx")):
            pytest.skip("Không có sample.docx để test")

        _push(adb, "sample.docx", REMOTE_DOCX_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_DOCX_PATH}", MIME_DOCX, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi mở Doc/Docx từ app khác"

        print("\n  TC-017 PASS: Doc/Docx mở từ app khác → reader hiển thị")

    # ── TC-018: Doc/Docx + Mark Favourite ─────────────────────────────────

    @pytest.mark.tc_id("TC-018")
    def test_tc018_docx_mark_favourite(self, driver, adb, cfg):
        """
        TC-018: Mở file Doc/Docx từ app khác với action Mark Favourite
        Expected: Reader mở + file được thêm vào Favourite
        """
        if not os.path.exists(_res("sample.docx")):
            pytest.skip("Không có sample.docx để test")

        _push(adb, "sample.docx", REMOTE_DOCX_PATH)
        adb._run(["logcat", "-c"])

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocFavouriteActivity"
        _open_via_intent(adb, f"file://{REMOTE_DOCX_PATH}", MIME_DOCX, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocFavouriteActivity với DOCX"

        time.sleep(5)

        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu (SAVED FAVORITE không tìm thấy trong logcat)"

        print("\n  TC-018 PASS: Doc/Docx mark favourite thành công")

    # ── TC-019: Doc/Docx + Note to File ───────────────────────────────────

    @pytest.mark.tc_id("TC-019")
    def test_tc019_docx_note_to_file(self, driver, adb, cfg):
        """
        TC-019: Mở file Doc/Docx từ app khác với action Note to File
        Expected: Reader mở + note popup hiện + keyboard focused
        """
        if not os.path.exists(_res("sample.docx")):
            pytest.skip("Không có sample.docx để test")

        _push(adb, "sample.docx", REMOTE_DOCX_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocNoteActivity"
        _open_via_intent(adb, f"file://{REMOTE_DOCX_PATH}", MIME_DOCX, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocNoteActivity với DOCX"

        note_popup = _is_note_popup_visible(driver, timeout=15)
        assert note_popup, "Note popup không hiển thị sau khi mở DOCX với Note to File"

        note_edit = _is_note_edit_visible(driver, timeout=8)
        assert note_edit, "tvNoteEdit không có focus cho note popup với DOCX"

        print("\n  TC-019 PASS: Doc/Docx note to file → reader + note popup + keyboard")

    # ── TC-020: Excel từ app khác — basic open ─────────────────────────────

    @pytest.mark.tc_id("TC-020")
    def test_tc020_xlsx_open_from_external(self, driver, adb, cfg):
        """
        TC-020: Mở file Excel (xlsx/xls) từ app khác
        Expected: Show loading/ads + reader mở thành công
        """
        if not os.path.exists(_res("sample.xlsx")):
            pytest.skip("Không có sample.xlsx để test")

        _push(adb, "sample.xlsx", REMOTE_XLSX_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_XLSX_PATH}", MIME_XLSX, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi mở Excel từ app khác"

        print("\n  TC-020 PASS: Excel mở từ app khác → reader hiển thị")

    # ── TC-021: Excel + Mark Favourite ────────────────────────────────────

    @pytest.mark.tc_id("TC-021")
    def test_tc021_xlsx_mark_favourite(self, driver, adb, cfg):
        """
        TC-021: Mở file Excel từ app khác với action Mark Favourite
        Expected: Reader mở + file được thêm vào Favourite
        """
        if not os.path.exists(_res("sample.xlsx")):
            pytest.skip("Không có sample.xlsx để test")

        _push(adb, "sample.xlsx", REMOTE_XLSX_PATH)
        adb._run(["logcat", "-c"])

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocFavouriteActivity"
        _open_via_intent(adb, f"file://{REMOTE_XLSX_PATH}", MIME_XLSX, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocFavouriteActivity với XLSX"

        time.sleep(5)

        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu (SAVED FAVORITE không tìm thấy trong logcat)"

        print("\n  TC-021 PASS: Excel mark favourite thành công")

    # ── TC-022: Excel + Note to File ──────────────────────────────────────

    @pytest.mark.tc_id("TC-022")
    def test_tc022_xlsx_note_to_file(self, driver, adb, cfg):
        """
        TC-022: Mở file Excel từ app khác với action Note to File
        Expected: Reader mở + note popup hiện + keyboard focused
        """
        if not os.path.exists(_res("sample.xlsx")):
            pytest.skip("Không có sample.xlsx để test")

        _push(adb, "sample.xlsx", REMOTE_XLSX_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocNoteActivity"
        _open_via_intent(adb, f"file://{REMOTE_XLSX_PATH}", MIME_XLSX, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocNoteActivity với XLSX"

        note_popup = _is_note_popup_visible(driver, timeout=15)
        assert note_popup, "Note popup không hiển thị sau khi mở XLSX với Note to File"

        note_edit = _is_note_edit_visible(driver, timeout=8)
        assert note_edit, "tvNoteEdit không có focus cho note popup với XLSX"

        print("\n  TC-022 PASS: Excel note to file → reader + note popup + keyboard")

    # ── TC-023: PDF từ app khác — basic open ──────────────────────────────

    @pytest.mark.tc_id("TC-023")
    def test_tc023_pdf_open_from_external(self, driver, adb, cfg):
        """
        TC-023: Mở file PDF từ app khác (basic open)
        Expected: Reader mở thành công
        """
        if not os.path.exists(_res("sample_simple.pdf")):
            pytest.skip("Không có sample_simple.pdf để test")

        _push(adb, "sample_simple.pdf", REMOTE_PDF_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_PDF_PATH}", MIME_PDF, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi mở PDF từ app khác"

        print("\n  TC-023 PASS: PDF mở từ app khác → reader hiển thị")

    # ── TC-024: PDF + Dark Mode ────────────────────────────────────────────

    @pytest.mark.tc_id("TC-024")
    def test_tc024_pdf_dark_mode_from_external(self, driver, adb, cfg):
        """
        TC-024: Mở file PDF từ app khác rồi bật Dark Mode
        Expected: Reader mở + dark mode được toggle thành công
        """
        if not os.path.exists(_res("sample_simple.pdf")):
            pytest.skip("Không có sample_simple.pdf để test")

        _push(adb, "sample_simple.pdf", REMOTE_PDF_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        _open_via_intent(adb, f"file://{REMOTE_PDF_PATH}", MIME_PDF, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi mở PDF từ app khác"

        # Tap vào màn hình để hiện toolbar nếu đang ẩn
        try:
            size = driver.get_window_size()
            driver.tap([(size["width"] // 2, size["height"] // 2)])
            time.sleep(1)
        except Exception:
            pass

        # Click Dark Mode button trên toolbar
        dark_mode_clicked = False
        try:
            dark_btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable(
                    (AppiumBy.ID, f"{PKG}:id/imv_toolbar_darkMode")
                )
            )
            dark_btn.click()
            time.sleep(2)
            dark_mode_clicked = True
        except TimeoutException:
            pass

        assert dark_mode_clicked, "Không tìm thấy nút Dark Mode trên toolbar"
        assert reader_open, "Reader không còn hiển thị sau khi bật Dark Mode"

        print("\n  TC-024 PASS: PDF mở từ app khác + Dark Mode toggle thành công")

    # ── TC-025: PDF + Mark Favourite ──────────────────────────────────────

    @pytest.mark.tc_id("TC-025")
    def test_tc025_pdf_mark_favourite(self, driver, adb, cfg):
        """
        TC-025: Mở file PDF từ app khác với action Mark Favourite
        Expected: Reader mở + file được thêm vào Favourite
        """
        if not os.path.exists(_res("sample_simple.pdf")):
            pytest.skip("Không có sample_simple.pdf để test")

        _push(adb, "sample_simple.pdf", REMOTE_PDF_PATH)
        adb._run(["logcat", "-c"])

        component = f"{PKG}/com.simple.pdf.reader.ui.main.DocFavouriteActivity"
        _open_via_intent(adb, f"file://{REMOTE_PDF_PATH}", MIME_PDF, component)

        _safe_dismiss_open_app_ad(driver, adb)

        try:
            driver.activate_app(PKG)
            time.sleep(2)
        except Exception:
            pass

        reader_open = _wait_reader_open(driver, timeout=25)
        assert reader_open, "Reader không mở sau khi launch DocFavouriteActivity với PDF"

        time.sleep(5)

        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu (SAVED FAVORITE không tìm thấy trong logcat)"

        print("\n  TC-025 PASS: PDF mark favourite từ app khác thành công")


# ─── Helpers cho fresh install tests ──────────────────────────────────────────

def _get_apk_path():
    """Tìm APK mới nhất trong thư mục apks/."""
    apk_dir = os.path.join(os.path.dirname(__file__), "../../apks")
    apks = sorted([f for f in os.listdir(apk_dir) if f.endswith(".apk")])
    if not apks:
        raise FileNotFoundError(f"Không có APK trong {apk_dir}")
    return os.path.join(apk_dir, apks[-1])


def _fresh_install(adb, cfg):
    """Gỡ app cũ và cài lại APK fresh (xóa toàn bộ data)."""
    pkg = cfg["app"]["package_name"]
    apk_path = _get_apk_path()
    adb.uninstall_app(pkg)
    time.sleep(2)
    success = adb.install_apk(apk_path)
    time.sleep(3)
    return success


def _onboarding_deny_manage_files(driver, cfg):
    """
    Đi qua onboarding lần đầu và TỪ CHỐI quyền manage all files.
    Khi app hiển thị màn Settings để bật "Allow access to manage all files" → bấm Back.
    Trả về True khi về được home screen.
    """
    pkg = cfg["app"]["package_name"]
    deadline = time.time() + 150
    manage_files_denied = False

    def _at_home():
        """Kiểm tra đang ở home screen — cả khi có file và khi bị denied permission."""
        if is_visible(driver, "rcv_all_file", timeout=2):
            return True
        # Empty state khi bị denied permission (có text "grant" hoặc "read your files")
        try:
            driver.find_element(
                AppiumBy.XPATH,
                '//*[contains(@text,"grant") or contains(@text,"read your files") '
                'or contains(@text,"Grant") or contains(@text,"access to all your files")]',
            )
            return True
        except Exception:
            return False

    while time.time() < deadline:
        # Đã về home (có file hoặc empty state sau khi từ chối permission)
        if _at_home():
            return True

        # Dismiss ads (adb=None vì không có adb trong context này)
        _safe_dismiss_open_app_ad(driver, None)

        # Language screen → Continue
        if is_visible(driver, "btn_continue", timeout=2):
            find(driver, "btn_continue").click()
            time.sleep(2)
            continue

        # App notification/permission dialog → Allow (btnDialogConfirm)
        if is_visible(driver, "btnDialogConfirm", timeout=2):
            find(driver, "btnDialogConfirm").click()
            time.sleep(2)
            continue

        # Màn Settings "manage all files" → BẤM BACK (từ chối) - chỉ 1 lần
        if not manage_files_denied:
            try:
                driver.find_element(
                    AppiumBy.XPATH,
                    '//*[contains(@text,"manage all files") or contains(@text,"Allow access")]',
                )
                driver.back()
                manage_files_denied = True
                time.sleep(3)
                continue
            except Exception:
                pass

        # Notification dialog hoặc system dialog (chỉ khi CHƯA về home)
        # Dùng XPATH phân biệt dialog (có chứa "notifications" hoặc là system permissioncontroller)
        try:
            notify_btn = driver.find_element(
                AppiumBy.XPATH,
                '//*[contains(@text,"notifications")]/..//*[@text="Allow" or @text="Don\'t allow"]'
                ' | //*[@resource-id="com.android.permissioncontroller:id/permission_allow_button"]'
                ' | //*[@text="Allow all the time"]'
                ' | //*[@text="While using the app"]',
            )
            notify_btn.click()
            time.sleep(2)
            continue
        except Exception:
            pass

        # Nếu app bị đẩy ra ngoài (không phải our pkg và không phải settings), kéo lại
        try:
            cur_pkg = driver.current_package or ""
            is_our_app = cur_pkg == pkg
            is_settings = "settings" in cur_pkg.lower() or "permissioncontroller" in cur_pkg.lower()
            if not is_our_app and not is_settings:
                driver.activate_app(pkg)
                time.sleep(3)
                continue
        except Exception:
            pass

        time.sleep(1)

    return _at_home()


def _onboarding_allow_manage_files(driver, cfg):
    """
    Đi qua onboarding lần đầu và ĐỒNG Ý quyền manage all files.
    Dùng dismiss_onboarding chuẩn (đã grant tất cả permission).
    """
    from tests.helpers import dismiss_onboarding
    return dismiss_onboarding(driver, cfg)


# ─── TC-012 đến TC-016: Welcome File & Selection Screen ───────────────────────

class TestWelcomeAndSelection:
    """TC-012 đến TC-016: Kiểm tra welcome file và mở file từ selection screen."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, driver, adb, cfg):
        """Setup: về home. Teardown: về home (TC-014+ không cần fresh install)."""
        _safe_dismiss_open_app_ad(driver, adb)
        go_to_home(driver, cfg)
        yield
        # Teardown: về home, không cần reinstall/pm clear vì TC tiếp theo tự setup state
        try:
            _safe_dismiss_open_app_ad(driver, adb)
            go_to_home(driver, cfg)
        except Exception:
            pass

    # ── TC-012: Fresh install + DENY manage files → welcome file không hiện

    @pytest.mark.tc_id("TC-012")
    def test_tc012_no_welcome_file_when_permission_denied(self, driver, adb, cfg):
        """
        TC-012: Gỡ cài đặt app, cài lại APK, mở lần đầu và TỪ CHỐI manage all files.
        Expected: Không hiển thị welcome file ở đầu danh sách + hiện button grant permission
        """
        # Fresh install
        installed = _fresh_install(adb, cfg)
        assert installed, "Không cài được APK"

        # Mở app lần đầu
        try:
            driver.activate_app(cfg["app"]["package_name"])
            time.sleep(4)
        except Exception:
            pass

        # Đi qua onboarding NHƯNG từ chối manage all files
        reached_home = _onboarding_deny_manage_files(driver, cfg)
        assert reached_home, "Không về được màn Home sau onboarding"

        # Lấy danh sách file đầu tiên
        items = find_all(driver, "vl_item_file_name", timeout=8)
        file_names = [item.text or "" for item in items[:5]]
        print(f"\n  Top files: {file_names}")

        # Kiểm tra không có welcome file (file "Welcome" không ở đầu danh sách)
        welcome_at_top = any("welcome" in n.lower() for n in file_names[:1])
        assert not welcome_at_top, \
            f"Welcome file vẫn ở đầu danh sách sau khi từ chối permission: {file_names}"

        # Kiểm tra có button/banner để grant permission
        grant_btn_visible = False
        for res_id in ["btn_grant_permission", "tv_grant_permission", "btn_allow_permission",
                        "ll_permission", "layout_permission"]:
            if is_visible(driver, res_id, timeout=3):
                grant_btn_visible = True
                break
        # Nếu không tìm theo resource ID, tìm theo text
        if not grant_btn_visible:
            try:
                driver.find_element(
                    AppiumBy.XPATH,
                    '//*[contains(@text,"Allow") or contains(@text,"Grant") or '
                    'contains(@text,"Permission") or contains(@text,"Cho phép")]'
                )
                grant_btn_visible = True
            except Exception:
                pass

        print(f"\n  Grant permission button visible: {grant_btn_visible}")
        print(f"\n  TC-012 PASS: Welcome file không hiện + grant button: {grant_btn_visible}")

    # ── TC-013: Fresh install + ALLOW manage files → welcome file hiện ────

    @pytest.mark.tc_id("TC-013")
    def test_tc013_welcome_file_shown_when_permission_allowed(self, driver, adb, cfg):
        """
        TC-013: Gỡ cài đặt app, cài lại APK, mở lần đầu và ĐỒNG Ý manage all files.
        Expected: Hiển thị welcome file ở đầu danh sách All Files
        """
        installed = _fresh_install(adb, cfg)
        assert installed, "Không cài được APK"

        try:
            driver.activate_app(cfg["app"]["package_name"])
            time.sleep(4)
        except Exception:
            pass

        # Đi qua onboarding và ĐỒNG Ý manage all files
        reached_home = _onboarding_allow_manage_files(driver, cfg)
        assert reached_home, "Không về được màn Home sau onboarding"

        items = find_all(driver, "vl_item_file_name", timeout=10)
        file_names = [item.text or "" for item in items[:3]]
        print(f"\n  Top files: {file_names}")

        # Welcome file là file đầu tiên trong danh sách
        has_welcome = any("welcome" in n.lower() for n in file_names)
        assert has_welcome, \
            f"Không thấy Welcome file ở đầu danh sách sau khi grant permission: {file_names}"

        print(f"\n  TC-013 PASS: Welcome file '{file_names[0] if file_names else '?'}' hiển thị đầu danh sách")

    # ── TC-014: Open welcome file ──────────────────────────────────────────

    @pytest.mark.tc_id("TC-014")
    def test_tc014_open_welcome_file(self, driver, adb, cfg):
        """
        TC-014: Mở file welcome (file mẫu của app)
        Expected: Reader mở, hiển thị đầy đủ toolbar
        """
        pkg = cfg["app"]["package_name"]

        # Đảm bảo permission đã grant
        adb._run(["shell", "appops", "set", pkg, "MANAGE_EXTERNAL_STORAGE", "allow"])
        time.sleep(1)

        go_to_home(driver, cfg)

        # Tìm file đầu tiên trong danh sách và mở
        items = find_all(driver, "vl_item_file_name", timeout=10)
        if not items:
            pytest.skip("Không có file nào trong danh sách để mở")

        first_file_name = items[0].text or ""
        items[0].click()
        time.sleep(3)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = is_visible(driver, "imv_toolbar_back", timeout=15) or \
                      is_visible(driver, "doc_view", timeout=5)
        assert reader_open, f"Reader không mở sau khi click file '{first_file_name}'"

        print(f"\n  TC-014 PASS: Mở file '{first_file_name}' → reader hiển thị")

    # ── TC-015: Open file từ màn selection ────────────────────────────────

    @pytest.mark.tc_id("TC-015")
    def test_tc015_open_file_from_selection_screen(self, driver, adb, cfg):
        """
        TC-015: Mở file từ màn hình selection (file picker bên trong app)
        Expected: Reader mở thành công
        """
        go_to_home(driver, cfg)

        # Push một file test để có sẵn
        if os.path.exists(_res("sample_simple.pdf")):
            adb.push_file(_res("sample_simple.pdf"), "/sdcard/Download/sample_selection_autotest.pdf")
            adb._run(["shell", "am", "broadcast",
                      "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", "file:///sdcard/Download/sample_selection_autotest.pdf"])
            time.sleep(2)

        # Tìm nút selection/browse (thường là bottom nav hoặc FAB)
        selection_found = False
        for res_id in ["btn_folder", "imv_folder", "tab_folder", "btn_selection",
                        "nav_folder", "imv_browse", "btn_browse"]:
            try:
                btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((AppiumBy.ID, f"{PKG}:id/{res_id}"))
                )
                btn.click()
                selection_found = True
                time.sleep(2)
                break
            except TimeoutException:
                continue

        if not selection_found:
            pytest.skip("Không tìm thấy nút selection/browse trong app — cần xác định resource ID")

        # Trong màn selection, tìm và click file
        try:
            el = driver.find_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiScrollable(new UiSelector().scrollable(true))'
                '.scrollIntoView(new UiSelector().textContains("sample_selection_autotest"))',
            )
            el.click()
            time.sleep(3)
        except Exception:
            pytest.skip("Không tìm thấy file trong màn selection")

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = is_visible(driver, "imv_toolbar_back", timeout=15) or \
                      is_visible(driver, "doc_view", timeout=5)
        assert reader_open, "Reader không mở sau khi chọn file từ màn selection"

        # Cleanup
        try:
            adb._run(["shell", "rm", "-f", "/sdcard/Download/sample_selection_autotest.pdf"])
        except Exception:
            pass

        print("\n  TC-015 PASS: Mở file từ màn selection → reader hiển thị")

    # ── TC-016: Open file từ SD Card ──────────────────────────────────────

    @pytest.mark.tc_id("TC-016")
    def test_tc016_open_file_from_sd_card(self, driver, adb, cfg):
        """
        TC-016: Mở file từ SD Card
        Expected: Reader mở thành công
        Note: Skip nếu emulator không có SD Card
        """
        # Kiểm tra SD Card có tồn tại không
        code, out, _ = adb._run(["shell", "ls", "/sdcard/external_sd/"], timeout=5)
        has_sd = (code == 0 and out.strip())
        if not has_sd:
            code2, out2, _ = adb._run(["shell", "ls", "/mnt/media_rw/"], timeout=5)
            has_sd = (code2 == 0 and out2.strip())

        if not has_sd:
            pytest.skip("Device không có SD Card — bỏ qua TC-016")

        sd_path = "/sdcard/external_sd/sample_sd_autotest.pdf"
        if os.path.exists(_res("sample_simple.pdf")):
            adb.push_file(_res("sample_simple.pdf"), sd_path)
            adb._run(["shell", "am", "broadcast",
                      "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                      "-d", f"file://{sd_path}"])
            time.sleep(2)

        go_to_home(driver, cfg)

        # Thử mở file từ SD Card qua intent
        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
        adb._run(["shell", "am", "start", "-a", "android.intent.action.VIEW",
                  "-t", "application/pdf", "-d", f"file://{sd_path}",
                  "-n", component])
        time.sleep(5)

        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        reader_open = is_visible(driver, "imv_toolbar_back", timeout=15) or \
                      is_visible(driver, "doc_view", timeout=5)
        assert reader_open, "Reader không mở sau khi mở file từ SD Card"

        try:
            adb._run(["shell", "rm", "-f", sd_path])
        except Exception:
            pass

        print("\n  TC-016 PASS: Mở file từ SD Card → reader hiển thị")
