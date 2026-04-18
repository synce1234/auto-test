"""
Helpers - Các utility dùng chung cho toàn bộ test suite.
"""
import time
import os
import re
from appium.webdriver.common.appiumby import AppiumBy
from appium import webdriver
from appium.options.android.uiautomator2.base import UiAutomator2Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess

PKG = "pdf.reader.pdf.viewer.all.document.reader.office.viewer"

def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"\n  [{ts}] {msg}")


def _focused_activity_via_dumpsys() -> str:
    """Trả về focused activity từ dumpsys window (best-effort)."""
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
    try:
        r = subprocess.run(
            adb_prefix + ["shell", "dumpsys", "window", "windows"],
            capture_output=True,
            text=True,
            timeout=6,
        )
        out = (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception:
        return ""

    m = re.search(r"mCurrentFocus=Window\{[^}]*\s([\w\.]+)/(\S+)\}", out)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.search(r"mFocusedApp=AppWindowToken\{[^}]*\s([\w\.]+)/(\S+)\}", out)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return ""


def is_uia2_instrumentation_crash(e: Exception) -> bool:
    """
    Detect UiAutomator2 crash signature:
    'cannot be proxied to UiAutomator2 server because the instrumentation process is not running'
    """
    s = str(e) if e is not None else ""
    return (
        "cannot be proxied to uiautomator2 server" in s.lower()
        and "instrumentation process is not running" in s.lower()
    )


def is_uia2_alive(driver) -> bool:
    """
    Probe nhẹ xem gọi driver có dính crash signature UiAutomator2 không.
    Trả về True nếu responsive, False nếu crash signature.
    """
    try:
        # Probe tối thiểu để trigger Appium tự restart UiA2 sau crash.
        # Tránh gọi get_window_size vì endpoint này hay fail lâu hơn (GET /window/current/size).
        driver.current_activity
        return True
    except Exception as e:
        if is_uia2_instrumentation_crash(e):
            _log(f"[UIA2] instrumentation crash detected on probe: {e}")
            focused = _focused_activity_via_dumpsys()
            _log(f"[UIA2][DUMPSYS] focused={focused or '<empty>'}")
            return False
        # lỗi khác: coi là chưa chắc, nhưng báo False để caller quyết định
        _log(f"[UIA2] probe failed (non-crash): {e}")
        return False


def rid(resource_id: str) -> str:
    """Trả về full resource-id string."""
    if ":" in resource_id:
        return resource_id
    return f"{PKG}:id/{resource_id}"


def find(driver, resource_id: str, timeout: int = 10):
    """Tìm element theo resource-id, chờ tối đa timeout giây."""
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, rid(resource_id)))
        )
    except Exception:
        return None


def find_and_click_dumpsys(driver, resource_id: str, timeout: int = 10) -> bool:
    """
    Find + click theo resource-id (đầu vào giống find()).
    Nếu find/click fail sẽ log dumpsys (focused activity) để debug.
    Trả về True nếu click thành công, False nếu không click được.
    """
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, rid(resource_id)))
        )
        el.click()
        return True
    except Exception as e:
        focused = _focused_activity_via_dumpsys()
        _log(f"[CLICK][DUMPSYS FALLBACK] click('{resource_id}') failed: {e}")
        _log(f"[CLICK][DUMPSYS] focused={focused or '<empty>'}")
        return False


def find_all(driver, resource_id: str, timeout: int = 10) -> list:
    """Tìm tất cả elements theo resource-id."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, rid(resource_id)))
        )
        return driver.find_elements(AppiumBy.ID, rid(resource_id))
    except Exception:
        return []


def find_text(driver, text: str, timeout: int = 10):
    """Tìm element theo text (exact match)."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((AppiumBy.XPATH, f'//*[@text="{text}"]'))
    )


def find_text_contains(driver, text: str, timeout: int = 10):
    """Tìm element chứa text."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(
            (AppiumBy.XPATH, f'//*[contains(@text, "{text}")]')
        )
    )


def is_visible(driver, resource_id: str, timeout: int = 5) -> bool:
    """Kiểm tra element có tồn tại trên màn hình không."""
    try:
        return bool(find(driver, resource_id, timeout=timeout))
    except Exception:
        return False


def wait_uia2_ready(driver, timeout: int = 40) -> bool:
    """
    Chờ UiAutomator2 responsive sau khi crash (vd: sau khi File Chooser đóng).
    Appium tự restart UiAutomator2 khi nhận lệnh đầu tiên sau crash.
    Poll driver.current_activity cho đến khi thành công.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            driver.current_activity
            return True
        except Exception:
            time.sleep(2)
    return False


def wait_for_activity(driver, activity_substr: str, timeout: int = 15) -> bool:
    """Chờ đến khi current activity chứa activity_substr."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            current = driver.current_activity or ""
            if activity_substr.lower() in current.lower():
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def close_recentapp2(driver, adb=None, pkg: str = PKG, home: bool = True) -> bool:
    """
    Close app/recent state bằng lifecycle command của Appium + fallback ADB force-stop.
    - terminate_app(pkg)
    - fallback: adb shell am force-stop pkg  (ưu tiên adb fixture nếu có)
    - optional: về HOME
    Trả về True nếu thực thi được ít nhất 1 phương án đóng app.
    """
    ok = False
    try:
        driver.terminate_app(pkg)
        ok = True
    except Exception:
        pass

    try:
        if adb is not None:
            adb._run(["shell", "am", "force-stop", pkg])
        else:
            subprocess.run(["adb", "shell", "am", "force-stop", pkg], capture_output=True, timeout=15)
        ok = True
    except Exception:
        pass

    if home:
        try:
            driver.press_keycode(3)  # KEYCODE_HOME
        except Exception:
            try:
                if adb is not None:
                    adb._run(["shell", "input", "keyevent", "3"])
                else:
                    subprocess.run(["adb", "shell", "input", "keyevent", "3"], capture_output=True, timeout=10)
            except Exception:
                pass
        time.sleep(1)

    return ok


# ─── Dismiss Ads ──────────────────────────────────────────────────────────────

def dismiss_ads(driver) -> bool:
    """
    Đóng Open App Ad / Interstitial Ad nếu đang hiển thị.

    Các pattern cần handle:
    1. "Continue to app" link (AdMob open app ad)
    2. Nút X / Close (Google GMS close_button)
    3. Tap góc màn hình (fallback)

    Trả về True nếu đã dismiss được ad.
    """
    _AD_CLOSE_XPATH = (
        '//*[contains(@text,"Continue to app")]'
        ' | //*[contains(@content-desc,"Continue to app")]'
        ' | //*[contains(@text,"Skip Ad")]'
        ' | //*[contains(@text,"Skip ad")]'
        ' | //*[contains(@content-desc,"Close ad")]'
        ' | //*[@resource-id="com.google.android.gms:id/close_button"]'
        ' | //*[@resource-id="com.google.android.gms:id/skip_ad_button"]'
    )

    # Thử trên tất cả window handles (ad có thể ở window khác)
    try:
        handles = driver.window_handles
        original = driver.current_window_handle
        for handle in handles:
            try:
                driver.switch_to.window(handle)
                el = driver.find_element(AppiumBy.XPATH, _AD_CLOSE_XPATH)
                el.click()
                time.sleep(1.5)
                return True
            except Exception:
                pass
        # Restore về window gốc
        try:
            driver.switch_to.window(original)
        except Exception:
            pass
    except Exception:
        pass

    # Thử trên window hiện tại (không dùng switch_to)
    try:
        el = driver.find_element(AppiumBy.XPATH, _AD_CLOSE_XPATH)
        el.click()
        time.sleep(1.5)
        return True
    except Exception:
        pass

    # Fallback: tap tọa độ điển hình bằng ADB thuần (tránh page_source/get_window_size
    # vì chúng crash UIA2 khi WebView/AdActivity đang ở foreground)
    try:
        import subprocess as _sp
        import re as _re
        serial = os.environ.get("TEST_DEVICE_SERIAL", "")
        _adb = ["adb", "-s", serial] if serial else ["adb"]
        # Lấy screen size bằng ADB
        _r = _sp.run(_adb + ["shell", "wm", "size"], capture_output=True, text=True, timeout=5)
        _m = _re.search(r"(\d+)x(\d+)", _r.stdout or "")
        w, h = (int(_m.group(1)), int(_m.group(2))) if _m else (1080, 2400)
        _positions = [
            (int(w * 0.89), int(h * 0.045)),  # AdActivity X button (top-right)
            (int(w * 0.96), int(h * 0.106)),  # App Open Ad "Continue to app"
            (int(w * 0.80), int(h * 0.055)),  # "Continue to app >" bar top-right
            (int(w * 0.95), int(h * 0.14)),   # X button top-right fallback
        ]
        for _x, _y in _positions:
            _sp.run(_adb + ["shell", "input", "tap", str(_x), str(_y)], capture_output=True)
            time.sleep(1.5)
            _r2 = _sp.run(_adb + ["shell", "dumpsys", "activity", "activities"],
                          capture_output=True, text=True, timeout=5)
            if "gms.ads.AdActivity" not in (_r2.stdout or ""):
                return True
    except Exception:
        pass

    return False


def close_exit_dialog(driver) -> bool:
    """
    Đóng dialog thoát / rate-us nếu đang hiển thị sau khi bấm Back.

    Dialog "Do you like PDF Reader?" xuất hiện khi back từ viewer về Home.
    Nút close có resource-id: imv_close_rate
    Fallback: btn_more_review ("I need more time to review")

    Trả về True nếu đã đóng được dialog, False nếu không có dialog.
    """
    # Thử click nút X (imv_close_rate)
    try:
        el = WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((AppiumBy.ID, rid("imv_close_rate")))
        )
        el.click()
        _log("[EXIT_DIALOG] Đã đóng dialog bằng imv_close_rate")
        time.sleep(0.5)
        return True
    except Exception:
        pass

    # Fallback: click "I need more time to review"
    try:
        el = WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((AppiumBy.ID, rid("btn_more_review")))
        )
        el.click()
        _log("[EXIT_DIALOG] Đã đóng dialog bằng btn_more_review")
        time.sleep(0.5)
        return True
    except Exception:
        pass

    _log("[EXIT_DIALOG] Không phát hiện dialog thoát")
    return False


def _is_ad_showing(driver) -> bool:
    """
    Kiểm tra có đang hiển thị open app ad không.
    Dùng ADB dumpsys (không phụ thuộc UIA2) để tránh crash khi WebView present.
    """
    import subprocess as _sp_ad
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_ad = ["adb", "-s", serial] if serial else ["adb"]
    try:
        _r = _sp_ad.run(
            _adb_ad + ["shell", "dumpsys", "activity", "activities"],
            capture_output=True, text=True, timeout=5,
        )
        _focus = ""
        for _line in (_r.stdout or "").splitlines():
            if "mCurrentFocus" in _line:
                _focus = _line.lower()
                break
        if any(a in _focus for a in ["adactivity", "admob", "interstitialad"]):
            return True
    except Exception:
        pass
    # Fallback: try Appium current_activity
    try:
        activity = driver.current_activity or ""
        if any(a in activity for a in ["AdActivity", "AdMob", "admob", "InterstitialAd"]):
            return True
    except Exception:
        pass
    return False


def _safe_dismiss_open_app_ad(driver) -> bool:
    """
    Dismiss AdMob Open App Ad bằng cách tap vào vị trí 'Continue to app >'.
    KHÔNG dùng window_handles hay page_source để tránh crash UIAutomator2.
    'Continue to app >' nằm trong WebView nên không thể find bằng XPATH.
    Coords: ~96% width, ~10.6% height trên màn hình 1080x2400.
    """
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            activity = driver.current_activity or ""
            is_ad = any(a in activity for a in ["AdActivity", "AdMob", "admob", "InterstitialAd"])
            if not is_ad:
                return True  # Không có ad
        except Exception:
            return True
        try:
            size = driver.get_window_size()
            x = int(size["width"] * 0.96)
            y = int(size["height"] * 0.106)
            driver.tap([(x, y)])
        except Exception:
            pass
        time.sleep(2)
    return False


# ─── App State ────────────────────────────────────────────────────────────────

def ensure_app_foreground(driver, cfg: dict):
    """Đảm bảo app đang ở foreground. Re-activate nếu bị đẩy về launcher."""
    pkg = cfg["app"]["package_name"]
    try:
        current_pkg = driver.current_package
        if current_pkg != pkg:
            driver.activate_app(pkg)
            time.sleep(3)
            # Dismiss ad ngay sau khi activate
            # if _is_ad_showing(driver):
            #     _safe_dismiss_open_app_ad(driver)
            #     time.sleep(1)
    except Exception:
        try:
            driver.activate_app(pkg)
            time.sleep(3)
        except Exception:
            pass


def _adb_dismiss_ad_if_active() -> bool:
    """
    Kiểm tra AdActivity có đang ở foreground không (qua dumpsys) và tap để dismiss.
    Dùng ADB thuần — không cần UiAutomator2 để tránh crash.
    Trả về True nếu đã tap (ad đang active).
    """
    import subprocess as _sp_ad
    import re as _re_ad
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    adb = ["adb", "-s", serial] if serial else ["adb"]
    try:
        r = _sp_ad.run(adb + ["shell", "dumpsys", "window", "|", "grep", "mCurrentFocus"],
                       capture_output=True, text=True, timeout=5)
        if "gms.ads.AdActivity" not in (r.stdout or ""):
            return False
        # Lấy screen size
        rs = _sp_ad.run(adb + ["shell", "wm", "size"], capture_output=True, text=True, timeout=4)
        m = _re_ad.search(r"(\d+)x(\d+)", rs.stdout or "")
        w, h = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
        # Tap các vị trí dismiss (X button, Continue to app)
        for tx, ty in [(int(w * 0.89), int(h * 0.045)), (int(w * 0.96), int(h * 0.106))]:
            _sp_ad.run(adb + ["shell", "input", "tap", str(tx), str(ty)], capture_output=True)
            time.sleep(2)
            r2 = _sp_ad.run(adb + ["shell", "dumpsys", "window", "|", "grep", "mCurrentFocus"],
                            capture_output=True, text=True, timeout=5)
            if "gms.ads.AdActivity" not in (r2.stdout or ""):
                return True
    except Exception:
        pass
    return True  # Đã tap dù chưa chắc dismiss


_SETTINGS_SCREEN_TEXTS = (
    "All files access",
    "Allow access to manage all files",
    "manage all files",
)

def _adb_back_if_settings() -> bool:
    """
    Kiểm tra app đang kẹt ở màn 'All files access' qua uiautomator dump (text-based).
    Detection bằng text vì Settings activity chạy trong task stack của app,
    nên mCurrentFocus vẫn thấy package của app → detect bằng package sẽ sai.
    Nếu phát hiện → press BACK bằng ADB. Trả về True nếu đã back.
    """
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb = ["adb", "-s", serial] if serial else ["adb"]
    try:
        _fname_chk = f"/sdcard/chk_{int(time.time()*1000)}.xml"
        subprocess.run(_adb + ["shell", "uiautomator", "dump", _fname_chk],
                       capture_output=True, text=True, timeout=8)
        _r_pull_chk = subprocess.run(_adb + ["pull", _fname_chk, "/tmp/chk_ui_tmp.xml"],
                                     capture_output=True, text=True, timeout=5)
        subprocess.run(_adb + ["shell", "rm", "-f", _fname_chk], capture_output=True, timeout=3)
        xml = ""
        if _r_pull_chk.returncode == 0:
            with open("/tmp/chk_ui_tmp.xml", "r", errors="replace") as _fc:
                xml = _fc.read()
        if any(t in xml for t in _SETTINGS_SCREEN_TEXTS):
            subprocess.run(_adb + ["shell", "input", "keyevent", "4"],
                           capture_output=True, timeout=5)
            time.sleep(1)
            return True
    except Exception:
        pass
    return False


def _is_home_screen(driver, serial: str = "") -> bool:
    """
    Kiểm tra đang ở Home fragment (tab "All" — danh sách tất cả file).
    Cần có cả rcv_all_file VÀ layoutAll (tab header của Home fragment).
    rcv_all_file xuất hiện ở cả file browser fragment nên không đủ để phân biệt.
    """
    _adb_h = ["adb", "-s", serial] if serial else ["adb"]
    try:
        _fname_h = f"/sdcard/home_{int(time.time()*1000)}.xml"
        subprocess.run(_adb_h + ["shell", "uiautomator", "dump", _fname_h],
                       capture_output=True, timeout=8)
        _r_h = subprocess.run(_adb_h + ["pull", _fname_h, "/tmp/home_check.xml"],
                              capture_output=True, text=True, timeout=5)
        subprocess.run(_adb_h + ["shell", "rm", "-f", _fname_h], capture_output=True, timeout=3)
        if _r_h.returncode == 0:
            with open("/tmp/home_check.xml", "r", errors="replace") as _fh:
                _xml_h = _fh.read()
            # layoutAll là tab "All" chỉ xuất hiện ở Home fragment, không có ở file browser
            if "rcv_all_file" in _xml_h and "layoutAll" in _xml_h:
                return True
    except Exception:
        pass
    # Appium fallback — normal home (có file)
    try:
        if find(driver, "rcv_all_file", timeout=2) and find(driver, "layoutAll", timeout=1):
            return True
    except Exception:
        pass
    # Permission-denied home: layoutAll + vl_setting_permission (rcv_all_file bị ẩn)
    try:
        if find(driver, "layoutAll", timeout=1) and find(driver, "vl_setting_permission", timeout=1):
            return True
    except Exception:
        pass
    return False


def _adb_click_by_id(serial: str, resource_id: str) -> bool:
    """
    Tìm element theo resource-id trong ADB dump và tap vào tâm của nó.
    Trả về True nếu tap thành công.
    """
    _adb_c = ["adb", "-s", serial] if serial else ["adb"]
    try:
        _fname_c = f"/sdcard/click_{int(time.time()*1000)}.xml"
        subprocess.run(_adb_c + ["shell", "uiautomator", "dump", _fname_c],
                       capture_output=True, timeout=8)
        _r_c = subprocess.run(_adb_c + ["pull", _fname_c, "/tmp/click_tmp.xml"],
                              capture_output=True, text=True, timeout=5)
        subprocess.run(_adb_c + ["shell", "rm", "-f", _fname_c], capture_output=True, timeout=3)
        if _r_c.returncode != 0:
            return False
        with open("/tmp/click_tmp.xml", "r", errors="replace") as _fc2:
            _xml_c = _fc2.read()
        _m_c = re.search(
            rf'resource-id="[^"]*{re.escape(resource_id)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            _xml_c,
        )
        if not _m_c:
            return False
        _cx = (int(_m_c.group(1)) + int(_m_c.group(3))) // 2
        _cy = (int(_m_c.group(2)) + int(_m_c.group(4))) // 2
        subprocess.run(_adb_c + ["shell", "input", "tap", str(_cx), str(_cy)],
                       capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def go_to_home(driver, cfg: dict) -> bool:
    """
    Navigate về màn hình Home (rcv_all_file — danh sách file).

    Luồng tối ưu:
      1. HOME keyevent (về launcher)
      2. Kill app
      3. Mở lại app
      4. Loop: dùng dumpsys activity (0.02s) để detect state, chỉ gọi
         uiautomator dump khi đang trong MainActivity cần check fragment.
         - AdActivity → BACK keyevent (0.5s, không cần dump)
         - SplashScreen / launcher → đợi 0.5s
         - MainActivity → ONE dump để check home + rating dialog cùng lúc
    """
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    pkg = cfg["app"]["package_name"]
    _adb_g = ["adb", "-s", serial] if serial else ["adb"]

    def _top_act():
        """dumpsys activity: 0.02s vs uiautomator dump 3s."""
        r = subprocess.run(_adb_g + ["shell", "dumpsys", "activity", "activities"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "topResumedActivity" in line:
                return line
        return ""

    def _dump_xml():
        fname = f"/sdcard/home_{int(time.time()*1000)}.xml"
        subprocess.run(_adb_g + ["shell", "uiautomator", "dump", fname],
                       capture_output=True, timeout=8)
        r = subprocess.run(_adb_g + ["pull", fname, "/tmp/home_check.xml"],
                           capture_output=True, text=True, timeout=5)
        subprocess.run(_adb_g + ["shell", "rm", "-f", fname],
                       capture_output=True, timeout=3)
        if r.returncode == 0:
            with open("/tmp/home_check.xml", errors="replace") as f:
                return f.read()
        return None

    def _is_home_in_xml(xml):
        # Home bình thường (có file list)
        if "rcv_all_file" in xml and "layoutAll" in xml:
            return True
        # Home permission-denied (rcv_all_file ẩn, hiện vl_setting_permission)
        if "layoutAll" in xml and "vl_setting_permission" in xml:
            return True
        return False

    def _tap_by_id_in_xml(xml, res_id):
        m = re.search(
            rf'resource-id="[^"]*{re.escape(res_id)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            xml,
        )
        if m:
            cx = (int(m.group(1)) + int(m.group(3))) // 2
            cy = (int(m.group(2)) + int(m.group(4))) // 2
            subprocess.run(_adb_g + ["shell", "input", "tap", str(cx), str(cy)],
                           capture_output=True, timeout=5)
            return True
        return False

    _log(f"[GO_HOME] start (serial={serial or 'default'}, pkg={pkg})")

    # 1. Về launcher
    subprocess.run(_adb_g + ["shell", "input", "keyevent", "3"],
                   capture_output=True, timeout=5)
    time.sleep(0.5)

    # 2. Kill app
    try:
        driver.terminate_app(pkg)
    except Exception:
        subprocess.run(_adb_g + ["shell", "am", "force-stop", pkg],
                       capture_output=True, timeout=5)

    # 3. Mở lại app
    try:
        driver.activate_app(pkg)
    except Exception:
        subprocess.run(
            _adb_g + ["shell", "monkey", "-p", pkg,
                      "-c", "android.intent.category.LAUNCHER", "1"],
            capture_output=True, timeout=8,
        )
    time.sleep(1.5)

    # 4. Loop: dumpsys-first, dump chỉ khi cần
    _splash_count = 0
    for _i in range(16):
        act = _top_act()
        _log(f"[GO_HOME] iter={_i+1} act={act[act.find('u0')+3:].split()[0] if 'u0' in act else act[:60]}")

        # AdActivity → BACK keyevent (0.5s, không cần dump)
        if "AdActivity" in act:
            subprocess.run(_adb_g + ["shell", "input", "keyevent", "4"],
                           capture_output=True, timeout=5)
            _log("[GO_HOME] AdActivity → BACK")
            _splash_count = 0
            time.sleep(0.5)
            continue

        # Chưa vào app (launcher / splash) → đợi
        # Sau 3 iter splash liên tiếp, tăng wait lên 1s; sau 5 iter thử dump XML
        # vì đôi khi activity vẫn là SplashScreenActivity nhưng home content đã load xong
        if pkg not in act or "SplashScreen" in act:
            _splash_count += 1
            if _splash_count > 5:
                _log(f"[GO_HOME] splash iter={_splash_count} → thử dump XML để check home")
                xml = _dump_xml()
                if xml and _is_home_in_xml(xml):
                    _tap_by_id_in_xml(xml, "layoutAll")
                    time.sleep(0.3)
                    _log(f"[GO_HOME] Home reached in splash (iter={_i+1}) ✓")
                    return True
                if xml and "imv_close_rate" in xml:
                    _tap_by_id_in_xml(xml, "imv_close_rate")
                    _log("[GO_HOME] rating dialog closed (in splash)")
                    time.sleep(0.5)
                    continue
            _wait = 1.0 if _splash_count > 3 else 0.5
            _log(f"[GO_HOME] launcher/splash → wait {_wait}s (consecutive={_splash_count})")
            time.sleep(_wait)
            continue

        _splash_count = 0

        # Đang trong app → ONE dump để check home + rating dialog
        xml = _dump_xml()
        if xml is None:
            time.sleep(0.5)
            continue

        # Rating dialog → close và loop lại
        if "imv_close_rate" in xml:
            if _tap_by_id_in_xml(xml, "imv_close_rate"):
                _log("[GO_HOME] rating dialog closed")
                time.sleep(0.5)
                continue

        # Home screen (có file) hoặc home screen permission-denied (vl_setting_permission)
        if _is_home_in_xml(xml):
            _tap_by_id_in_xml(xml, "layoutAll")
            time.sleep(0.3)
            _log(f"[GO_HOME] Home reached (iter={_i+1}) ✓")
            return True

        _log("[GO_HOME] in app but not home → wait 0.5s")
        time.sleep(0.5)

    # Final fallback
    xml = _dump_xml()
    if xml and _is_home_in_xml(xml):
        _tap_by_id_in_xml(xml, "layoutAll")
        time.sleep(0.3)
        _log("[GO_HOME] end: home reached (fallback) ✓")
        return True
    _log("[GO_HOME] end: home NOT reached ✗")
    return False


def open_fab_menu(driver):
    """Mở FAB tool menu."""
    # Nếu FAB menu đang mở rồi thì close trước
    if is_visible(driver, "btn_split_file", timeout=1):
        close_fab_menu(driver)
        time.sleep(0.5)
    btn = find(driver, "btn_action_create_file")
    btn.click()
    time.sleep(1)
    return is_visible(driver, "btn_split_file", timeout=5)


def close_fab_menu(driver):
    """Đóng FAB menu bằng cách tap vùng ngoài."""
    try:
        driver.find_element(AppiumBy.ID, rid("touch_outside")).click()
    except Exception:
        driver.back()
    time.sleep(0.5)


# ─── Onboarding ───────────────────────────────────────────────────────────────

def dismiss_onboarding(driver, cfg: dict):
    """
    Bỏ qua toàn bộ màn hình onboarding:
      Language → Permission dialog → System permission → Open App Ad → Home

    Gọi trước khi bắt đầu test.
    """
    # try:
    #     driver.press_keycode(3)  # KEYCODE_HOME
    # except Exception:
    #     subprocess.run(["adb", "shell", "input", "keyevent", "3"], capture_output=True, timeout=10)
    # except Exception:
    #     pass
    # time.sleep(1)
    
    pkg = cfg["app"]["package_name"]
    deadline = time.time() + 90  # tối đa 90 giây cho toàn bộ onboarding

    # ADB prefix dùng xuyên suốt vòng lặp
    _serial_ob = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_ob = ["adb", "-s", _serial_ob] if _serial_ob else ["adb"]

    _SETTINGS_TEXTS = ("All files access", "Allow access to manage all files",
                       "manage all files", "MANAGE_EXTERNAL_STORAGE")

    def _adb_dump_xml_ob() -> str:
        """Dump UI hierarchy qua ADB. Dùng tên file unique (timestamp) để tránh stale cache."""
        try:
            _fname = f"/sdcard/ob_{int(time.time()*1000)}.xml"
            subprocess.run(
                _adb_ob + ["shell", "uiautomator", "dump", _fname],
                capture_output=True, text=True, timeout=8,
            )
            r_pull = subprocess.run(
                _adb_ob + ["pull", _fname, "/tmp/ob_ui_tmp.xml"],
                capture_output=True, text=True, timeout=5,
            )
            subprocess.run(_adb_ob + ["shell", "rm", "-f", _fname],
                           capture_output=True, timeout=3)
            if r_pull.returncode != 0:
                return ""
            with open("/tmp/ob_ui_tmp.xml", "r", errors="replace") as _f:
                return _f.read()
        except Exception:
            return ""

    def _is_settings_screen_ob(xml: str) -> bool:
        """Kiểm tra có phải màn All files access không (theo text, không theo package)."""
        return any(t in xml for t in _SETTINGS_TEXTS)

    def _get_focused_window_ob() -> str:
        """
        Lấy mCurrentFocus từ dumpsys activity activities.
        Chú ý: dumpsys window windows không có mCurrentFocus trên một số Android version —
        dùng dumpsys activity activities thay thế.
        """
        try:
            r = subprocess.run(
                _adb_ob + ["shell", "dumpsys", "activity", "activities"],
                capture_output=True, text=True, timeout=8,
            )
            for line in (r.stdout or "").splitlines():
                if "mCurrentFocus" in line or "mFocusedApp" in line:
                    return line.strip()
        except Exception:
            pass
        return ""

    def _is_settings_foreground_ob() -> bool:
        """Kiểm tra Settings 'All files access' có đang ở foreground không."""
        focus = _get_focused_window_ob()
        return bool(focus) and (
            "settings" in focus.lower() or "permissioncontroller" in focus.lower()
        )

    def _is_ad_activity_ob() -> bool:
        """Kiểm tra AdActivity (Google Ads) có đang foreground không."""
        focus = _get_focused_window_ob()
        return bool(focus) and "adactivity" in focus.lower()

    def _check_settings_closed_ob() -> bool:
        """Kiểm tra Settings đã đóng chưa."""
        return not _is_settings_foreground_ob()

    def _adb_back_ob():
        """Nhấn BACK bằng ADB."""
        try:
            subprocess.run(_adb_ob + ["shell", "input", "keyevent", "4"],
                           capture_output=True, timeout=5)
            time.sleep(1.5)
        except Exception:
            pass

    def _adb_launch_app_ob():
        """Mở lại app bằng ADB monkey (không cần UIA2)."""
        try:
            subprocess.run(
                _adb_ob + ["shell", "monkey", "-p", pkg, "-c",
                           "android.intent.category.LAUNCHER", "1"],
                capture_output=True, timeout=8,
            )
            time.sleep(2)
        except Exception:
            pass

    _iter_ob = 0
    _settings_granted = False  # True sau khi đã click toggle + back lần đầu
    while time.time() < deadline:
        _iter_ob += 1
        _time_left = int(deadline - time.time())
        _log(f"[ONBOARD iter={_iter_ob}] bắt đầu, còn {_time_left}s")

        # 0. Detect Settings "All files access":
        #    - Ưu tiên: dumpsys window (luôn hoạt động, kể cả khi uiautomator dump fail)
        #    - Fallback: parse text từ XML dump
        _focused_win = _get_focused_window_ob()
        _log(f"[ONBOARD iter={_iter_ob}] focused_window='{_focused_win}'")
        _xml_ob = _adb_dump_xml_ob()
        _log(f"[ONBOARD iter={_iter_ob}] dump ok, xml_len={len(_xml_ob)}")

        _on_settings = (
            _is_settings_foreground_ob()  # primary: dumpsys window
            or _is_settings_screen_ob(_xml_ob)  # fallback: XML text
        )

        if _on_settings:
            if _settings_granted:
                _log(f"[ONBOARD iter={_iter_ob}] step0: Settings lại sau khi đã grant → back×2 + relaunch")
                _adb_back_ob()
                _adb_back_ob()
                _adb_launch_app_ob()
            else:
                _log(f"[ONBOARD iter={_iter_ob}] step0: Settings detected → tap toggle")
                # Lấy screen size
                try:
                    _r_wm0 = subprocess.run(_adb_ob + ["shell", "wm", "size"],
                                            capture_output=True, text=True, timeout=5)
                    _wm0 = re.search(r"(\d+)x(\d+)", _r_wm0.stdout or "")
                    _sw0, _sh0 = (int(_wm0.group(1)), int(_wm0.group(2))) if _wm0 else (1080, 2400)
                except Exception:
                    _sw0, _sh0 = 1080, 2400
                _log(f"[ONBOARD iter={_iter_ob}] screen={_sw0}x{_sh0}")

                # Thử tap từ Switch bounds trong XML trước (nếu dump có dữ liệu)
                _tapped_and_closed = False
                if _xml_ob:
                    _sw_matches = list(re.finditer(
                        r'<node[^>]*class="android\.widget\.Switch[^"]*"[^>]*/>', _xml_ob))
                    _log(f"[ONBOARD iter={_iter_ob}] found {len(_sw_matches)} Switch(es) in XML")
                    for _sw_m in _sw_matches:
                        _sw_node = _sw_m.group(0)
                        if 'checked="false"' in _sw_node:
                            _bm = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', _sw_node)
                            if _bm:
                                _tcx = (int(_bm.group(1)) + int(_bm.group(3))) // 2
                                _tcy = (int(_bm.group(2)) + int(_bm.group(4))) // 2
                                subprocess.run(_adb_ob + ["shell", "input", "tap", str(_tcx), str(_tcy)],
                                               capture_output=True, timeout=5)
                                time.sleep(1.5)
                                _log(f"[ONBOARD iter={_iter_ob}] XML bounds tap ({_tcx},{_tcy})")
                                if _check_settings_closed_ob():
                                    _log(f"[ONBOARD iter={_iter_ob}] Settings closed after XML tap ✓")
                                    _tapped_and_closed = True
                            break

                if not _tapped_and_closed:
                    # Tap theo tọa độ: thử nhiều vị trí toggle (X~88%) và text row (X~40%)
                    # Y range rộng (15%–50%) để cover các kích thước màn hình khác nhau
                    _y_pcts = [0.20, 0.25, 0.28, 0.30, 0.33, 0.37, 0.41, 0.45, 0.50]
                    for _x_pct in [0.88, 0.75, 0.50, 0.40]:
                        _tx = int(_sw0 * _x_pct)
                        for _y_pct in _y_pcts:
                            _ty = int(_sh0 * _y_pct)
                            subprocess.run(
                                _adb_ob + ["shell", "input", "tap", str(_tx), str(_ty)],
                                capture_output=True, timeout=5,
                            )
                            time.sleep(0.6)
                            _log(f"[ONBOARD iter={_iter_ob}] coord tap ({_tx},{_ty}) [{_x_pct:.0%},{_y_pct:.0%}]")
                            if _check_settings_closed_ob():
                                _log(f"[ONBOARD iter={_iter_ob}] Settings closed after coord tap ✓")
                                _tapped_and_closed = True
                                break
                        if _tapped_and_closed:
                            break

                if not _tapped_and_closed:
                    _log(f"[ONBOARD iter={_iter_ob}] all taps failed → press BACK anyway")
                    _adb_back_ob()

                # Grant bằng appops để đảm bảo permission được cấp
                # (tap tọa độ có thể dismiss dialog mà không enable toggle thực sự)
                try:
                    _r_ops = subprocess.run(
                        _adb_ob + ["shell", "appops", "set", pkg,
                                   "MANAGE_EXTERNAL_STORAGE", "allow"],
                        capture_output=True, text=True, timeout=8,
                    )
                    _log(f"[ONBOARD iter={_iter_ob}] appops set MANAGE_EXTERNAL_STORAGE allow: "
                         f"{(_r_ops.stdout + _r_ops.stderr).strip() or 'ok'}")
                except Exception as _e_ops:
                    _log(f"[ONBOARD iter={_iter_ob}] appops set failed: {_e_ops}")

                # Force-stop Settings để xóa activity khỏi task stack của app
                # (Settings launched via startActivityForResult còn sống dù app bị kill)
                try:
                    subprocess.run(
                        _adb_ob + ["shell", "am", "force-stop", "com.android.settings"],
                        capture_output=True, timeout=5,
                    )
                    _log(f"[ONBOARD iter={_iter_ob}] force-stop com.android.settings ✓")
                except Exception:
                    pass

                _settings_granted = True
            continue

        # Lấy current package (Appium, best-effort)
        try:
            current_pkg = driver.current_package or ""
        except Exception:
            current_pkg = ""
        _log(f"[ONBOARD iter={_iter_ob}] current_pkg='{current_pkg}'")

        # 1. App chưa ở foreground
        if current_pkg != pkg:
            _log(f"[ONBOARD iter={_iter_ob}] step1: app not foreground (pkg={current_pkg}) → activate")
            try:
                driver.activate_app(pkg)
                time.sleep(2)
            except Exception:
                _adb_launch_app_ob()
            continue
        time.sleep(10)
        # 1b. AdActivity đang foreground → dismiss ad rồi tiếp tục
        if _is_ad_activity_ob():
            _log(f"[ONBOARD iter={_iter_ob}] step1b: AdActivity detected → dismiss ad")
            from tests.helpers import dismiss_ads as _dismiss_ads_ob
            try:
                _dismiss_ads_ob(driver)
            except Exception:
                pass
            time.sleep(2)
            continue

        # 2. Đã ở home → xong
        _home_visible = is_visible(driver, "rcv_all_file", timeout=2)
        _log(f"[ONBOARD iter={_iter_ob}] step2: rcv_all_file visible={_home_visible}")
        if _home_visible:
            _log(f"[ONBOARD iter={_iter_ob}] HOME reached ✓")
            return True

        # 3. Language screen → click btn_continue
        # Kiểm tra theo activity name (ChooseLanguageActivity) hoặc Appium find
        _on_lang_act = False
        try:
            _on_lang_act = "ChooseLanguage" in driver.current_activity
        except Exception:
            pass
        _lang_visible = _on_lang_act or is_visible(driver, "btn_continue", timeout=2)
        _log(f"[ONBOARD iter={_iter_ob}] step3: btn_continue visible={_lang_visible} (on_lang_act={_on_lang_act})")
        if _lang_visible:
            _clicked_lang = False
            _btn = find(driver, "btn_continue")
            if _btn is not None:
                _btn.click()
                _clicked_lang = True
                _log(f"[ONBOARD iter={_iter_ob}] step3: clicked btn_continue ✓")
            if not _clicked_lang:
                # ADB tap fallback — btn_continue bounds=[930,132][1080,279], center≈(1005,206)
                try:
                    _sz_ob = driver.get_window_size()
                    _tx_ob = int(_sz_ob["width"] * 0.93)
                    _ty_ob = int(_sz_ob["height"] * 0.086)
                except Exception:
                    _tx_ob, _ty_ob = 1005, 206
                subprocess.run(
                    _adb_ob + ["shell", "input", "tap", str(_tx_ob), str(_ty_ob)],
                    capture_output=True, timeout=5,
                )
                _log(f"[ONBOARD iter={_iter_ob}] step3: ADB tap ({_tx_ob},{_ty_ob}) for language confirm")
            time.sleep(2)
            continue

        # 4. PermissionActivity (btnDialogConfirm) — reuse XML dump từ step 0
        _app_allow_clicked = False
        _m4 = re.search(
            r'resource-id="[^"]*btnDialogConfirm"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            _xml_ob,
        )
        if not _m4:
            _m4 = re.search(
                r'text="Allow"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', _xml_ob,
            )
        if _m4:
            _cx4 = (int(_m4.group(1)) + int(_m4.group(3))) // 2
            _cy4 = (int(_m4.group(2)) + int(_m4.group(4))) // 2
            subprocess.run(_adb_ob + ["shell", "input", "tap", str(_cx4), str(_cy4)],
                           capture_output=True, timeout=5)
            _app_allow_clicked = True
            _log(f"[ONBOARD iter={_iter_ob}] step4: ADB tap btnDialogConfirm at ({_cx4},{_cy4}) ✓")
        else:
            _log(f"[ONBOARD iter={_iter_ob}] step4: btnDialogConfirm not in dump → try Appium")
            try:
                from selenium.webdriver.support.ui import WebDriverWait as _WDW4
                from selenium.webdriver.support import expected_conditions as _EC4
                _allow_el = _WDW4(driver, 5).until(
                    _EC4.presence_of_element_located((AppiumBy.ID, rid("btnDialogConfirm")))
                )
                _allow_el.click()
                _app_allow_clicked = True
                _log(f"[ONBOARD iter={_iter_ob}] step4: Appium tap btnDialogConfirm ✓")
            except Exception as _e4a:
                _log(f"[ONBOARD iter={_iter_ob}] step4: Appium btnDialogConfirm failed")
        if _app_allow_clicked:
            time.sleep(2)
            continue

        # 5. System permission dialog
        _log(f"[ONBOARD iter={_iter_ob}] step5: checking system permission dialog")
        try:
            allow = driver.find_element(
                AppiumBy.XPATH,
                '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_button"]'
                ' | //*[@text="Allow" and @class="android.widget.Button"]'
                ' | //*[@text="Allow all the time"]'
                ' | //*[@text="While using the app"]',
            )
            allow.click()
            _log(f"[ONBOARD iter={_iter_ob}] step5: system permission Allow clicked ✓")
            time.sleep(5)
            continue
        except Exception:
            _log(f"[ONBOARD iter={_iter_ob}] step5: no system permission dialog")

        _log(f"[ONBOARD iter={_iter_ob}] no step matched → sleep 1s")
        time.sleep(1)

    _final = is_visible(driver, "rcv_all_file", timeout=5)
    _log(f"[ONBOARD] deadline reached, rcv_all_file={_final}")
    return _final


def app_init(driver, cfg: dict) -> bool:
    """
    Khởi tạo app lần đầu sau khi cài mới:
      1. Launch app
      2. Bỏ qua toàn bộ onboarding (chọn ngôn ngữ, cấp quyền đọc file, quyền noti, dismiss ads)
      3. Chờ đến khi vào được màn Home
      4. Kill app

    Gọi 1 lần duy nhất trước khi chạy test suite, sau bước cài APK.
    Trả về True nếu onboarding hoàn thành thành công.
    """
    pkg = cfg["app"]["package_name"]

    print("\n  [INIT] Khởi động app lần đầu để thiết lập...")
    
    # Nhấn Home để đảm bảo bắt đầu từ màn hình chính
    _serial_init = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_init = ["adb", "-s", _serial_init] if _serial_init else ["adb"]
    subprocess.run(_adb_init + ["shell", "input", "keyevent", "3"], capture_output=True)
    time.sleep(2)

    # Launch app
    try:
        driver.activate_app(pkg)
        time.sleep(3)
    except Exception:
        pass

    # Chạy dismiss_onboarding — xử lý toàn bộ luồng onboarding
    result = dismiss_onboarding(driver, cfg)
    print(f"  [INIT] Onboarding {'hoàn thành ✓' if result else 'timeout (tiếp tục)'}")

    # ADB cleanup: nếu vẫn kẹt ở "All files access" sau onboarding → back + relaunch
    # Detect bằng text (uiautomator dump) vì mCurrentFocus không phân biệt được
    _serial_init = os.environ.get("TEST_DEVICE_SERIAL", "")
    _adb_init = ["adb", "-s", _serial_init] if _serial_init else ["adb"]
   
    # Kill app sau khi onboarding xong
    time.sleep(1)
    try:
        driver.terminate_app(pkg)
        print("  [INIT] Đã kill app ✓")
    except Exception:
        subprocess.run(_adb_init + ["shell", "am", "force-stop", pkg], capture_output=True)
        print("  [INIT] Đã kill app (ADB) ✓")

    time.sleep(5)
    
    # Grant tất cả runtime permissions cần thiết qua ADB
    _runtime_perms = [
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VISUAL_USER_SELECTED",
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.CAMERA",
        "android.permission.SCHEDULE_EXACT_ALARM",
    ]
    for perm in _runtime_perms:
        r = subprocess.run(
            _adb_init + ["shell", "pm", "grant", pkg, perm],
            capture_output=True, text=True
        )
        status = "✓" if r.returncode == 0 else f"✗ ({r.stderr.strip()[:60]})"
        print(f"  [INIT] grant {perm.split('.')[-1]}: {status}")

    # MANAGE_EXTERNAL_STORAGE cần appops (không grant được qua pm grant)
    # r = subprocess.run(
    #     _adb_init + ["shell", "appops", "set", pkg, "MANAGE_EXTERNAL_STORAGE", "allow"],
    #     capture_output=True, text=True
    # )
    # print(f"  [INIT] appops MANAGE_EXTERNAL_STORAGE: {'✓' if r.returncode == 0 else '✗'}")

    return result


# Alias — phiên bản mới của dismiss_onboarding: full init flow (activate + onboarding + cleanup + kill + relaunch)
dismiss_onboarding2 = app_init


def _load_config():
    import yaml
    # config.yaml nằm ở project root (1 cấp trên tests/)
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(tests_dir, "..", "config.yaml")
    config_path = os.path.normpath(config_path)
    with open(config_path) as f:
        return yaml.safe_load(f)

def recreate_driver(old_driver=None, device_serial: str = ""):
    """
    Recreate Appium driver session và kết nối lại tới Appium server.
    - Quit old_driver (nếu có)
    - Tạo webdriver.Remote mới theo cfg["appium"], cfg["app"], cfg["device"]
    """
    cfg = _load_config()
    try:
        if old_driver:
            old_driver.quit()
    except Exception:
        pass

    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.app_package = cfg["app"]["package_name"]
    options.app_activity = cfg["app"]["main_activity"]
    options.no_reset = True
    options.auto_grant_permissions = True
    options.new_command_timeout = 120
    options.uiautomator2_server_install_timeout = 60000
    options.adb_exec_timeout = 60000

    if device_serial:
        options.udid = device_serial

    host = cfg["appium"]["host"]
    port = cfg["appium"]["port"]

    drv = webdriver.Remote(f"http://{host}:{port}", options=options)
    try:
        drv.implicitly_wait(cfg["device"]["ui_timeout"])
    except Exception:
        pass
    return drv


def restart_appium_server(port: int = 4723) -> bool:
    """
    Best-effort restart Appium local server.
    Dùng khi UiA2 crash liên tục và cần reset server.
    """
    try:
        _log(f"[APPIUM] restarting server on port {port} ...")
        subprocess.run(["pkill", "-f", "node.*appium"], capture_output=True, timeout=10)
        time.sleep(2)
        subprocess.Popen(
            ["appium", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        _log("[APPIUM] restart issued ✓")
        return True
    except Exception as e:
        _log(f"[APPIUM] restart failed ✗: {e}")
        return False
