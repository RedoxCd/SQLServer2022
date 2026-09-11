# SQLServer2022
This project is for the "Porte Ouverte de l'ETML", where people without any IT knowledge will discover the SQL Server 2022 software. The public will have an activity that is 5 to 7 minutes long to complete and have fun.

## Modeling
If you have any issues understanding how the database works and how the connections between tables are made, you can check **Porte_Ouverte.loo**. It will open Looping, which is the modeling software that I used. Both MCD and MLD (Merise method) can be checked.

## Script
### 1: 
In the folder "Script", create_data_base.txt is the script to create the database and the table, it has to be executed before any other script or operations.  
### 2:
Again in "Script" folder, create_data_PO.txt is the big script to create every data(50 million) at once.

__*Disclaimer:*__ Since we are creating around 50 million records at once, the IDENTITY column of the t_billets table might be too small—even though it can hold up to 2.14 billion records. So don't forget to drop the table if you re-execute the script.

## Démo interactive (application pywebview)

Le dossier [demo_app/](demo_app/) contient l'application autonome (pywebview + pyodbc)
utilisée le jour des Portes Ouvertes : vente de billets en direct, incident
(DELETE massif) puis restauration en 3 étapes (FULL / DIFF / LOG avec STOPAT).

### Préparation (à faire avant l'événement)

1. Exécuter `Script/create_database_script.txt`.
2. **Passer la base en recovery model FULL** (indispensable pour les sauvegardes
   DIFF et LOG utilisées par la démo) :
   ```sql
   ALTER DATABASE CinemaBilletterie SET RECOVERY FULL;
   ```
3. Exécuter `Script/create_data_PO.txt` (génération des 50 millions de billets).
4. Prendre la sauvegarde complète (FULL) :
   ```sql
   BACKUP DATABASE CinemaBilletterie TO DISK = 'C:\Demo\Backups\CinemaBilletterie_FULL.bak' WITH INIT;
   ```
5. (optionnel) Simuler un peu d'activité, puis prendre la sauvegarde
   différentielle (DIFF) :
   ```sql
   BACKUP DATABASE CinemaBilletterie TO DISK = 'C:\Demo\Backups\CinemaBilletterie_DIFF.bak' WITH DIFFERENTIAL, INIT;
   ```
6. Adapter `demo_app/config.json` (serveur, driver ODBC, chemins des `.bak`/`.trn`)
   à la machine utilisée le jour J.
7. Lancer l'application : voir [demo_app/README d'utilisation ci-dessous](#lancement).

### Lancement

```
cd demo_app
pip install -r requirements.txt
python main.py
```

### Empaquetage en .exe portable

```
pip install pyinstaller
cd demo_app
pyinstaller --onefile --windowed --name DemoSQLServer2022 --add-data "index.html;." --add-data "style.css;." --add-data "app.js;." main.py
```

Puis copier `config.json` et le dossier `sql/` à côté de `dist/DemoSQLServer2022.exe`
(ils restent volontairement en dehors du `.exe` pour être modifiables le jour J
sans reconstruire le paquet). Sous Linux/macOS, remplacer `;` par `:` dans les
options `--add-data`.
