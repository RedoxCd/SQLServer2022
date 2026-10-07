"""Installateur de la démo LootTable — Portes Ouvertes ETML.

Fenêtre pywebview (index.html) avec une classe Api exposée au JavaScript :
vérifie les prérequis puis, en un clic, exécute dans l'ordre
  01_create_database.sql  -> base + tables (DROP DATABASE si elle existe)
  02_generate_data.sql    -> 42 jeux + 10 000 000 joueurs + idx_pseudo désactivé
  03_golden_backup.sql    -> recovery FULL + sauvegarde GOLDEN
  07_reset.sql            -> restaure GOLDEN et crée le FULL de départ de la chaîne
Les scripts sont lus tels quels dans Script/ (rien n'est copié ici).

Application indépendante de demo_app : la logique d'exécution des scripts
(découpe GO, USE séparés, drainage des résultats, connexion sur master en
autocommit, pooling désactivé) est reprise de demo_app/main.py.
"""

import copy
import functools
import json
import ntpath
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path

import pyodbc
import webview

# Aucune connexion ne doit rester posée sur LootTable (DROP / RESTORE exigent
# un accès exclusif) : pas de pooling, et on ne fait jamais de USE LootTable
# que le temps d'un script.
pyodbc.pooling = False

RE_GO = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)
RE_COMMENTAIRE_DEBUT = re.compile(r"\A\s*(?:/\*.*?\*/|--[^\n]*(?:\n|\Z))", re.DOTALL)
RE_USE_DEBUT = re.compile(r"\A\s*USE\s+\[?(\w+)\]?\s*;?", re.IGNORECASE)
RE_BACKUP_VERS = re.compile(r"\bTO\s+DISK\s*=\s*N'([^']+)'", re.IGNORECASE)

ETAPES = [
    {"script": "01_create_database.sql", "titre": "Création de la base et des tables"},
    {"script": "02_generate_data.sql", "titre": "Chargement des 10 millions de joueurs"},
    {"script": "03_golden_backup.sql", "titre": "Sauvegarde GOLDEN (état initial de la démo)"},
    {"script": "07_reset.sql", "titre": "Préparation de la chaîne de sauvegarde"},
]
ETAPE_JOUEURS = 1  # index de l'étape de chargement des joueurs (sonde de progression)
SCRIPT_GOLDEN = "03_golden_backup.sql"
SCRIPT_FULL = "07_reset.sql"

TOTAL_JOUEURS = 10_000_000
TOTAL_JEUX = 42
ESPACE_MINIMUM_GO_DEFAUT = 25
INTERVALLE_SONDE_S = 2
GO = 1024**3

SQL_NB_JOUEURS = (
    "SELECT SUM(p.rows) FROM [{db}].sys.partitions p "
    "WHERE p.object_id = OBJECT_ID(?) AND p.index_id IN (0,1);"
)


def base_dir() -> Path:
    """Dossier contenant l'exécutable (ou le script) : config.json y vit en
    dehors du bundle PyInstaller pour rester éditable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def resource_dir() -> Path:
    """Dossier des ressources embarquées (index.html/style.css/app.js)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


BASE_DIR = base_dir()
CONFIG_PATH = BASE_DIR / "config.json"


def message_erreur(err):
    if isinstance(err, pyodbc.Error) and err.args:
        return " ".join(str(a) for a in err.args)
    return str(err)


def formater_go(octets):
    return f"{octets / GO:.1f} Go".replace(".", ",")


def _api(fonction):
    """Méthode exposée au JS : toute erreur devient {"success": False, "error": ...}."""

    @functools.wraps(fonction)
    def enveloppe(self, *args, **kwargs):
        if self.erreur_config:
            return {"success": False, "error": self.erreur_config}
        try:
            return fonction(self, *args, **kwargs)
        except Exception as e:  # noqa: BLE001 - tout est renvoyé à l'UI
            return {"success": False, "error": message_erreur(e)}

    return enveloppe


class Api:
    # Attributs d'état privés (« _ ») : pywebview n'expose au JS que les publics.
    def __init__(self):
        self._config = None
        self._db = "LootTable"
        self.erreur_config = None
        self._verrou = threading.RLock()
        self._etat = self._etat_initial()
        self._arret_sonde = None
        self._thread_sonde = None

        try:
            self._config = self._charger_config()
            self._db = self._config["connexion"]["database"]
        except Exception as e:
            self.erreur_config = f"Impossible de lire config.json : {e}"

    # ------------------------------------------------------------------ #
    # Configuration & connexion
    # ------------------------------------------------------------------ #
    def _charger_config(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"Fichier introuvable : {CONFIG_PATH}")
        # utf-8-sig : tolère un BOM (fichier ré-édité avec Notepad sous Windows)
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _nouvelle_connexion(self):
        """Connexion sur master en autocommit, sans timeout de requête (les
        scripts durent des dizaines de minutes). À fermer par l'appelant."""
        cfg = self._config["connexion"]
        morceaux = [
            f"DRIVER={{{cfg['driver']}}}",
            f"SERVER={cfg['server']}",
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
        conn = pyodbc.connect(
            ";".join(morceaux) + ";", timeout=cfg.get("timeout_secondes", 30), autocommit=True
        )
        conn.timeout = 0  # 0 = pas de limite de durée par requête
        return conn

    @staticmethod
    def _fermer(conn):
        if conn is not None:
            try:
                conn.close()
            except pyodbc.Error:
                pass

    # ------------------------------------------------------------------ #
    # Scripts SQL (lus dans Script/)
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
        # utf-8-sig : accepte les scripts avec ou sans BOM
        return chemin.read_text(encoding="utf-8-sig")

    @staticmethod
    def _extraire_use(lot):
        """Sépare les « USE base; » en tête de lot (commentaires ignorés) du
        reste : USE est exécuté dans une requête à part."""
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
    def _decouper(texte_sql):
        """Liste des lots d'un script : [(bases_USE, requête), ...]."""
        lots = []
        for lot in RE_GO.split(texte_sql):
            requete, bases = Api._extraire_use(lot.strip())
            if requete or bases:
                lots.append((bases, requete))
        return lots

    @staticmethod
    def _drainer(cursor):
        """Parcourt tous les résultats d'un lot. Indispensable pour BACKUP /
        RESTORE avec pyodbc : ils ne sont terminés (et leurs erreurs levées)
        qu'une fois les résultats et messages consommés via nextset()."""
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
        """Exécute un script lot par lot (séparateur GO). Quoi qu'il arrive, la
        connexion repasse sur master à la fin."""
        resultats = []
        cursor = conn.cursor()
        cursor.timeout = 0
        try:
            for bases, requete in self._decouper(texte_sql):
                for base in bases:
                    cursor.execute(f"USE [{base}];")
                    self._drainer(cursor)
                if requete:
                    cursor.execute(requete)
                    resultats.extend(self._drainer(cursor))
        finally:
            try:
                cursor.execute("USE master;")
                self._drainer(cursor)
            except pyodbc.Error:
                pass
            cursor.close()
        return resultats

    def _nom_sauvegarde(self, script):
        """Nom du .bak écrit par un script (lu dans son BACKUP ... TO DISK)."""
        trouves = RE_BACKUP_VERS.findall(self._lire_script(script))
        if not trouves:
            raise ValueError(f"Aucun BACKUP ... TO DISK dans {script}.")
        return ntpath.basename(trouves[0])

    # ------------------------------------------------------------------ #
    # Prérequis
    # ------------------------------------------------------------------ #
    @staticmethod
    def _espace_libre(chemin):
        """(octets libres, identifiant du volume) du dossier ou de son plus
        proche parent existant."""
        p = Path(chemin)
        while not p.exists() and p != p.parent:
            p = p.parent
        return shutil.disk_usage(p).free, os.stat(p).st_dev

    def _verifications(self, creer_dossiers=True):
        """Prérequis affichés avec ✔/⚠/✘. Renvoie
        {"verifications": [...], "bloquant": bool, "confirmation": str|None, "orphelins": [...]}."""
        res = []

        def ajouter(cle, libelle, etat, detail=""):
            res.append({"cle": cle, "libelle": libelle, "etat": etat, "detail": detail})

        confirmation, orphelins = None, []
        conn = None
        infos = None

        # --- SQL Server joignable, version, édition -----------------------
        try:
            conn = self._nouvelle_connexion()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT CAST(SERVERPROPERTY('Edition') AS NVARCHAR(100)), "
                "CAST(SERVERPROPERTY('EngineEdition') AS INT), "
                "CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(50)), "
                "CAST(SERVERPROPERTY('ProductMajorVersion') AS INT);"
            )
            infos = cursor.fetchone()
            cursor.close()
        except Exception as e:  # noqa: BLE001
            ajouter("serveur", "SQL Server joignable", "erreur", message_erreur(e))
        else:
            edition, moteur, version, majeure = infos
            ajouter("serveur", "SQL Server joignable", "ok", f"{self._config['connexion']['server']}")
            if majeure is not None and majeure < 16:
                ajouter("version", "SQL Server 2022 ou plus récent", "erreur",
                        f"Version {version} : 02_generate_data.sql utilise GENERATE_SERIES (SQL Server 2022).")
            else:
                ajouter("version", "SQL Server 2022 ou plus récent", "ok", f"Version {version}")
            if moteur == 4 or "express" in (edition or "").lower():
                ajouter("edition", "Édition de SQL Server", "avert",
                        f"{edition} : limite de 10 Go de données par base. La base LootTable "
                        "démarre à 8 Go : surveillez sa taille. Les sauvegardes ne sont pas compressées.")
            else:
                ajouter("edition", "Édition de SQL Server", "ok", edition)

        if infos is None:
            for cle, libelle in (("version", "SQL Server 2022 ou plus récent"),
                                 ("edition", "Édition de SQL Server")):
                ajouter(cle, libelle, "ignore", "SQL Server est injoignable.")

        # --- Scripts ------------------------------------------------------
        dossier_scripts = self._dossier_scripts()
        manquants = [e["script"] for e in ETAPES if not (dossier_scripts / e["script"]).exists()]
        if manquants:
            ajouter("scripts", "Scripts SQL trouvés", "erreur",
                    f"Introuvables dans {dossier_scripts} : {', '.join(manquants)}")
        else:
            ajouter("scripts", "Scripts SQL trouvés", "ok", str(dossier_scripts))

        # --- Dossiers de données et de sauvegardes -------------------------
        dossiers = [
            ("données", self._config.get("donnees", {}).get("dossier", r"C:\LootTable\Data")),
            ("sauvegardes", self._config["sauvegardes"]["dossier"]),
        ]
        details, etat = [], "ok"
        for nom, chemin in dossiers:
            try:
                if creer_dossiers:
                    existait = Path(chemin).exists()
                    os.makedirs(chemin, exist_ok=True)
                    details.append(f"{chemin} ({'présent' if existait else 'créé'})")
                else:
                    details.append(f"{chemin} ({'présent' if Path(chemin).exists() else 'absent : sera créé'})")
            except OSError as e:
                etat = "erreur"
                details.append(f"{chemin} : impossible à créer ({e})")
        ajouter("dossiers", "Dossiers de la démo", etat, " — ".join(details))

        # --- Espace disque -------------------------------------------------
        minimum = float(self._config.get("espace_libre_minimum_go", ESPACE_MINIMUM_GO_DEFAUT)) * GO
        try:
            vus, lignes, etat = {}, [], "ok"
            for nom, chemin in dossiers:
                libre, volume = self._espace_libre(chemin)
                if volume in vus:
                    continue
                vus[volume] = libre
                lignes.append(f"{chemin} : {formater_go(libre)} libres")
                if libre < minimum:
                    etat = "erreur"
            detail = " — ".join(lignes) + f" (minimum {minimum / GO:.0f} Go)"
            ajouter("espace", "Espace disque libre", etat, detail)
        except OSError as e:
            ajouter("espace", "Espace disque libre", "erreur", str(e))

        # --- La base existe-t-elle déjà ? ----------------------------------
        if conn is not None:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT state_desc FROM sys.databases WHERE name = ?;", self._db)
                ligne = cursor.fetchone()
                cursor.close()
                if ligne:
                    ajouter("base", f"Base {self._db}", "avert",
                            f"La base existe déjà (état : {ligne[0].lower()}) : elle sera supprimée puis recréée.")
                    confirmation = (
                        f"La base {self._db} existe déjà. Cela supprime la base et ses données. "
                        "Voulez-vous continuer ?"
                    )
                else:
                    ajouter("base", f"Base {self._db}", "ok", "Absente : prête à être créée.")
                    orphelins = self._fichiers_orphelins(dossiers[0][1])
                    if orphelins:
                        noms = ", ".join(orphelins)
                        ajouter("orphelins", "Fichiers restés sur le disque", "avert",
                                f"{noms} : la base est absente (détachée ?) mais ses fichiers existent. "
                                "Ils seront supprimés.")
                        confirmation = (
                            f"Des fichiers d'une ancienne base sont restés sur le disque ({noms}). "
                            "Cela supprime ces fichiers et leurs données. Voulez-vous continuer ?"
                        )
            except pyodbc.Error as e:
                ajouter("base", f"Base {self._db}", "erreur", message_erreur(e))
        else:
            ajouter("base", f"Base {self._db}", "ignore", "SQL Server est injoignable.")
        self._fermer(conn)

        return {
            "verifications": res,
            "bloquant": any(v["etat"] == "erreur" for v in res),
            "confirmation": confirmation,
            "orphelins": [str(Path(dossiers[0][1]) / n) for n in orphelins],
        }

    @staticmethod
    def _fichiers_orphelins(dossier_donnees):
        try:
            return [n for n in ("LootTable.mdf", "LootTable_log.ldf") if (Path(dossier_donnees) / n).is_file()]
        except OSError:
            return []

    # ------------------------------------------------------------------ #
    # Contrôle final
    # ------------------------------------------------------------------ #
    def _controler(self, conn):
        """Contrôle de l'installation (aucune modification). Renvoie
        {"controles": [{"libelle","etat","detail"}], "ok": bool}."""
        controles = []

        def ajouter(libelle, ok, detail):
            controles.append({"libelle": libelle, "etat": "ok" if ok else "erreur", "detail": detail})

        cursor = conn.cursor()
        cursor.execute(
            "SELECT state_desc, recovery_model_desc FROM sys.databases WHERE name = ?;", self._db
        )
        base = cursor.fetchone()
        if not base:
            ajouter(f"Base {self._db} présente", False, "Introuvable : lancez « Créer la base ».")
        else:
            ajouter(f"Base {self._db} en ligne", base[0] == "ONLINE", f"État : {base[0].lower()}")
            ajouter("Mode de récupération FULL", base[1] == "FULL", f"Mode : {base[1]}")
            if base[0] == "ONLINE":
                cursor.execute(SQL_NB_JOUEURS.format(db=self._db), f"{self._db}.dbo.t_joueur")
                n = cursor.fetchone()[0]
                n = int(n or 0)
                ajouter("10 000 000 de joueurs", n == TOTAL_JOUEURS, f"{n:,} lignes dans t_joueur".replace(",", " "))
                cursor.execute(f"SELECT COUNT(*) FROM [{self._db}].dbo.t_jeux;")
                n = cursor.fetchone()[0]
                ajouter("42 jeux", n == TOTAL_JEUX, f"{n} lignes dans t_jeux")
                cursor.execute(
                    f"SELECT is_disabled FROM [{self._db}].sys.indexes "
                    "WHERE object_id = OBJECT_ID(?) AND name = 'idx_pseudo';",
                    f"{self._db}.dbo.t_joueur",
                )
                ligne = cursor.fetchone()
                ajouter("Index idx_pseudo désactivé", bool(ligne and ligne[0]),
                        "Introuvable" if not ligne else ("désactivé" if ligne[0] else "ACTIF (devrait être désactivé)"))
        cursor.close()

        dossier = self._config["sauvegardes"]["dossier"]
        for script in (SCRIPT_GOLDEN, SCRIPT_FULL):
            try:
                nom = self._nom_sauvegarde(script)
                chemin = Path(dossier) / nom
                if chemin.is_file():
                    ajouter(f"Sauvegarde {nom}", True, formater_go(chemin.stat().st_size))
                else:
                    ajouter(f"Sauvegarde {nom}", False, f"Absente de {dossier}")
            except (OSError, ValueError) as e:
                ajouter(f"Sauvegarde ({script})", False, str(e))
        return {"controles": controles, "ok": all(c["etat"] == "ok" for c in controles)}

    # ------------------------------------------------------------------ #
    # Installation en arrière-plan
    # ------------------------------------------------------------------ #
    @staticmethod
    def _etat_initial():
        return {
            "phase": "inactif",  # inactif | en_cours | termine | erreur
            "etape": 0,  # numéro (1 à 4) de l'étape en cours
            "etapes": [
                {"titre": e["titre"], "script": e["script"], "etat": "attente", "duree_ms": None}
                for e in ETAPES
            ],
            "joueurs": 0,
            "total_joueurs": TOTAL_JOUEURS,
            "debut": None,
            "ecoule_ms": 0,
            "erreur": None,
            "controle": None,
        }

    def _maj(self, **champs):
        with self._verrou:
            self._etat.update(champs)

    def _maj_etape(self, index, etat, duree_ms=None):
        with self._verrou:
            self._etat["etapes"][index]["etat"] = etat
            self._etat["etapes"][index]["duree_ms"] = duree_ms

    def _sonde(self, arret):
        """Compte les joueurs chargés toutes les 2 s, avec une seconde connexion
        (métadonnées sys.partitions, sans NOLOCK)."""
        conn = None
        try:
            conn = self._nouvelle_connexion()
            cursor = conn.cursor()
            cursor.execute("SET LOCK_TIMEOUT 1500;")  # ne jamais rester bloquée derrière le chargement
            while not arret.wait(INTERVALLE_SONDE_S):
                try:
                    cursor.execute(SQL_NB_JOUEURS.format(db=self._db), f"{self._db}.dbo.t_joueur")
                    ligne = cursor.fetchone()
                    self._maj(joueurs=int(ligne[0] or 0))
                except pyodbc.Error:
                    pass  # base pas encore prête ou verrou : on réessaiera
        except Exception:  # noqa: BLE001 - la sonde ne doit jamais faire échouer l'installation
            pass
        finally:
            self._fermer(conn)

    def _demarrer_sonde(self):
        self._arret_sonde = threading.Event()
        self._thread_sonde = threading.Thread(target=self._sonde, args=(self._arret_sonde,), daemon=True)
        self._thread_sonde.start()

    def _arreter_sonde(self):
        if self._arret_sonde is not None:
            self._arret_sonde.set()
        if self._thread_sonde is not None:
            self._thread_sonde.join(timeout=10)
        self._arret_sonde = self._thread_sonde = None

    def _installer(self):
        debut = self._etat["debut"]
        conn = None
        index = 0
        try:
            conn = self._nouvelle_connexion()
            for index, etape in enumerate(ETAPES):
                texte = self._lire_script(etape["script"])
                self._maj(etape=index + 1)
                self._maj_etape(index, "en_cours")
                t0 = time.perf_counter()
                if index == ETAPE_JOUEURS:
                    self._demarrer_sonde()
                try:
                    self._executer_script(conn, texte)
                finally:
                    if index == ETAPE_JOUEURS:
                        self._arreter_sonde()
                self._maj_etape(index, "ok", round((time.perf_counter() - t0) * 1000))
                if index == ETAPE_JOUEURS:
                    self._maj(joueurs=TOTAL_JOUEURS)
            controle = self._controler(conn)
            self._maj(
                phase="termine",
                controle=controle,
                ecoule_ms=round((time.perf_counter() - debut) * 1000),
            )
        except Exception as e:  # noqa: BLE001
            with self._verrou:
                if self._etat["etapes"][index]["etat"] == "en_cours":
                    self._etat["etapes"][index]["etat"] = "erreur"
                self._etat["phase"] = "erreur"
                self._etat["erreur"] = (
                    f"Étape {index + 1}/{len(ETAPES)} ({ETAPES[index]['script']}) :\n{message_erreur(e)}"
                )
                self._etat["ecoule_ms"] = round((time.perf_counter() - debut) * 1000)
        finally:
            self._fermer(conn)

    # ------------------------------------------------------------------ #
    # API exposée au JavaScript
    # ------------------------------------------------------------------ #
    @_api
    def verifier_prerequis(self):
        """Prérequis (crée les dossiers manquants)."""
        v = self._verifications(creer_dossiers=True)
        return {"success": True, **{k: v[k] for k in ("verifications", "bloquant", "confirmation")}}

    @_api
    def creer_base(self, confirme=False):
        """Lance l'installation dans un thread. Si la base (ou ses fichiers) existe
        déjà, renvoie `confirmation_requise` tant que `confirme` n'est pas vrai."""
        with self._verrou:
            if self._etat["phase"] == "en_cours":
                return {"success": False, "error": "Une installation est déjà en cours."}
        v = self._verifications(creer_dossiers=True)
        if v["bloquant"]:
            return {
                "success": False,
                "error": "Les vérifications ont échoué : corrigez les points marqués ✘.",
                "verifications": v["verifications"],
            }
        if v["confirmation"] and not confirme:
            return {"success": False, "confirmation_requise": v["confirmation"], "verifications": v["verifications"]}
        for chemin in v["orphelins"]:  # confirmés : fichiers d'une base détachée
            os.remove(chemin)
        with self._verrou:
            self._etat = self._etat_initial()
            self._etat["phase"] = "en_cours"
            self._etat["debut"] = time.perf_counter()
        threading.Thread(target=self._installer, daemon=True).start()
        return {"success": True}

    @_api
    def get_progression(self):
        with self._verrou:
            etat = copy.deepcopy(self._etat)
        if etat["phase"] == "en_cours":
            etat["ecoule_ms"] = round((time.perf_counter() - etat["debut"]) * 1000)
        etat.pop("debut", None)
        return {"success": True, **etat}

    @_api
    def verifier_installation(self):
        """Contrôle de fin seul, sans rien modifier."""
        with self._verrou:
            if self._etat["phase"] == "en_cours":
                return {"success": False, "error": "Une installation est en cours."}
        conn = self._nouvelle_connexion()
        try:
            return {"success": True, **self._controler(conn)}
        finally:
            self._fermer(conn)


def main():
    api = Api()
    webview.create_window(
        "Installateur LootTable",
        str(resource_dir() / "index.html"),
        js_api=api,
        width=1100,
        height=820,
        resizable=False,
    )
    webview.start()


if __name__ == "__main__":
    main()
