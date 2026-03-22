#!/usr/bin/env python3
"""
Orchestrator - Script chính điều phối toàn bộ update test flow.

Cách dùng:
  python orchestrator.py                        # dùng config.yaml mặc định
  python orchestrator.py --latest apks/v2.6.8.apk
  python orchestrator.py --versions v2.6.5,v2.6.6  # chỉ test 1 số version
  python orchestrator.py --dry-run              # chỉ in flow, không chạy thật
"""
import argparse
import os
import sys
import time
import datetime
import yaml

sys.path.insert(0, os.path.dirname(__file__))

from core.adb_controller import ADBController
from core.app_installer import AppInstaller
from core.device_manager import DeviceManager, get_all_connected_devices


# ─── Màu terminal ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def ok(msg):   print(f"{GREEN}✅ {msg}{RESET}")
def fail(msg): print(f"{RED}❌ {msg}{RESET}")
def info(msg): print(f"{CYAN}ℹ  {msg}{RESET}")
def warn(msg): print(f"{YELLOW}⚠  {msg}{RESET}")


# ─── Load config ──────────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# ─── Chạy pytest test suite ───────────────────────────────────────────────────

def run_tests(report_dir: str, device_serial: str = "", dry_run: bool = False) -> tuple[int, int]:
    """
    Chạy pytest và trả về (passed, total).
    device_serial được truyền qua env var TEST_DEVICE_SERIAL để conftest đọc.
    """
    import subprocess

    os.makedirs(report_dir, exist_ok=True)
    junit_xml = os.path.join(report_dir, "junit.xml")

    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_suite/",
        "-v",
        "--tb=short",
        f"--junitxml={junit_xml}",
    ]

    if dry_run:
        info(f"[DRY RUN] Sẽ chạy: {' '.join(cmd)}")
        return 5, 5

    # Truyền serial vào pytest qua env var
    env = os.environ.copy()
    if device_serial:
        env["TEST_DEVICE_SERIAL"] = device_serial

    print(f"\n  Chạy: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=os.path.dirname(__file__), env=env)

    passed, total = parse_junit_result(junit_xml)
    return passed, total


def parse_junit_result(xml_path: str) -> tuple[int, int]:
    """Parse junit XML để lấy số test pass/total"""
    if not os.path.exists(xml_path):
        return 0, 0
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(xml_path)
        root = tree.getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is None:
            return 0, 0
        total   = int(suite.get("tests", 0))
        errors  = int(suite.get("errors", 0))
        failures= int(suite.get("failures", 0))
        skipped = int(suite.get("skipped", 0))
        passed  = total - errors - failures - skipped
        return passed, total
    except Exception:
        return 0, 0


# ─── Main flow ────────────────────────────────────────────────────────────────

def run_update_test(
    adb: ADBController,
    installer: AppInstaller,
    device_mgr: DeviceManager,
    cfg: dict,
    old_apk: str,
    latest_apk: str,
    report_base: str,
    dry_run: bool = False,
    label: str = "",
    report_folder: str = "",
) -> dict:
    """
    Chạy 1 vòng: cài old_apk → update latest_apk → test.
    Trả về dict kết quả cho version này.
    """
    if not label:
        label = f"{os.path.basename(old_apk)} → {os.path.basename(latest_apk)}"
    if not report_folder:
        report_folder = os.path.basename(old_apk).replace(".apk", "")
    report_dir = os.path.join(report_base, report_folder)

    print(f"\n{'═'*60}")
    print(f"  TEST: {label}")
    print(f"{'═'*60}")

    result = {
        "label": label,
        "old_apk": report_folder,
        "passed": 0,
        "total": 0,
        "status": "FAIL",
        "report_dir": report_dir,
    }

    # B1: Cài APK cũ (clean)
    info("B1: Cài APK version cũ...")
    if not dry_run:
        if not installer.clean_install(old_apk):
            fail("Cài APK cũ thất bại, bỏ qua version này")
            result["status"] = "INSTALL_FAIL"
            return result

        # Mở app 1 lần để init data
        installer.setup_initial_data(
            cfg["app"]["main_activity"],
            cfg["device"]["launch_timeout"],
        )
        # Cấp quyền storage
        device_mgr.prepare_test_storage(cfg["app"]["package_name"])
    else:
        info(f"[DRY RUN] Sẽ cài: {old_apk}")

    # B2: Update lên APK mới nhất
    info("B2: Update lên APK mới nhất...")
    if not dry_run:
        if not installer.update_install(latest_apk):
            fail("Update APK thất bại, bỏ qua version này")
            result["status"] = "UPDATE_FAIL"
            return result
        time.sleep(cfg["device"]["launch_timeout"])
    else:
        info(f"[DRY RUN] Sẽ update: {latest_apk}")

    # B3: Chạy test suite
    info("B3: Chạy test suite...")
    passed, total = run_tests(report_dir, device_serial=adb.serial, dry_run=dry_run)

    result["passed"] = passed
    result["total"]  = total
    result["status"] = "PASS" if passed == total and total > 0 else "FAIL"

    if result["status"] == "PASS":
        ok(f"{label}: {passed}/{total} tests passed")
    else:
        fail(f"{label}: {passed}/{total} tests passed")

    return result


def scan_apks(apks_dir: str) -> list[dict]:
    """
    Quét thư mục apks/, đọc version từng file bằng aapt2.
    Trả về list dict sắp xếp theo versionCode tăng dần:
      [{"path": ..., "version_name": "2.6.5", "version_code": 235}, ...]
    """
    from core.adb_controller import ADBController
    apk_files = sorted([
        os.path.join(apks_dir, f)
        for f in os.listdir(apks_dir)
        if f.endswith(".apk")
    ])

    if not apk_files:
        return []

    print(f"\n[SCAN] Tìm thấy {len(apk_files)} APK trong '{apks_dir}/':")
    entries = []
    for path in apk_files:
        apk_info = ADBController.get_apk_info(path)
        entry = {
            "path": path,
            "version_name": apk_info["version_name"],
            "version_code": apk_info["version_code"],
        }
        entries.append(entry)
        print(f"  • {os.path.basename(path)}")
        print(f"    → versionName={entry['version_name']}  versionCode={entry['version_code']}")

    # Sắp xếp theo versionCode tăng dần
    entries.sort(key=lambda x: x["version_code"])
    return entries


def run_on_device(device: dict, apk_entries: list, cfg: dict, report_base: str, dry_run: bool):
    """Chạy toàn bộ test suite trên 1 device cụ thể."""
    serial = device["serial"]
    label  = f"{device['model']} [{serial}] Android {device['android']}"

    print(f"\n{'█'*60}")
    print(f"  DEVICE: {label}")
    print(f"{'█'*60}")

    adb        = ADBController(serial)
    installer  = AppInstaller(adb, cfg["app"]["package_name"])
    device_mgr = DeviceManager(adb)

    if not dry_run:
        if not device_mgr.check_device_ready():
            fail(f"Device {serial} không sẵn sàng, bỏ qua.")
            return []
        device_mgr.disable_animations()

    latest_entry = apk_entries[-1]
    old_entries  = apk_entries[:-1] if len(apk_entries) > 1 else apk_entries

    latest_apk   = latest_entry["path"]
    device_report = os.path.join(report_base, serial.replace(":", "_"))

    results = []
    for entry in old_entries:
        r = run_update_test(
            adb, installer, device_mgr, cfg,
            entry["path"], latest_apk, device_report,
            dry_run=dry_run,
            label=f"v{entry['version_name']} → v{latest_entry['version_name']}",
            report_folder=f"v{entry['version_name']}",
        )
        r["device"] = label
        results.append(r)

    if not dry_run:
        device_mgr.restore_animations()

    return results


def print_summary(results: list[dict]):
    print(f"\n{'═'*60}")
    print("  TỔNG KẾT")
    print(f"{'═'*60}")
    all_pass = True

    # Nhóm theo device
    by_device = {}
    for r in results:
        dev = r.get("device", "unknown")
        by_device.setdefault(dev, []).append(r)

    for device_label, device_results in by_device.items():
        print(f"\n  [{device_label}]")
        for r in device_results:
            if r["status"] == "PASS":
                ok(f"  {r['label']}: {r['passed']}/{r['total']} tests")
            elif r["status"] in ("INSTALL_FAIL", "UPDATE_FAIL"):
                fail(f"  {r['label']}: {r['status']}")
                all_pass = False
            else:
                fail(f"  {r['label']}: {r['passed']}/{r['total']} tests")
                all_pass = False
    print()
    if all_pass:
        ok("Tất cả devices đều pass!")
    else:
        fail("Có device/version bị fail. Kiểm tra reports/ để xem chi tiết.")


def main():
    parser = argparse.ArgumentParser(description="PDF App Update Auto Test")
    parser.add_argument("--config", default="config.yaml", help="Đường dẫn config file")
    parser.add_argument("--dry-run", action="store_true", help="In flow mà không chạy thật")
    args = parser.parse_args()

    base_dir = os.path.dirname(__file__)

    # Load config
    config_path = os.path.join(base_dir, args.config)
    cfg = load_config(config_path)

    # ── Tự động scan APK ──
    apks_dir = os.path.join(base_dir, cfg["apks"]["dir"])
    if not os.path.isdir(apks_dir):
        fail(f"Thư mục APK không tồn tại: {apks_dir}")
        sys.exit(1)

    apk_entries = scan_apks(apks_dir)
    if not apk_entries:
        fail(f"Không tìm thấy file .apk nào trong '{apks_dir}'")
        sys.exit(1)

    latest_entry = apk_entries[-1]
    print(f"\n[AUTO] Latest APK: {os.path.basename(latest_entry['path'])} (v{latest_entry['version_name']})")
    if len(apk_entries) == 1:
        warn("Chỉ có 1 APK → sẽ test install + smoke (không có update flow)")
    else:
        print(f"[AUTO] Sẽ test update từ {len(apk_entries)-1} version cũ lên latest")

    # ── Tự động phát hiện devices ──
    exclude = cfg["device"].get("exclude", []) or []
    if not args.dry_run:
        devices = get_all_connected_devices(exclude=exclude)
        if not devices:
            fail("Không tìm thấy device nào đang kết nối!")
            fail("  - Kiểm tra USB debugging / Wireless debugging")
            fail("  - Chạy 'adb devices' để xem danh sách")
            sys.exit(1)

        print(f"\n[DEVICES] Tìm thấy {len(devices)} device:")
        for d in devices:
            print(f"  • {d['serial']} | {d['model']} | Android {d['android']} (SDK {d['sdk']})")
    else:
        # Dry-run: giả lập 2 device
        devices = [
            {"serial": "emulator-5554", "model": "Emulator", "android": "16", "sdk": "36"},
            {"serial": "emulator-5556", "model": "Emulator2", "android": "14", "sdk": "34"},
        ]
        print(f"\n[DRY RUN] Giả lập {len(devices)} devices")

    # Folder reports theo timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_base = os.path.join(base_dir, "reports", timestamp)
    os.makedirs(report_base, exist_ok=True)
    info(f"Reports sẽ lưu tại: reports/{timestamp}/")

    # ── Chạy lần lượt từng device ──
    all_results = []
    for i, device in enumerate(devices, 1):
        print(f"\n[{i}/{len(devices)}] Bắt đầu test trên: {device['model']} [{device['serial']}]")
        results = run_on_device(device, apk_entries, cfg, report_base, dry_run=args.dry_run)
        all_results.extend(results)

    # Tổng kết
    print_summary(all_results)


if __name__ == "__main__":
    main()
