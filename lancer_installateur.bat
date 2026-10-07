@echo off
cd /d "%~dp0"
python installer_app/main.py
if errorlevel 1 pause
