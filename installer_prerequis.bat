@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title LootTable - Installation des prerequis

rem ===== Droits administrateur (necessaires pour Python et le pilote ODBC) =====
net session >nul 2>&1
if errorlevel 1 (
    echo Demande des droits administrateur...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo  LootTable - installation de Python 3.12 et du pilote ODBC 18
echo ============================================================
echo.

where winget >nul 2>&1
if errorlevel 1 (
    echo ERREUR : winget est introuvable.
    echo Installez "Programme d'installation d'application" depuis le Microsoft Store,
    echo ou installez a la main Python 3.12 et "ODBC Driver 18 for SQL Server".
    pause
    exit /b 1
)

rem ===== 1/4 Python =====
set "PYEXE="
python --version >nul 2>&1 && set "PYEXE=python"
if defined PYEXE (
    echo [1/4] Python est deja installe.
) else (
    echo [1/4] Installation de Python 3.12...
    winget install -e --id Python.Python.3.12 --scope machine --accept-package-agreements --accept-source-agreements
    if exist "%ProgramFiles%\Python312\python.exe" set "PYEXE=%ProgramFiles%\Python312\python.exe"
)
if not defined PYEXE (
    echo.
    echo Python vient d'etre installe mais n'est pas encore visible.
    echo Fermez cette fenetre, puis relancez installer_prerequis.bat.
    pause
    exit /b 1
)

rem ===== 2/4 Pilote ODBC 18 =====
reg query "HKLM\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 18 for SQL Server" >nul 2>&1
if errorlevel 1 (
    echo [2/4] Installation de ODBC Driver 18 for SQL Server...
    winget install -e --id Microsoft.msodbcsql.18 --accept-package-agreements --accept-source-agreements
) else (
    echo [2/4] ODBC Driver 18 est deja installe.
)

rem ===== 3/4 WebView2 (affichage de la fenetre, deja present sous Windows 11) =====
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if errorlevel 1 (
    echo [3/4] Installation de Microsoft Edge WebView2...
    winget install -e --id Microsoft.EdgeWebView2Runtime --accept-package-agreements --accept-source-agreements
) else (
    echo [3/4] WebView2 est deja installe.
)

rem ===== 4/4 Modules Python (pywebview, pyodbc) =====
echo [4/4] Installation des modules Python...
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r "%~dp0demo_app\requirements.txt"
if errorlevel 1 (
    echo ERREUR : l'installation des modules Python a echoue.
    pause
    exit /b 1
)

echo.
echo ---------------- Verification ----------------
"%PYEXE%" --version
"%PYEXE%" -c "import pyodbc, webview; print('Modules OK - pilotes SQL Server :', [d for d in pyodbc.drivers() if 'SQL Server' in d])"
if errorlevel 1 (
    echo.
    echo Les modules ne se chargent pas encore. Redemarrez l'ordinateur puis relancez ce script.
    pause
    exit /b 1
)
echo.
echo Termine. Vous pouvez lancer lancer_installateur.bat.
echo (Si "python" n'est pas reconnu ensuite : fermez la session Windows puis rouvrez-la.)
pause
