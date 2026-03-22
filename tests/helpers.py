"""
Helpers - Các utility dùng chung cho toàn bộ test suite.
"""
import time
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

PKG = "pdf.reader.pdf.viewer.all.document.reader.office.viewer"


def rid(resource_id: str) -> str:
    """Trả về full resource-id string."""
    if ":" in resource_id:
        return resource_id
    return f"{PKG}:id/{resource_id}"


def find(driver, resource_id: str, timeout: int = 10):
    """Tìm element theo resource-id, chờ tối đa timeout giây."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((AppiumBy.ID, rid(resource_id)))
    )


def find_all(driver, resource_id: str, timeout: int = 10) -> list:
    """Tìm tất cả elements theo resource-id."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, rid(resource_id)))
        )
        return driver.find_elements(AppiumBy.ID, rid(resource_id))
    except TimeoutException:
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
        find(driver, resource_id, timeout=timeout)
        return True
    except (TimeoutException, NoSuchElementException):
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

    # Fallback: tap vào vị trí điển hình của "Continue to app" (góc trên phải)
    try:
        size = driver.get_window_size()
        w, h = size["width"], size["height"]
        # "Continue to app >" nằm ở góc trên phải của overlay bar
        candidate_positions = [
            (int(w * 0.80), int(h * 0.055)),  # "Continue to app >" top-right bar
            (int(w * 0.95), int(h * 0.055)),
            (int(w * 0.05), int(h * 0.14)),   # X button top-left
            (int(w * 0.95), int(h * 0.14)),   # X button top-right
        ]
        source_before = driver.page_source
        for x, y in candidate_positions:
            driver.tap([(x, y)])
            time.sleep(1.2)
            source_after = driver.page_source
            if source_after != source_before:
                return True
    except Exception:
        pass

    return False


def _is_ad_showing(driver) -> bool:
    """
    Kiểm tra có đang hiển thị open app ad không.
    AdMob Open App Ad thường chạy trong Activity riêng — cần check nhiều cách.
    """
    try:
        # Cách 1: Check activity name (AdMob dùng AdActivity hoặc tương tự)
        activity = driver.current_activity or ""
        if any(a in activity for a in ["AdActivity", "AdMob", "admob", "InterstitialAd"]):
            return True

        # Cách 2: Check tất cả windows (ad có thể ở window khác)
        current_source = ""
        try:
            handles = driver.window_handles
            original = driver.current_window_handle
            for handle in handles:
                try:
                    driver.switch_to.window(handle)
                    current_source += driver.page_source
                except Exception:
                    pass
            driver.switch_to.window(original)
        except Exception:
            current_source = driver.page_source

        ad_indicators = [
            "Continue to app",
            "com.google.android.gms:id/close_button",
            "com.google.android.gms:id/skip_ad_button",
        ]
        if any(indicator in current_source for indicator in ad_indicators):
            return True

        # Cách 3: XPATH tìm trực tiếp element "Continue to app"
        try:
            el = driver.find_element(
                AppiumBy.XPATH,
                '//*[contains(@text,"Continue to app") or contains(@content-desc,"Continue to app")]'
            )
            return el is not None
        except Exception:
            pass

        return False
    except Exception:
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
            if _is_ad_showing(driver):
                dismiss_ads(driver)
                time.sleep(1)
    except Exception:
        try:
            driver.activate_app(pkg)
            time.sleep(3)
        except Exception:
            pass


def go_to_home(driver, cfg: dict):
    """Navigate về màn hình Home. Dismiss ad và re-launch app nếu cần."""
    ensure_app_foreground(driver, cfg)

    for _ in range(6):
        # Dismiss ad nếu đang show
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)

        if is_visible(driver, "rcv_all_file", timeout=2):
            return True
        try:
            driver.back()
            time.sleep(1)
        except Exception:
            pass

    ensure_app_foreground(driver, cfg)
    return is_visible(driver, "rcv_all_file", timeout=5)


def open_fab_menu(driver):
    """Mở FAB tool menu."""
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
    pkg = cfg["app"]["package_name"]
    deadline = time.time() + 90  # tối đa 90 giây cho toàn bộ onboarding

    while time.time() < deadline:

        # 0. Đảm bảo app ở foreground
        try:
            if driver.current_package != pkg:
                driver.activate_app(pkg)
                time.sleep(3)
        except Exception:
            pass

        # 1. Đã ở home → xong
        if is_visible(driver, "rcv_all_file", timeout=2):
            return True

        # 2. Open App Ad ("Continue to app" hoặc nút X)
        if _is_ad_showing(driver):
            dismiss_ads(driver)
            time.sleep(1)
            continue

        # 3. Language screen → click nút ✓ (btn_continue)
        if is_visible(driver, "btn_continue", timeout=2):
            find(driver, "btn_continue").click()
            time.sleep(2)
            continue

        # 4. App permission dialog (btnDialogConfirm = "Allow" của app)
        if is_visible(driver, "btnDialogConfirm", timeout=2):
            find(driver, "btnDialogConfirm").click()
            time.sleep(2)
            try:
                driver.activate_app(pkg)
                time.sleep(2)
            except Exception:
                pass
            continue

        # 5. System permission dialog — "Allow" button
        try:
            allow = driver.find_element(
                AppiumBy.XPATH,
                '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_button"]'
                ' | //*[@text="Allow" and @class="android.widget.Button"]'
                ' | //*[@text="Allow all the time"]'
                ' | //*[@text="While using the app"]',
            )
            allow.click()
            time.sleep(2)
            try:
                driver.activate_app(pkg)
                time.sleep(2)
            except Exception:
                pass
            continue
        except Exception:
            pass

        # 6. "Allow access to manage all files" toggle (Settings page)
        try:
            toggle = driver.find_element(
                AppiumBy.XPATH,
                '//*[contains(@text,"manage all files") or contains(@text,"Allow access")]',
            )
            toggle.click()
            time.sleep(2)
            driver.back()
            time.sleep(1)
            continue
        except Exception:
            pass

        time.sleep(1)

    return is_visible(driver, "rcv_all_file", timeout=5)
