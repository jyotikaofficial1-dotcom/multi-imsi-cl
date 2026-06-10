@echo off
title Multi-IMSI Test Tool — Setup
echo ============================================
echo  Multi-IMSI Test Tool — First-Time Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

echo Installing dependencies...
pip install pyscard PyQt6 PyYAML cryptography Jinja2 --quiet
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. See output above.
    pause
    exit /b 1
)

echo.
echo Dependencies installed OK.
echo.

:: Create vault if it doesn't exist
if not exist "security\key_store.enc" (
    echo Creating ADM key vault...
    echo Enter your ADM key in HEX when prompted.
    echo Example: 49265449A3B5C2D1  (replace with your real key)
    echo.
    set /p ADM_KEY="ADM Key (hex): "
    python -c "from security.adm_keys import create_vault; create_vault('security/key_store.enc', {'default': '%ADM_KEY%'})"
    echo Vault created.
    echo.
)

echo Setup complete! Run launch.bat to start the tool.
echo.
pause
