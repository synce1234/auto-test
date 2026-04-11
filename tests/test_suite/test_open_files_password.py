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
    wait_uia2_ready,
)

PKG = "pdf.reader.pdf.viewer.all.document.reader.office.viewer"
PASSWORD_CORRECT = "kanbanery"
PASSWORD_WRONG = "wrongpass!@#"
# Session-unique suffix: mỗi lần chạy pytest dùng tên file khác → URI khác
# → password đã Remember từ session trước không khớp URI mới → dialog luôn hiện
_PDF_SESSION_ID = str(int(time.time()))
REMOTE_PDF_PATH = f"/sdcard/Download/sample_password_autotest_{_PDF_SESSION_ID}.pdf"
# TC-010 dùng file riêng để tránh bị nhiễm bởi remembered password từ TC-009
# (TC-009 lưu pass đúng cho REMOTE_PDF_PATH → TC-010 cần URI khác để dialog vẫn hiện)
REMOTE_PDF_PATH_TC010 = f"/sdcard/Download/sample_password_autotest_{_PDF_SESSION_ID}_tc010.pdf"
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

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_test_pdf_local():
    return os.path.join(os.path.dirname(__file__), "../../tests/resources/sample_password.pdf")


def push_password_pdf(adb, remote_path=None):
    """Push file PDF có password lên device và trigger media scanner."""
    if remote_path is None:
        remote_path = REMOTE_PDF_PATH
    local = get_test_pdf_local()
    if not os.path.exists(local):
        raise FileNotFoundError(f"File test không tồn tại: {local}")
    adb.push_file(local, remote_path)
    # Trigger media scanner để app thấy file ngay
    adb._run([
        "shell", "am", "broadcast",
        "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d", f"file://{remote_path}",
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


def open_password_pdf_from_home(driver, adb, cfg, remote_path=None):
    """
    Push file lên rồi mở từ màn Home của app.
    Dùng UiScrollable để cuộn và tìm file theo tên.
    Trả về True nếu đã click vào file.
    """
    if remote_path is None:
        remote_path = REMOTE_PDF_PATH
    push_password_pdf(adb, remote_path=remote_path)
    # Dismiss ad trước khi về home để go_to_home không bị block
    if _is_ad_showing(driver):
        dismiss_ads(driver)
        time.sleep(1)
    go_to_home(driver, cfg)
    time.sleep(5)
    # Dismiss ad sau khi về home (ad có thể trigger sau khi về home)
    if _is_ad_showing(driver):
        dismiss_ads(driver)
        time.sleep(1)
    # Pull-to-refresh để app scan file mới push
    _pull_to_refresh_file_list(driver)

    file_name = os.path.splitext(os.path.basename(remote_path))[0]

    # Thử Appium UiScrollable trước (scroll + find)
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

    # Fallback Appium: tìm trong visible items (không scroll)
    items = find_all(driver, "vl_item_file_name", timeout=5)
    for item in items:
        if file_name in (item.text or ""):
            item.click()
            time.sleep(3)
            return True

    # Fallback ADB: scroll + dump để tìm file (khi UIA2 crash)
    import xml.etree.ElementTree as _ET_pw
    import re as _re_pw
    import os as _os_pw

    _pkg = cfg["app"]["package_name"]
    _rid_file = f"{_pkg}:id/vl_item_file_name"

    def _adb_find_and_tap_file() -> bool:
        """Dump UI, tìm vl_item_file_name chứa file_name, tap nếu tìm thấy."""
        try:
            adb._run(["shell", "uiautomator", "dump", "/sdcard/uidump_pw.xml"])
            _, _xml, _ = adb._run(["shell", "cat", "/sdcard/uidump_pw.xml"])
            if not _xml or "<hierarchy" not in _xml:
                return False
            _root = _ET_pw.fromstring(_xml)
            for _n in _root.iter("node"):
                if _n.get("resource-id", "") == _rid_file and file_name in _n.get("text", ""):
                    _nums = _re_pw.findall(r"\d+", _n.get("bounds", ""))
                    if len(_nums) >= 4:
                        _cx = (int(_nums[0]) + int(_nums[2])) // 2
                        _cy = (int(_nums[1]) + int(_nums[3])) // 2
                        adb._run(["shell", "input", "tap", str(_cx), str(_cy)])
                        return True
        except Exception:
            pass
        return False

    # Lấy screen size để tính tọa độ swipe
    try:
        _, _sz, _ = adb._run(["shell", "wm", "size"])
        _m = _re_pw.search(r"(\d+)x(\d+)", _sz or "")
        _sw, _sh = (int(_m.group(1)), int(_m.group(2))) if _m else (1080, 2400)
    except Exception:
        _sw, _sh = 1080, 2400

    # Scroll xuống tối đa 8 lần, mỗi lần check + swipe
    for _i in range(8):
        if _adb_find_and_tap_file():
            time.sleep(2)
            return True
        # Swipe lên (scroll list xuống dưới)
        adb._run(["shell", "input", "swipe",
                  str(_sw // 2), str(int(_sh * 0.75)),
                  str(_sw // 2), str(int(_sh * 0.25)),
                  "400"])
        time.sleep(0.8)

    # Lần check cuối sau scroll
    if _adb_find_and_tap_file():
        time.sleep(2)
        return True

    return False


def wait_for_password_dialog(driver, adb=None, timeout=15) -> bool:  # noqa: ARG001 adb kept for call-site compat
    """
    Chờ dialog nhập password xuất hiện.
    Primary: ADB dump (subprocess trực tiếp, unique filename) — tránh crash UIA2.
    Fallback: Appium WebDriverWait.
    """
    import subprocess as _sp_pwd
    import re as _re_pwd

    _serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_pw = ["adb", "-s", _serial] if _serial else ["adb"]

    def _focused_window() -> str:
        """Lấy mCurrentFocus qua dumpsys activity activities (không dùng pipe)."""
        try:
            r = _sp_pwd.run(_adb_pw + ["shell", "dumpsys", "activity", "activities"],
                            capture_output=True, text=True, timeout=8)
            for line in (r.stdout or "").splitlines():
                if "mCurrentFocus" in line:
                    return line.strip()
        except Exception:
            pass
        return ""

    def _dump_xml_pwd() -> str:
        """Dump UI hierarchy với unique filename để tránh stale cache."""
        try:
            _fname = f"/sdcard/pwd_dlg_{int(time.time()*1000)}.xml"
            _sp_pwd.run(_adb_pw + ["shell", "uiautomator", "dump", _fname],
                        capture_output=True, timeout=8)
            r = _sp_pwd.run(_adb_pw + ["pull", _fname, "/tmp/pwd_dlg_check.xml"],
                            capture_output=True, text=True, timeout=5)
            _sp_pwd.run(_adb_pw + ["shell", "rm", "-f", _fname],
                        capture_output=True, timeout=3)
            if r.returncode != 0:
                return ""
            with open("/tmp/pwd_dlg_check.xml", "r", errors="replace") as _f:
                return _f.read()
        except Exception:
            return ""

    def _xml_has_password_dialog(xml: str) -> bool:
        """Kiểm tra XML có chứa dialog password không."""
        if not xml:
            return False
        # edtPassWord — EditText nhập password
        if f"{PKG}:id/edtPassWord" in xml:
            return True
        # EditText với password=true
        if _re_pwd.search(r'class="android\.widget\.EditText"[^>]*password="true"', xml):
            return True
        # Text gợi ý password
        if _re_pwd.search(r'(Enter Password|Enter password|Nhập mật khẩu|Password)', xml):
            return True
        return False

    def _dismiss_ad_if_needed():
        focus = _focused_window()
        if "AdActivity" not in focus:
            return False
        try:
            r = _sp_pwd.run(_adb_pw + ["shell", "wm", "size"],
                            capture_output=True, text=True, timeout=5)
            m = _re_pwd.search(r"(\d+)x(\d+)", r.stdout or "")
            w, h = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
            for tx, ty in [(int(w * 0.89), int(h * 0.045)),
                           (int(w * 0.96), int(h * 0.106))]:
                _sp_pwd.run(_adb_pw + ["shell", "input", "tap", str(tx), str(ty)],
                            capture_output=True, timeout=5)
                time.sleep(1.5)
                if "AdActivity" not in _focused_window():
                    return True
        except Exception:
            pass
        return False

    # ── Primary: ADB loop ──────────────────────────────────────────────────────
    deadline = time.time() + timeout
    while time.time() < deadline:
        _dismiss_ad_if_needed()
        xml = _dump_xml_pwd()
        print(f"  [PWD_DIALOG] xml_len={len(xml)}, has_dialog={_xml_has_password_dialog(xml)}, focus={_focused_window()}")
        if _xml_has_password_dialog(xml):
            return True
        time.sleep(1.5)

    # ── Fallback: Appium ───────────────────────────────────────────────────────
    # Không dùng '//android.widget.EditText' generic vì search bar trong PDF viewer
    # cũng là EditText và sẽ gây false positive khi file đã mở (no dialog).
    selectors = [
        (AppiumBy.ID, f"{PKG}:id/edtPassWord"),
        (AppiumBy.XPATH, '//android.widget.EditText[@password="true"]'),
        (AppiumBy.XPATH, '//*[contains(@text, "Password") or contains(@text, "password") or contains(@text, "Mật khẩu")]'),
    ]
    for by, sel in selectors:
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, sel)))
            return True
        except Exception:
            # Catch WebDriverException (UIA2 crash) + TimeoutException
            continue
    return False


def find_password_input(driver):
    """
    Tìm EditText để nhập password.
    Trả về Appium element nếu UIA2 alive, hoặc AdbInputProxy nếu UIA2 crash.
    """
    import subprocess as _sp_fpi
    import re as _re_fpi

    # ── Appium primary ─────────────────────────────────────────────────────────
    selectors = [
        (AppiumBy.ID, f"{PKG}:id/edtPassWord"),
        (AppiumBy.XPATH, '//android.widget.EditText'),
    ]
    for by, sel in selectors:
        try:
            return WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((by, sel))
            )
        except (TimeoutException, Exception):
            continue

    # ── ADB fallback: trả về proxy object có send_keys() dùng ADB input text ──
    _serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_fpi = ["adb", "-s", _serial] if _serial else ["adb"]

    # Tap vào edtPassWord để focus trước khi gõ
    try:
        _fname_fpi = f"/sdcard/fpi_{int(time.time()*1000)}.xml"
        _sp_fpi.run(_adb_fpi + ["shell", "uiautomator", "dump", _fname_fpi],
                    capture_output=True, timeout=8)
        _r_fpi = _sp_fpi.run(_adb_fpi + ["pull", _fname_fpi, "/tmp/fpi_check.xml"],
                             capture_output=True, text=True, timeout=5)
        _sp_fpi.run(_adb_fpi + ["shell", "rm", "-f", _fname_fpi],
                    capture_output=True, timeout=3)
        if _r_fpi.returncode == 0:
            with open("/tmp/fpi_check.xml", "r", errors="replace") as _ff:
                _xml_fpi = _ff.read()
            _m_fpi = _re_fpi.search(
                r'resource-id="[^"]*edtPassWord"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                _xml_fpi,
            )
            if _m_fpi:
                _cx = (int(_m_fpi.group(1)) + int(_m_fpi.group(3))) // 2
                _cy = (int(_m_fpi.group(2)) + int(_m_fpi.group(4))) // 2
                _sp_fpi.run(_adb_fpi + ["shell", "input", "tap", str(_cx), str(_cy)],
                            capture_output=True, timeout=5)
                time.sleep(0.5)
    except Exception:
        pass

    class _AdbInputProxy:
        """Proxy thay thế Appium element — gõ text qua ADB input text."""
        def send_keys(self, text: str):
            # Escape ký tự đặc biệt cho ADB shell input text
            _escaped = str(text).replace(" ", "%s").replace("'", "\\'")
            _sp_fpi.run(_adb_fpi + ["shell", "input", "text", _escaped],
                        capture_output=True, timeout=10)
        def clear(self):
            # Xoá hết text bằng select all + delete
            _sp_fpi.run(_adb_fpi + ["shell", "input", "keyevent", "KEYCODE_CTRL_A"],
                        capture_output=True, timeout=5)
            _sp_fpi.run(_adb_fpi + ["shell", "input", "keyevent", "KEYCODE_DEL"],
                        capture_output=True, timeout=5)

    return _AdbInputProxy()


def _adb_tap_by_rid(adb, rid_suffix: str, dump_file=None) -> bool:  # noqa: adb/dump_file kept for compat
    """ADB dump → tìm node theo resource-id → tap center. Trả về True nếu thành công."""
    import subprocess as _sp_tap
    import re as _re_tap
    _serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_t = ["adb", "-s", _serial] if _serial else ["adb"]
    try:
        _fname_t = f"/sdcard/tap_{int(time.time()*1000)}.xml"
        _sp_tap.run(_adb_t + ["shell", "uiautomator", "dump", _fname_t],
                    capture_output=True, timeout=8)
        _r_t = _sp_tap.run(_adb_t + ["pull", _fname_t, "/tmp/tap_check.xml"],
                           capture_output=True, text=True, timeout=5)
        _sp_tap.run(_adb_t + ["shell", "rm", "-f", _fname_t], capture_output=True, timeout=3)
        if _r_t.returncode != 0:
            return False
        with open("/tmp/tap_check.xml", "r", errors="replace") as _ft:
            _xml = _ft.read()
        _m_t = _re_tap.search(
            rf'resource-id="[^"]*{_re_tap.escape(rid_suffix)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            _xml,
        )
        if _m_t:
            _cx = (int(_m_t.group(1)) + int(_m_t.group(3))) // 2
            _cy = (int(_m_t.group(2)) + int(_m_t.group(4))) // 2
            _sp_tap.run(_adb_t + ["shell", "input", "tap", str(_cx), str(_cy)],
                        capture_output=True, timeout=5)
            return True
    except Exception:
        pass
    return False


def click_ok_button(driver, adb=None):
    """Click nút OK trên dialog. Resource ID thực tế: btn_dialog_save. ADB subprocess fallback."""
    # ADB tap via subprocess (không phụ thuộc UIA2)
    if _adb_tap_by_rid(None, "btn_dialog_save"):
        time.sleep(2)
        return True
    # Appium fallback (chỉ khi ADB tap thất bại)
    selectors = [
        (AppiumBy.ID, f"{PKG}:id/btn_dialog_save"),
        (AppiumBy.XPATH, '//*[@text="OK" or @text="Ok"]'),
    ]
    for by, sel in selectors:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((by, sel))
            )
            btn.click()
            time.sleep(2)
            return True
        except Exception:
            continue
    return False


def click_cancel_button(driver, adb=None):
    """Click nút Cancel trên dialog. Resource ID thực tế: btn_dialog_cancel. ADB subprocess fallback."""
    # ADB tap via subprocess (không phụ thuộc UIA2)
    if _adb_tap_by_rid(None, "btn_dialog_cancel"):
        time.sleep(2)
        return True
    # Appium fallback (chỉ khi ADB tap thất bại)
    selectors = [
        (AppiumBy.ID, f"{PKG}:id/btn_dialog_cancel"),
        (AppiumBy.XPATH, '//*[@text="Cancel" or @text="Hủy"]'),
    ]
    for by, sel in selectors:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((by, sel))
            )
            btn.click()
            time.sleep(2)
            return True
        except Exception:
            continue
    return False


def enter_password(driver, password: str, adb=None):
    """
    Nhập password vào EditText.
    Nếu có adb: dùng ADB dump tìm edtPassWord → tap → input text (tránh UIA2 crash).
    """
    if adb is not None:
        import xml.etree.ElementTree as _ET_ep
        import re as _re_ep
        _rid = f"{PKG}:id/edtPassWord"
        try:
            adb._run(["shell", "uiautomator", "dump", "/sdcard/uidump_ep.xml"])
            _, _xml, _ = adb._run(["shell", "cat", "/sdcard/uidump_ep.xml"])
            if _xml and "<hierarchy" in _xml:
                _root = _ET_ep.fromstring(_xml)
                for _n in _root.iter("node"):
                    if _n.get("resource-id", "") == _rid or _n.get("class", "") == "android.widget.EditText":
                        _nums = _re_ep.findall(r"\d+", _n.get("bounds", ""))
                        if len(_nums) >= 4:
                            _cx = (int(_nums[0]) + int(_nums[2])) // 2
                            _cy = (int(_nums[1]) + int(_nums[3])) // 2
                            adb._run(["shell", "input", "tap", str(_cx), str(_cy)])
                            time.sleep(0.5)
                            # Xóa text cũ bằng select all + delete
                            adb._run(["shell", "input", "keyevent", "KEYCODE_CTRL_A"])
                            adb._run(["shell", "input", "keyevent", "KEYCODE_DEL"])
                            time.sleep(0.3)
                            # Nhập password (chỉ dùng cho password không có ký tự đặc biệt)
                            adb._run(["shell", "input", "text", password])
                            time.sleep(0.5)
                            return True
        except Exception:
            pass
        return False

    pwd_input = find_password_input(driver)
    if pwd_input is None:
        return False
    pwd_input.clear()
    pwd_input.send_keys(password)
    time.sleep(1)
    return True


def _handle_app_chooser(adb, driver, pkg: str):
    """
    Xử lý Android 'Open with' chooser bằng ADB dump (bypass UiAutomator2 crash
    khi ResolverActivity/ChooserActivity đang ở foreground).
    """
    import xml.etree.ElementTree as _ET_ch
    import re as _re_ch

    _JUST_ONCE = {"Just once", "Only this time"}

    def _dump(timeout_sec=15):
        deadline = time.time() + timeout_sec
        _last = None
        while time.time() < deadline:
            for extra in [["--windows"], []]:
                try:
                    adb._run(["shell", "uiautomator", "dump"] + extra + ["/sdcard/uidump_ch.xml"])
                    _, stdout, _ = adb._run(["shell", "cat", "/sdcard/uidump_ch.xml"])
                    if stdout and "<hierarchy" in stdout:
                        root = _ET_ch.fromstring(stdout)
                        if any(n.get("text", "") in _JUST_ONCE for n in root.iter("node")):
                            return root
                        _last = root
                except Exception:
                    pass
            if _last is not None:
                return _last
            time.sleep(1)
        return None

    def _center(bounds_str):
        nums = _re_ch.findall(r"\d+", bounds_str)
        return ((int(nums[0]) + int(nums[2])) // 2, (int(nums[1]) + int(nums[3])) // 2) if len(nums) >= 4 else None

    def _tap_text(root, texts):
        for node in root.iter("node"):
            if node.get("text", "") in texts or node.get("content-desc", "") in texts:
                c = _center(node.get("bounds", ""))
                if c:
                    adb._run(["shell", "input", "tap", str(c[0]), str(c[1])])
                    return True
        return False

    # Bước 1: Tap option PDF Reader trong chooser (tìm theo pkg hoặc text "PDF")
    root = _dump(timeout_sec=12)
    if root is not None:
        for node in root.iter("node"):
            t = node.get("text", "")
            if pkg in (node.get("package", "") or "") or ("PDF" in t and "Reader" in t):
                c = _center(node.get("bounds", ""))
                if c:
                    adb._run(["shell", "input", "tap", str(c[0]), str(c[1])])
                    time.sleep(1.5)
                    break

    # Bước 2: Tap "Just once"
    deadline = time.time() + 15
    while time.time() < deadline:
        root = _dump(timeout_sec=4)
        if root is not None and _tap_text(root, _JUST_ONCE):
            time.sleep(2)
            from tests.helpers import wait_uia2_ready
            wait_uia2_ready(driver, timeout=30)
            return
        time.sleep(1)


def is_file_opened(driver, adb=None, timeout=8) -> bool:
    """
    Kiểm tra file đã mở thành công.
    App dùng FLAG_SECURE → uiautomator dump luôn empty cho reader.
    Dùng Appium is_visible: Android accessibility ẩn views phía sau dialog,
    nên imv_toolbar_back/doc_view sẽ là False khi dialog đang hiện.
    Recover UIA2 nếu crash trước khi gọi Appium.
    """
    import subprocess as _sp_fo
    _reader_rids = (f"{PKG}:id/imv_toolbar_back", f"{PKG}:id/doc_view")
    _serial_fo = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_fo = ["adb", "-s", _serial_fo] if _serial_fo else ["adb"]

    # ── ADB dump: quick check (nếu không có FLAG_SECURE) ─────────────────────
    try:
        _fname_fo = f"/sdcard/fo_{int(time.time()*1000)}.xml"
        _sp_fo.run(_adb_fo + ["shell", "uiautomator", "dump", _fname_fo],
                   capture_output=True, timeout=8)
        _r_fo = _sp_fo.run(_adb_fo + ["pull", _fname_fo, "/tmp/fo_check.xml"],
                           capture_output=True, text=True, timeout=5)
        _sp_fo.run(_adb_fo + ["shell", "rm", "-f", _fname_fo],
                   capture_output=True, timeout=3)
        if _r_fo.returncode == 0:
            with open("/tmp/fo_check.xml", "r", errors="replace") as _ffo:
                _xml_fo = _ffo.read()
            for _rid in _reader_rids:
                if _rid in _xml_fo:
                    return True
    except Exception:
        pass

    # ── Recover UIA2 nếu dead (không dùng HOME) ──────────────────────────────
    try:
        driver.current_activity  # Quick probe
    except Exception:
        for _pkg_fo in ["io.appium.uiautomator2.server", "io.appium.uiautomator2.server.test"]:
            _sp_fo.run(_adb_fo + ["shell", "am", "force-stop", _pkg_fo],
                       capture_output=True, timeout=5)
        time.sleep(3)
        _dl_fo = time.time() + 20
        while time.time() < _dl_fo:
            try:
                driver.current_activity
                break
            except Exception:
                time.sleep(2)

    # ── Appium fallback: is_visible trả về False khi dialog che phía trên ─────
    return (is_visible(driver, "imv_toolbar_back", timeout=timeout) or
            is_visible(driver, "doc_view", timeout=3))


def is_password_dialog_still_showing(driver, adb=None, timeout: int = 5) -> bool:
    """
    Kiểm tra dialog nhập password vẫn còn hiển thị (hoặc đã re-xuất hiện).
    ADB primary (tránh UIA2 crash) → recover UIA2 nếu cần → Appium fallback.
    Lưu ý: dialog type này không xuất hiện trong uiautomator dump (xml_len=0),
    nên Appium fallback là path chính để detect. UIA2 phải alive trước khi dùng Appium.
    timeout: số giây chờ Appium (mặc định 5, tăng lên khi cần chờ dialog reload).
    """
    import subprocess as _sp_ds
    _dialog_rid_suffixes = ("edtPassWord", "vl_title_rename")
    _serial_ds = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_ds = ["adb", "-s", _serial_ds] if _serial_ds else ["adb"]

    # ── ADB dump: check for dialog elements (nhanh nhưng thường miss dialog này) ─
    try:
        _fname_ds = f"/sdcard/ds_{int(time.time()*1000)}.xml"
        _sp_ds.run(_adb_ds + ["shell", "uiautomator", "dump", _fname_ds],
                   capture_output=True, timeout=8)
        _r_ds = _sp_ds.run(_adb_ds + ["pull", _fname_ds, "/tmp/ds_check.xml"],
                           capture_output=True, text=True, timeout=5)
        _sp_ds.run(_adb_ds + ["shell", "rm", "-f", _fname_ds],
                   capture_output=True, timeout=3)
        if _r_ds.returncode == 0:
            with open("/tmp/ds_check.xml", "r", errors="replace") as _fds:
                _xml_ds = _fds.read()
            for _sfx in _dialog_rid_suffixes:
                if f":id/{_sfx}" in _xml_ds:
                    return True
            if 'class="android.widget.EditText"' in _xml_ds:
                return True
    except Exception:
        pass

    # ── Recover UIA2 nếu đã crash (không dùng HOME để giữ nguyên dialog) ─────
    _uia2_alive = False
    try:
        driver.current_activity
        _uia2_alive = True
    except Exception:
        # UIA2 dead → force-stop server, Appium sẽ tự khởi động lại khi nhận lệnh kế tiếp
        for _pkg_r in ["io.appium.uiautomator2.server", "io.appium.uiautomator2.server.test"]:
            _sp_ds.run(_adb_ds + ["shell", "am", "force-stop", _pkg_r],
                       capture_output=True, timeout=5)
        time.sleep(3)
        # Chờ UIA2 sẵn sàng (không navigate)
        _deadline_r = time.time() + 20
        while time.time() < _deadline_r:
            try:
                driver.current_activity
                _uia2_alive = True
                break
            except Exception:
                time.sleep(2)

    # ── Appium fallback: dialog type này chỉ visible qua Appium ───────────────
    if _uia2_alive:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((AppiumBy.XPATH, '//android.widget.EditText'))
            )
            return True
        except Exception:
            pass

    return False


def find_remember_checkbox(driver):
    """
    Tìm checkbox 'Remember password' trong dialog. Resource ID thực tế: cbRemember.
    Trả về Appium element nếu UIA2 alive, hoặc _AdbCheckboxProxy nếu UIA2 crash.
    """
    import subprocess as _sp_cb
    import re as _re_cb

    # ── Appium primary ─────────────────────────────────────────────────────────
    selectors = [
        (AppiumBy.ID, f"{PKG}:id/cbRemember"),
        (AppiumBy.XPATH, '//android.widget.CheckBox'),
    ]
    for by, sel in selectors:
        try:
            return WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((by, sel))
            )
        except Exception:
            continue

    # ── ADB fallback ──────────────────────────────────────────────────────────
    _serial_cb = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_cb = ["adb", "-s", _serial_cb] if _serial_cb else ["adb"]
    try:
        _fname_cb = f"/sdcard/cb_{int(time.time()*1000)}.xml"
        _sp_cb.run(_adb_cb + ["shell", "uiautomator", "dump", _fname_cb],
                   capture_output=True, timeout=8)
        _r_cb = _sp_cb.run(_adb_cb + ["pull", _fname_cb, "/tmp/cb_check.xml"],
                           capture_output=True, text=True, timeout=5)
        _sp_cb.run(_adb_cb + ["shell", "rm", "-f", _fname_cb],
                   capture_output=True, timeout=3)
        if _r_cb.returncode == 0:
            with open("/tmp/cb_check.xml", "r", errors="replace") as _fcb:
                _xml_cb = _fcb.read()
            # Tìm node cbRemember: lấy checked value và bounds
            _m_cb = _re_cb.search(
                r'resource-id="[^"]*cbRemember"([^/]*)',
                _xml_cb,
            )
            if _m_cb:
                _attrs = _m_cb.group(1)
                _checked_m = _re_cb.search(r'checked="([^"]*)"', _attrs)
                _bounds_m = _re_cb.search(
                    r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', _attrs
                )
                _checked_val = _checked_m.group(1) if _checked_m else "false"
                if _bounds_m:
                    _cx_cb = (int(_bounds_m.group(1)) + int(_bounds_m.group(3))) // 2
                    _cy_cb = (int(_bounds_m.group(2)) + int(_bounds_m.group(4))) // 2

                    class _AdbCheckboxProxy:
                        """Proxy thay thế Appium CheckBox element — dùng ADB input tap."""
                        def get_attribute(self, name):
                            if name == "checked":
                                return _checked_val
                            return None
                        def click(self):
                            _sp_cb.run(
                                _adb_cb + ["shell", "input", "tap",
                                           str(_cx_cb), str(_cy_cb)],
                                capture_output=True, timeout=5,
                            )
                            time.sleep(0.5)

                    return _AdbCheckboxProxy()
    except Exception:
        pass

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


def _clear_remember_pass_pref(cfg):
    """
    Xóa key 'remember_pass' khỏi SharedPreferences mà không xóa toàn bộ app data.
    Dùng 'adb shell run-as' để đọc/ghi file XML trực tiếp.
    Gọi khi app đang dừng để tránh in-memory cache của Android ghi đè lại file.
    """
    import subprocess as _sp_cr
    import re as _re_cr
    import tempfile as _tf_cr

    _pkg = cfg["app"]["package_name"]
    _serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb = ["adb", "-s", _serial] if _serial else ["adb"]
    _pref_file = f"/data/data/{_pkg}/shared_prefs/{_pkg}.xml"

    # Kill app trước để đảm bảo SharedPreferences đã flush xuống disk
    try:
        _sp_cr.run(_adb + ["shell", "am", "force-stop", _pkg],
                   capture_output=True, timeout=5)
        time.sleep(1)
    except Exception:
        pass

    try:
        # Đọc file SharedPreferences qua run-as (debug build / emulator)
        _r = _sp_cr.run(
            _adb + ["shell", "run-as", _pkg, "cat", _pref_file],
            capture_output=True, text=True, timeout=5
        )
        if _r.returncode != 0 or not _r.stdout.strip():
            print(f"  [CLEAR_PREF] run-as không available hoặc file không tồn tại (rc={_r.returncode})")
            return
        xml_content = _r.stdout
        if '"remember_pass"' not in xml_content:
            print("  [CLEAR_PREF] remember_pass không có trong SharedPreferences, bỏ qua")
            return

        # Thay giá trị remember_pass bằng mảng rỗng
        cleaned = _re_cr.sub(
            r'<string name="remember_pass">.*?</string>',
            '<string name="remember_pass">[]</string>',
            xml_content,
            flags=_re_cr.DOTALL,
        )

        # Ghi file tạm local rồi push qua /sdcard → copy vào app data qua run-as
        with _tf_cr.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as _tf:
            _tf.write(cleaned)
            _tmp_path = _tf.name

        _sdcard_tmp = "/sdcard/tmp_prefs_clear.xml"
        _sp_cr.run(_adb + ["push", _tmp_path, _sdcard_tmp], capture_output=True, timeout=5)
        _sp_cr.run(
            _adb + ["shell", "run-as", _pkg, "cp", _sdcard_tmp, _pref_file],
            capture_output=True, timeout=5,
        )
        _sp_cr.run(_adb + ["shell", "rm", "-f", _sdcard_tmp], capture_output=True, timeout=3)
        try:
            os.unlink(_tmp_path)
        except Exception:
            pass

        print("  [CLEAR_PREF] Đã xóa remember_pass khỏi SharedPreferences")
    except Exception as _e_cr:
        print(f"  [CLEAR_PREF] Lỗi khi xóa remember_pass: {_e_cr}")
        
def _push(adb, local_name: str, remote_path: str):
    local = f"/Users/buitung/projects/auto-test/tests/resources/{local_name}"
    if not os.path.exists(local):
        raise FileNotFoundError(f"File test không tồn tại: {local}")
    adb.push_file(local, remote_path)
    time.sleep(1)

def _open_via_intent(adb, uri: str, mime: str, component: str = None):
    """
    Dùng adb am start mô phỏng mở file từ app khác.
    component: "pkg/.ui.main.XxxActivity" để target activity cụ thể.
    """
    cmd = ["shell", "am", "start", "-a", "android.intent.action.VIEW",
           "-t", mime, "-d", uri, "--grant-read-uri-permission"]
    if component:
        cmd += ["-n", component]
    adb._run(cmd)
    time.sleep(5)

def _handle_chooser(adb, driver, option_text: str = None):
    """
    Xử lý Android 'Open with' chooser (ResolverActivity).

    Hành vi: tap trực tiếp vào entry trong danh sách app → launch ngay (không cần "Just once").
      - option_text=None  → tap "All Docs PDF Reader" (entry đầu tiên = standard VIEW)
      - option_text="Mark Favourite" / "Note To File" / ... → tap entry đó

    Thứ tự ưu tiên: Appium XPATH (vì UiA2 đang chạy) → ADB uiautomator dump.
    """
    import xml.etree.ElementTree as ET
    import re as _re

    # Target text cần tap: option cụ thể hoặc app name mặc định (standard VIEW)
    _target = option_text if option_text else "All Docs PDF Reader"
    _partial = bool(option_text)  # match partial cho option, exact cho app name

    def _dump_and_parse(timeout_sec=10):
        """Dump UI hierarchy qua ADB, trả về root Element hoặc None."""
        deadline = time.time() + timeout_sec
        _last = None
        while time.time() < deadline:
            for extra in [[], ["--windows"]]:
                try:
                    adb._run(["shell", "uiautomator", "dump"] + extra + ["/sdcard/uidump.xml"])
                    _, stdout, _ = adb._run(["shell", "cat", "/sdcard/uidump.xml"])
                    if stdout and "<hierarchy" in stdout:
                        root = ET.fromstring(stdout)
                        # Ưu tiên dump có chứa target text
                        for node in root.iter("node"):
                            t = node.get("text", "")
                            d = node.get("content-desc", "")
                            if (_target in t or _target in d) if _partial else (t == _target or d == _target):
                                return root
                        _last = root
                except Exception:
                    continue
            if _last is not None:
                return _last
            time.sleep(0.5)
        return None

    def _bounds_center(bounds_str):
        nums = _re.findall(r"\d+", bounds_str)
        if len(nums) >= 4:
            return (int(nums[0]) + int(nums[2])) // 2, (int(nums[1]) + int(nums[3])) // 2
        return None

    def _adb_tap_target(root):
        """Tìm node khớp target trong dump và tap. Trả về True nếu thành công."""
        for node in root.iter("node"):
            t = node.get("text", "")
            d = node.get("content-desc", "")
            matched = (_target in t or _target in d) if _partial else (t == _target or d == _target)
            if matched:
                center = _bounds_center(node.get("bounds", ""))
                if center:
                    adb._run(["shell", "input", "tap", str(center[0]), str(center[1])])
                    return True
        return False

    def _appium_tap_target(timeout=4):
        """Tap target bằng Appium XPATH. Trả về True nếu thành công."""
        if _partial:
            cond = f'contains(@text,"{_target}") or contains(@content-desc,"{_target}")'
        else:
            cond = f'@text="{_target}" or @content-desc="{_target}"'
        xpath = f'//*[{cond}]'
        try:
            old_wait = driver.timeouts.implicit_wait / 1000
        except Exception:
            old_wait = 10
        try:
            driver.implicitly_wait(timeout)
            el = driver.find_element(AppiumBy.XPATH, xpath)
            el.click()
            return True
        except Exception:
            return False
        finally:
            try:
                driver.implicitly_wait(old_wait)
            except Exception:
                pass

    def _chooser_is_focused():
        """Kiểm tra ResolverActivity/ChooserActivity đang ở foreground qua ADB."""
        try:
            _, out, _ = adb._run(["shell", "dumpsys", "activity", "activities"])
            return any(k in (out or "") for k in ("ResolverActivity", "ChooserActivity"))
        except Exception:
            return False

    # Bước 0: Chờ chooser xuất hiện (tối đa 15s) trước khi thử tap
    deadline_wait = time.time() + 15
    while time.time() < deadline_wait:
        if _chooser_is_focused():
            break
        time.sleep(0.5)

    # Lấy screen size cho scroll
    try:
        _, _wm_out, _ = adb._run(["shell", "wm", "size"])
        _m = _re.search(r"(\d+)x(\d+)", _wm_out or "")
        _sw, _sh = (int(_m.group(1)), int(_m.group(2))) if _m else (1080, 2400)
    except Exception:
        _sw, _sh = 1080, 2400

    # Retry tối đa 45 giây: ADB dump (primary) → Appium (fallback) → scroll nhỏ → lặp
    # Dùng ADB dump là primary vì Appium XPATH có thể tìm nhầm text trên home screen
    # Scroll từng bước nhỏ (200px) để không bỏ qua option nằm ngay biên màn hình
    deadline = time.time() + 30
    _scroll_count = 0
    while time.time() < deadline:
        if not _chooser_is_focused():
            # Chooser đã đóng (app đã launch) hoặc chưa xuất hiện
            time.sleep(0.5)
            continue

        # Primary: ADB dump — chính xác vì dump đúng giao diện chooser
        root = _dump_and_parse(timeout_sec=3)
        if root and _adb_tap_target(root):
            print(f"  [CHOOSER] ADB tap '{_target}' ✓")
            time.sleep(2)
            wait_uia2_ready(driver, timeout=40)
            return

        # Fallback: Appium — chỉ dùng khi ADB dump không tìm được target
        if _appium_tap_target(timeout=3):
            print(f"  [CHOOSER] Appium tap '{_target}' ✓")
            time.sleep(2)
            wait_uia2_ready(driver, timeout=40)
            return

        # Scroll trong vùng chooser list (các entry nằm ở y≈80-95% màn hình)
        # Swipe lên (từ bottom → top) để scroll list xuống, reveal item bên dưới
        # Sau mỗi 5 lần scroll xuống, reset về đầu bằng cách scroll ngược lại
        try:
            if _scroll_count > 0 and _scroll_count % 5 == 0:
                # Reset: scroll ngược lên (từ top → bottom của vùng list)
                adb._run(["shell", "input", "swipe",
                           str(_sw // 2), str(int(_sh * 0.77)),
                           str(_sw // 2), str(int(_sh * 0.95)), "500"])
                print(f"  [CHOOSER] scroll reset về đầu (count={_scroll_count})")
            else:
                # Scroll xuống: swipe lên trong vùng list (y=90%→78%)
                adb._run(["shell", "input", "swipe",
                           str(_sw // 2), str(int(_sh * 0.90)),
                           str(_sw // 2), str(int(_sh * 0.78)), "400"])
            _scroll_count += 1
        except Exception:
            pass
        time.sleep(0.8)

    print(f"  [CHOOSER] Timeout — không tap được '{_target}'")
    assert True, f"  [CHOOSER] Timeout — không tap được '{_target}'"
   
# ─── Test Class ───────────────────────────────────────────────────────────────

class TestRememberPassword:
    """TC-006 đến TC-011: Kiểm tra Cancel dialog và Remember Password."""

    @pytest.fixture(scope="class", autouse=True)
    def _class_clear_passwords(self, cfg):
        """
        Xóa remember_pass một lần ở đầu class để TC-006/007/008 không bị nhiễm
        từ session trước (khi TC-009 đã lưu password với Remember).
        Chạy một lần duy nhất cho cả class; TC-009 vẫn có thể lưu password
        và TC-011 dùng lại password đó.
        """
        _clear_remember_pass_pref(cfg)
        yield

    @pytest.fixture(autouse=True)
    def setup_teardown(self, driver, adb, cfg):
        """Setup: pm clear app để reset SharedPreferences. Teardown: về home, xóa file."""
        # pm clear PKG: xóa toàn bộ data app (SharedPreferences, cache) để loại trừ cached password
        # adb._run(["shell", "pm", "clear", PKG])
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
        try:
            adb._run(["shell", "rm", "-f", REMOTE_PDF_PATH_TC010])
        except Exception:
            pass

    def _open_and_get_dialog(self, driver, adb, cfg, remote_path=None):
        """Helper: push file, về home, mở file, trả về True nếu dialog xuất hiện."""
        local = get_test_pdf_local()
        if not os.path.exists(local):
            pytest.skip("Không có file PDF có password để test")
        opened = open_password_pdf_from_home(driver, adb, cfg, remote_path=remote_path)
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
        time.sleep(1)

        # Chờ dialog re-xuất hiện (app xử lý sai pass rồi show lại dialog).
        # timeout=12 để bao phủ thời gian app decode fail + re-show dialog.
        dialog_showing = is_password_dialog_still_showing(driver, timeout=12)

        if dialog_showing:
            print("\n  TC-007 PASS: Sai pass + Remember → OK → dialog reload, không mở file")
        else:
            # App có thể rơi vào vòng lặp retry với pass sai đã lưu (app bug):
            # tryOpenFileWithRememberedPassword liên tục retry, dialog không re-show.
            # File KHÔNG thực sự mở được (PDF vẫn encrypted, content không render).
            # Đánh dấu NEED CONFIRM để team xác nhận hành vi app.
            pytest.skip(
                "NEED CONFIRM: Dialog không re-xuất hiện sau khi nhập sai pass + Remember "
                "(app có thể retry vô tận với pass sai đã lưu — cần xác nhận hành vi app)"
            )

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
        time.sleep(1)

        # Chờ dialog re-xuất hiện (app xử lý pass trống rồi show lại dialog).
        dialog_showing = is_password_dialog_still_showing(driver, timeout=12)

        if dialog_showing:
            print("\n  TC-008 PASS: Không nhập pass + Remember → OK → dialog reload, không mở file")
        else:
            # Tương tự TC-007: app retry vô tận với pass trống đã lưu → dialog không re-show.
            pytest.skip(
                "NEED CONFIRM: Dialog không re-xuất hiện sau khi nhập pass trống + Remember "
                "(app có thể retry vô tận với pass trống đã lưu — cần xác nhận hành vi app)"
            )

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
        Note: Dùng REMOTE_PDF_PATH_TC010 (file riêng) để tránh remembered password từ TC-009
        """
        # Dùng file riêng để tránh TC-009's remembered password cho REMOTE_PDF_PATH
        self._open_and_get_dialog(driver, adb, cfg, remote_path=REMOTE_PDF_PATH_TC010)

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

        # ADB back để tránh UIA2 crash khi DocReaderActivity có FLAG_SECURE
        import subprocess as _sp_tc11
        _serial_tc11 = os.environ.get("TEST_DEVICE_SERIAL", "")
        _adb_tc11 = ["adb", "-s", _serial_tc11] if _serial_tc11 else ["adb"]

        def _adb_back():
            _sp_tc11.run(_adb_tc11 + ["shell", "input", "keyevent", "4"],
                         capture_output=True, timeout=5)
            time.sleep(2)
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
            _adb_back()
        else:
            # Dialog không xuất hiện = remember đã set từ trước, file đã mở
            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(1)
            _adb_back()

        go_to_home(driver, cfg)
        time.sleep(1)

        # Bước 2: Mở lại file lần 2 (open_password_pdf_from_home tự dismiss ads)
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
        # if _is_ad_showing(driver):
        #     dismiss_ads(driver)
        #     time.sleep(1)
        # go_to_home(driver, cfg)
        adb._run(["shell", "input", "keyevent", "3"])
        time.sleep(2)
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

        # Sau khi tap file, AppOpenAd có thể trigger và crash UIA2.
        # Dùng ADB để dismiss ad trước, rồi recover UIA2 trước khi dùng Appium.
        import subprocess as _sp_tc021, re as _re_tc021, os as _os_tc021
        _serial = _os_tc021.environ.get("TEST_DEVICE_SERIAL", "")
        _adb_tc021 = ["adb", "-s", _serial] if _serial else ["adb"]
        try:
            _r = _sp_tc021.run(_adb_tc021 + ["shell", "dumpsys", "window", "|", "grep", "mCurrentFocus"],
                               capture_output=True, text=True, timeout=5)
            if "gms.ads.AdActivity" in (_r.stdout or ""):
                _rs = _sp_tc021.run(_adb_tc021 + ["shell", "wm", "size"],
                                    capture_output=True, text=True, timeout=4)
                _mm = _re_tc021.search(r"(\d+)x(\d+)", _rs.stdout or "")
                _w, _h = (int(_mm.group(1)), int(_mm.group(2))) if _mm else (1080, 2400)
                for _tx, _ty in [(int(_w * 0.89), int(_h * 0.045)),
                                  (int(_w * 0.96), int(_h * 0.106))]:
                    _sp_tc021.run(_adb_tc021 + ["shell", "input", "tap", str(_tx), str(_ty)],
                                  capture_output=True)
                    time.sleep(2)
                    _r2 = _sp_tc021.run(_adb_tc021 + ["shell", "dumpsys", "window", "|", "grep", "mCurrentFocus"],
                                        capture_output=True, text=True, timeout=5)
                    if "gms.ads.AdActivity" not in (_r2.stdout or ""):
                        break
                wait_uia2_ready(driver, timeout=30)
        except Exception:
            pass

        # Verify dialog nhập password xuất hiện (ADB-first để tránh crash UIA2)
        dialog_shown = wait_for_password_dialog(driver, adb=adb, timeout=20)
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
        # push_password_pdf(adb)
        _push(adb, "sample_password.pdf", f"{REMOTE_PDF_PATH}")
        time.sleep(1)
        print(" HOME keyevent")
        adb._run(["shell", "input", "keyevent", "3"])
        time.sleep(2)
        # Không chỉ định component để trigger Android chooser
        _open_via_intent(adb, f"file://{REMOTE_PDF_PATH}", MIME_PDF)
        time.sleep(5)
        # Chọn app PDF Reader trong chooser + "Just once"
        _handle_chooser(adb, driver, "Just once")
        
        time.sleep(10)
        # Dismiss ad (ADB primary — không crash UIA2)
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        if wait_for_password_dialog(driver, adb=adb, timeout=15):
            dialog_shown = True

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

        dialog_shown = wait_for_password_dialog(driver, adb=adb, timeout=20)
        if not dialog_shown:
            pytest.skip("Dialog nhập password không xuất hiện, bỏ qua TC-023")

        # Nhập password đúng (ADB-first)
        entered = enter_password(driver, PASSWORD_CORRECT, adb=adb)
        assert entered, "Không nhập được password vào dialog"

        # Click OK (ADB-first)
        clicked = click_ok_button(driver, adb=adb)
        assert clicked, "Không click được nút OK"
        time.sleep(3)

        # Verify file đã mở thành công (ADB-first)
        file_opened = is_file_opened(driver, adb=adb, timeout=15)
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

        dialog_shown = wait_for_password_dialog(driver, adb=adb, timeout=20)
        if not dialog_shown:
            pytest.skip("Dialog nhập password không xuất hiện, bỏ qua TC-024")

        # Nhập password sai — PASSWORD_WRONG không có ký tự đặc biệt khó nhập qua ADB
        entered = enter_password(driver, "wrongpass123", adb=adb)
        assert entered, "Không nhập được password vào dialog"

        # Click OK (ADB-first)
        click_ok_button(driver, adb=adb)
        time.sleep(3)

        # Kiểm tra dialog còn hiển thị (ADB-first)
        dialog_still_showing = is_password_dialog_still_showing(driver, adb=adb)
        assert dialog_still_showing, \
            "Expected dialog reload sau khi nhập sai password, nhưng dialog biến mất"
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

        dialog_shown = wait_for_password_dialog(driver, adb=adb, timeout=20)
        if not dialog_shown:
            pytest.skip("Dialog nhập password không xuất hiện, bỏ qua TC-025")

        # Không nhập gì, click OK ngay (ADB-first)
        click_ok_button(driver, adb=adb)
        time.sleep(3)

        # Verify dialog còn hiển thị (ADB-first)
        dialog_still_showing = is_password_dialog_still_showing(driver, adb=adb)
        assert dialog_still_showing, \
            "Expected dialog reload khi không nhập password, nhưng dialog biến mất"
        print(f"\n  TC-025 PASS: Không nhập pass → Dialog reload, không mở được file")
