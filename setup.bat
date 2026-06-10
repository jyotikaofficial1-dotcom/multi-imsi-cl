@echo off
setlocal enabledelayedexpansion
title Multi-IMSI Test Tool — Setup
echo ============================================
echo  Multi-IMSI Test Tool — First-Time Setup
echo ============================================
echo.

:: Prefer Python 3.12 via the py launcher; fall back to whatever python is on PATH
set PY=
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set PY=py -3.12
    echo Using Python 3.12 ^(via py launcher^)
) else (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python not found.
        echo Install Python 3.12 from https://python.org/downloads/release/python-3128/
        echo Make sure to tick "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    set PY=python
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    echo Using Python !PY_VER!
    echo !PY_VER! | findstr /b "3.14" >nul
    if not errorlevel 1 (
        echo.
        echo WARNING: Python 3.14 has no pre-built pyscard wheel.
        echo Install Python 3.12 from https://python.org/downloads/release/python-3128/
        echo then re-run this script.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Installing dependencies...
%PY% -m pip install pyscard PyQt6 PyYAML cryptography Jinja2 --only-binary=pyscard --quiet
if errorlevel 1 (
    echo.
    echo Retrying pyscard without --only-binary...
    %PY% -m pip install pyscard --quiet
    if errorlevel 1 (
        echo.
        echo ERROR: pyscard failed to install.
        echo Try installing the Windows SDK:
        echo   Visual Studio Installer ^> Modify ^> Individual Components
        echo   ^> search "Windows 11 SDK" ^> Install
        echo.
        pause
        exit /b 1
    )
    %PY% -m pip install PyQt6 PyYAML cryptography Jinja2 --quiet
)

echo.
echo Dependencies installed OK.
echo.

:: Create vault if it doesn't exist
if not exist "security\key_store.enc" (
    echo Creating ADM key vault...
    echo.
    echo Enter your ADM key in HEX ^(from your card personalisation data^).
    echo Example for test cards: 3733323339313637
    echo Leave blank to skip.
    echo.
    set /p ADM_KEY="ADM Key (hex): "
    if not "!ADM_KEY!"=="" (
        %PY% -c "from security.adm_keys import create_vault; create_vault('security/key_store.enc', {'default': '!ADM_KEY!'})"
        echo Vault created at security\key_store.enc
    ) else (
        echo Skipped vault creation.
    )
    echo.
)

echo Setup complete! Run launch.bat to start the tool.
echo.
pause
