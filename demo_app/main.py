"""Démo interactive SQL Server 2022 — Portes Ouvertes ETML (thème LootTable).

Fenêtre pywebview affichant index.html, avec une classe Api exposée au
JavaScript (window.pywebview.api) pour piloter la démo : catalogue de jeux,
cadeau à un ami (INSERT dans une transaction), recherche lente puis rapide
(index activé par l'animateur), incident silencieux puis restauration.

Les scripts SQL de l'animateur (04a, 04b, 05, 06, 07) sont lus tels quels dans
le dossier Script/ du dépôt : aucune copie n'est faite dans demo_app/.
"""

import functools
import json
import ntpath
import re
import sys
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pyodbc
import webview

# Une seule connexion vivante côté appli (+ une éphémère pour la sauvegarde
# DIFF en arrière-plan) : le pooling ODBC pourrait sinon laisser traîner une
# connexion fantôme, et RESTORE DATABASE / DETACH exigent un accès exclusif.
pyodbc.pooling = False

RE_GO = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)
RE_COMMENTAIRE_DEBUT = re.compile(r"\A\s*(?:/\*.*?\*/|--[^\n]*(?:\n|\Z))", re.DOTALL)
RE_USE_DEBUT = re.compile(r"\A\s*USE\s+\[?(\w+)\]?\s*;?", re.IGNORECASE)
RE_RESTORE_DISK = re.compile(
    r"RESTORE\s+(?:DATABASE|LOG)\s+\w+\s+FROM\s+DISK\s*=\s*N'([^']+)'", re.IGNORECASE
)

# Scripts de la démo (dossier Script/, faisant foi).
SCRIPT_INDEX = "04a_activer_index.sql"
SCRIPT_BACKUP_DIFF = "04b_backup_diff.sql"
SCRIPT_INCIDENT = "05_incident.sql"
SCRIPT_RESTORE = "06_restore_chain.sql"
SCRIPT_RESET = "07_reset.sql"

# Commandes affichées à l'écran pour expliquer les étapes de l'appli (les {valeurs}
# sont remplies côté JavaScript). Les scripts de l'animateur, eux, sont lus dans Script/.
SQL_AFFICHE = {
    "jeux": (
        "SELECT TOP (50) jeux_id, titre, plateforme, genre, prix, editeur, anneeSortie\n"
        "FROM LootTable.dbo.t_jeux\n"
        "WHERE titre LIKE '%{texte}%' OR genre LIKE '%{texte}%' OR plateforme LIKE '%{texte}%'\n"
        "ORDER BY titre;"
    ),
    "offrir": (
        "-- Tout ou rien : si une des deux lignes échoue, rien n'est enregistré\n"
        "BEGIN TRANSACTION;\n"
        "\n"
        "INSERT INTO LootTable.dbo.t_joueur (pseudo, dateCreation)\n"
        "VALUES ('{ami}', SYSDATETIME());\n"
        "\n"
        "INSERT INTO LootTable.dbo.t_achats (jeux_id, joueur_id, prixPaye, dateAchat, offertPar)\n"
        "VALUES ({jeux_id}, SCOPE_IDENTITY(), {prix}, SYSDATETIME(), '{visiteur}');\n"
        "\n"
        "COMMIT TRANSACTION;"
    ),
    "joueur": (
        "SELECT joueur_id, pseudo, dateCreation\n"
        "FROM LootTable.dbo.t_joueur\n"
        "WHERE pseudo = '{pseudo}';"
    ),
}
SQL_SCRIPTS = {
    "index": [SCRIPT_INDEX, SCRIPT_BACKUP_DIFF],
    "restauration": [SCRIPT_RESTORE],
    "reset": [SCRIPT_RESET],
}

TYPES_RESTAURATION = {"D": "FULL", "I": "DIFF", "L": "LOG"}
LONGUEUR_PSEUDO_MAX = 50
MESSAGE_BASE_INTROUVABLE = "Base introuvable : lancez d'abord l'installateur"


def base_dir() -> Path:
    """Dossier contenant l'exécutable (ou le script) : config.json y vit en
    dehors du bundle PyInstaller pour rester éditable le jour J."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def resource_dir() -> Path:
    """Dossier des ressources embarquées (index.html/style.css/app.js),
    potentiellement extraites par PyInstaller dans sys._MEIPASS."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


BASE_DIR = base_dir()
CONFIG_PATH = BASE_DIR / "config.json"


def _json(valeur):
    """Convertit les types SQL non sérialisables en JSON (Decimal, dates)."""
    if isinstance(valeur, Decimal):
        return float(valeur)
    if isinstance(valeur, datetime):
        return valeur.isoformat(sep=" ", timespec="seconds")
    if isinstance(valeur, date):
        return valeur.isoformat()
    return valeur


def _lignes_en_dicts(resultat):
    cols = resultat["colonnes"]
    return [{c: _json(v) for c, v in zip(cols, ligne)} for ligne in resultat["lignes"]]


def _api(fonction):
    """Méthode exposée au JS : vérifie la connexion et convertit toute erreur
    en {"success": False, "error": ...} plutôt que de lever côté JavaScript."""

    @functools.wraps(fonction)
    def enveloppe(self, *args, **kwargs):
        erreur = self._verifier_pret()
        if erreur:
            return {"success": False, "error": erreur}
        try:
            return fonction(self, *args, **kwargs)
        except Exception as e:  # noqa: BLE001 - tout est renvoyé à l'UI
            return self._echec(e)

    return enveloppe


class Api:
    # Tous les attributs d'état commencent par « _ » : pywebview n'expose au
    # JavaScript que les attributs publics (donc uniquement les méthodes d'API).
    def __init__(self):
        self._conn = None
        self._config = None
        self._db = "LootTable"
        self.erreur_demarrage = None  # lu par _verifier_pret
        self._verrou = threading.RLock()  # une seule requête à la fois sur _conn
        self._operation_en_cours = None
        self._index_active = False
        self._dernier_achat_id = None
        self._thread_backup = None
        self._backup = {"etat": "inactif", "duree_ms": None, "erreur": None}

        try:
            self._config = self._charger_config()
            self._db = self._config["connexion"]["database"]
        except Exception as e:
            self.erreur_demarrage = f"Impossible de lire config.json : {e}"
            return

        try:
            self._conn = self._nouvelle_connexion()
            self.erreur_demarrage = self._message_base_introuvable()
        except Exception as e:
            self.erreur_demarrage = self._message_erreur(e)

    # ------------------------------------------------------------------ #
    # Configuration & connexion
    # ------------------------------------------------------------------ #
    def _charger_config(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"Fichier introuvable : {CONFIG_PATH}")
        # utf-8-sig : tolère un BOM (ex: fichier ré-édité avec Notepad sous Windows)
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _nouvelle_connexion(self):
        cfg = self._config["connexion"]
        morceaux = [
            f"DRIVER={{{cfg['driver']}}}",
            f"SERVER={cfg['server']}",
            # On se connecte toujours sur master : la base de démo ne doit
            # jamais rester « USE »-ée, sous peine de bloquer 05, 06 et 07
            # (SINGLE_USER, DETACH, RESTORE exigent un accès exclusif).
            "DATABASE=master",
        ]
        if cfg.get("trusted_connection", True):
            morceaux.append("Trusted_Connection=yes")
        else:
            morceaux.append(f"UID={cfg.get('user', '')}")
            morceaux.append(f"PWD={cfg.get('password', '')}")
        morceaux.append(f"Encrypt={'yes' if cfg.get('encrypt') else 'no'}")
        morceaux.append(
            "TrustServerCertificate="
            + ("yes" if cfg.get("trust_server_certificate", True) else "no")
        )
        chaine = ";".join(morceaux) + ";"
        return pyodbc.connect(
            chaine, timeout=cfg.get("timeout_secondes", 30), autocommit=True
        )

    def reessayer_connexion(self):
        """Appelé depuis l'UI si la connexion initiale (ou en cours de route) a échoué."""
        with self._verrou:
            try:
                if not self._config:
                    self._config = self._charger_config()
                    self._db = self._config["connexion"]["database"]
                if self._conn is not None:
                    try:
                        self._conn.close()
                    except pyodbc.Error:
                        pass
                self._conn = self._nouvelle_connexion()
                self.erreur_demarrage = self._message_base_introuvable()
            except Exception as e:
                self.erreur_demarrage = self._message_erreur(e)
                return {"success": False, "error": self.erreur_demarrage}
        return self.get_status()

    def _message_base_introuvable(self):
        """Message à afficher si la base n'a jamais été installée, sinon None.
        Une base absente mais ayant un historique de sauvegardes (détachée par
        l'incident de la démo) n'est PAS « introuvable » : c'est la panne, que
        « Restaurer » répare."""
        try:
            if self._requete("SELECT DB_ID(?);", self._db)[0][0] is not None:
                return None
            nb = self._requete(
                "SELECT COUNT(*) FROM msdb.dbo.backupset WHERE database_name = ?;", self._db
            )[0][0]
            return MESSAGE_BASE_INTROUVABLE if nb == 0 else None
        except pyodbc.Error:
            return None  # msdb illisible : on laisse l'appli démarrer normalement

    def _message_erreur(self, err):
        if isinstance(err, pyodbc.Error) and err.args:
            return " ".join(str(a) for a in err.args)
        return str(err)

    def _echec(self, err):
        """Transforme une exception en réponse d'erreur ; une coupure de
        connexion (SQLSTATE 08xxx) invalide la connexion pour proposer « Réessayer »."""
        msg = self._message_erreur(err)
        if isinstance(err, pyodbc.Error) and err.args and str(err.args[0]).startswith("08"):
            self._conn = None
            self.erreur_demarrage = f"Connexion à SQL Server perdue : {msg}"
            return {"success": False, "error": self.erreur_demarrage}
        if isinstance(err, (pyodbc.Error, FileNotFoundError, ValueError)):
            return {"success": False, "error": msg}
        return {"success": False, "error": f"Erreur inattendue : {msg}"}

    def _verifier_pret(self):
        if self.erreur_demarrage:
            return self.erreur_demarrage
        if not self._conn:
            return "Aucune connexion à la base de données."
        return None

    # ------------------------------------------------------------------ #
    # Scripts SQL (lus dans Script/, jamais copiés)
    # ------------------------------------------------------------------ #
    def _dossier_scripts(self):
        dossier = Path(self._config.get("scripts", {}).get("dossier", "../Script"))
        return (dossier if dossier.is_absolute() else BASE_DIR / dossier).resolve()

    def _lire_script(self, nom):
        chemin = self._dossier_scripts() / nom
        if not chemin.exists():
            raise FileNotFoundError(
                f"Script introuvable : {chemin}\n"
                "Vérifie le chemin dans config.json (section \"scripts\")."
            )
        # utf-8-sig : les scripts du dossier Script/ commencent par un BOM
        return chemin.read_text(encoding="utf-8-sig")

    def _verifier_fichiers(self, texte_sql):
        """Vérifie que les .bak lus par un script (RESTORE ... FROM DISK) sont
        bien dans le dossier de sauvegardes. Les noms viennent du script."""
        dossier = self._config.get("sauvegardes", {}).get("dossier")
        if not dossier:
            return
        for chemin in RE_RESTORE_DISK.findall(texte_sql):
            nom = ntpath.basename(chemin)
            try:
                if not (Path(dossier) / nom).exists():
                    raise FileNotFoundError(
                        f"Sauvegarde introuvable : {Path(dossier) / nom}\n"
                        "Vérifie le dossier \"sauvegardes\" dans config.json "
                        "(et que la démo a bien été déroulée jusqu'ici)."
                    )
            except OSError:
                # Dossier non accessible depuis ce poste (SQL Server distant) :
                # SQL Server lèvera lui-même l'erreur.
                pass

    @staticmethod
    def _extraire_use(lot):
        """Sépare les « USE base; » en tête de lot (commentaires ignorés) du
        reste : USE est exécuté dans une requête à part, car combiné à un
        SELECT il fait pointer fetch*() sur le résultat (vide) du USE."""
        bases = []
        reste = lot
        while True:
            m = RE_COMMENTAIRE_DEBUT.match(reste)
            if m:
                reste = reste[m.end():]
                continue
            m = RE_USE_DEBUT.match(reste)
            if m:
                bases.append(m.group(1))
                reste = reste[m.end():]
                continue
            break
        return reste.strip(), bases

    @staticmethod
    def _drainer(cursor):
        """Parcourt tous les résultats d'un lot. Indispensable pour BACKUP /
        RESTORE : avec pyodbc, ils ne sont terminés (et leurs erreurs levées)
        qu'une fois les résultats/messages consommés via nextset()."""
        resultats = []
        while True:
            if cursor.description:
                resultats.append(
                    {
                        "colonnes": [c[0] for c in cursor.description],
                        "lignes": [list(r) for r in cursor.fetchall()],
                    }
                )
            if not cursor.nextset():
                break
        return resultats

    def _executer_script(self, conn, texte_sql):
        """Exécute un script lot par lot (séparateur GO) et renvoie la liste
        des jeux de résultats. Quoi qu'il arrive, la connexion repasse sur master."""
        resultats = []
        cursor = conn.cursor()
        try:
            for lot in RE_GO.split(texte_sql):
                lot, bases = self._extraire_use(lot.strip())
                for base in bases:
                    cursor.execute(f"USE [{base}];")
                    self._drainer(cursor)
                if lot:
                    cursor.execute(lot)
                    resultats.extend(self._drainer(cursor))
        finally:
            try:
                cursor.execute("USE master;")
                self._drainer(cursor)
            except pyodbc.Error:
                pass
            cursor.close()
        return resultats

    @contextmanager
    def _operation(self, nom):
        """Section exclusive sur la connexion applicative ; get_status() voit
        `nom` sans toucher à la base pendant les opérations longues."""
        with self._verrou:
            self._operation_en_cours = nom
            try:
                yield
            finally:
                self._operation_en_cours = None

    def _requete(self, sql, *params):
        """SELECT court sur la connexion applicative (noms préfixés par la base)."""
        with self._verrou:
            cursor = self._conn.cursor()
            try:
                cursor.execute(sql, *params)
                return cursor.fetchall()
            finally:
                cursor.close()

    def _nom(self, table):
        return f"[{self._db}].dbo.{table}"

    def _index_desactive(self):
        """is_disabled de idx_pseudo (None si l'index n'existe pas)."""
        rows = self._requete(
            f"SELECT is_disabled FROM [{self._db}].sys.indexes "
            "WHERE object_id = OBJECT_ID(?) AND name = 'idx_pseudo';",
            f"{self._db}.dbo.t_joueur",
        )
        return bool(rows[0][0]) if rows else None

    @staticmethod
    def _pseudo_valide(valeur, libelle):
        pseudo = (valeur or "").strip()
        if not pseudo:
            raise ValueError(f"{libelle} : merci d'écrire un pseudo.")
        if len(pseudo) > LONGUEUR_PSEUDO_MAX:
            raise ValueError(f"{libelle} : {LONGUEUR_PSEUDO_MAX} caractères maximum.")
        return pseudo

    # ------------------------------------------------------------------ #
    # Sauvegarde différentielle en arrière-plan (04b)
    # ------------------------------------------------------------------ #
    def _lancer_backup_diff(self, texte_sql):
        self._backup = {"etat": "en_cours", "duree_ms": None, "erreur": None}
        self._thread_backup = threading.Thread(
            target=self._backup_diff, args=(texte_sql,), daemon=True
        )
        self._thread_backup.start()

    def _backup_diff(self, texte_sql):
        # Connexion dédiée (sur master) : la connexion applicative reste libre
        # pour la recherche rapide du visiteur. Fermée dès la fin du script.
        debut = time.perf_counter()
        conn = None
        try:
            conn = self._nouvelle_connexion()
            self._executer_script(conn, texte_sql)
            self._backup = {
                "etat": "ok",
                "duree_ms": round((time.perf_counter() - debut) * 1000),
                "erreur": None,
            }
        except Exception as e:  # noqa: BLE001
            self._backup = {"etat": "erreur", "duree_ms": None, "erreur": self._message_erreur(e)}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except pyodbc.Error:
                    pass

    def _attendre_backup(self):
        t = self._thread_backup
        if t is not None and t.is_alive():
            t.join()

    # ------------------------------------------------------------------ #
    # API exposée au JavaScript
    # ------------------------------------------------------------------ #
    def get_sql(self, nom):
        """Texte SQL à afficher à l'écran pour l'étape `nom` (aucun accès à la base)."""
        try:
            if nom in SQL_AFFICHE:
                return {"success": True, "sql": SQL_AFFICHE[nom]}
            if nom not in SQL_SCRIPTS:
                raise ValueError(f"Commande inconnue : {nom}")
            if not self._config:
                raise FileNotFoundError("config.json non chargé.")
            textes = [self._lire_script(f).strip() for f in SQL_SCRIPTS[nom]]
            return {"success": True, "sql": "\n\n".join(textes)}
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}

    @_api
    def get_status(self):
        base = {
            "success": True,
            "operation": self._operation_en_cours,
            "sauvegarde": dict(self._backup),
            "index_active": self._index_active,
        }
        # Opération longue en cours (rebuild, restore, reset...) : la connexion
        # est occupée, on répond sans toucher à la base.
        if not self._verrou.acquire(blocking=False):
            return {**base, "occupe": True, "etat": None}
        try:
            rows = self._requete(
                "SELECT state_desc FROM sys.databases WHERE name = ?;", self._db
            )
            if not rows:
                return {**base, "occupe": False, "etat": "absente"}  # détachée : panne
            etat = rows[0][0].lower()  # online, restoring, ...
            rep = {**base, "occupe": False, "etat": "en_ligne" if etat == "online" else etat}
            if etat == "online":
                rep["index_desactive"] = self._index_desactive()
            return rep
        finally:
            self._verrou.release()

    @_api
    def rechercher_jeux(self, texte=""):
        texte = (texte or "").strip()[:100]
        echappe = re.sub(r"([\\%_\[])", r"\\\1", texte)
        motif = f"%{echappe}%"
        rows = self._requete(
            "SELECT TOP (50) jeux_id, titre, plateforme, genre, prix, editeur, anneeSortie "
            f"FROM {self._nom('t_jeux')} "
            "WHERE titre LIKE CAST(? AS VARCHAR(200)) ESCAPE '\\' "
            "OR genre LIKE CAST(? AS VARCHAR(200)) ESCAPE '\\' "
            "OR plateforme LIKE CAST(? AS VARCHAR(200)) ESCAPE '\\' "
            "ORDER BY titre;",
            motif, motif, motif,
        )
        jeux = [
            {
                "jeux_id": r[0], "titre": r[1], "plateforme": r[2], "genre": r[3],
                "prix": float(r[4]), "editeur": r[5], "annee": r[6],
            }
            for r in rows
        ]
        return {"success": True, "jeux": jeux}

    @_api
    def offrir_jeu(self, jeux_id, pseudo_ami, pseudo_visiteur):
        """Cadeau : nouveau joueur (l'ami) puis achat (prixPaye = prix du jeu,
        offertPar = pseudo du visiteur), le tout dans une seule transaction."""
        jeux_id = int(jeux_id)
        ami = self._pseudo_valide(pseudo_ami, "Pseudo de ton ami")
        visiteur = self._pseudo_valide(pseudo_visiteur, "Ton pseudo")
        with self._verrou:
            cursor = self._conn.cursor()
            try:
                cursor.execute(
                    "SET NOCOUNT ON; SET XACT_ABORT ON; "
                    "DECLARE @prix DECIMAL(5,2), @joueur INT, @achat INT; "
                    "BEGIN TRANSACTION; "
                    f"SELECT @prix = prix FROM {self._nom('t_jeux')} WHERE jeux_id = ?; "
                    "IF @prix IS NULL THROW 50001, N'Jeu introuvable.', 1; "
                    f"INSERT INTO {self._nom('t_joueur')} (pseudo, dateCreation) "
                    "VALUES (CAST(? AS VARCHAR(50)), SYSDATETIME()); "
                    "SET @joueur = SCOPE_IDENTITY(); "
                    f"INSERT INTO {self._nom('t_achats')} "
                    "(jeux_id, joueur_id, prixPaye, dateAchat, offertPar) "
                    "VALUES (?, @joueur, @prix, SYSDATETIME(), CAST(? AS VARCHAR(50))); "
                    "SET @achat = SCOPE_IDENTITY(); "
                    "COMMIT TRANSACTION; "
                    "SELECT @achat, @joueur, @prix;",
                    jeux_id, ami, jeux_id, visiteur,
                )
                achat_id, joueur_id, prix = cursor.fetchone()
            finally:
                cursor.close()
            self._dernier_achat_id = achat_id
        return {
            "success": True,
            "achats_id": achat_id,
            "joueur_id": joueur_id,
            "prix_paye": float(prix),
        }

    @_api
    def rechercher_joueur(self, pseudo):
        """Recherche exacte dans t_joueur (10 M de lignes). La durée mesurée
        (ms) couvre exécution + lecture du résultat ; idx_pseudo désactivé =
        lecture complète de la table, activé = accès direct."""
        pseudo = self._pseudo_valide(pseudo, "Pseudo")
        with self._verrou:
            cursor = self._conn.cursor()
            try:
                debut = time.perf_counter()
                cursor.execute(
                    "SELECT joueur_id, pseudo, dateCreation "
                    f"FROM {self._nom('t_joueur')} WHERE pseudo = CAST(? AS VARCHAR(50));",
                    pseudo,
                )
                rows = cursor.fetchall()
                duree_ms = round((time.perf_counter() - debut) * 1000)
            finally:
                cursor.close()
            index_desactive = self._index_desactive()
        joueurs = [
            {"joueur_id": r[0], "pseudo": r[1], "dateCreation": _json(r[2])} for r in rows
        ]
        return {
            "success": True,
            "trouve": bool(joueurs),
            "joueurs": joueurs,
            "duree_ms": duree_ms,
            "index_desactive": index_desactive,
        }

    @_api
    def activer_index(self):
        """04a (REBUILD, durée mesurée) puis 04b (LOG0 + DIFF) en arrière-plan."""
        script_index = self._lire_script(SCRIPT_INDEX)
        script_backup = self._lire_script(SCRIPT_BACKUP_DIFF)
        with self._operation("index"):
            debut = time.perf_counter()
            self._executer_script(self._conn, script_index)
            duree_ms = round((time.perf_counter() - debut) * 1000)
            self._index_active = True
        self._lancer_backup_diff(script_backup)
        return {"success": True, "duree_ms": duree_ms, "backup_lance": True}

    @_api
    def valider_achat(self):
        """Clic « OK » du visiteur : écrit une opération dans la base (pour que
        le log de transactions ne soit pas vide) puis lance l'incident (05) en silence."""
        script_incident = self._lire_script(SCRIPT_INCIDENT)
        if not self._index_active or self._backup["etat"] == "inactif":
            raise ValueError(
                "L'index n'a pas été activé : la sauvegarde différentielle "
                "(étape 4) manque, la restauration serait impossible."
            )
        # BACKUP LOG (05) ne doit pas chevaucher le BACKUP DIFF (04b)
        self._attendre_backup()
        if self._backup["etat"] == "erreur":
            raise ValueError(
                "La sauvegarde différentielle (04b) a échoué : " + (self._backup["erreur"] or "")
            )
        with self._operation("incident"):
            cursor = self._conn.cursor()
            try:
                achat_id = self._dernier_achat_id
                if achat_id is None:
                    cursor.execute(f"SELECT MAX(achats_id) FROM {self._nom('t_achats')};")
                    achat_id = cursor.fetchone()[0]
                cursor.execute(
                    f"UPDATE {self._nom('t_achats')} SET dateAchat = SYSDATETIME() "
                    "WHERE achats_id = ?;",
                    achat_id,
                )
                if cursor.rowcount == 0:
                    raise ValueError("Aucun achat à valider dans t_achats.")
            finally:
                cursor.close()
            debut = time.perf_counter()
            self._executer_script(self._conn, script_incident)
            duree_ms = round((time.perf_counter() - debut) * 1000)
        return {"success": True, "panne": True, "duree_ms": duree_ms}

    @_api
    def restaurer(self):
        """06 : FULL -> DIFF -> LOG (STOPAT). Renvoie les durées de chaque
        restauration (lues dans msdb) et le reveal (derniers achats)."""
        script = self._lire_script(SCRIPT_RESTORE)
        self._verifier_fichiers(script)
        with self._operation("restauration"):
            cursor = self._conn.cursor()
            try:
                cursor.execute("SELECT SYSDATETIME();")
                debut_serveur = cursor.fetchone()[0]
            finally:
                cursor.close()
            debut = time.perf_counter()
            resultats = self._executer_script(self._conn, script)
            duree_ms = round((time.perf_counter() - debut) * 1000)
            etapes = self._durees_restauration(debut_serveur)

        reveal = []
        for r in resultats:
            if "achats_id" in r["colonnes"]:
                reveal = _lignes_en_dicts(r)
        return {"success": True, "duree_ms": duree_ms, "etapes": etapes, "reveal": reveal}

    def _durees_restauration(self, debut_serveur):
        """Durée de chaque RESTORE, déduite des dates de fin dans
        msdb.dbo.restorehistory (le script 06 enchaîne les 3 dans un seul lot).
        Facultatif : liste vide si msdb est illisible."""
        try:
            rows = self._requete(
                "SELECT restore_type, restore_date FROM msdb.dbo.restorehistory "
                "WHERE destination_database_name = ? AND restore_date >= ? "
                "ORDER BY restore_history_id;",
                self._db, debut_serveur,
            )
        except pyodbc.Error:
            return []
        etapes, precedent = [], debut_serveur
        for type_, fin in rows:
            if type_ not in TYPES_RESTAURATION:
                continue
            etapes.append(
                {
                    "nom": TYPES_RESTAURATION[type_],
                    "duree_ms": max(0, round((fin - precedent).total_seconds() * 1000)),
                }
            )
            precedent = fin
        return etapes

    @_api
    def reset(self):
        """07 : restaure GOLDEN et recrée le FULL (1 à 2 min). Attend la fin
        d'une éventuelle sauvegarde 04b encore en cours."""
        script = self._lire_script(SCRIPT_RESET)
        self._verifier_fichiers(script)
        self._attendre_backup()
        with self._operation("reset"):
            debut = time.perf_counter()
            resultats = self._executer_script(self._conn, script)
            duree_ms = round((time.perf_counter() - debut) * 1000)
            self._index_active = False
            self._dernier_achat_id = None
            self._backup = {"etat": "inactif", "duree_ms": None, "erreur": None}
        controle = {}
        for r in resultats:
            if "is_disabled" in r["colonnes"] and r["lignes"]:
                controle["index_desactive"] = bool(r["lignes"][0][r["colonnes"].index("is_disabled")])
            if "nb_achats" in r["colonnes"] and r["lignes"]:
                controle["nb_achats"] = int(r["lignes"][0][r["colonnes"].index("nb_achats")])
        return {"success": True, "duree_ms": duree_ms, **controle}


def main():
    api = Api()
    webview.create_window(
        "Démo SQL Server 2022 — LootTable",
        str(resource_dir() / "index.html"),
        js_api=api,
        width=1280,
        height=800,
        resizable=False,
    )
    webview.start()


if __name__ == "__main__":
    main()
