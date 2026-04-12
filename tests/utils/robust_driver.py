"""
RobustDriver: util wrapper quanh Appium WebDriver với retry + recovery.

Behavior:
- Nếu exception là UiAutomator2 crash → restart Appium server + (best-effort) recreate driver, rồi thử lại.
- Nếu exception khác → fallback dump UI bằng adb (uiautomator dump) → lấy tọa độ bounds → adb input tap.
- Nếu vẫn không được → return False (click/scroll), None (find).
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable, Tuple

from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

_RETRY_EXCEPTIONS = (
    NoSuchElementException,
    StaleElementReferenceException,
    ElementNotInteractableException,
    WebDriverException,
)


class RobustDriver:
    """
    Wraps a WebDriver instance and delegates all attribute access transparently,
    so it can be passed anywhere a WebDriver is expected (e.g. WebDriverWait).

    Extra methods:
        find_with_retry(by, selector, retries=3, delay=1.0) -> WebElement | None
        click_with_retry(element, retries=3, delay=1.0) -> bool

        find(by, selector, ...) -> WebElement | None
        is_visible(by, selector, ...) -> bool
        click(by, selector, ...) -> bool
        scroll_swipe(...) -> bool
    """

    def __init__(self, driver: WebDriver):
        object.__setattr__(self, "_driver", driver)
        object.__setattr__(self, "_serial", os.environ.get("TEST_DEVICE_SERIAL", ""))
        object.__setattr__(self, "_driver_factory", None)
        object.__setattr__(self, "_adb", None)

    def configure_recovery(
        self,
        *,
        serial: str | None = None,
        adb=None,
        driver_factory: Callable[[], WebDriver] | None = None,
    ) -> "RobustDriver":
        """
        Optional config to enable better recovery behaviors.

        - serial: device serial for adb/appium restart (defaults to env TEST_DEVICE_SERIAL)
        - adb: instance of core.adb_controller.ADBController or compatible (has _run())
        - driver_factory: callable returning a new WebDriver session
        """
        if serial is not None:
            object.__setattr__(self, "_serial", serial)
        if adb is not None:
            object.__setattr__(self, "_adb", adb)
        if driver_factory is not None:
            object.__setattr__(self, "_driver_factory", driver_factory)
        return self

    # --- transparent delegation ---

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_driver"), name)

    def __setattr__(self, name, value):
        if name == "_driver":
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "_driver"), name, value)

    # --- recovery helpers ---

    def _is_uia2_crash(self, exc: Exception) -> bool:
        s = str(exc) or ""
        needles = [
            "instrumentation process is not running",
            "uiautomator2",
            "UiAutomator2",
            "The instrumentation process cannot be initialized",
            "Could not proxy command to the remote server",
            "socket hang up",
        ]
        return any(n in s for n in needles)

    def restart_appium_server(self, port: int, serial: str = "") -> bool:
        """
        Restart local Appium server on given port (best-effort).
        """
        try:
            subprocess.run(["pkill", "-f", "node.*appium"], capture_output=True)
        except Exception:
            pass
        time.sleep(3)
        try:
            subprocess.Popen(
                ["appium", "--port", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return False

        adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                r = subprocess.run(
                    adb_prefix + ["shell", "echo", "ok"],
                    capture_output=True,
                    text=True,
                )
                if r.returncode == 0 and "ok" in (r.stdout or ""):
                    break
            except Exception:
                break
            time.sleep(2)

        for _ in range(20):
            time.sleep(2)
            try:
                with urllib.request.urlopen(
                    f"http://localhost:{port}/status", timeout=2
                ) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
        return False

    def _try_recreate_driver_after_restart(self) -> bool:
        factory = object.__getattribute__(self, "_driver_factory")
        if factory:
            try:
                new_drv = factory()
                object.__setattr__(self, "_driver", new_drv)
                return True
            except Exception:
                return False

        # Best-effort recreation from current driver endpoint + capabilities
        try:
            old = object.__getattribute__(self, "_driver")
            url = getattr(getattr(old, "command_executor", None), "_url", None)
            caps = getattr(old, "capabilities", None)
            if not url or not isinstance(caps, dict):
                return False
            from appium import webdriver as _appium_webdriver

            new_drv = _appium_webdriver.Remote(
                command_executor=url, desired_capabilities=caps
            )
            object.__setattr__(self, "_driver", new_drv)
            return True
        except Exception:
            return False

    def _adb_controller(self):
        adb = object.__getattribute__(self, "_adb")
        if adb is not None:
            return adb
        serial = object.__getattribute__(self, "_serial")
        try:
            from core.adb_controller import ADBController

            return ADBController(serial)
        except Exception:
            return None

    def _adb_dump_ui_xml(self, timeout: int = 20) -> str | None:
        adb = self._adb_controller()
        if adb is None:
            return None
        remote = "/sdcard/window_dump.xml"
        try:
            adb._run(["shell", "uiautomator", "dump", remote], timeout=timeout)
            code, out, _ = adb._run(["shell", "cat", remote], timeout=timeout)
            xml = out or ""
            if code != 0 or "<hierarchy" not in xml:
                _, out2, _ = adb._run(["exec-out", "cat", remote], timeout=timeout)
                xml = out2 or xml
            return xml if "<hierarchy" in xml else None
        except Exception:
            return None

    def _center_from_bounds(self, bounds: str) -> Tuple[int, int] | None:
        nums = list(map(int, re.findall(r"\d+", bounds or "")))
        if len(nums) < 4:
            return None
        x1, y1, x2, y2 = nums[0], nums[1], nums[2], nums[3]
        return (x1 + x2) // 2, (y1 + y2) // 2

    def _match_node(self, node: ET.Element, by, selector: str) -> bool:
        by_s = str(by).lower()
        sel = str(selector)
        rid = node.attrib.get("resource-id", "") or ""
        txt = node.attrib.get("text", "") or ""
        desc = node.attrib.get("content-desc", "") or ""

        if "accessibility" in by_s or by_s in ("accessibility_id", "accessibility id"):
            return desc == sel or (sel and sel in desc)
        if by_s in ("id", "resource-id"):
            return rid == sel or rid.endswith(sel) or (sel and sel in rid)
        if "xpath" in by_s:
            return False
        return bool(sel) and (sel in rid or sel in txt or sel in desc)

    def _adb_exists_by_locator(self, by, selector: str) -> bool:
        xml = self._adb_dump_ui_xml()
        if not xml:
            return False
        try:
            root = ET.fromstring(xml)
        except Exception:
            return False
        for n in root.iter():
            if n.tag != "node":
                continue
            if self._match_node(n, by, selector):
                return True
        return False

    def _adb_tap_by_locator(self, by, selector: str) -> bool:
        adb = self._adb_controller()
        if adb is None:
            return False
        xml = self._adb_dump_ui_xml()
        if not xml:
            return False
        try:
            root = ET.fromstring(xml)
        except Exception:
            return False

        bounds = None
        for n in root.iter():
            if n.tag != "node":
                continue
            if self._match_node(n, by, selector):
                bounds = n.attrib.get("bounds")
                if bounds:
                    break
        if not bounds:
            return False
        center = self._center_from_bounds(bounds)
        if not center:
            return False
        cx, cy = center
        try:
            adb._run(["shell", "input", "tap", str(cx), str(cy)], timeout=10)
            return True
        except Exception:
            return False

    # --- higher-level wrappers (locator-based) ---

    def find(self, by, selector, retries: int = 3, delay: float = 1.0):
        """
        Robust find_element:
        - If UiA2 crash: restart Appium via restart_appium_server() then try again.
        - Otherwise: retry and return None.
        """
        for attempt in range(retries):
            driver = object.__getattribute__(self, "_driver")
            try:
                return driver.find_element(by, selector)
            except _RETRY_EXCEPTIONS as exc:
                if self._is_uia2_crash(exc):
                    serial = object.__getattribute__(self, "_serial")
                    port = int(os.environ.get("APPIUM_PORT", "4723"))
                    self.restart_appium_server(port, serial)
                    self._try_recreate_driver_after_restart()
                if attempt < retries - 1:
                    time.sleep(delay)
        return None

    def is_visible(self, by, selector, retries: int = 2, delay: float = 0.5) -> bool:
        el = self.find(by, selector, retries=retries, delay=delay)
        if not el:
            return self._adb_exists_by_locator(by, str(selector))
        try:
            return bool(el.is_displayed())
        except Exception:
            return self._adb_exists_by_locator(by, str(selector))

    def click(self, by, selector, retries: int = 3, delay: float = 1.0) -> bool:
        """
        Robust click:
        - UiA2 crash: restart Appium + recreate driver (best-effort) then retry
        - Other exceptions: adb dump UI + coordinates + adb tap
        - If adb still fails: False
        """
        for attempt in range(retries):
            try:
                el = self.find(by, selector, retries=1, delay=delay)
                if el is None:
                    raise NoSuchElementException(f"Not found: {by}={selector}")
                el.click()
                return True
            except _RETRY_EXCEPTIONS as exc:
                if self._is_uia2_crash(exc):
                    serial = object.__getattribute__(self, "_serial")
                    port = int(os.environ.get("APPIUM_PORT", "4723"))
                    self.restart_appium_server(port, serial)
                    self._try_recreate_driver_after_restart()
                    if attempt < retries - 1:
                        time.sleep(delay)
                    continue

                return self._adb_tap_by_locator(by, str(selector))
        return False

    def open_notification_shade(self, retries: int = 2, delay: float = 1.0) -> bool:
        """
        Kéo notification shade xuống.

        Ưu tiên:
        - Appium: driver.open_notifications()
        Recovery:
        - UiA2 crash: restart Appium + recreate driver, rồi thử lại.
        - Lỗi khác: fallback ADB swipe từ mép trên xuống.
        """
        serial = object.__getattribute__(self, "_serial")
        port = int(os.environ.get("APPIUM_PORT", "4723"))

        for attempt in range(retries):
            try:
                driver = object.__getattribute__(self, "_driver")
                driver.open_notifications()
                return True
            except Exception as exc:
                if self._is_uia2_crash(exc):
                    self.restart_appium_server(port, serial)
                    self._try_recreate_driver_after_restart()
                    if attempt < retries - 1:
                        time.sleep(delay)
                    continue

                # fallback ADB swipe
                adb = self._adb_controller()
                if adb is None:
                    return False
                try:
                    # Swipe down from near top-center
                    w, h = 1080, 2400
                    try:
                        driver = object.__getattribute__(self, "_driver")
                        size = driver.get_window_size()
                        w, h = int(size.get("width", w)), int(size.get("height", h))
                    except Exception:
                        pass
                    x = w // 2
                    y1 = int(h * 0.02)
                    y2 = int(h * 0.45)
                    adb._run(
                        ["shell", "input", "swipe", str(x), str(y1), str(x), str(y2), "300"],
                        timeout=10,
                    )
                    return True
                except Exception:
                    return False
        return False

    # ── Ad dismissal ──────────────────────────────────────────────────────────

    # Activities được coi là ad overlay
    _AD_ACTIVITIES = (
        "adactivity",
        "mraid",
        "admob",
        "adsactivity",
        "interstitial",
        "com.google.android.gms.ads",
    )

    # Resource-id phổ biến của nút đóng ad
    _AD_CLOSE_RIDS = (
        "closeButton",
        "close_button",
        "close",
        "dismiss",
        "cancel",
        "com.google.android.gms:id/cancel",
        "com.google.android.gms:id/close_button",
        "com.google.android.gms:id/closeButton",
    )

    # Text / content-desc phổ biến của nút đóng ad
    _AD_CLOSE_TEXTS = (
        "Continue to app", "닫기", "Close", "close", "CLOSE",
        "Skip", "SKIP", "Skip Ad", "Skip ad",
        "X", "✕", "×",
        "Dismiss", "DISMISS",
    )

    def is_ad_visible(self) -> bool:
        import subprocess as _sp_ad
        serial = os.environ.get("TEST_DEVICE_SERIAL", "")
        _adb_ad = ["adb", "-s", serial] if serial else ["adb"]
        time.sleep(5)
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
            driver = object.__getattribute__(self, "_driver")
            activity = driver.current_activity or ""
            if any(a in activity for a in ["AdActivity", "AdMob", "admob", "InterstitialAd"]):
                return True
        except Exception:
            pass
        return False

    def dismiss_ad(self, timeout: float = 5.0) -> bool:
        """
        Đóng interstitial ad nếu đang hiển thị.

        Chiến lược (theo thứ tự ưu tiên):
        1. Kiểm tra activity → nếu không phải ad, return False ngay.
        2. Appium: tìm nút đóng qua resource-id / text / content-desc phổ biến.
        3. ADB dump UI → parse XML → tìm và tap nút đóng
           (uiautomator dump đôi khi bị block bởi ad overlay, nên có guard).
        4. Fallback cuối: nhấn Back.

        Args:
            timeout: thời gian tối đa (giây) cho mỗi lần Appium find_element.

        Returns:
            True  – đóng được ad (hoặc ad tự biến mất).
            False – không phát hiện ad hoặc không đóng được.
        """
        if not self.is_ad_visible():
            return False

        print("  [AD] Phát hiện ad overlay, đang cố đóng...")

        driver = object.__getattribute__(self, "_driver")
        adb = self._adb_controller()

        # Tạm giảm implicit_wait để find không chờ quá lâu, restore sau
        try:
            driver.implicitly_wait(min(timeout, 2.0))
        except Exception:
            pass

        try:
            result = self._dismiss_ad_inner(driver, adb)
        finally:
            try:
                driver.implicitly_wait(timeout)
            except Exception:
                pass
        return result

    def _dismiss_ad_inner(self, driver, adb) -> bool:
        from appium.webdriver.common.appiumby import AppiumBy
        from selenium.webdriver.common.by import By

        # ── Layer 1: Appium – resource-id ─────────────────────────────────────
        print("  [AD] Layer 1: tìm nút đóng bằng Appium resource-id...")
        for rid in self._AD_CLOSE_RIDS:
            try:
                el = driver.find_element(By.ID, rid)
                if el and el.is_displayed():
                    el.click()
                    print(f"  [AD] ✓ Đóng via Appium resource-id={rid}")
                    time.sleep(0.8)
                    return True
            except Exception:
                pass
        print("  [AD] Layer 1: không tìm thấy")

        # ── Layer 2: Appium – text / content-desc ─────────────────────────────
        print("  [AD] Layer 2: tìm nút đóng bằng Appium text/content-desc...")
        for text in self._AD_CLOSE_TEXTS:
            for by, tmpl in (
                (By.XPATH, f'//android.widget.Button[@text="{text}"]'),
                (By.XPATH, f'//*[@text="{text}"]'),
                (By.XPATH, f'//*[@content-desc="{text}"]'),
                (AppiumBy.ACCESSIBILITY_ID, text),
            ):
                try:
                    el = driver.find_element(by, tmpl)
                    if el and el.is_displayed():
                        el.click()
                        print(f"  [AD] ✓ Đóng via Appium text/desc={repr(text)}")
                        time.sleep(0.8)
                        return True
                except Exception:
                    pass
        print("  [AD] Layer 2: không tìm thấy")

        # ── Layer 3: ADB dump UI ───────────────────────────────────────────────
        print("  [AD] Layer 3: tìm nút đóng bằng ADB uiautomator dump...")
        if adb is not None:
            xml = None
            try:
                remote = "/sdcard/uidump_ad.xml"
                adb._run(["shell", "rm", "-f", remote], timeout=3)
                rc, _, _ = adb._run(
                    ["shell", "uiautomator", "dump", remote], timeout=6
                )
                print(f"  [AD] Layer 3: uiautomator dump rc={rc}")
                if rc == 0:
                    _, xml_out, _ = adb._run(["shell", "cat", remote], timeout=5)
                    if "<hierarchy" in (xml_out or ""):
                        xml = xml_out
                        print("  [AD] Layer 3: dump XML OK")
                    else:
                        print("  [AD] Layer 3: dump XML trống hoặc không hợp lệ")
            except Exception as e:
                print(f"  [AD] Layer 3: exception khi dump: {e}")

            if xml:
                try:
                    root = ET.fromstring(xml)
                    for node in root.iter("node"):
                        rid = node.get("resource-id", "")
                        txt = node.get("text", "")
                        desc = node.get("content-desc", "")
                        is_close = (
                            any(r in rid for r in self._AD_CLOSE_RIDS)
                            or txt in self._AD_CLOSE_TEXTS
                            or desc in self._AD_CLOSE_TEXTS
                        )
                        if is_close:
                            bounds = node.get("bounds", "")
                            center = self._center_from_bounds(bounds)
                            if center:
                                cx, cy = center
                                adb._run(
                                    ["shell", "input", "tap", str(cx), str(cy)],
                                    timeout=5,
                                )
                                print(
                                    f"  [AD] ✓ Đóng via ADB dump tap ({cx},{cy})"
                                    f" text={repr(txt)} desc={repr(desc)}"
                                )
                                time.sleep(0.8)
                                return True
                    print("  [AD] Layer 3: không tìm thấy node đóng trong XML")
                except Exception as e:
                    print(f"  [AD] Layer 3: exception khi parse XML: {e}")
        else:
            print("  [AD] Layer 3: bỏ qua (không có ADB controller)")

        # ── Layer 4: Fallback – nhấn Back ─────────────────────────────────────
        print("  [AD] Layer 4 (fallback): nhấn Back để đóng ad")
        try:
            driver.press_keycode(4)  # KEYCODE_BACK
            time.sleep(0.8)
            if not self.is_ad_visible():
                print("  [AD] ✓ Đóng via Appium press_keycode(Back)")
                return True
        except Exception as e:
            print(f"  [AD] Layer 4: press_keycode thất bại: {e}")

        if adb is not None:
            try:
                adb._run(["shell", "input", "keyevent", "4"], timeout=5)
                time.sleep(0.8)
                if not self.is_ad_visible():
                    print("  [AD] ✓ Đóng via ADB keyevent Back")
                    return True
            except Exception as e:
                print(f"  [AD] Layer 4: ADB keyevent thất bại: {e}")

        print("  [AD] ✗ Tất cả layers đều thất bại, không thể đóng ad")
        return False

    def dismiss_ad_if_any(self, max_attempts: int = 3, delay: float = 1.0) -> bool:
        """
        Kiểm tra và đóng ad nhiều lần nếu cần (ví dụ khi có nhiều lớp ad).

        Returns True nếu đóng được ít nhất 1 ad.
        """
        print(f"  [AD] dismiss_ad_if_any: kiểm tra ad (tối đa {max_attempts} lần)")
        closed_any = False
        for attempt in range(max_attempts):
            if not self.is_ad_visible():
                print(f"  [AD] dismiss_ad_if_any: không có ad (attempt {attempt + 1})")
                break
            print(f"  [AD] dismiss_ad_if_any: attempt {attempt + 1}/{max_attempts}")
            if self.dismiss_ad():
                closed_any = True
                time.sleep(delay)
            else:
                break
        print(f"  [AD] dismiss_ad_if_any: kết quả closed_any={closed_any}")
        return closed_any

    def scroll_swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 400,
    ) -> bool:
        """
        Scroll by swipe with fallback to adb input swipe.
        """
        try:
            driver = object.__getattribute__(self, "_driver")
            driver.swipe(start_x, start_y, end_x, end_y, duration_ms)
            return True
        except Exception as exc:
            if self._is_uia2_crash(exc):
                serial = object.__getattribute__(self, "_serial")
                port = int(os.environ.get("APPIUM_PORT", "4723"))
                self.restart_appium_server(port, serial)
                self._try_recreate_driver_after_restart()
                try:
                    driver = object.__getattribute__(self, "_driver")
                    driver.swipe(start_x, start_y, end_x, end_y, duration_ms)
                    return True
                except Exception:
                    pass

            adb = self._adb_controller()
            if adb is None:
                return False
            try:
                adb._run(
                    [
                        "shell",
                        "input",
                        "swipe",
                        str(start_x),
                        str(start_y),
                        str(end_x),
                        str(end_y),
                        str(duration_ms),
                    ],
                    timeout=10,
                )
                return True
            except Exception:
                return False

