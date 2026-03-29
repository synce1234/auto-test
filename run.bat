@echo off
:: =============================================================================
:: run.bat — Khoi dong Auto Test Dashboard (Windows)
::
:: Cach dung:
::   Double-click run.bat
::   Hoac: run.bat [--port PORT] [--no-appium]
:: =============================================================================
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_PYTHON=%SCRIPT_DIR%\.venv\Scripts\python.exe"
set "SERVER=%SCRIPT_DIR%\server.py"
set "PORT=8080"
set "APPIUM_PORT=4723"
set "START_APPIUM=true"

:: ── Parse args ────────────────────────────────────────────────────────────────
:parse_args
if "%~1"=="--port"      set "PORT=%~2"    & shift & shift & goto parse_args
if "%~1"=="--no-appium" set "START_APPIUM=false" & shift & goto parse_args
if "%~1"=="-h"          goto show_help
if "%~1"=="--help"      goto show_help
if not "%~1"==""        echo [!] Bo qua: %~1 & shift & goto parse_args
goto start

:show_help
echo Cach dung: run.bat [--port PORT] [--no-appium]
exit /b 0

:start
echo.
echo ============================================
echo    Auto Test Dashboard -- Start (Windows)
echo ============================================

:: ── Kiem tra .venv ────────────────────────────────────────────────────────────
if not exist "%VENV_PYTHON%" (
    echo [!] .venv khong tim thay. Hay chay 'setup.bat' truoc.
    pause
    exit /b 1
)

:: ── Android SDK path ──────────────────────────────────────────────────────────
if not defined ANDROID_SDK_ROOT (
    set "ANDROID_SDK_ROOT=%LOCALAPPDATA%\Android\Sdk"
)
set "PATH=%PATH%;%ANDROID_SDK_ROOT%\platform-tools;%ANDROID_SDK_ROOT%\emulator"

:: ── Appium ────────────────────────────────────────────────────────────────────
if "%START_APPIUM%"=="true" (
    echo [*] Kiem tra Appium...
    netstat -ano | findstr ":%APPIUM_PORT% " | findstr "LISTENING" >nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] Appium dang chay tren port %APPIUM_PORT%
    ) else (
        where appium >nul 2>&1
        if %errorlevel% equ 0 (
            echo [->] Dang start Appium ^(port %APPIUM_PORT%^)...
            start /b "" appium --port %APPIUM_PORT% --log-level error --log "%TEMP%\appium.log"
            timeout /t 3 /nobreak >nul
            echo [OK] Appium da start ^(log: %TEMP%\appium.log^)
        ) else (
            echo [!] Appium chua cai -- chay 'setup.bat' truoc
        )
    )
)

:: ── Start server ──────────────────────────────────────────────────────────────
echo.
echo   Dashboard : http://localhost:%PORT%
echo   Project   : %SCRIPT_DIR%
echo.
echo   Nhan Ctrl+C de dung.
echo.

"%VENV_PYTHON%" "%SERVER%" --port %PORT%

pause
