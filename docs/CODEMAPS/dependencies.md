<!-- Generated: 2026-04-18 | Files scanned: 22 | Token estimate: ~400 -->

# Dependencies

## Python Packages (requirements.txt)

| Package | Version | Role |
|---------|---------|------|
| Appium-Python-Client | >=3.1.0 | Appium WebDriver client |
| pytest | >=7.4.0 | Test runner |
| pytest-html | >=4.0.0 | HTML report plugin |
| PyYAML | >=6.0 | config.yaml parsing |
| selenium | >=4.15.0 | WebDriver base (used by Appium) |
| flask | >=3.0.0 | Web dashboard server |
| werkzeug | >=3.0.0 | Flask dependency + secure_filename |
| openpyxl | >=3.1.0 | Read/write test_cases.xlsx + reports |

## External Services / Tools

| Tool | Purpose | Config |
|------|---------|--------|
| Appium Server | Mobile automation server | host: 127.0.0.1, port: 4723 (config.yaml) |
| ADB (Android Debug Bridge) | Device control, file push, screencap | Must be in PATH |
| aapt2 | APK version info extraction | Auto-detected from Android SDK build-tools |
| UiAutomator2 | Android UI interaction driver | Installed by Appium on device |

## Android SDK Requirements
- `ANDROID_SDK_ROOT` env var (defaults to `~/Library/Android/sdk`)
- `build-tools/*/aapt2` — for APK version parsing in `ADBController.get_apk_info()`

## App Under Test
- **Source project**: `/Users/buitung/StudioProjects/pdf-reade` (Android Studio)
- **Package**: `pdf.reader.pdf.viewer.all.document.reader.office.viewer`
- **Main activity**: `com.simple.pdf.reader.ui.main.SplashScreenActivity`
- **APK drop location**: `apks/` in this project root

## Internal Cross-References

```
conftest.py
  → core.adb_controller.ADBController
  → core.device_manager (get_all_connected_devices)
  → test_cases.tc_pytest_plugin (SESSION_TIMESTAMP)
  → tests.helpers (close_recentapp2, dismiss_onboarding2, dismiss_ads)

server.py
  → core.adb_controller.ADBController
  → test_cases.tc_manager (via api_testcases AST scan)

orchestrator.py
  → core.adb_controller.ADBController
  → core.app_installer.AppInstaller
  → core.device_manager.DeviceManager, get_all_connected_devices
```
