@echo off
setlocal
title Multi-IMSI Test Tool
cd /d "%~dp0"

:: Use py -3.12 if available, else fall back to python
set PY=python
py -3.12 --version >nul 2>&1
if not errorlevel 1 set PY=py -3.12

:: Check deps
%PY% -c "import smartcard, PyQt6, yaml, cryptography, jinja2" >nul 2>&1
if errorlevel 1 (
    echo Dependencies missing. Run setup.bat first.
    pause
    exit /b 1
)

%PY% main.py
