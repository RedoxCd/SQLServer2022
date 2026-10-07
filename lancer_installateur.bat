@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 installer_app\main.py
) else (
    python installer_app\main.py
)
if errorlevel 1 pause
