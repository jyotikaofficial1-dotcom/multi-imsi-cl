@echo off
title Multi-IMSI Test Tool — Setup
echo ============================================
echo  Multi-IMSI Test Tool — First-Time Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install Python 3.12 from https://python.org/downloads/release/python-3128/
    pause
    exit /b 1
)

:: Warn if Python 3.14 (pyscard has no pre-built wheel yet)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo Detected Python %PY_VER%
echo %PY_VER% | findstr /b "3.14" >nul
if not errorlevel 1 (
    echo.
    echo WARNING: Python 3.14 detected.
    echo pyscard does not yet have a pre-built wheel for Python 3.14.
    echo.
    echo Recommended fix: install Python 3.12 side-by-side and run:
    echo   py -3.12 -m pip install -r requirements.txt
    echo   py -3.12 main.py
    echo.
    echo Trying anyway with binary-only install ^(may still fail^)...
    echo.
)

:: Install other deps first (always have wheels)
echo Installing core dependencies...
pip install PyQt6 PyYAML cryptography Jinja2 --quiet
if errorlevel 1 (
    echo ERROR: Failed to install core dependencies.
    pause
    exit /b 1
)

:: Try pyscard binary wheel only (no compile)
echo Installing pyscard (binary wheel)...
pip install pyscard --only-binary=:all: --quiet 2>nul
if errorlevel 1 (
    echo.
    echo Could not find a pre-built pyscard wheel for your Python version.
    echo.
    echo Options:
    echo  1. Install Python 3.12 from https://python.org/downloads/release/python-3128/
    echo     then re-run this script.
    echo  2. Install Windows SDK (for C compiler):
    echo     Open Visual Studio Installer ^> Modify ^> Individual Components
    echo     ^> Search "Windows 11 SDK" ^> Install
    echo     Then re-run this script.
    echo.
    echo The tool will still run in DEMO mode without a real card reader.
    echo Press any key to continue setup without pyscard...
    pause
)

echo.
echo Dependencies installed.
echo.

:: Create vault if it doesn't exist
if not exist "security\key_store.enc" (
    echo Creating ADM key vault...
    echo.
    echo Enter your ADM key in HEX ^(from your card personalisation data^).
    echo Example for test cards: 3733323339313637
    echo Leave blank to skip vault creation.
    echo.
    set /p ADM_KEY="ADM Key (hex): "
    if not "!ADM_KEY!"=="" (
        python -c "from security.adm_keys import create_vault; create_vault('security/key_store.enc', {'default': '!ADM_KEY!'})"
        echo Vault created at security\key_store.enc
    ) else (
        echo Skipped vault creation. You can run this script again to create one.
    )
    echo.
)

echo Setup complete! Run launch.bat to start the tool.
echo.
pause
