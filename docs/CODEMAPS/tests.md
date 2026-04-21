<!-- Generated: 2026-04-18 | Files scanned: 22 | Token estimate: ~650 -->

# Test Suite

## Active Suite: tests/test_suite/

| File | Class | TC IDs | Lines |
|------|-------|--------|-------|
| test_smoke.py | TestSmoke | TC_SM_001–004 | 90 |
| test_open_pdf.py | TestOpenPDF | TC_PDF_001–009 | 144 |
| test_pdf_tools.py | TestPDFTools | TC_TOOL_001–007 | 172 |
| test_data_migration.py | TestDataMigration | TC_DM_001–007 | 169 |
| test_open_files_password.py | TestRememberPassword, TestOpenFilesPassword | TC-006–011, TC-021–025 | 1513 |
| test_open_files_other.py | TestOpenFilesOther | TC-026–054 | 3687 |
| test_notification.py | TestNotification | TC-NTF-001–019 | 1768 |

## Key Fixtures (conftest.py, 795 lines)

```
cfg          (session) — parsed config.yaml
adb          (session) — ADBController(TEST_DEVICE_SERIAL)
driver       (session) — DriverProxy wrapping Appium WebDriver
tc_manager   (session) — TCManager for Excel result writing
tc_result    (function)— _TCResult helper for per-test result capture

setup_before_test  (autouse, function) — full Appium restart + DriverProxy recreate before each test
video_recorder     (autouse, function) — start_recording_screen before / stop+save MP4 after
```

## pytest Hooks (conftest.py)

```
pytest_runtest_protocol  (tryfirst)  — start screen recording before any fixture
pytest_runtest_call      (wrapper)   — map tc_id marker → TCManager.update_result
pytest_runtest_makereport (tryfirst) — save screenshot (PASS+FAIL) via Appium or ADB fallback
pytest_runtest_teardown  (trylast)   — _recover_uia2_after_test_if_needed
```

## Shared Helpers (tests/helpers.py, 1230 lines)

Key functions used across test files:
- `go_to_home(driver)` — navigate to app home screen
- `close_recentapp2(driver, adb, pkg, home)` — kill app + clear recents
- `dismiss_onboarding2(driver, cfg)` — handle first-launch onboarding flow
- `dismiss_ads(driver)` — close ad overlays
- `_is_ad_showing(driver)` — detect active ad overlay

## TC ID Naming Conventions

| Prefix | Feature Area |
|--------|-------------|
| TC_SM_  | Smoke tests (app launch, basic nav) |
| TC_PDF_ | Open/view PDF files |
| TC_TOOL_| PDF tools (split, merge, scanner, sign) |
| TC_DM_  | Data migration after update |
| TC-NNN  | Legacy numeric IDs (password, other files) |
| TC-NTF_ | Notification tests |

## Environment Variables

| Var | Purpose |
|-----|---------|
| `TEST_DEVICE_SERIAL` | ADB serial of target device (empty = first connected) |
| `RUN_INIT` | Set to `1` to run full app onboarding init before first test |
| `INSTALL_APK` | APK filename in apks/ to install before run |
