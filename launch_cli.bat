@echo off
title Multi-IMSI Test Tool — CLI
cd /d "%~dp0"

:: Run all tests, output HTML report
python main.py --cli --all --out report.html

echo.
echo Report saved to report.html
start report.html
pause
