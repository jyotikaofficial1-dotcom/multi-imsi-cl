@echo off
setlocal
title Multi-IMSI Test Tool — CLI
cd /d "%~dp0"

:: Use py -3.12 if available, else fall back to python
set PY=python
py -3.12 --version >nul 2>&1
if not errorlevel 1 set PY=py -3.12

%PY% main.py --cli --all --out report.html

echo.
echo Report saved to report.html
start report.html
pause
