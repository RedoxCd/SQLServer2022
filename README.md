# LootTable – Activité SQL Server 2022

🇫🇷 [Français](#français) · 🇬🇧 [English](#english)

---

## Français

### Présentation
Activité des **Portes Ouvertes de l'ETML** (projet P_BD_141) pour des visiteurs sans connaissances en informatique. En **5 à 8 minutes**, le visiteur découvre SQL Server 2022 à travers une boutique de jeux vidéo : il cherche un jeu, l'offre à un ami, constate l'effet d'un **index** sur 10 millions de lignes, puis assiste à une **panne** et à la **restauration** de la base.

Base **LootTable** : `t_jeux` (42 jeux), `t_joueur` (10 000 000 joueurs), `t_achats`.

### Prérequis
- Windows 10 ou 11 (64 bits), droits **administrateur**
- **25 Go libres** sur le disque `C:`
- Internet pour l'installation (ou l'installeur SQL Server sur clé USB, voir plus bas)

### Installation (3 étapes)
1. **Télécharger le projet** : bouton *Code → Download ZIP* sur GitHub, puis extraire ; ou `git clone https://github.com/RedoxCd/SQLServer2022.git`.
2. **Double-cliquer sur `installer_prerequis.bat`** (15 à 30 min). Il installe tout, même sur un Windows vierge :
   - SQL Server 2022 Express (instance `SQLEXPRESS`, le compte Windows actuel devient administrateur SQL)
   - SSMS, Python 3.12, ODBC Driver 18, WebView2 et les modules Python
   - les dossiers `C:\LootTable\Data` et `C:\LootTable\Backup`, puis il teste la connexion

   Il peut être relancé sans risque. **Sans Internet** : placer `SQLEXPRADV_x64_FRA.exe` (ou `SQLEXPR_x64_ENU.exe`) à côté du script ou dans un dossier `Installeurs\`.
3. **Double-cliquer sur `lancer_installateur.bat`**, puis sur **« Créer la base »** (5 à 10 min). Attendre le message **« Prêt pour l'activité »**.

Ensuite, l'activité se lance avec **`lancer_activite.bat`**.

### Déroulement de l'activité
| Étape | Ce qui se passe |
|---|---|
| 1 | Le visiteur cherche un jeu (petite table, réponse immédiate) |
| 2 | Il l'offre à un ami : ajout du joueur et de l'achat dans une **transaction** |
| 3 | Il cherche son ami parmi 10 millions de joueurs **sans index** : c'est lent, le temps est affiché |
| 4 | L'animateur clique sur **« Activer l'index »** (une sauvegarde différentielle part en arrière-plan) |
| 5 | Même recherche **avec index** : quasi instantanée, les deux temps sont comparés |
| 6 | Le visiteur valide : une **panne** survient (la base disparaît) |
| 7 | L'animateur clique sur **« Restaurer »** : sauvegardes complète → différentielle → journal |
| 8 | Révélation : l'achat et l'ami sont de retour, aucune donnée perdue |
| 9 | L'animateur clique sur **« Reset »** pour le visiteur suivant (1 à 2 min) |

La commande SQL exécutée s'affiche en bas de l'écran pour que l'animateur puisse l'expliquer.

### Pour l'animateur
- **Ctrl+Maj+L** (ou 5 clics rapides sur le logo) affiche ou masque les boutons de l'animateur.
- Faire **« Reset »** après chaque visiteur.
- `demo_app/demo_hors_ligne.html` : version de démonstration sans base de données, qui s'ouvre dans n'importe quel navigateur.

### Dépannage
| Problème | Solution |
|---|---|
| « Base introuvable » au lancement de l'activité | Lancer d'abord `lancer_installateur.bat` |
| SQL Server injoignable | Vérifier le nom du serveur (`localhost\SQLEXPRESS`) dans `installer_app/config.json` et `demo_app/config.json`, ou redémarrer le PC |
| L'installation de SQL Server échoue | Consulter `C:\Program Files\Microsoft SQL Server\160\Setup Bootstrap\Log\Summary.txt` |
| La fenêtre de l'activité ne s'ouvre pas | Relancer `installer_prerequis.bat` (WebView2) |

### Contenu du dépôt
| Dossier / fichier | Rôle |
|---|---|
| `installer_prerequis.bat` | Installe le poste complet |
| `lancer_installateur.bat` / `installer_app/` | Crée la base et les sauvegardes |
| `lancer_activite.bat` / `demo_app/` | L'activité pour les visiteurs |
| `Script/` | Scripts SQL de l'activité (`01` à `08`), lus directement par les applications |
| `Modelisation/LootTable.loo` | MCD et MLD (méthode Merise), à ouvrir avec Looping |

*SQL Server Express ne gère pas la compression des sauvegardes : les fichiers `.bak` sont donc volumineux, d'où les 25 Go requis.*

---

## English

### Overview
Activity for the **ETML Open Days** (project P_BD_141) for visitors with no IT background. In **5 to 8 minutes**, the visitor discovers SQL Server 2022 through a video game shop: they look for a game, give it to a friend, see the effect of an **index** on 10 million rows, then watch a **database failure** and its **restore**.

**LootTable** database: `t_jeux` (42 games), `t_joueur` (10,000,000 players), `t_achats` (purchases).

### Requirements
- Windows 10 or 11 (64-bit), **administrator** rights
- **25 GB free** on drive `C:`
- Internet access during installation (or the SQL Server installer on a USB stick, see below)

### Installation (3 steps)
1. **Download the project**: *Code → Download ZIP* on GitHub, then extract; or `git clone https://github.com/RedoxCd/SQLServer2022.git`.
2. **Double-click `installer_prerequis.bat`** (15 to 30 min). It installs everything, even on a fresh Windows:
   - SQL Server 2022 Express (instance `SQLEXPRESS`, the current Windows account becomes SQL administrator)
   - SSMS, Python 3.12, ODBC Driver 18, WebView2 and the Python modules
   - the `C:\LootTable\Data` and `C:\LootTable\Backup` folders, then it tests the connection

   It can safely be run again. **Offline**: put `SQLEXPRADV_x64_FRA.exe` (or `SQLEXPR_x64_ENU.exe`) next to the script or in an `Installeurs\` folder.
3. **Double-click `lancer_installateur.bat`**, then **"Créer la base"** (5 to 10 min). Wait for **"Prêt pour l'activité"**.

Then start the activity with **`lancer_activite.bat`**.

### How the activity works
| Step | What happens |
|---|---|
| 1 | The visitor looks for a game (small table, instant answer) |
| 2 | They give it to a friend: player and purchase are added in one **transaction** |
| 3 | They search for their friend among 10 million players **without an index**: slow, time displayed |
| 4 | The host clicks **"Activer l'index"** (a differential backup runs in the background) |
| 5 | Same search **with the index**: almost instant, both times are compared |
| 6 | The visitor confirms: a **failure** happens (the database disappears) |
| 7 | The host clicks **"Restaurer"**: full → differential → log backups |
| 8 | Reveal: the purchase and the friend are back, no data lost |
| 9 | The host clicks **"Reset"** for the next visitor (1 to 2 min) |

The SQL command being executed is shown at the bottom of the screen so the host can explain it.

### For the host
- **Ctrl+Shift+L** (or 5 quick clicks on the logo) shows or hides the host buttons.
- Click **"Reset"** after each visitor.
- `demo_app/demo_hors_ligne.html`: demo version without a database, opens in any browser.

### Troubleshooting
| Problem | Solution |
|---|---|
| "Base introuvable" when starting the activity | Run `lancer_installateur.bat` first |
| SQL Server unreachable | Check the server name (`localhost\SQLEXPRESS`) in `installer_app/config.json` and `demo_app/config.json`, or restart the PC |
| SQL Server installation fails | Check `C:\Program Files\Microsoft SQL Server\160\Setup Bootstrap\Log\Summary.txt` |
| The activity window does not open | Run `installer_prerequis.bat` again (WebView2) |

### Repository content
| Folder / file | Purpose |
|---|---|
| `installer_prerequis.bat` | Installs the whole computer |
| `lancer_installateur.bat` / `installer_app/` | Creates the database and the backups |
| `lancer_activite.bat` / `demo_app/` | The activity for visitors |
| `Script/` | SQL scripts of the activity (`01` to `08`), read directly by the apps |
| `Modelisation/LootTable.loo` | Conceptual and logical data models (Merise), open with Looping |

*SQL Server Express does not support backup compression: `.bak` files are large, hence the 25 GB requirement.*
