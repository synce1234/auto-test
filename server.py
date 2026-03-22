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
SCRIPTS_DIR = os.path.join(BASE_DIR, "test_cases", "scripts")

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

    # Build pytest args — support "file.py::ClassName" node IDs
    if scripts:
        test_paths = []
        for s in scripts:
            if "::" in s:
                fname, cls = s.split("::", 1)
                test_paths.append(os.path.join(SCRIPTS_DIR, fname) + "::" + cls)
            else:
                test_paths.append(os.path.join(SCRIPTS_DIR, s))
    else:
        test_paths = [SCRIPTS_DIR]

    cmd = [sys.executable, "-m", "pytest"] + test_paths + ["-v", "--tb=short", "--no-header"]

    env = os.environ.copy()
    if device_serial:
        env["TEST_DEVICE_SERIAL"] = device_serial

    def _run_thread():
        global _run_active, _run_proc
        try:
            # Optional: install APKs in order
            for apk_fname in install_apks:
                apk_path = os.path.join(APKS_DIR, _safe_apk_name(apk_fname))
                if not os.path.isfile(apk_path):
                    _emit({"type": "log", "text": f"[INSTALL] SKIP (not found): {apk_fname}"})
                    continue
                _emit({"type": "log", "text": f"[INSTALL] Installing {apk_fname}..."})
                adb_cmd = ["adb"]
                if device_serial:
                    adb_cmd += ["-s", device_serial]
                adb_cmd += ["install", "-r", apk_path]
                r = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=120)
                ok = r.returncode == 0 and "Success" in r.stdout
                _emit({"type": "log", "text": f"[INSTALL] {'OK ✓' if ok else 'FAILED ✗'} {r.stdout.strip() or r.stderr.strip()}"})
                if not ok:
                    _emit({"type": "done", "code": 1})
                    return

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
