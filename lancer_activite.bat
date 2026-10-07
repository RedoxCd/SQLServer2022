@echo off
cd /d "%~dp0"
python demo_app/main.py
if errorlevel 1 pause
