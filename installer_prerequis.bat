@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title LootTable - Installation du poste

rem ===== Droits administrateur =====
rem On transmet le compte Windows de la personne qui lance le script, pour le
rem rendre administrateur de SQL Server (l'activite se connecte avec ce compte).
net session >nul 2>&1
if errorlevel 1 (
    echo Demande des droits administrateur...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%USERDOMAIN%\%USERNAME%' -Verb RunAs"
    exit /b
)
set "COMPTE_UTILISATEUR=%~1"
if not defined COMPTE_UTILISATEUR set "COMPTE_UTILISATEUR=%USERDOMAIN%\%USERNAME%"
set "COMPTE_ADMIN=%USERDOMAIN%\%USERNAME%"

echo ============================================================
echo  LootTable - installation complete du poste
echo  SQL Server 2022 Express, SSMS 20 FR, Python 3.12, ODBC 18, WebView2
echo ============================================================
echo.
echo Duree estimee : 15 a 30 minutes selon la connexion Internet.
echo Ne fermez pas cette fenetre et NE CLIQUEZ PAS dedans :
echo un clic met le script en pause, le titre affiche alors "Selection".
echo Si cela arrive, appuyez sur Echap pour reprendre.
echo.

rem ===== Reglages =====
set "INSTANCE=SQLEXPRESS"
set "URL_SQLEXPRESS=https://download.microsoft.com/download/29654887-7cde-4397-bba3-d7f087970845/SQL2022-SSEI-Expr.exe"
rem SSMS 20.2.1 en francais (clcid=0x40c = francais)
set "URL_SSMS=https://go.microsoft.com/fwlink/?linkid=2313753&clcid=0x40c"
set "PAGE_SSMS=https://learn.microsoft.com/fr-fr/ssms/release-history"
set "URL_PYTHON=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
set "URL_ODBC=https://go.microsoft.com/fwlink/?linkid=2378279"
set "URL_WEBVIEW2=https://go.microsoft.com/fwlink/p/?LinkId=2124703"
set "DOSSIER_DONNEES=C:\LootTable\Data"
set "DOSSIER_SAUVEGARDES=C:\LootTable\Backup"
set "DL=%TEMP%\LootTable_prerequis"
if not exist "%DL%" mkdir "%DL%"

rem winget est optionnel : sur une machine neuve il peut manquer ou echouer.
rem On force la source "winget" : la source "msstore" plante souvent sur
rem un poste neuf ou un reseau d'ecole (erreur de certificat 0x8a15005e).
set "HAVE_WINGET="
where winget >nul 2>&1 && set "HAVE_WINGET=1"
if not defined HAVE_WINGET echo winget introuvable : les logiciels seront telecharges directement.
set "WINGET_OPTS=-e --source winget --silent --accept-package-agreements --accept-source-agreements"


rem ================= 1/7 SQL Server 2022 Express =================
call :has_sql
if defined SQL_OK (
    echo [1/7] SQL Server 2022 Express - instance %INSTANCE% deja installee.
    goto sql_dossiers
)
echo [1/7] Installation de SQL Server 2022 Express - instance %INSTANCE%...
echo       Cette etape est la plus longue, 10 a 20 minutes.
echo       Il est normal que rien ne bouge a l'ecran : ne fermez pas la fenetre.

rem a) Un installeur complet est-il deja a cote du script, par ex. sur une cle USB ?
set "SQLPKG="
for %%F in ("%~dp0SQLEXPR*.exe" "%~dp0Installeurs\SQLEXPR*.exe") do if not defined SQLPKG set "SQLPKG=%%~fF"
if defined SQLPKG goto sql_local

rem b) Sinon on telecharge le petit lanceur Microsoft, qui telecharge le paquet complet
echo       Telechargement de SQL Server 2022 Express depuis Microsoft...
call :download "%URL_SQLEXPRESS%" "%DL%\SQL2022-SSEI-Expr.exe" || goto sql_fail
if exist "%DL%\SQLMedia" rmdir /s /q "%DL%\SQLMedia"
"%DL%\SQL2022-SSEI-Expr.exe" /ACTION=Download /MEDIAPATH="%DL%\SQLMedia" /MEDIATYPE=Core /QUIET /IACCEPTSQLSERVERLICENSETERMS
for /r "%DL%\SQLMedia" %%F in (SQLEXPR*.exe) do if not defined SQLPKG set "SQLPKG=%%~fF"
if defined SQLPKG goto sql_extraire

rem c) Dernier recours : le lanceur installe lui-meme l'instance par defaut SQLEXPRESS
echo       Telechargement du paquet impossible : installation directe par le lanceur...
"%DL%\SQL2022-SSEI-Expr.exe" /ACTION=Install /QUIET /IACCEPTSQLSERVERLICENSETERMS /ENU /INSTALLPATH="%ProgramFiles%\Microsoft SQL Server"
set "SQL_CODE=%errorlevel%"
if "%SQL_CODE%"=="3010" set "REDEMARRAGE=1"
call :has_sql
if defined SQL_OK goto sql_dossiers
goto sql_fail

:sql_local
echo       Installeur local trouve : %SQLPKG%

:sql_extraire
echo       Extraction des fichiers d'installation...
if exist "%DL%\SQLSetup" rmdir /s /q "%DL%\SQLSetup"
"%SQLPKG%" /q /x:"%DL%\SQLSetup"
if not exist "%DL%\SQLSetup\setup.exe" goto sql_fail

rem Un paquet en anglais sur un Windows francais a besoin du parametre /ENU
set "OPT_LANGUE="
echo %SQLPKG% | find /i "_ENU" >nul && set "OPT_LANGUE=/ENU"

set "SYSADMINS="%COMPTE_UTILISATEUR%""
if /i not "%COMPTE_ADMIN%"=="%COMPTE_UTILISATEUR%" set "SYSADMINS="%COMPTE_UTILISATEUR%" "%COMPTE_ADMIN%""

echo       Installation de l'instance %INSTANCE%, administrateur SQL : %COMPTE_UTILISATEUR%
"%DL%\SQLSetup\setup.exe" /Q /ACTION=Install /FEATURES=SQLEngine /INSTANCENAME=%INSTANCE% /SQLSYSADMINACCOUNTS=%SYSADMINS% /IACCEPTSQLSERVERLICENSETERMS /SUPPRESSPRIVACYSTATEMENTNOTICE /UPDATEENABLED=False %OPT_LANGUE%
set "SQL_CODE=%errorlevel%"
if "%SQL_CODE%"=="3010" set "REDEMARRAGE=1"
call :has_sql
if defined SQL_OK goto sql_dossiers

:sql_fail
echo.
echo ERREUR : SQL Server 2022 Express n'a pas pu etre installe.
if defined SQL_CODE echo Code de retour de l'installation : %SQL_CODE%
echo Journal detaille : "%ProgramFiles%\Microsoft SQL Server\160\Setup Bootstrap\Log\Summary.txt"
echo Solution de secours : copiez SQLEXPRADV_x64_FRA.exe ou SQLEXPR_x64_ENU.exe
echo a cote de ce script, puis relancez-le.
pause
exit /b 1

:sql_dossiers
rem Services : SQL Server en demarrage automatique, et SQL Server Browser active.
rem Sans le Browser, "localhost\SQLEXPRESS" echoue avec l'erreur
rem "Error Locating Server/Instance Specified" (il est desactive par defaut).
sc config "MSSQL$%INSTANCE%" start= auto >nul 2>&1
net start "MSSQL$%INSTANCE%" >nul 2>&1
sc config SQLBrowser start= auto >nul 2>&1
net start SQLBrowser >nul 2>&1
echo       Services SQL Server et SQL Server Browser demarres.
rem Le service SQL Server doit pouvoir ecrire la base et les sauvegardes
if not exist "%DOSSIER_DONNEES%" mkdir "%DOSSIER_DONNEES%"
if not exist "%DOSSIER_SAUVEGARDES%" mkdir "%DOSSIER_SAUVEGARDES%"
icacls "C:\LootTable" /grant "NT SERVICE\MSSQL$%INSTANCE%:(OI)(CI)M" /T /Q >nul 2>&1
icacls "C:\LootTable" /grant "*S-1-5-32-545:(OI)(CI)M" /Q >nul 2>&1
echo       Dossiers C:\LootTable\Data et C:\LootTable\Backup prets.


rem ================= 2/7 SSMS 20.2.1 en francais =================
call :has_ssms
if defined SSMS_OK (
    echo [2/7] SSMS 20 est deja installe.
    goto python
)
echo [2/7] Installation de SQL Server Management Studio 20.2.1 en francais, 5 a 15 minutes...
echo       Il est normal que rien ne bouge a l'ecran : ne fermez pas la fenetre.

rem Installeur deja present a cote du script, par ex. sur une cle USB ?
set "SSMSPKG="
for %%F in ("%~dp0SSMS-Setup-FRA.exe" "%~dp0Installeurs\SSMS-Setup-FRA.exe") do if not defined SSMSPKG if exist "%%~fF" set "SSMSPKG=%%~fF"
if defined SSMSPKG goto ssms_installer

echo       Telechargement de SSMS 20.2.1 FR depuis Microsoft, environ 500 Mo...
call :download "%URL_SSMS%" "%DL%\SSMS-Setup-FRA.exe" || goto ssms_warn
set "SSMSPKG=%DL%\SSMS-Setup-FRA.exe"

:ssms_installer
"%SSMSPKG%" /install /quiet /norestart
if "%errorlevel%"=="3010" set "REDEMARRAGE=1"
call :has_ssms
if defined SSMS_OK goto python

:ssms_warn
echo       ATTENTION : SSMS 20 n'est pas detecte. L'activite fonctionne sans.
echo       Pour l'installer a la main : version 20.2.1, langue francais, sur
echo       %PAGE_SSMS%


rem ================= 3/7 Python 3.12 =================
:python
call :find_python
if defined PYEXE (
    echo [3/7] Python est deja installe.
    goto odbc
)
echo [3/7] Installation de Python 3.12...
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
echo en cochant "Add python.exe to PATH", puis relancez ce script.
pause
exit /b 1

:python_ok
echo       Python installe : %PYEXE%


rem ================= 4/7 Pilote ODBC 18 =================
:odbc
call :has_odbc
if defined ODBC_OK (
    echo [4/7] ODBC Driver 18 est deja installe.
    goto webview
)
echo [4/7] Installation de ODBC Driver 18 for SQL Server...
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


rem ================= 5/7 WebView2 =================
:webview
call :has_webview2
if defined WV2_OK (
    echo [5/7] WebView2 est deja installe.
    goto modules
)
echo [5/7] Installation de Microsoft Edge WebView2...
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


rem ================= 6/7 Modules Python =================
:modules
echo [6/7] Installation des modules Python...
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r "%~dp0demo_app\requirements.txt"
if errorlevel 1 (
    echo ERREUR : l'installation des modules Python a echoue.
    echo Verifiez la connexion Internet puis relancez ce script.
    pause
    exit /b 1
)


rem ================= 7/7 Verification =================
echo.
echo [7/7] ---------------- Verification ----------------
"%PYEXE%" --version
"%PYEXE%" -c "import pyodbc, webview; print('Modules OK - pilotes SQL Server :', [d for d in pyodbc.drivers() if 'SQL Server' in d])"
if errorlevel 1 (
    echo.
    echo Les modules ne se chargent pas encore. Redemarrez l'ordinateur puis relancez ce script.
    pause
    exit /b 1
)
"%PYEXE%" -c "import pyodbc; c=pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost\\%INSTANCE%;DATABASE=master;Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes', timeout=15); print('Connexion SQL Server OK :', c.cursor().execute('SELECT @@VERSION').fetchone()[0].splitlines()[0])"
if errorlevel 1 (
    echo.
    echo ATTENTION : la connexion a localhost\%INSTANCE% a echoue.
    echo Redemarrez l'ordinateur puis relancez ce script.
    pause
    exit /b 1
)
echo.
if defined REDEMARRAGE (
    echo Termine. SQL Server demande un redemarrage : redemarrez l'ordinateur,
    echo puis lancez lancer_installateur.bat.
) else (
    echo Termine. Vous pouvez lancer lancer_installateur.bat.
)
pause
exit /b 0


rem ================= Sous-routines =================

:has_sql
set "SQL_OK="
reg query "HKLM\SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL" /v %INSTANCE% >nul 2>&1 && set "SQL_OK=1"
if defined SQL_OK sc query "MSSQL$%INSTANCE%" >nul 2>&1 || set "SQL_OK="
exit /b 0

:has_ssms
rem On veut SSMS 20, la version du cours, en francais
set "SSMS_OK="
if exist "%ProgramFiles(x86)%\Microsoft SQL Server Management Studio 20\Common7\IDE\Ssms.exe" set "SSMS_OK=1"
exit /b 0

:find_python
rem Cherche d'abord les chemins d'installation connus : le PATH de cette
rem fenetre n'est pas mis a jour juste apres une installation.
set "PYEXE="
if exist "%ProgramFiles%\Python312\python.exe" set "PYEXE=%ProgramFiles%\Python312\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PYEXE exit /b 0
rem Sinon un Python deja present dans le PATH ; le raccourci Microsoft Store echoue ici
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
rem curl.exe (inclus dans Windows 10/11) affiche une barre de progression ;
rem PowerShell sert de secours s'il est absent ou echoue.
if exist "%~2" del /f /q "%~2" >nul 2>&1
where curl.exe >nul 2>&1 || goto download_ps
curl.exe -L --fail --retry 3 --progress-bar -o "%~2" "%~1"
if not errorlevel 1 if exist "%~2" exit /b 0
if exist "%~2" del /f /q "%~2" >nul 2>&1
:download_ps
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%~1' -OutFile '%~2' -UseBasicParsing; exit 0 } catch { Write-Host ('      Echec du telechargement : ' + $_.Exception.Message); exit 1 }"
if not exist "%~2" exit /b 1
exit /b 0
