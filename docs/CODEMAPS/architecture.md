<!-- Generated: 2026-04-18 | Files scanned: 22 | Token estimate: ~600 -->

# Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────┐
│  Entry Points                                            │
│  server.py (:8080)          orchestrator.py (CLI)        │
└──────────────┬───────────────────────┬───────────────────┘
               │ SSE + REST            │ subprocess
               ▼                       ▼
        ┌─────────────────────────────────────┐
        │   pytest + conftest.py (root)        │
        │   Fixtures: driver, cfg, adb,        │
        │   tc_manager, video_recorder         │
        └──────────────┬──────────────────────┘
                       │ Appium WebDriver
                       ▼
        ┌─────────────────────────────────────┐
        │   Appium Server (:4723)              │
        │   UiAutomator2 on Android device     │
        └──────────────┬──────────────────────┘
                       │ ADB
                       ▼
        ┌─────────────────────────────────────┐
        │   Android Device / Emulator          │
        │   App: pdf.reader.pdf.viewer.*       │
        │   Source: /Users/buitung/            │
        │           StudioProjects/pdf-reade   │
        └─────────────────────────────────────┘
```

## Data Flow: Test Execution
1. User clicks Run in browser → `POST /api/run` (server.py)
2. Flask thread spawns `pytest tests/test_suite/` subprocess
3. `conftest.py` `setup_before_test` (autouse) restarts Appium + creates DriverProxy
4. Test method executes via Appium → UiAutomator2 → device
5. `video_recorder` (autouse) saves MP4; `pytest_runtest_makereport` saves PNG
6. `tc_pytest_plugin.pytest_sessionfinish` writes Excel + HTML dashboard to `reports/`

## Key Design Decisions
- **DriverProxy**: proxy object allowing underlying Appium session swap without breaking fixture references
- **Full Appium restart per test**: prevents UiAutomator2 crash accumulation across tests
- **Two-level UiA2 recovery**: ADB HOME → full Appium restart + driver recreate
- **TC ID → node mapping**: built dynamically from AST scan (no registry file)
