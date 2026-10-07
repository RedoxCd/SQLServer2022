# SQLServer2022
This project is for the "Porte Ouverte de l'ETML", where people without any IT knowledge will discover the SQL Server 2022 software. The public will have an activity that is 5 to 8 minutes long to complete and have fun.

The demo uses the **LootTable** database (a video game shop): 10 million players, a small catalogue of games and the purchases (`t_jeux`, `t_joueur`, `t_achats`).

## Modeling
If you have any issues understanding how the database works and how the connections between tables are made, you can check **Modelisation/LootTable.loo**. It will open Looping, which is the modeling software that I used. Both MCD and MLD (Merise method) can be checked.

## Installation en un clic
Pour préparer la base sans lancer les scripts à la main, utilise l'installateur, **puis** l'activité :

1. Double-clique sur `lancer_installateur.bat` (ou `python installer_app/main.py`).
2. Vérifie les prérequis affichés (✔ / ⚠ / ✘) : SQL Server joignable, édition, dossiers `C:\LootTable\Data` et `C:\LootTable\Backup` (créés au besoin), **25 Go libres**, base déjà existante (une confirmation est demandée avant de l'écraser).
3. Clique sur **« Créer la base »**. L'installateur exécute, dans l'ordre, `01_create_database.sql`, `02_generate_data.sql`, `03_golden_backup.sql` puis `07_reset.sql` (quelques minutes, environ **5 à 10 min** ; étape en cours, temps écoulé et progression des joueurs affichés). En cas d'erreur, le message SQL complet est affiché avec un bouton « Réessayer ».
4. À la fin, un contrôle automatique affiche « Prêt pour l'activité » (10 000 000 joueurs, 42 jeux, `idx_pseudo` désactivé, `LootTable_GOLDEN.bak` et `LootTable_FULL.bak` présents). Le bouton « Vérifier l'installation » refait ce contrôle sans rien modifier.
5. Lance l'activité avec `lancer_activite.bat` (ou `python demo_app/main.py`). Si la base n'est pas installée, elle affiche « Base introuvable : lancez d'abord l'installateur ».

Les réglages (serveur, dossier **Script/**, dossiers de données et de sauvegardes, espace minimum) sont dans `installer_app/config.json`. `python installer_app/smoke_test.py` lance les vérifications sans rien créer.

Les sauvegardes ne sont **pas compressées** (SQL Server Express ne supporte pas `COMPRESSION`) : les `.bak` sont donc plus volumineux qu'avec compression.

## Sur un autre PC (Sébeillon)
1. Cloner le dépôt : `git clone https://github.com/RedoxCd/SQLServer2022.git`
2. Installer **Python 3** et l'**ODBC Driver 18 for SQL Server**, puis `pip install -r installer_app/requirements.txt` (identique à `demo_app/requirements.txt`).
3. Vérifier le nom du serveur dans `installer_app/config.json` et `demo_app/config.json` (par défaut `localhost\SQLEXPRESS`).
4. Lancer `lancer_installateur.bat` : **25 Go libres** sont requis sur le disque. Puis `lancer_activite.bat`.

## Script
Everything lives in the **Script/** folder. Create `C:\LootTable\Backup` (write access for the SQL Server service account) before starting, then run in this order:

1. `create_database_script.txt` — creates the LootTable database and its three tables. It has to be executed before any other script or operation.
2. `create_data_loot_table.txt` — the big script that generates the data (10 million players, the games and a few purchases) at once. It empties the tables and reseeds the IDENTITY columns first, so it can be re-executed.
3. `03_golden_backup.sql` — the « GOLDEN » backup (initial state of the demo). Before running it, check that `idx_pseudo` is disabled (`is_disabled = 1`): the demo relies on it.
4. `07_reset.sql` — restores GOLDEN and creates the FULL backup that starts the FULL / DIFF / LOG chain. The database is then ready for the demo.

`create_database_script.txt` and `create_data_loot_table.txt` are kept as they are. `01_create_database.sql` and `02_generate_data.sql` are an equivalent variant (42 real games, files in `C:\LootTable\Data`) and can replace steps 1 and 2.

### Don't want to generate 10 million rows?
The backup file can be downloaded instead: open the page in **backup-download/** (`index.html`, it downloads `LootTable.bak`). Rename it `LootTable_GOLDEN.bak`, put it in `C:\LootTable\Backup`, then run `07_reset.sql` (steps 1 to 3 are not needed). Keep a copy on a USB drive.

### The demo, step by step
The scripts below are the reference of the demo; the application reads them directly from **Script/** (nothing is copied).

| Step | What happens | Script |
|---|---|---|
| 1 | The visitor looks for a game (`t_jeux`, small table, fast) | app |
| 2 | The visitor offers it to a friend: INSERT in `t_joueur` then `t_achats`, in one transaction | app |
| 3 | The visitor searches the friend in `t_joueur` (10 M rows, `idx_pseudo` disabled): slow, duration displayed | app |
| 4 | The host clicks « Activer l'index », then the DIFF backup starts in the background | `04a_activer_index.sql`, `04b_backup_diff.sql` |
| 5 | Same search: almost instant, both durations side by side | app |
| 6 | The visitor clicks « OK »: the app writes a validation in the database, then silently triggers the incident (log backup, detach) | `05_incident.sql` |
| 7 | The host clicks « Restaurer »: FULL → DIFF → LOG, durations displayed | `06_restore_chain.sql` |
| 8 | Reveal: the last purchase and the friend's nickname are back | last SELECT of `06` |
| 9 | The host clicks « Reset » for the next visitor (1 to 2 min) | `07_reset.sql` |

`08_verification.sql` contains control queries, and `Script/LISEZ-MOI_demo.md` the execution order and what to measure during rehearsals.

## Application (demo_app/)
A pywebview window (Python + pyodbc) that drives the demo.

```
pip install -r demo_app/requirements.txt
python demo_app/main.py
```

Settings are in `demo_app/config.json`:
- `connexion`: SQL Server instance, driver, authentication. The app stays connected to `master` and prefixes table names (`LootTable.dbo.t_jeux`), so that detach and restore are never blocked by an open connection.
- `scripts.dossier`: path of the **Script/** folder (relative to `config.json`, `../Script` by default).
- `sauvegardes.dossier`: folder of the `.bak` files (`C:\LootTable\Backup`). The file names come from the scripts; the app only checks that they exist before a restore.

Host buttons (« Activer l'index », « Restaurer », « Reset ») are hidden: press **Ctrl+Shift+L**, or click the logo 5 times quickly, to show or hide the host panel.

`demo_app/smoke_test.py` plays the whole scenario without the interface and prints the duration of each step. It really runs the scripts (detach, restore, reset): use it only on the demo database, with the app closed (`python demo_app/smoke_test.py`).

Each step shows the SQL command being executed at the bottom of the screen (« Commande SQL »), so the host can explain it to the visitor. The app queries are in `SQL_AFFICHE` (`main.py`); the host scripts are read from **Script/**. The cause of the outage (`05_incident.sql`) is never displayed.

`demo_app/demo_hors_ligne.html` is a standalone version with no database, to try the activity in any browser. It is generated: after changing `index.html`, `style.css`, `app.js` or `mock_api.js`, run `python demo_app/build_hors_ligne.py`.
