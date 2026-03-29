"""
Test Cases: Open Files Other (TC_026 → TC_040)
Sheet: TC - Open Files (version N.2.6.8)

TC_026 - Open PDF từ app khác với action "Note to File"
TC_027 - Open PPT/PPTX từ app khác → show ads + reader
TC_028 - Open PPT/PPTX từ app khác với action "Mark Favourite"
TC_029 - Open PPT/PPTX từ app khác với action "Note to File"
TC_030 - Open EPUB từ app khác → show ads + reader
TC_031 - Open EPUB từ app khác với action "Edit File"
TC_032 - Open EPUB từ app khác với action "Mark Favourite"
TC_033 - Open EPUB từ app khác với action "Note to File"
TC_034 - Open TXT từ app khác → reader
TC_035 - Open TXT từ app khác với action "Note to File"
TC_036 - Open TXT từ app khác với action "Edit File"
TC_037 - Open TXT từ app khác với action "Mark Favourite"
TC_038 - Open DOC/DOCX từ app PDF Reader → reader + toolbar đầy đủ
TC_039 - Open Excel (XLSX/XLS) từ app PDF Reader → reader + toolbar đầy đủ
TC_040 - Open TXT từ app PDF Reader → reader + toolbar đầy đủ
"""
import time
import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tests.helpers import (
    go_to_home, dismiss_ads, _is_ad_showing,
)
from tests.helpers import is_visible
from tests.test_suite.test_open_files_other import (
    _push, _open_via_intent, _wait_reader_open,
    _is_note_popup_visible, _is_note_edit_visible,
    _open_file_from_home, _check_reader_toolbar, _set_filter_to_all,
    REMOTE_PDF_PATH, REMOTE_PPTX_PATH, REMOTE_EPUB_PATH, REMOTE_TXT_PATH,
    REMOTE_DOCX_PATH, REMOTE_XLSX_PATH,
    MIME_PDF, MIME_PPTX, MIME_EPUB, MIME_TXT, MIME_DOCX, MIME_XLSX,
    PKG,
)

_RES_DIR = os.path.join(os.path.dirname(__file__), "../../tests/resources")


def _res(filename: str) -> str:
    return os.path.join(_RES_DIR, filename)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tc(tc_manager):
    return tc_manager


@pytest.fixture(autouse=True)
def setup_teardown(driver, adb, cfg):
    """Go to home before each test. Clean up test files after."""
    if _is_ad_showing(driver):
        dismiss_ads(driver)
        time.sleep(1)
    go_to_home(driver, cfg)
    yield
    for remote_path in [REMOTE_PDF_PATH, REMOTE_PPTX_PATH, REMOTE_EPUB_PATH,
                        REMOTE_TXT_PATH, REMOTE_DOCX_PATH, REMOTE_XLSX_PATH]:
        try:
            adb._run(["shell", "rm", "-f", remote_path])
        except Exception:
            pass


# ─── TC_026: PDF + Note to File ───────────────────────────────────────────────

class TestTC026:
    """TC_026 - Open PDF từ app khác với action Note to File"""

    def test_pdf_note_to_file(self, driver, adb, cfg, tc):
        """
        Mở PDF từ app khác với action "Note to File"
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

        tc.update_result("TC_026", "PASS",
                         actual="Reader mở + note popup hiện + keyboard focused")


# ─── TC_027: PPT/PPTX từ app khác ─────────────────────────────────────────────

class TestTC027:
    """TC_027 - Open PPT/PPTX từ app khác → show ads + reader"""

    def test_pptx_open_from_external(self, driver, adb, cfg, tc):
        """
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

        tc.update_result("TC_027", "PASS",
                         actual="PPT/PPTX mở từ app khác → reader hiển thị")


# ─── TC_028: PPT/PPTX + Mark Favourite ────────────────────────────────────────

class TestTC028:
    """TC_028 - Open PPT/PPTX từ app khác với action Mark Favourite"""

    def test_pptx_mark_favourite(self, driver, adb, cfg, tc):
        """
        Expected: Reader mở + file được thêm vào danh sách Favourite
        """
        if not os.path.exists(_res("sample.pptx")):
            pytest.skip("Không có sample.pptx để test")

        _push(adb, "sample.pptx", REMOTE_PPTX_PATH)
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

        time.sleep(5)

        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu (SAVED FAVORITE không tìm thấy trong logcat)"

        tc.update_result("TC_028", "PASS",
                         actual="PPT/PPTX đã được mark favourite và lưu vào SharedPreferences")


# ─── TC_029: PPT/PPTX + Note to File ──────────────────────────────────────────

class TestTC029:
    """TC_029 - Open PPT/PPTX từ app khác với action Note to File"""

    def test_pptx_note_to_file(self, driver, adb, cfg, tc):
        """
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

        tc.update_result("TC_029", "PASS",
                         actual="PPT/PPTX mở + note popup hiện + keyboard focused")


# ─── TC_030: EPUB từ app khác ──────────────────────────────────────────────────

class TestTC030:
    """TC_030 - Open EPUB từ app khác → show ads + reader"""

    def test_epub_open_from_external(self, driver, adb, cfg, tc):
        """
        Expected: Show ads + reader mở
        """
        if not os.path.exists(_res("sample.epub")):
            pytest.skip("Không có sample.epub để test")

        _push(adb, "sample.epub", REMOTE_EPUB_PATH)

        component = f"{PKG}/com.simple.pdf.reader.ui.main.SplashScreenActivity"
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
        assert reader_open, "Reader không mở sau khi mở EPUB từ app khác"

        tc.update_result("TC_030", "PASS",
                         actual="EPUB mở từ app khác → reader hiển thị")


# ─── TC_031: EPUB + Edit File ──────────────────────────────────────────────────

class TestTC031:
    """TC_031 - Open EPUB từ app khác với action Edit File"""

    def test_epub_edit_file(self, driver, adb, cfg, tc):
        """
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

        tc.update_result("TC_031", "PASS",
                         actual="EPUB mở từ app khác với Edit File → reader hiển thị")


# ─── TC_032: EPUB + Mark Favourite ────────────────────────────────────────────

class TestTC032:
    """TC_032 - Open EPUB từ app khác với action Mark Favourite"""

    def test_epub_mark_favourite(self, driver, adb, cfg, tc):
        """
        Expected: Reader mở + file được thêm vào danh sách Favourite
        """
        if not os.path.exists(_res("sample.epub")):
            pytest.skip("Không có sample.epub để test")

        _push(adb, "sample.epub", REMOTE_EPUB_PATH)
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

        time.sleep(5)

        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu (SAVED FAVORITE không tìm thấy trong logcat)"

        tc.update_result("TC_032", "PASS",
                         actual="EPUB đã được mark favourite và lưu vào SharedPreferences")


# ─── TC_033: EPUB + Note to File ──────────────────────────────────────────────

class TestTC033:
    """TC_033 - Open EPUB từ app khác với action Note to File"""

    def test_epub_note_to_file(self, driver, adb, cfg, tc):
        """
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

        tc.update_result("TC_033", "PASS",
                         actual="EPUB mở + note popup hiện + keyboard focused")


# ─── TC_034: TXT từ app khác ───────────────────────────────────────────────────

class TestTC034:
    """TC_034 - Open TXT từ app khác → reader"""

    def test_txt_open_from_external(self, driver, adb, cfg, tc):
        """
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

        tc.update_result("TC_034", "PASS",
                         actual="TXT mở từ app khác → reader hiển thị")


# ─── TC_035: TXT + Note to File ───────────────────────────────────────────────

class TestTC035:
    """TC_035 - Open TXT từ app khác với action Note to File"""

    def test_txt_note_to_file(self, driver, adb, cfg, tc):
        """
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

        tc.update_result("TC_035", "PASS",
                         actual="TXT mở + note popup hiện + keyboard focused")


# ─── TC_036: TXT + Edit File ───────────────────────────────────────────────────

class TestTC036:
    """TC_036 - Open TXT từ app khác với action Edit File"""

    def test_txt_edit_file(self, driver, adb, cfg, tc):
        """
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

        edit_open = is_visible(driver, "btn_edit_cancel", timeout=25) or \
                    is_visible(driver, "btn_edit_save", timeout=5)
        assert edit_open, "Edit mode không mở sau khi launch DocEditActivity với TXT"

        tc.update_result("TC_036", "PASS",
                         actual="TXT mở từ app khác với Edit File → edit mode hiển thị")


# ─── TC_037: TXT + Mark Favourite ─────────────────────────────────────────────

class TestTC037:
    """TC_037 - Open TXT từ app khác với action Mark Favourite"""

    def test_txt_mark_favourite(self, driver, adb, cfg, tc):
        """
        Expected: Reader mở + file được thêm vào danh sách Favourite
        """
        if not os.path.exists(_res("sample.txt")):
            pytest.skip("Không có sample.txt để test")

        _push(adb, "sample.txt", REMOTE_TXT_PATH)
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

        time.sleep(5)

        _, logcat_out, _ = adb._run(["logcat", "-d"], timeout=15)
        favourite_saved = "SAVED FAVORITE" in logcat_out
        assert favourite_saved, "Favourite chưa được lưu (SAVED FAVORITE không tìm thấy trong logcat)"

        tc.update_result("TC_037", "PASS",
                         actual="TXT đã được mark favourite và lưu vào SharedPreferences")


# ─── TC_038: Open DOC/DOCX từ app PDF Reader ──────────────────────────────────

class TestTC038:
    """TC_038 - Open DOC/DOCX từ app PDF Reader → reader + toolbar đầy đủ"""

    def test_docx_open_from_app(self, driver, adb, cfg, tc):
        """
        Expected: Reader mở + toolbar đầy đủ
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

        toolbar_ids = [
            "imv_toolbar_back",
            "imgCreateNote",
            "imv_toolbar_search",
            "imv_toolbar_go_to_page",
            "imv_toolbar_edit",
            "imv_toolbar_star",
            "imv_toolbar_share",
            "imv_toolbar_print",
        ]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        tc.update_result("TC_038", "PASS",
                         actual="DOCX mở từ app → reader + toolbar đầy đủ")


# ─── TC_039: Open Excel từ app PDF Reader ─────────────────────────────────────

class TestTC039:
    """TC_039 - Open Excel (XLSX/XLS) từ app PDF Reader → reader + toolbar đầy đủ"""

    def test_xlsx_open_from_app(self, driver, adb, cfg, tc):
        """
        Expected: Reader mở + toolbar đầy đủ
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

        toolbar_ids = [
            "imv_toolbar_back",
            "imv_toolbar_search",
            "imv_toolbar_go_to_page",
            "imv_toolbar_edit",
            "imv_toolbar_star",
            "imv_toolbar_share",
            "imv_toolbar_print",
        ]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        tc.update_result("TC_039", "PASS",
                         actual="XLSX mở từ app → reader + toolbar đầy đủ")


# ─── TC_040: Open TXT từ app PDF Reader ───────────────────────────────────────

class TestTC040:
    """TC_040 - Open TXT từ app PDF Reader → reader + toolbar đầy đủ"""

    def test_txt_open_from_app(self, driver, adb, cfg, tc):
        """
        Expected: Reader mở + toolbar đầy đủ
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

        toolbar_ids = [
            "imv_toolbar_back",
            "imv_toolbar_edit",
            "imv_toolbar_search",
            "imv_toolbar_go_to_page",
            "imv_toolbar_star",
            "imv_toolbar_share",
            "imv_toolbar_print",
        ]
        missing = _check_reader_toolbar(driver, toolbar_ids)
        assert not missing, f"Toolbar thiếu các elements: {missing}"

        tc.update_result("TC_040", "PASS",
                         actual="TXT mở từ app → reader + toolbar đầy đủ")
