@echo off
:: =============================================================================
:: setup.bat — Cai dat day du Auto Test Dashboard (Windows)
::
:: Cach dung:
::   Double-click setup.bat
::   Hoac: setup.bat (trong Command Prompt / PowerShell)
:: =============================================================================
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_DIR=%SCRIPT_DIR%\.venv"
set "REQUIREMENTS=%SCRIPT_DIR%\requirements.txt"

echo.
echo ============================================
echo    Auto Test Dashboard -- Cai dat (Windows)
echo ============================================
echo   Thu muc: %SCRIPT_DIR%
echo.

:: ── Python 3.10+ ──────────────────────────────────────────────────────────────
echo [*] Kiem tra Python...
set "PYTHON="
for %%p in (python3.13 python3.12 python3.11 python3.10 python3 python) do (
    if not defined PYTHON (
        where %%p >nul 2>&1 && (
            for /f "tokens=*" %%v in ('%%p -c "import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")" 2^>nul') do (
                for /f "tokens=1,2 delims=." %%a in ("%%v") do (
                    if %%a geq 3 if %%b geq 10 (
                        set "PYTHON=%%p"
                        echo [OK] Python %%v ^(%%p^)
                    )
                )
            )
        )
    )
)

if not defined PYTHON (
    echo [!] Python 3.10+ chua duoc cai.
    echo     Tai Python tai: https://www.python.org/downloads/
    echo     Chon "Add Python to PATH" khi cai.
    pause
    exit /b 1
)

:: ── Node.js ───────────────────────────────────────────────────────────────────
echo.
echo [*] Kiem tra Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Node.js chua duoc cai.
    echo     Tai Node.js tai: https://nodejs.org/ ^(chon LTS^)
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do echo [OK] Node.js %%v

:: ── Java ──────────────────────────────────────────────────────────────────────
echo.
echo [*] Kiem tra Java...
where java >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Java chua duoc cai.
    echo     Tai OpenJDK 17 tai: https://adoptium.net/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('java -version 2^>^&1 ^| findstr /i "version"') do (
    echo [OK] %%v
    goto :java_ok
)
:java_ok

:: ── Android SDK ───────────────────────────────────────────────────────────────
echo.
echo [*] Kiem tra Android SDK (adb)...
where adb >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('adb version 2^>nul ^| findstr /i "version"') do echo [OK] %%v
) else (
    set "ADB_PATH=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
    if exist "!ADB_PATH!" (
        echo [OK] adb tim thay tai !ADB_PATH!
        set "PATH=%PATH%;%LOCALAPPDATA%\Android\Sdk\platform-tools"
    ) else (
        echo [!] adb khong tim thay -- cai Android Studio va them platform-tools vao PATH
        echo     https://developer.android.com/studio
    )
)

:: ── Appium ────────────────────────────────────────────────────────────────────
echo.
echo [*] Kiem tra Appium...
where appium >nul 2>&1
if %errorlevel% neq 0 (
    echo [->] Dang cai Appium...
    npm install -g appium
    if %errorlevel% neq 0 (
        echo [!] Cai Appium that bai
        pause
        exit /b 1
    )
    echo [OK] Appium da cai xong
) else (
    for /f "tokens=*" %%v in ('appium --version 2^>nul') do echo [OK] Appium %%v
)

echo.
echo [*] Kiem tra UIAutomator2 driver...
appium driver list --installed 2>nul | findstr /i "uiautomator2" >nul
if %errorlevel% neq 0 (
    echo [->] Dang cai UIAutomator2 driver...
    appium driver install uiautomator2
    echo [OK] UIAutomator2 driver da cai xong
) else (
    echo [OK] UIAutomator2 driver da co
)

:: ── Python venv ───────────────────────────────────────────────────────────────
echo.
echo [*] Tao Python virtual environment...
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [OK] .venv da ton tai
) else (
    echo [->] Dang tao .venv...
    %PYTHON% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [!] Khong tao duoc .venv
        pause
        exit /b 1
    )
    echo [OK] .venv da tao xong
)

:: ── Python packages ───────────────────────────────────────────────────────────
echo.
echo [*] Cai Python packages...
"%VENV_DIR%\Scripts\pip.exe" install --quiet --upgrade pip
"%VENV_DIR%\Scripts\pip.exe" install --quiet -r "%REQUIREMENTS%"
if %errorlevel% neq 0 (
    echo [!] Cai packages that bai
    pause
    exit /b 1
)
echo [OK] Tat ca packages da cai xong

:: ── Xong ──────────────────────────────────────────────────────────────────────
echo.
echo ============================================
echo   Cai dat hoan tat!
echo   De chay dashboard: run.bat
echo ============================================
echo.
pause
