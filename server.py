#!/usr/bin/env python3
"""
Auto Test Web Dashboard - Local web server

Cách chạy:
  python server.py                        # dùng thư mục chứa script
  python server.py --dir /path/to/proj   # chỉ định thư mục project
  python server.py --port 9090           # đổi port (mặc định 8080)
  → Mở trình duyệt: http://localhost:8080
"""
import os
import sys
import json
import yaml
import queue
import argparse
import threading
import subprocess
import datetime
from pathlib import Path
from flask import Flask, jsonify, request, Response, send_from_directory
from werkzeug.utils import secure_filename

# ── CLI args (parse trước khi import bất kỳ thứ gì dùng BASE_DIR) ─────────────
_parser = argparse.ArgumentParser(description="Auto Test Dashboard")
_parser.add_argument(
    "--dir", default="",
    help="Thư mục gốc của auto-test project (mặc định: thư mục chứa server.py)",
)
_parser.add_argument(
    "--port", type=int, default=8080,
    help="Port server (mặc định: 8080)",
)
_args, _ = _parser.parse_known_args()

BASE_DIR = (
    os.path.abspath(_args.dir)
    if _args.dir
    else os.path.dirname(os.path.abspath(__file__))
)

def _safe_apk_name(filename: str) -> str:
    """Sanitize APK filename: strip path separators but keep original characters."""
    name = os.path.basename(filename).strip()
    if not name or "/" in name or "\\" in name or "\x00" in name:
        return ""
    return name

sys.path.insert(0, BASE_DIR)

from core.adb_controller import ADBController

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "web"))

# ── Config ────────────────────────────────────────────────────────────────────

def _load_cfg():
    with open(os.path.join(BASE_DIR, "config.yaml")) as f:
        return yaml.safe_load(f)

CFG = _load_cfg()
APKS_DIR    = os.path.join(BASE_DIR, CFG["apks"]["dir"])
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
# Ưu tiên tests/test_suite (active suite), fallback về test_cases/scripts (legacy)
_TEST_SUITE_DIR = os.path.join(BASE_DIR, "tests", "test_suite")
_LEGACY_DIR     = os.path.join(BASE_DIR, "test_cases", "scripts")
SCRIPTS_DIR = _TEST_SUITE_DIR if os.path.isdir(_TEST_SUITE_DIR) else _LEGACY_DIR

# ── Global run state ──────────────────────────────────────────────────────────

_run_lock  = threading.Lock()
_run_queue: queue.Queue = queue.Queue()
_run_active = False
_run_proc: subprocess.Popen | None = None


# ── Routes: frontend ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE_DIR, "web"), "index.html")


# ── API: APKs ─────────────────────────────────────────────────────────────────

@app.route("/api/apks")
def api_list_apks():
    os.makedirs(APKS_DIR, exist_ok=True)
    apks = []
    for fname in sorted(os.listdir(APKS_DIR)):
        if not fname.endswith(".apk"):
            continue
        path = os.path.join(APKS_DIR, fname)
        info = ADBController.get_apk_info(path)
        apks.append({
            "filename":     fname,
            "version_name": info["version_name"],
            "version_code": info["version_code"],
            "size_mb":      round(os.path.getsize(path) / 1024 / 1024, 1),
            "modified":     datetime.datetime.fromtimestamp(
                                os.path.getmtime(path)
                            ).strftime("%Y-%m-%d %H:%M"),
        })
    return jsonify(apks)


@app.route("/api/apks/upload", methods=["POST"])
def api_upload_apk():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files["file"]
    if not f.filename or not f.filename.endswith(".apk"):
        return jsonify({"error": "File must be .apk"}), 400
    fname = secure_filename(f.filename)
    os.makedirs(APKS_DIR, exist_ok=True)
    save_path = os.path.join(APKS_DIR, fname)
    f.save(save_path)
    info = ADBController.get_apk_info(save_path)
    return jsonify({
        "ok": True,
        "filename":     fname,
        "version_name": info["version_name"],
        "version_code": info["version_code"],
    })


@app.route("/api/apks/<filename>", methods=["DELETE"])
def api_delete_apk(filename):
    path = os.path.join(APKS_DIR, _safe_apk_name(filename))
    if not os.path.isfile(path):
        return jsonify({"error": "Not found"}), 404
    os.remove(path)
    return jsonify({"ok": True})


# ── API: Devices ──────────────────────────────────────────────────────────────

@app.route("/api/devices")
def api_devices():
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")[1:]
        devices = []
        for line in lines:
            line = line.strip()
            if "\t" not in line or "offline" in line:
                continue
            serial = line.split("\t")[0]
            adb  = ADBController(serial)
            info = adb.get_device_info()
            devices.append({
                "serial":  serial,
                "model":   info.get("model", serial),
                "android": info.get("android_version", "?"),
            })
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: TC Map (TC ID → pytest node ID) ─────────────────────────────────

def _build_tc_map() -> dict:
    """
    Scan test files từ cả 2 thư mục → {TC_ID: pytest_node_id}.
    Ưu tiên: @pytest.mark.tc_id marker → tên class TestTC001 → TC_001.
    """
    import ast as _ast
    import re as _re
    tc_map = {}

    scan_dirs = []
    # Legacy dir trước — class-name mapping (TestTC001→TC_001) có ưu tiên cao nhất
    if os.path.isdir(_LEGACY_DIR):
        scan_dirs.append((_LEGACY_DIR, "marker+class"))
    # Test suite sau — marker-based, chỉ map nếu TC ID chưa có trong map
    if os.path.isdir(SCRIPTS_DIR) and SCRIPTS_DIR != _LEGACY_DIR:
        scan_dirs.append((SCRIPTS_DIR, "marker+class"))

    for scan_dir, mode in scan_dirs:
        rel_base = os.path.relpath(scan_dir, BASE_DIR)
        for fname in sorted(os.listdir(scan_dir)):
            if not (fname.startswith("test_") and fname.endswith(".py")):
                continue
            fpath = os.path.join(scan_dir, fname)
            rel_path = os.path.join(rel_base, fname)
            try:
                with open(fpath) as f:
                    tree = _ast.parse(f.read())
                for cls_node in _ast.walk(tree):
                    if not (isinstance(cls_node, _ast.ClassDef) and cls_node.name.startswith("Test")):
                        continue

                    # 1. Marker-based: @pytest.mark.tc_id trên từng method
                    for func_node in cls_node.body:
                        if not (isinstance(func_node, _ast.FunctionDef) and func_node.name.startswith("test_")):
                            continue
                        for deco in func_node.decorator_list:
                            if not isinstance(deco, _ast.Call):
                                continue
                            attr = getattr(deco.func, "attr", None) or getattr(deco.func, "id", None)
                            if attr == "tc_id" and deco.args and isinstance(deco.args[0], _ast.Constant):
                                tc_id = str(deco.args[0].value).replace("-", "_")
                                # Marker trỏ vào method cụ thể (không chạy cả class)
                                if tc_id not in tc_map:
                                    tc_map[tc_id] = f"{rel_path}::{cls_node.name}::{func_node.name}"

                    # 2. Class-name-based: TestTC001 → TC_001 (nếu chưa có trong map)
                    m = _re.match(r"TestTC(\d+)$", cls_node.name)
                    if m:
                        tc_id = f"TC_{m.group(1).zfill(3)}"
                        if tc_id not in tc_map:
                            tc_map[tc_id] = f"{rel_path}::{cls_node.name}"

            except Exception:
                pass

    return tc_map


@app.route("/api/testcases")
def api_testcases():
    """Trả về toàn bộ TC database kèm trạng thái automation."""
    try:
        import openpyxl as _xl
        tc_map = _build_tc_map()
        tc_excel = os.path.join(BASE_DIR, "test_cases", "test_cases.xlsx")
        tcs = []
        if os.path.exists(tc_excel):
            wb = _xl.load_workbook(tc_excel, read_only=True, data_only=True)
            ws = wb["Test Cases"]
            row_num = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row[0]:
                    continue
                row_num += 1
                tc_id = str(row[0]).strip()
                tcs.append({
                    "rowId":     row_num,   # ID cố định theo thứ tự trong Excel
                    "id":        tc_id,
                    "group":     str(row[1] or "").strip(),
                    "title":     str(row[2] or "").strip(),
                    "status":    str(row[7] or "NOT RUN").strip().upper(),
                    "automated": tc_id in tc_map,
                    "nodeid":    tc_map.get(tc_id, ""),
                })
        return jsonify(tcs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Test scripts ─────────────────────────────────────────────────────────

@app.route("/api/test-scripts")
def api_test_scripts():
    scripts = []
    if os.path.isdir(SCRIPTS_DIR):
        for fname in sorted(os.listdir(SCRIPTS_DIR)):
            if fname.startswith("test_") and fname.endswith(".py"):
                # Parse class / function names for display
                fpath = os.path.join(SCRIPTS_DIR, fname)
                cases = _parse_test_cases(fpath)
                scripts.append({"filename": fname, "cases": cases})
    return jsonify(scripts)


def _parse_test_cases(path: str) -> list[dict]:
    """Extract class-level test case names from a test file."""
    import ast
    cases = []
    try:
        with open(path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                methods = [
                    n.name for n in ast.walk(node)
                    if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
                ]
                cases.append({"cls": node.name, "methods": methods})
    except Exception:
        pass
    return cases


# ── API: Run tests ────────────────────────────────────────────────────────────

@app.route("/api/run/status")
def api_run_status():
    return jsonify({"running": _run_active})


@app.route("/api/run", methods=["POST"])
def api_start_run():
    global _run_active, _run_proc, _run_queue

    with _run_lock:
        if _run_active:
            return jsonify({"error": "Test already running"}), 409
        _run_active = True
        _run_queue  = queue.Queue()

    data          = request.json or {}
    device_serial = data.get("device", "")
    scripts       = data.get("scripts", [])      # ["test_open_app.py::TestTC001", ...]
    install_apks  = data.get("install_apks", []) # list of filenames in apks/
    run_init      = data.get("run_init", False)  # chạy bước khởi tạo app trước test

    # Build pytest args — node IDs từ _build_tc_map() là path tương đối từ BASE_DIR
    if scripts:
        test_paths = []
        for s in scripts:
            if "::" in s:
                rel_path, node = s.split("::", 1)
                # Nếu rel_path đã chứa '/' → là relative path từ BASE_DIR
                if os.sep in rel_path or "/" in rel_path:
                    test_paths.append(os.path.join(BASE_DIR, rel_path) + "::" + node)
                else:
                    test_paths.append(os.path.join(SCRIPTS_DIR, rel_path) + "::" + node)
            else:
                if os.sep in s or "/" in s:
                    test_paths.append(os.path.join(BASE_DIR, s))
                else:
                    test_paths.append(os.path.join(SCRIPTS_DIR, s))
    else:
        test_paths = [SCRIPTS_DIR]

    # rootdir = BASE_DIR để pytest tìm conftest.py ở root
    cmd = [sys.executable, "-m", "pytest"] + test_paths + [
        "--rootdir", BASE_DIR,
        "-v", "--tb=short", "--no-header",
        "-s",  # Không capture stdout để print() trong fixtures hiển thị real-time
    ]

    env = os.environ.copy()
    if device_serial:
        env["TEST_DEVICE_SERIAL"] = device_serial

    def _run_thread():
        global _run_active, _run_proc
        try:
            # Optional: uninstall + install APKs in order
            pkg_name = CFG.get("app", {}).get("package_name", "")
            for apk_fname in install_apks:
                apk_path = os.path.join(APKS_DIR, _safe_apk_name(apk_fname))
                if not os.path.isfile(apk_path):
                    _emit({"type": "log", "text": f"[INSTALL] SKIP (not found): {apk_fname}"})
                    continue

                adb_prefix = ["adb"]
                if device_serial:
                    adb_prefix += ["-s", device_serial]

                # Bước 1: Gỡ APK hiện tại
                if pkg_name:
                    _emit({"type": "log", "text": f"[UNINSTALL] Gỡ {pkg_name}..."})
                    r_un = subprocess.run(
                        adb_prefix + ["uninstall", pkg_name],
                        capture_output=True, text=True, timeout=60
                    )
                    un_out = (r_un.stdout + r_un.stderr).strip()
                    _emit({"type": "log", "text": f"[UNINSTALL] {un_out or 'done'}"})

                # Bước 2: Cài APK mới
                _emit({"type": "log", "text": f"[INSTALL] Cài {apk_fname}..."})
                r = subprocess.run(
                    adb_prefix + ["install", apk_path],
                    capture_output=True, text=True, timeout=120
                )
                ok = r.returncode == 0 and "Success" in r.stdout
                _emit({"type": "log", "text": f"[INSTALL] {'OK ✓' if ok else 'FAILED ✗'} {r.stdout.strip() or r.stderr.strip()}"})
                if not ok:
                    _emit({"type": "done", "code": 1})
                    return

            # Truyền RUN_INIT vào env để conftest.py xử lý trong cùng Appium session
            if run_init:
                env["RUN_INIT"] = "1"
                _emit({"type": "log", "text": "[INIT] Bước khởi tạo app sẽ chạy trước test case đầu tiên"})
                _emit({"type": "log", "text": ""})

            # Run pytest
            _emit({"type": "log", "text": f"[CMD] {' '.join(cmd)}"})
            _emit({"type": "log", "text": ""})
            proc = subprocess.Popen(
                cmd, cwd=BASE_DIR, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            _run_proc = proc
            for line in proc.stdout:
                _emit({"type": "log", "text": line.rstrip()})
            proc.wait()
            _emit({"type": "done", "code": proc.returncode})
        except Exception as e:
            _emit({"type": "log",  "text": f"[ERROR] {e}"})
            _emit({"type": "done", "code": -1})
        finally:
            _run_active = False
            _run_proc   = None

    threading.Thread(target=_run_thread, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/run/stop", methods=["POST"])
def api_stop_run():
    global _run_proc
    if _run_proc:
        _run_proc.terminate()
    return jsonify({"ok": True})


@app.route("/api/run/stream")
def api_run_stream():
    """Server-Sent Events stream for live test output."""
    def generate():
        while True:
            try:
                msg = _run_queue.get(timeout=30)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("type") == "done":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _emit(msg: dict):
    _run_queue.put(msg)


# ── API: Config ───────────────────────────────────────────────────────────────

_CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Trả về nội dung config.yaml dưới dạng JSON."""
    try:
        with open(_CONFIG_PATH) as f:
            cfg = yaml.safe_load(f)
        return jsonify(cfg)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config", methods=["POST"])
def api_save_config():
    """Cập nhật config.yaml từ JSON gửi lên. Chỉ cập nhật các field đã biết."""
    try:
        data = request.json or {}
        with open(_CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}

        # Merge từng section — chỉ ghi đè key đã biết, giữ nguyên phần còn lại
        _merge = lambda dst, src: dst.update({k: v for k, v in src.items() if v is not None}) if src else None

        if "app" in data:
            cfg.setdefault("app", {})
            _merge(cfg["app"], data["app"])
        if "appium" in data:
            cfg.setdefault("appium", {})
            _merge(cfg["appium"], data["appium"])
        if "device" in data:
            cfg.setdefault("device", {})
            _merge(cfg["device"], data["device"])
        if "test" in data:
            cfg.setdefault("test", {})
            # Booleans được phép là False nên xử lý riêng
            for k, v in (data["test"] or {}).items():
                if v is not None:
                    cfg["test"][k] = v
        if "apks" in data:
            cfg.setdefault("apks", {})
            _merge(cfg["apks"], data["apks"])

        with open(_CONFIG_PATH, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Reload global CFG
        global CFG
        CFG = _load_cfg()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Reports ──────────────────────────────────────────────────────────────

@app.route("/api/reports")
def api_reports():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    reports = []
    for fname in sorted(os.listdir(REPORTS_DIR), reverse=True):
        if not (fname.startswith("dashboard_") and fname.endswith(".html")):
            continue
        ts   = fname.replace("dashboard_", "").replace(".html", "")
        path = os.path.join(REPORTS_DIR, fname)
        # Count pass/fail from matching xlsx
        xlsx = os.path.join(REPORTS_DIR, f"report_{ts}.xlsx")
        reports.append({
            "ts":       ts,
            "filename": fname,
            "size_kb":  round(os.path.getsize(path) / 1024),
            "has_xlsx": os.path.isfile(xlsx),
        })
    return jsonify(reports)


@app.route("/reports/<path:filename>")
def serve_report(filename):
    return send_from_directory(REPORTS_DIR, filename)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = _args.port
    print(f"\n  Auto Test Dashboard  →  http://localhost:{port}")
    print(f"  Project dir          :  {BASE_DIR}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
