<#
.SYNOPSIS
    Installe et prépare la démo "Portes Ouvertes" CinemaBilletterie en une
    seule commande : création de la base, passage en recovery FULL,
    génération des 50 millions de billets, sauvegardes FULL + DIFF,
    mise à jour de demo_app/config.json et installation des dépendances Python.

.PARAMETER Server
    Nom de l'instance SQL Server (ex: "localhost", "localhost\SQLEXPRESS").

.PARAMETER BackupDir
    Dossier où seront écrites les sauvegardes .bak / .trn. Créé si absent.

.PARAMETER Driver
    Nom du driver ODBC à écrire dans config.json (optionnel). Ne touche pas
    config.json si omis.

.PARAMETER Force
    Si la base CinemaBilletterie existe déjà, la supprime et la recrée
    proprement au lieu de s'arrêter.

.EXAMPLE
    .\install_demo.ps1 -Server "localhost\SQLEXPRESS" -BackupDir "C:\Demo\Backups"

.NOTES
    Ce script prépare la VRAIE activité (50 millions de billets — ça prend du
    temps, potentiellement plusieurs dizaines de minutes selon la machine).
    Pour un test rapide en cours de développement avec un petit volume,
    exécute directement en SQL :
        EXEC dbo.sp_GenererDonneesCinema @NbBillets = 500000, @TailleLot = 100000;
    (voir README.md, section "Démo interactive").
#>

param(
    [string]$Server = "localhost\SQLEXPRESS",
    [string]$BackupDir = "C:\Demo\Backups",
    [string]$Driver = $null,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$ScriptDir = Join-Path $RepoRoot "Script"
$DemoAppDir = Join-Path $RepoRoot "demo_app"
$ConfigPath = Join-Path $DemoAppDir "config.json"

function Write-Etape($texte) {
    Write-Host ""
    Write-Host "=== $texte ===" -ForegroundColor Cyan
}

function Write-Ok($texte) {
    Write-Host "OK - $texte" -ForegroundColor Green
}

function Invoke-SqlQuery {
    param([string]$Query)
    $sortie = & sqlcmd -S $Server -E -b -h -1 -W -Q $Query 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Échec de la requête SQL (code $LASTEXITCODE) :`n$Query`n$sortie"
    }
    return $sortie
}

function Invoke-SqlFile {
    param([string]$Chemin)
    if (-not (Test-Path $Chemin)) {
        throw "Script SQL introuvable : $Chemin"
    }
    & sqlcmd -S $Server -E -b -i $Chemin
    if ($LASTEXITCODE -ne 0) {
        throw "Échec de l'exécution de $Chemin (code $LASTEXITCODE)."
    }
}

# ---------------------------------------------------------------------- #
# 0. Vérifications préalables
# ---------------------------------------------------------------------- #
Write-Etape "Vérification des prérequis"

if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
    throw "sqlcmd introuvable dans le PATH. Installe 'Microsoft Command Line Utilities for SQL Server' ou les outils SQL Server."
}

try {
    Invoke-SqlQuery "SELECT 1;" | Out-Null
} catch {
    throw "Impossible de se connecter à l'instance '$Server'. Vérifie que le service SQL Server tourne et que le nom d'instance est correct.`n$_"
}
Write-Ok "Connexion à '$Server' réussie."

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}
Write-Ok "Dossier de sauvegardes : $BackupDir"

$CheminFull = Join-Path $BackupDir "CinemaBilletterie_FULL.bak"
$CheminDiff = Join-Path $BackupDir "CinemaBilletterie_DIFF.bak"
$CheminTailLog = Join-Path $BackupDir "CinemaBilletterie_TAILLOG.trn"

# ---------------------------------------------------------------------- #
# 1. Base de données
# ---------------------------------------------------------------------- #
Write-Etape "Base de données CinemaBilletterie"

$existe = (Invoke-SqlQuery "SET NOCOUNT ON; SELECT CASE WHEN DB_ID(N'CinemaBilletterie') IS NOT NULL THEN 1 ELSE 0 END;").Trim()

if ($existe -eq "1") {
    if ($Force) {
        Write-Host "La base existe déjà : suppression (-Force)..." -ForegroundColor Yellow
        Invoke-SqlQuery @"
ALTER DATABASE CinemaBilletterie SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
DROP DATABASE CinemaBilletterie;
"@ | Out-Null
        Invoke-SqlFile (Join-Path $ScriptDir "create_database_script.txt")
        Write-Ok "Base recréée."
    } else {
        Write-Host "La base CinemaBilletterie existe déjà : création ignorée (relance avec -Force pour repartir de zéro)." -ForegroundColor Yellow
    }
} else {
    Invoke-SqlFile (Join-Path $ScriptDir "create_database_script.txt")
    Write-Ok "Base créée."
}

Invoke-SqlQuery "ALTER DATABASE CinemaBilletterie SET RECOVERY FULL;" | Out-Null
Write-Ok "Recovery model : FULL."

# ---------------------------------------------------------------------- #
# 2. Génération des données (50 millions de billets)
# ---------------------------------------------------------------------- #
Write-Etape "Génération des données (peut prendre plusieurs dizaines de minutes)"
Invoke-SqlFile (Join-Path $ScriptDir "create_data_PO.txt")
Write-Ok "Données générées."

# ---------------------------------------------------------------------- #
# 3. Sauvegardes FULL puis DIFF
# ---------------------------------------------------------------------- #
Write-Etape "Sauvegarde complète (FULL)"
Invoke-SqlQuery "BACKUP DATABASE CinemaBilletterie TO DISK = N'$CheminFull' WITH INIT;" | Out-Null
Write-Ok "FULL -> $CheminFull"

Write-Etape "Sauvegarde différentielle (DIFF)"
Invoke-SqlQuery "BACKUP DATABASE CinemaBilletterie TO DISK = N'$CheminDiff' WITH DIFFERENTIAL, INIT;" | Out-Null
Write-Ok "DIFF -> $CheminDiff"

# ---------------------------------------------------------------------- #
# 4. Mise à jour de demo_app/config.json
# ---------------------------------------------------------------------- #
Write-Etape "Mise à jour de config.json"

if (-not (Test-Path $ConfigPath)) {
    throw "config.json introuvable : $ConfigPath"
}
$config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

$config.connexion.server = $Server
if ($Driver) { $config.connexion.driver = $Driver }
$config.sauvegardes.full = $CheminFull
$config.sauvegardes.diff = $CheminDiff
$config.sauvegardes.tail_log = $CheminTailLog

$jsonTexte = $config | ConvertTo-Json -Depth 10
# Ecriture explicite en UTF-8 SANS BOM : Set-Content -Encoding UTF8 ajoute un
# BOM sous PowerShell 5.1, ce qui ferait planter json.load() côté Python.
[System.IO.File]::WriteAllText($ConfigPath, $jsonTexte, (New-Object System.Text.UTF8Encoding $false))
Write-Ok "config.json mis à jour (server, chemins de sauvegarde)."

# ---------------------------------------------------------------------- #
# 5. Dépendances Python
# ---------------------------------------------------------------------- #
Write-Etape "Dépendances Python"

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m pip install -r (Join-Path $DemoAppDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Échec de pip install -- installe les dépendances manuellement." -ForegroundColor Yellow
    } else {
        Write-Ok "Dépendances installées."
    }
} else {
    Write-Host "Python introuvable dans le PATH : installe-le puis lance 'pip install -r demo_app\requirements.txt' manuellement." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------- #
Write-Host ""
Write-Host "=== Installation terminée ===" -ForegroundColor Green
Write-Host "Pour lancer la démo :" -ForegroundColor Green
Write-Host "  cd demo_app" -ForegroundColor Green
Write-Host "  python main.py" -ForegroundColor Green
