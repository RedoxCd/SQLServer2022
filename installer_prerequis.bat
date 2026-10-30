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

rem Liens de telechargement direct (utilises si winget est absent ou echoue)
set "URL_PYTHON=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
set "URL_ODBC=https://go.microsoft.com/fwlink/?linkid=2378279"
set "URL_WEBVIEW2=https://go.microsoft.com/fwlink/p/?LinkId=2124703"
set "DL=%TEMP%\LootTable_prerequis"
if not exist "%DL%" mkdir "%DL%"

rem winget est optionnel : sur une machine neuve il peut manquer ou echouer.
rem On force la source "winget" : la source "msstore" plante souvent sur
rem un poste neuf ou un reseau d'ecole (erreur de certificat 0x8a15005e).
set "HAVE_WINGET="
where winget >nul 2>&1 && set "HAVE_WINGET=1"
if not defined HAVE_WINGET echo winget introuvable : les prerequis seront telecharges directement.
set "WINGET_OPTS=-e --source winget --silent --accept-package-agreements --accept-source-agreements"

rem ================= 1/4 Python 3.12 =================
call :find_python
if defined PYEXE (
    echo [1/4] Python est deja installe.
    goto odbc
)
echo [1/4] Installation de Python 3.12...
if defined HAVE_WINGET winget install --id Python.Python.3.12 --scope machine %WINGET_OPTS%
call :find_python
if defined PYEXE goto python_ok

echo       winget n'a pas pu installer Python : telechargement direct depuis python.org...
call :download "%URL_PYTHON%" "%DL%\python-3.12-amd64.exe" || goto python_fail
"%DL%\python-3.12-amd64.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 Include_test=0
call :find_python
if defined PYEXE goto python_ok

:python_fail
echo.
echo ERREUR : Python 3.12 n'a pas pu etre installe.
echo Installez-le a la main depuis %URL_PYTHON%
echo (cochez "Add python.exe to PATH"), puis relancez ce script.
pause
exit /b 1

:python_ok
echo       Python installe : %PYEXE%

rem ================= 2/4 Pilote ODBC 18 =================
:odbc
call :has_odbc
if defined ODBC_OK (
    echo [2/4] ODBC Driver 18 est deja installe.
    goto webview
)
echo [2/4] Installation de ODBC Driver 18 for SQL Server...
if defined HAVE_WINGET winget install --id Microsoft.msodbcsql.18 %WINGET_OPTS%
call :has_odbc
if defined ODBC_OK goto webview

echo       winget n'a pas pu installer le pilote : telechargement direct depuis Microsoft...
call :download "%URL_ODBC%" "%DL%\msodbcsql18.msi" || goto odbc_fail
msiexec /i "%DL%\msodbcsql18.msi" /qn /norestart IACCEPTMSODBCSQLLICENSETERMS=YES
call :has_odbc
if defined ODBC_OK goto webview

:odbc_fail
echo.
echo ERREUR : le pilote "ODBC Driver 18 for SQL Server" n'a pas pu etre installe.
echo Telechargez-le a la main : %URL_ODBC%
echo puis relancez ce script.
pause
exit /b 1

rem ================= 3/4 WebView2 =================
:webview
call :has_webview2
if defined WV2_OK (
    echo [3/4] WebView2 est deja installe.
    goto modules
)
echo [3/4] Installation de Microsoft Edge WebView2...
if defined HAVE_WINGET winget install --id Microsoft.EdgeWebView2Runtime %WINGET_OPTS%
call :has_webview2
if defined WV2_OK goto modules

echo       winget n'a pas pu installer WebView2 : telechargement direct depuis Microsoft...
call :download "%URL_WEBVIEW2%" "%DL%\MicrosoftEdgeWebview2Setup.exe" || goto webview_warn
"%DL%\MicrosoftEdgeWebview2Setup.exe" /silent /install
call :has_webview2
if defined WV2_OK goto modules

:webview_warn
echo       ATTENTION : WebView2 n'est pas detecte. Si la fenetre de l'activite
echo       ne s'ouvre pas, installez-le depuis %URL_WEBVIEW2%

rem ================= 4/4 Modules Python =================
:modules
echo [4/4] Installation des modules Python...
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r "%~dp0demo_app\requirements.txt"
if errorlevel 1 (
    echo ERREUR : l'installation des modules Python a echoue.
    echo Verifiez la connexion Internet puis relancez ce script.
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
pause
exit /b 0


rem ================= Sous-routines =================

:find_python
rem Cherche d'abord les chemins d'installation connus (le PATH de cette
rem fenetre n'est pas mis a jour juste apres une installation).
set "PYEXE="
if exist "%ProgramFiles%\Python312\python.exe" set "PYEXE=%ProgramFiles%\Python312\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PYEXE exit /b 0
rem Sinon un Python deja present dans le PATH (le raccourci Microsoft Store echoue ici)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYEXE=python"
exit /b 0

:has_odbc
set "ODBC_OK="
reg query "HKLM\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 18 for SQL Server" >nul 2>&1 && set "ODBC_OK=1"
exit /b 0

:has_webview2
set "WV2_OK="
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1 && set "WV2_OK=1"
if not defined WV2_OK reg query "HKCU\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1 && set "WV2_OK=1"
exit /b 0

:download
rem %1 = URL, %2 = fichier de destination
if exist "%~2" del /f /q "%~2" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%~1' -OutFile '%~2' -UseBasicParsing; exit 0 } catch { Write-Host ('      Echec du telechargement : ' + $_.Exception.Message); exit 1 }"
if not exist "%~2" exit /b 1
exit /b 0
