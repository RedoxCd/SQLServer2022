@echo off
REM Double-clique ce fichier pour installer la démo (voir install_demo.ps1
REM pour les options -Server / -BackupDir / -Force).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_demo.ps1" %*
pause
