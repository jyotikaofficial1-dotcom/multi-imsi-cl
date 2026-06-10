@echo off
title Multi-IMSI Test Tool
cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Run setup.bat first.
    pause
    exit /b 1
)

:: Check if deps are installed
python -c "import smartcard, PyQt6, yaml, cryptography, jinja2" >nul 2>&1
if errorlevel 1 (
    echo Dependencies missing. Running setup...
    pip install pyscard PyQt6 PyYAML cryptography Jinja2 --quiet
)

:: Launch GUI
python main.py
