<!-- Generated: 2026-04-18 | Files scanned: 22 | Token estimate: ~700 -->

# Backend

## Flask API Routes (server.py)

```
GET  /                          → serve web/index.html
GET  /api/apks                  → list APKs in apks/ with version info
POST /api/apks/upload           → upload new .apk file
DEL  /api/apks/<filename>       → delete APK file
GET  /api/devices               → list connected ADB devices
GET  /api/testcases             → TC database from test_cases.xlsx + automation status
GET  /api/test-scripts          → list test files + class/method names
GET  /api/run/status            → { running: bool }
POST /api/run                   → start pytest subprocess (body: device, scripts, install_apks, run_init)
POST /api/run/stop              → terminate running pytest
GET  /api/run/stream            → SSE stream of live pytest output
GET  /api/config                → read config.yaml as JSON
POST /api/config                → update config.yaml fields
GET  /api/reports               → list dashboard_*.html in reports/
GET  /reports/<filename>        → serve report file
```

## Core Layer (core/)

```
ADBController (adb_controller.py, 220 lines)
  install_apk(apk_path, replace) → bool
  uninstall_app(package_name) → bool
  is_app_installed(package_name) → bool
  get_installed_version(package_name) → str
  launch_app(package_name, activity) → bool
  force_stop_app(package_name)
  clear_app_data(package_name) → bool
  take_screenshot(save_path) → bool
  push_file(local_path, remote_path) → bool
  get_apk_info(apk_path) → {version_name, version_code}  [staticmethod, uses aapt2]
  get_device_info() → {model, android_version, sdk_version}

AppInstaller (app_installer.py, 74 lines)
  clean_install(apk_path) → bool          # uninstall + install
  update_install(apk_path) → bool         # install -r (keep data)
  setup_initial_data(activity, timeout)   # launch once to init
  get_apk_list(apks_dir) → list[str]

DeviceManager (device_manager.py, 87 lines)
  get_all_connected_devices(exclude) → list[dict]   [module-level fn]
  check_device_ready() → bool
  prepare_test_storage(package_name)      # grant storage perms via ADB
  push_test_pdfs(pdf_files)
  disable_animations() / restore_animations()
```

## TC Management (test_cases/)

```
TCManager (tc_manager.py)
  get(tc_id) → dict
  get_all() → dict
  update_result(tc_id, status, actual, duration)
  save_report(report_path)               # writes Excel + triggers HTML gen

tc_pytest_plugin.py
  Fixtures: tc_manager (session), tc_result (function)
  Hooks:    pytest_runtest_call → update_result
            pytest_runtest_logreport → capture status
            pytest_sessionfinish → save_report → Excel + HTML dashboard
```

## Orchestrator (orchestrator.py, 360 lines)

```
main()
  scan_apks(apks_dir) → list[{path, version_name, version_code}]
  get_all_connected_devices(exclude)
  run_on_device(device, apk_entries, cfg, report_base, dry_run)
    └─ run_update_test(adb, installer, device_mgr, cfg, old_apk, latest_apk, ...)
         B1: clean_install(old_apk)
         B2: update_install(latest_apk)
         B3: run_tests() → parse_junit_result()
```
