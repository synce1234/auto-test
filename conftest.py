"""
conftest.py gốc — dùng chung cho toàn bộ test suite.
Gộp từ tests/conftest.py và test_cases/scripts/conftest.py.
"""
import os
import re
import sys
import base64
import time
import subprocess
import pytest
import yaml
from datetime import datetime

# Đảm bảo project root luôn trong sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Đăng ký tc_pytest_plugin — tự động generate Excel + HTML dashboard khi session kết thúc
pytest_plugins = ["test_cases.tc_pytest_plugin"]

from appium import webdriver
from appium.options.android.uiautomator2.base import UiAutomator2Options
from core.adb_controller import ADBController
from test_cases.tc_pytest_plugin import SESSION_TIMESTAMP
from tests.helpers import close_recentapp2


# ─── Load config ───────────────────────────────────────────────────────────────

def _load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


CFG = _load_config()

_REPORTS_ROOT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
_SCREENSHOT_DIR = os.path.join(_REPORTS_ROOT, "screenshots", SESSION_TIMESTAMP)
_VIDEO_DIR      = os.path.join(_REPORTS_ROOT, "videos",      SESSION_TIMESTAMP)
_LOG_DIR        = os.path.join(_REPORTS_ROOT, "logs",        SESSION_TIMESTAMP)

# Session driver reference — dùng để start recording sớm nhất có thể (trước fixtures)
_session_driver  = None
_recording_active = False  # True khi đang có recording chạy


# ─── Logging helper ────────────────────────────────────────────────────────────

def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n  [{ts}] {msg}")


# ─── Stdout tee (ghi đồng thời ra terminal và buffer để capture log) ───────────

class _TeeWriter:
    """Ghi đồng thời ra stdout thật và StringIO buffer để capture console log."""
    def __init__(self, real, buf):
        self._real = real
        self._buf  = buf

    def write(self, data):
        self._real.write(data)
        self._buf.write(data)

    def flush(self):
        self._real.flush()

    def fileno(self):
        return self._real.fileno()

    def isatty(self):
        return getattr(self._real, "isatty", lambda: False)()


# ─── Driver proxy (cho phép recreate session giữa test) ────────────────────────

class DriverProxy:
    """
    Wrapper giữ reference tới Appium WebDriver hiện tại.
    Cho phép thay thế driver (recreate session) mà không đổi object fixture.
    """
    def __init__(self):
        self._drv = None

    def set_driver(self, drv):
        self._drv = drv

    @property
    def driver(self):
        return self._drv

    def quit(self):
        if self._drv:
            return self._drv.quit()

    def __getattr__(self, name):
        drv = self._drv
        if drv is None:
            raise RuntimeError("DriverProxy chưa có driver instance")
        return getattr(drv, name)


def _create_appium_driver(serial: str = ""):
    """Tạo Appium driver mới (reusable cho initial + recovery)."""
    _log(f"[APPIUM] Creating driver (serial={serial or 'default'})...")
    options = UiAutomator2Options()
    options.platform_name          = "Android"
    options.app_package            = CFG["app"]["package_name"]
    options.app_activity           = CFG["app"]["main_activity"]
    options.no_reset               = True
    options.auto_grant_permissions = True
    options.new_command_timeout    = 120
    options.uiautomator2_server_install_timeout = 60000
    options.adb_exec_timeout                    = 60000

    if serial:
        options.udid = serial

    host = CFG["appium"]["host"]
    port = CFG["appium"]["port"]

    drv = None
    for attempt in range(3):
        try:
            _log(f"[APPIUM] webdriver.Remote attempt {attempt + 1}/3")
            drv = webdriver.Remote(f"http://{host}:{port}", options=options)
            break
        except Exception as e:
            err = str(e)
            need_restart = (
                "Appium Settings app is not running" in err
                or "Connection refused" in err
                or "Failed to establish a new connection" in err
            )
            if need_restart and attempt < 2:
                _log(f"[APPIUM] Connection failed ({type(e).__name__}), restarting Appium (attempt {attempt + 1})...")
                _restart_appium(port, serial)
            else:
                raise

    drv.implicitly_wait(CFG["device"]["ui_timeout"])
    _log("[APPIUM] Driver created ✓")
    # import pdb; pdb.set_trace()
    return drv


def _post_create_driver_init(drv, serial: str = ""):
    """
    Init nhẹ sau khi tạo driver (permission + onboarding) để giảm crash dây chuyền.
    Tránh làm quá nặng; best-effort.
    """
    _adb = ADBController(serial)
    pkg  = CFG["app"]["package_name"]
    _log(f"[DRIVER] Post-create init: grant perms + onboarding (pkg={pkg})")
    for perm in [
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.READ_MEDIA_VIDEO",
        "android.permission.READ_MEDIA_AUDIO",
    ]:
        try:
            _adb._run(["shell", "pm", "grant", pkg, perm])
        except Exception:
            pass
    # MANAGE_EXTERNAL_STORAGE (All Files Access) — phải dùng appops set, không dùng pm grant
    # Cần thiết để app thấy file trong /sdcard/Download/ trên Android 11+
    try:
        _adb._run(["shell", "appops", "set", pkg, "MANAGE_EXTERNAL_STORAGE", "allow"])
    except Exception:
        pass

    # Chờ app khởi động rồi dismiss onboarding/ads best-effort
    time.sleep(CFG["device"]["launch_timeout"])
    try:
        from tests.helpers import dismiss_onboarding2, dismiss_ads, _is_ad_showing
        if _is_ad_showing(drv):
            dismiss_ads(drv)
            time.sleep(1)
        dismiss_onboarding2(drv, CFG)
    except Exception as e:
        _log(f"[DRIVER] init/onboarding warning (recovery): {e}")


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def cfg():
    return CFG


@pytest.fixture(scope="session")
def adb():
    """ADB controller dùng chung — serial lấy từ env var."""
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    return ADBController(serial)


def _wait_for_device(serial: str = "", timeout: int = 60) -> bool:
    """Chờ ADB device online và authorized."""
    adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            adb_prefix + ["shell", "echo", "ok"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and "ok" in result.stdout:
            return True
        time.sleep(2)
    return False


def _restart_appium(port: int, serial: str = ""):
    """Restart Appium server, chờ device authorized và Appium sẵn sàng."""
    _log(f"[APPIUM] Restarting Appium on port {port}...")
    subprocess.run(["pkill", "-f", "node.*appium"], capture_output=True)
    time.sleep(3)
    subprocess.Popen(
        ["appium", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Chờ device authorized trước
    _wait_for_device(serial)
    # Chờ Appium sẵn sàng
    import urllib.request
    for _ in range(20):
        time.sleep(2)
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/status", timeout=2) as r:
                if r.status == 200:
                    _log("[APPIUM] Restart OK ✓")
                    return True
        except Exception:
            pass
    _log("[APPIUM] Restart timeout ✗")
    return False


@pytest.fixture(scope="session")
def driver():
    """Tạo Appium driver 1 lần cho cả session test. Tự restart Appium nếu gặp Settings timeout."""
    global _session_driver
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")

    proxy = DriverProxy()
    drv = _create_appium_driver(serial)
    proxy.set_driver(drv)

    # Lưu reference sớm để pytest_runtest_protocol có thể dùng
    _session_driver = proxy

    adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
    pkg  = CFG["app"]["package_name"]

    # Init đầy đủ như trước (giữ hành vi cũ cho lần tạo driver đầu tiên)
    try:
        from tests.helpers import dismiss_onboarding2, dismiss_ads, _is_ad_showing
        run_init = os.environ.get("RUN_INIT", "0") == "1"
        if run_init:
            print("\n  [INIT] Chạy bước khởi tạo app...")
            # Grant notification permission trước khi launch để tránh popup xin quyền trong onboarding
            print("  [INIT] Grant POST_NOTIFICATIONS via ADB...")
            try:
                _r_notif = subprocess.run(
                    (["adb", "-s", serial] if serial else ["adb"])
                    + ["shell", "pm", "grant", pkg, "android.permission.POST_NOTIFICATIONS"],
                    capture_output=True, text=True, timeout=10,
                )
                print(f"  [INIT] POST_NOTIFICATIONS: {(_r_notif.stdout + _r_notif.stderr).strip() or 'ok'}")
            except Exception as _e_notif:
                print(f"  [INIT] POST_NOTIFICATIONS failed: {_e_notif}")
            # dismiss_onboarding2 = app_init: tự xử lý activate → ads → onboarding → kill → relaunch
            ok = dismiss_onboarding2(proxy, CFG)
            print(f"  [INIT] Onboarding {'hoàn thành ✓' if ok else 'timeout (tiếp tục)'}")
            print("  [INIT] Chờ UiAutomator2 sẵn sàng...")
            _adb_recover_home(serial)
            _wait_uia2_ready(proxy, timeout=40)
            print("  [INIT] Sẵn sàng chạy test ✓")
        else:
            if _is_ad_showing(proxy):
                dismiss_ads(proxy)
                time.sleep(1)
            try:
                proxy.terminate_app(pkg)
            except Exception:
                pass
            time.sleep(1)
            print("  [INIT] Đã kill app ✓")
            try:
                proxy.activate_app(pkg)
                time.sleep(2)
                print("  [INIT] Đã activate lại app ✓")
            except Exception:
                pass
    except Exception as e:
        print(f"\n  [DRIVER] init/onboarding warning: {e}")
        if os.environ.get("RUN_INIT", "0") == "1":
            try:
                _adb_recover_home(serial)
                _wait_uia2_ready(proxy, timeout=40)
            except Exception:
                pass

    yield proxy
    _session_driver = None
    try:
        proxy.quit()
    except Exception:
        pass


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _tc_id_from_item(item) -> str | None:
    """
    Lấy TC ID từ test item.
    Ưu tiên: @pytest.mark.tc_id → tc_result.tc_id → tên class (TestTC001 → TC_001).
    """
    # 1. Từ @pytest.mark.tc_id("TC-026")
    marker = item.get_closest_marker("tc_id")
    if marker and marker.args:
        return str(marker.args[0]).replace("-", "_")

    # 2. Từ tc_result fixture
    funcargs = getattr(item, "funcargs", None)
    if funcargs:
        tc_result_obj = funcargs.get("tc_result")
        tc_id = getattr(tc_result_obj, "tc_id", None) if tc_result_obj else None
        if tc_id:
            return tc_id

    # 3. Từ tên class (TestTC001 → TC_001)
    cls = getattr(item, "cls", None)
    if cls:
        m = re.match(r"TestTC(\d+)", cls.__name__)
        if m:
            return f"TC_{m.group(1).zfill(3)}"

    return None


# ─── Video recording ───────────────────────────────────────────────────────────

def _video_enabled() -> bool:
    return CFG.get("test", {}).get("record_video", False)


def _video_quality() -> str:
    return CFG.get("test", {}).get("video_quality", "medium")


def _save_video(drv, test_name: str) -> str | None:
    """Stop recording và lưu video ra file MP4."""
    try:
        video_b64 = drv.stop_recording_screen()
        if not video_b64:
            return None
        os.makedirs(_VIDEO_DIR, exist_ok=True)
        path = os.path.join(_VIDEO_DIR, f"{test_name}.mp4")
        with open(path, "wb") as f:
            f.write(base64.b64decode(video_b64))
        return path
    except Exception as e:
        print(f"\n  [VIDEO SAVE FAILED] {e}")
        return None


def _do_start_recording(drv) -> bool:
    """Gọi start_recording_screen, trả về True nếu thành công."""
    global _recording_active
    if _recording_active:
        return True
    quality_map = {"high": 8000000, "medium": 4000000, "low": 1000000}
    bit_rate = quality_map.get(_video_quality(), 4000000)
    try:
        drv.start_recording_screen(
            video_size="1080x1920",
            time_limit="600",
            bit_rate=bit_rate,
        )
        _recording_active = True
        return True
    except Exception as e:
        print(f"\n  [VIDEO START FAILED] {e}")
        return False


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """
    Start recording TRƯỚC KHI bất kỳ fixture nào chạy.
    Đồng thời capture toàn bộ stdout (print) trong test → lưu vào reports/logs/<ts>/.
    """
    import io as _io
    global _recording_active
    _recording_active = False  # Reset cho mỗi test
    need_confirm = item.get_closest_marker("need_confirm") is not None
    if _session_driver and (_video_enabled() or need_confirm):
        _do_start_recording(_session_driver)

    # Bắt đầu capture stdout qua tee
    _log_buf      = _io.StringIO()
    _real_stdout  = sys.stdout
    sys.stdout    = _TeeWriter(_real_stdout, _log_buf)

    yield

    # Khôi phục stdout và lưu log
    sys.stdout = _real_stdout
    log_content = _log_buf.getvalue()
    if log_content.strip():
        tc_id = _tc_id_from_item(item)
        fname = f"{tc_id}_{item.name}" if tc_id else item.name
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
            with open(os.path.join(_LOG_DIR, f"{fname}.txt"), "w", encoding="utf-8") as _f:
                _f.write(log_content)
        except Exception:
            pass


def _is_uia2_crash(e: Exception) -> bool:
    """Kiểm tra exception có phải do UiAutomator2 instrumentation crash không."""
    return "instrumentation process is not running" in str(e)


def _adb_recover_home(serial: str = ""):
    """
    Dùng ADB thuần (bypass UiAutomator2) để về Home screen.
    Gọi khi UiAutomator2 bị crash và Appium command không dùng được.
    """
    adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
    _log(f"[ADB] Recover HOME + force-stop UiA2 (serial={serial or 'default'})")
    # Force-stop UiAutomator2 server để Appium restart lại khi cần
    for pkg in ["io.appium.uiautomator2.server", "io.appium.uiautomator2.server.test"]:
        subprocess.run(adb_prefix + ["shell", "am", "force-stop", pkg],
                       capture_output=True)
    # Dùng ADB input để press Home (không cần UiAutomator2)
    subprocess.run(adb_prefix + ["shell", "input", "keyevent", "3"],
                   capture_output=True)
    time.sleep(3)


def _wait_uia2_ready(driver, timeout: int = 30):
    """
    Chờ UiAutomator2 thực sự responsive bằng cách probe liên tục.
    Appium sẽ tự restart UiAutomator2 server khi nhận lệnh đầu tiên sau crash.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            driver.current_activity
            return True  # UiAutomator2 đã sẵn sàng
        except Exception:
            time.sleep(2)
    return False


def _ensure_uia2_alive(driver, serial: str = ""):
    """
    Kiểm tra UiAutomator2 còn sống không bằng cách gọi 1 lệnh nhẹ.
    Nếu fail vì bất kỳ lý do gì → recover để đảm bảo test tiếp theo không bị crash.
    """
    try:
        _log("[UIA2] Probe before test: current_activity")
        driver.current_activity
        print("  [UIA2] OK ✓ (probe current_activity)")
    except Exception as e:
        # Recover cho mọi loại exception (crash, timeout, connection error, v.v.)
        _log(f"[UIA2] Probe failed ({type(e).__name__}) — recovering...")
        _recover_uia2_after_test_if_needed(driver, serial)


def _full_restart_appium_driver(driver_proxy, serial: str = ""):
    """
    Tắt Appium server, bật lại, tạo lại Appium driver session hoàn toàn mới.
    Gọi đầu mỗi test case để đảm bảo UiAutomator2 luôn sạch trạng thái,
    tránh crash tích lũy giữa các test.
    Không chạy onboarding/permission — chỉ tạo session mới thuần túy.
    """
    t0 = time.time()
    _log("[RESTART 1/3] Quit session cũ...")
    try:
        old_drv = getattr(driver_proxy, "_drv", None)
        if old_drv is None:
            old_drv = getattr(driver_proxy, "driver", None)
        if old_drv:
            old_drv.quit()
        _log("[RESTART 1/3] Session cũ đã quit ✓")
    except Exception as e:
        _log(f"[RESTART 1/3] Quit failed (bỏ qua): {e}")

    _log("[RESTART 2/3] Tắt + bật lại Appium server...")
    port = CFG["appium"]["port"]
    ok = _restart_appium(port, serial)
    _log(f"[RESTART 2/3] Appium server {'sẵn sàng ✓' if ok else 'timeout (tiếp tục)'}")

    _log("[RESTART 3/3] Tạo driver session mới...")
    new_drv = _create_appium_driver(serial)

    if hasattr(driver_proxy, "set_driver"):
        driver_proxy.set_driver(new_drv)

    global _session_driver, _recording_active
    _session_driver = driver_proxy

    # Driver mới chưa có recording — start lại nếu video đang bật
    # (hook pytest_runtest_protocol đã start trên driver cũ rồi quit mất)
    if _video_enabled():
        _recording_active = False
        _do_start_recording(driver_proxy)
        _log("[RESTART] Recording khởi động lại trên driver mới ✓")

    elapsed = time.time() - t0
    _log(f"[RESTART DONE] Driver đã reset xong ✓ ({elapsed:.1f}s)")


def _recover_uia2_after_test_if_needed(driver, serial: str = ""):
    """
    Recovery nhẹ sau mỗi test để giảm crash khi chuyển sang test tiếp theo.
    Nếu UiAutomator2 đã crash → recover bằng ADB rồi chờ UiA2 responsive lại.
    """
    try:
        driver.current_activity
        _log(f"[UIA2 CRASH] Recovered")
        return
    except Exception as e:
        if not _is_uia2_crash(e):
            return
        # Level 1: force-stop UiA2 server + HOME, retry 2 lần
        for attempt in range(2):
            _log(f"[UIA2 CRASH] Level 1 recover (attempt {attempt + 1}/2)")
            _adb_recover_home(serial)
            try:
                driver.current_activity
                return
            except Exception as e1:
                if not _is_uia2_crash(e1):
                    return
                time.sleep(2)

        # Level 2: restart Appium + recreate driver session, swap vào proxy
        _log("[UIA2 CRASH] Escalate to level 2: restart Appium + recreate driver session")
        try:
            port = CFG["appium"]["port"]
            _restart_appium(port, serial)
        except Exception as e2:
            _log(f"[APPIUM RESTART FAILED] {e2}")

        # driver ở đây là DriverProxy (session fixture) → swap underlying driver
        try:
            old = getattr(driver, "driver", None)
            try:
                if old:
                    old.quit()
            except Exception:
                pass

            new_drv = _create_appium_driver(serial)
            _post_create_driver_init(new_drv, serial)

            if hasattr(driver, "set_driver"):
                driver.set_driver(new_drv)
            else:
                # Fallback: không phải proxy → không thể swap
                try:
                    new_drv.quit()
                except Exception:
                    pass
                return

            # Cập nhật _session_driver để recording hook dùng đúng instance
            global _session_driver
            _session_driver = driver

            # Probe để chắc chắn session mới hoạt động
            try:
                driver.current_activity
            except Exception:
                pass
        except Exception as e3:
            _log(f"[RECOVER LEVEL2 FAILED] {e3}")
        return


@pytest.fixture(autouse=True)
def setup_before_test(driver):
    """Kill app PDF, xoá recent apps và về home screen trước mỗi test."""
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    # Chờ device sẵn sàng
    _wait_for_device(serial, timeout=30)

    # Kiểm tra và recover UiAutomator2 nếu crash từ test trước
    # _ensure_uia2_alive(driver, serial)

    # Tắt Appium + khởi tạo lại driver hoàn toàn để tránh UiA2 crash tích lũy
    _full_restart_appium_driver(driver, serial)

    # Đảm bảo MANAGE_EXTERNAL_STORAGE luôn được cấp (có thể bị thu hồi sau force-stop)
    pkg = CFG["app"]["package_name"]
    try:
        subprocess.run(
            (["adb", "-s", serial] if serial else ["adb"])
            + ["shell", "appops", "set", pkg, "MANAGE_EXTERNAL_STORAGE", "allow"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass

    # Close app state bằng lifecycle command (shared helper)
    # (thay cho thao tác Recent Apps UI để giảm crash UiAutomator2)
    try:
        close_recentapp2(driver, adb=None, pkg=pkg, home=True)
    except Exception:
        pass

    # Close app/home lại 1 lần nữa để đảm bảo clean state (dùng shared helper)
    try:
        close_recentapp2(driver, adb=None, pkg=pkg, home=True)
    except Exception as e:
        if _is_uia2_crash(e):
            _log("[UIA2 CRASH] close_recentapp2 crashed, recovering via ADB...")
            _adb_recover_home(serial)
            _wait_uia2_ready(driver, timeout=30)
        else:
            pass
    time.sleep(1)

    # Mở app → dismiss App Open Ad → terminate app → về home
    # AdActivity (com.google.android.gms.ads.AdActivity): nút X ở góc trên-phải (~89%, ~4.5%)
    # App Open Ad overlay: "Continue to app >" (~96%, ~10.6%)
    # uiautomator dump không hoạt động khi AdActivity → dùng tap ADB thuần
    adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
    # try:
    #     driver.activate_app(pkg)
    #     time.sleep(5)  # chờ app load + ad xuất hiện

    #     # Lấy screen size bằng ADB (không dùng Appium để tránh crash)
    #     try:
    #         result = subprocess.run(
    #             (["adb", "-s", serial] if serial else ["adb"]) + ["shell", "wm", "size"],
    #             capture_output=True, text=True, timeout=5
    #         )
    #         import re as _re
    #         m = _re.search(r"(\d+)x(\d+)", result.stdout or "")
    #         w, h = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
    #     except Exception:
    #         w, h = 1080, 2400

    #     # Thử nhiều vị trí: nút X AdActivity và "Continue to app" App Open Ad
    #     tap_positions = [
    #         (int(w * 0.89), int(h * 0.045)),  # AdActivity X button (~961, ~108)
    #         (int(w * 0.96), int(h * 0.106)),  # App Open Ad "Continue to app"
    #     ]

    #     # Tap tối đa 10 lần (xen kẽ 2 vị trí), mỗi lần cách nhau 2s
    #     for i in range(10):
    #         tx, ty = tap_positions[i % len(tap_positions)]
    #         subprocess.run(
    #             adb_prefix + ["shell", "input", "tap", str(tx), str(ty)],
    #             capture_output=True,
    #         )
    #         time.sleep(2)
    #         # Kiểm tra AdActivity đã đóng chưa bằng dumpsys
    #         try:
    #             r = subprocess.run(
    #                 adb_prefix + ["shell", "dumpsys", "activity", "activities"],
    #                 capture_output=True, text=True, timeout=5
    #             )
    #             if "gms.ads.AdActivity" not in (r.stdout or ""):
    #                 break
    #         except Exception:
    #             break
    # except Exception:
    #     pass

    # try:
    #     driver.terminate_app(pkg)
    # except Exception:
    #     subprocess.run(adb_prefix + ["shell", "am", "force-stop", pkg], capture_output=True)
    time.sleep(1)
    subprocess.run(adb_prefix + ["shell", "input", "keyevent", "3"], capture_output=True)
    time.sleep(1)
    print("Finish setup before test")

    yield


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    """Chạy sau mỗi test để đảm bảo UiAutomator2 không crash sang test tiếp theo."""
    drv = item.funcargs.get("driver") if hasattr(item, "funcargs") and item.funcargs else None
    if not drv:
        return
    serial = os.environ.get("TEST_DEVICE_SERIAL", "")
    _recover_uia2_after_test_if_needed(drv, serial)


@pytest.fixture(autouse=True)
def video_recorder(driver, request):
    """
    Quay video toàn bộ quá trình test từ lúc start đến khi kết thúc.
    Luôn lưu video sau mỗi test (không phân biệt pass/fail).
    Recording khởi động bởi pytest_runtest_protocol hook (trước mọi fixture).
    Fixture này chỉ start nếu hook chưa start (test đầu tiên của session).
    """
    global _recording_active
    need_confirm = request.node.get_closest_marker("need_confirm") is not None
    if not _video_enabled() and not need_confirm:
        yield
        return

    # Chỉ start nếu hook chưa start (thường là test đầu tiên của session)
    if not _recording_active:
        _do_start_recording(driver)

    yield

    # ── Teardown: dừng và lưu video ──
    _recording_active = False

    tc_id = _tc_id_from_item(request.node)
    fname = f"{tc_id}_{request.node.name}" if tc_id else request.node.name
    path  = _save_video(driver, fname)
    if path:
        print(f"\n  [VIDEO] {path}")


# ─── Ghi kết quả từ @pytest.mark.tc_id ────────────────────────────────────────

_last_printed_tc_id: list[str] = [None]  # dùng list để mutate trong nested scope

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """Map @pytest.mark.tc_id marker → TCManager để update Excel/HTML dashboard."""
    tc_id_log = _tc_id_from_item(item) or item.name
    if tc_id_log != _last_printed_tc_id[0]:
        print(f"\n{'─' * 20} Đang chạy {tc_id_log} {'─' * 20}")
        _last_printed_tc_id[0] = tc_id_log
    start = time.time()
    outcome = yield
    duration = time.time() - start

    # Không xử lý nếu test dùng tc_result fixture (tránh double-write)
    if item.funcargs.get("tc_result"):
        return

    tc_mgr = item.funcargs.get("tc_manager")
    if not tc_mgr:
        return

    marker = item.get_closest_marker("tc_id")
    if not marker or not marker.args:
        return

    tc_id = str(marker.args[0]).replace("-", "_")

    if outcome.excinfo:
        exc_type = outcome.excinfo[0]
        exc_val  = outcome.excinfo[1]
        import _pytest.outcomes as _outcomes
        if exc_type is not None and issubclass(exc_type, _outcomes.Skipped):
            reason = str(exc_val)
            if "NEED CONFIRM" in reason.upper():
                status = "NEED CONFIRM"
            else:
                status = "SKIP"
            actual = reason
        else:
            status = "FAIL"
            actual = str(exc_val)
    else:
        status = "PASS"
        actual = "Test passed"

    tc_mgr.update_result(tc_id=tc_id, status=status, actual=actual, duration=duration)


# ─── Screenshot khi call phase kết thúc ───────────────────────────────────────

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report  = outcome.get_result()

    if report.when != "call":
        return

    drv = item.funcargs.get("driver") if hasattr(item, "funcargs") and item.funcargs else None
    if not drv:
        return

    tc_id = _tc_id_from_item(item)
    fname = f"{tc_id}_{item.name}" if tc_id else item.name

    # Screenshot — chụp cả PASS lẫn FAIL
    if report.passed or report.failed:
        try:
            os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
            suffix = "PASS" if report.passed else "FAIL"
            path   = os.path.join(_SCREENSHOT_DIR, f"{fname}_{suffix}.png")
            drv.save_screenshot(path)
            print(f"\n  [SCREENSHOT] {path}")
        except Exception as e:
            # print(f"\n  [SCREENSHOT FAILED]")
            # Fallback: UiAutomator2 có thể crash → dùng ADB screencap để vẫn có ảnh
            try:
                serial = os.environ.get("TEST_DEVICE_SERIAL", "")
                adb_prefix = ["adb", "-s", serial] if serial else ["adb"]
                # Cách 1: exec-out (nhanh, không cần file tạm trên device)
                r = subprocess.run(
                    adb_prefix + ["exec-out", "screencap", "-p"],
                    capture_output=True,
                    timeout=15,
                )
                if r.returncode == 0 and r.stdout:
                    with open(path, "wb") as f:
                        f.write(r.stdout)
                    print(f"\n  [SCREENSHOT][ADB] {path}")
                else:
                    # Cách 2: screencap ra /sdcard rồi pull về (fallback thêm)
                    safe_fname = re.sub(r"[^\w\-.]", "_", fname)
                    remote = f"/sdcard/Download/{safe_fname}_{suffix}_fallback.png"
                    subprocess.run(adb_prefix + ["shell", "screencap", "-p", remote],
                                   capture_output=True, timeout=15)
                    pull = subprocess.run(adb_prefix + ["pull", remote, path],
                                          capture_output=True, timeout=30)
                    if pull.returncode == 0 and os.path.exists(path):
                        print(f"\n  [SCREENSHOT][ADB-PULL] {path}")
                    subprocess.run(adb_prefix + ["shell", "rm", "-f", remote],
                                   capture_output=True, timeout=10)
            except Exception as e2:
                print(f"\n  [SCREENSHOT][ADB FAILED] {e2}")
