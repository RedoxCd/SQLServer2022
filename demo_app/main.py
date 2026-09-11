"""Démo interactive SQL Server 2022 — Portes Ouvertes ETML.

Fenêtre pywebview affichant index.html, avec une classe Api exposée au
JavaScript (window.pyapi) pour piloter la démo : vente de billets, incident
(DELETE massif) et restauration en 3 étapes (FULL / DIFF / LOG + STOPAT).
"""

import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pyodbc
import webview

# Une seule connexion vivante pendant toute la vie de l'appli : le pooling ODBC
# pourrait sinon laisser traîner une connexion fantôme sur CinemaBilletterie,
# ce qui ferait échouer RESTORE DATABASE (accès exclusif requis).
pyodbc.pooling = False

RE_GO = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)

STEP_FILES = {
    1: "restore_step1.sql",
    2: "restore_step2.sql",
    3: "restore_step3.sql",
}


def base_dir() -> Path:
    """Dossier contenant l'exécutable (ou le script) : config.json et /sql y
    vivent en dehors du bundle PyInstaller pour rester éditables le jour J."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def resource_dir() -> Path:
    """Dossier des ressources embarquées (index.html/style.css/app.js),
    potentiellement extraites par PyInstaller dans sys._MEIPASS."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


BASE_DIR = base_dir()
SQL_DIR = BASE_DIR / "sql"
CONFIG_PATH = BASE_DIR / "config.json"


class Api:
    def __init__(self):
        self.conn = None
        self.config = None
        self.erreur_demarrage = None
        self.incident_stopat = None
        self.etape_max_terminee = 0

        try:
            self.config = self._charger_config()
        except Exception as e:
            self.erreur_demarrage = f"Impossible de lire config.json : {e}"
            return

        try:
            self._connecter()
        except Exception as e:
            self.erreur_demarrage = self._message_erreur(e)

    # ------------------------------------------------------------------ #
    # Configuration & connexion
    # ------------------------------------------------------------------ #
    def _charger_config(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"Fichier introuvable : {CONFIG_PATH}")
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _connecter(self):
        cfg = self.config["connexion"]
        morceaux = [
            f"DRIVER={{{cfg['driver']}}}",
            f"SERVER={cfg['server']}",
            # On se connecte toujours sur master : la base de démo ne doit
            # jamais être "USE"-ée par défaut, sous peine de bloquer les
            # RESTORE DATABASE (qui exigent un accès exclusif).
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

        self.conn = pyodbc.connect(
            chaine, timeout=cfg.get("timeout_secondes", 30), autocommit=True
        )
        self.db_name = cfg["database"]

    def reessayer_connexion(self):
        """Appelé depuis l'UI si la connexion initiale a échoué."""
        try:
            if not self.config:
                self.config = self._charger_config()
            self._connecter()
            self.erreur_demarrage = None
            total = self._get_count()
            return {"success": True, "total": total}
        except Exception as e:
            self.erreur_demarrage = self._message_erreur(e)
            return {"success": False, "error": self.erreur_demarrage}

    def _message_erreur(self, err):
        if isinstance(err, pyodbc.Error) and err.args:
            return " ".join(str(a) for a in err.args)
        return str(err)

    # ------------------------------------------------------------------ #
    # Exécution SQL
    # ------------------------------------------------------------------ #
    def _executer_script(self, texte_sql):
        lots = [lot.strip() for lot in RE_GO.split(texte_sql)]
        cursor = self.conn.cursor()
        for lot in lots:
            if lot:
                cursor.execute(lot)

    def _contexte_placeholders(self):
        cfg = self.config
        move_clause = ""
        if cfg["restauration"].get("deplacer_fichiers"):
            r = cfg["restauration"]
            move_clause = (
                ",\nMOVE N'{}' TO N'{}',\nMOVE N'{}' TO N'{}'"
            ).format(
                r["nom_logique_data"], r["chemin_data"],
                r["nom_logique_log"], r["chemin_log"],
            )
        return {
            "DB_NAME": cfg["database"],
            "FULL_BACKUP_PATH": cfg["sauvegardes"]["full"],
            "DIFF_BACKUP_PATH": cfg["sauvegardes"]["diff"],
            "TAIL_LOG_PATH": cfg["sauvegardes"]["tail_log"],
            "STOPAT": self.incident_stopat or "",
            "MOVE_CLAUSE": move_clause,
        }

    def _substituer(self, template):
        texte = template
        for cle, valeur in self._contexte_placeholders().items():
            texte = texte.replace("{{" + cle + "}}", str(valeur))
        return texte

    def _verifier_fichier(self, chemin, libelle):
        try:
            if chemin and not Path(chemin).exists():
                raise FileNotFoundError(
                    f"Fichier {libelle} introuvable : {chemin}\n"
                    "Vérifie le chemin dans config.json (section \"sauvegardes\")."
                )
        except OSError:
            # Chemin non accessible depuis ce poste (SQL Server distant, etc.) :
            # on laisse SQL Server lever l'erreur lui-même.
            pass

    def _get_count(self):
        cursor = self.conn.cursor()
        cursor.execute(
            f"USE [{self.db_name}]; "
            "SELECT SUM(p.rows) FROM sys.partitions p "
            "WHERE p.object_id = OBJECT_ID('dbo.t_billets') AND p.index_id IN (0, 1);"
        )
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def _verifier_pret(self):
        if self.erreur_demarrage:
            return self.erreur_demarrage
        if not self.conn:
            return "Aucune connexion à la base de données."
        return None

    # ------------------------------------------------------------------ #
    # API exposée au JavaScript
    # ------------------------------------------------------------------ #
    def get_status(self):
        erreur = self._verifier_pret()
        if erreur:
            return {"success": False, "error": erreur}
        try:
            total = self._get_count()
            return {
                "success": True,
                "total": total,
                "etape_max_terminee": self.etape_max_terminee,
                "incident_actif": bool(self.incident_stopat)
                and self.etape_max_terminee < 3,
            }
        except pyodbc.Error as e:
            msg = self._message_erreur(e)
            en_restauration = "restor" in msg.lower()
            return {
                "success": False,
                "error": "Base en cours de restauration…" if en_restauration else msg,
                "restauration_en_cours": en_restauration,
            }
        except Exception as e:
            return {"success": False, "error": f"Erreur inattendue : {e}"}

    def vendre_billets(self, nombre=None):
        erreur = self._verifier_pret()
        if erreur:
            return {"success": False, "error": erreur}
        try:
            cfg_v = self.config["vente"]
            n = int(nombre) if nombre else random.randint(cfg_v["min"], cfg_v["max"])

            cursor = self.conn.cursor()
            cursor.execute(f"USE [{self.db_name}];")
            cursor.execute(
                f"SELECT TOP ({n}) seances_id FROM t_seances ORDER BY NEWID();"
            )
            ids_seances = [row[0] for row in cursor.fetchall()]
            if not ids_seances:
                return {
                    "success": False,
                    "error": "Aucune séance disponible pour générer des ventes.",
                }

            maintenant = datetime.now()
            lignes = [
                (round(random.uniform(8, 20), 2), maintenant, sid)
                for sid in ids_seances
            ]
            cursor.executemany(
                "INSERT INTO t_billets (prix, dateAchat, seances_id) VALUES (?, ?, ?);",
                lignes,
            )
            total = self._get_count()
            return {"success": True, "vendus": len(lignes), "total": total}
        except pyodbc.Error as e:
            return {"success": False, "error": self._message_erreur(e)}
        except Exception as e:
            return {"success": False, "error": f"Erreur inattendue : {e}"}

    def declencher_incident(self):
        erreur = self._verifier_pret()
        if erreur:
            return {"success": False, "error": erreur}
        try:
            script = SQL_DIR / "incident.sql"
            if not script.exists():
                return {"success": False, "error": f"Script introuvable : {script}"}

            cursor = self.conn.cursor()
            cursor.execute(f"USE [{self.db_name}]; SELECT SYSDATETIME();")
            point_avant_incident = cursor.fetchone()[0]
            self.incident_stopat = point_avant_incident.strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]

            self._executer_script(self._substituer(script.read_text(encoding="utf-8")))
            self.etape_max_terminee = 0

            total = self._get_count()
            return {"success": True, "total": total}
        except pyodbc.Error as e:
            return {"success": False, "error": self._message_erreur(e)}
        except Exception as e:
            return {"success": False, "error": f"Erreur inattendue : {e}"}

    def restaurer_etape(self, etape):
        erreur = self._verifier_pret()
        if erreur:
            return {"success": False, "error": erreur}
        try:
            etape = int(etape)
            if etape not in STEP_FILES:
                return {"success": False, "error": f"Étape inconnue : {etape}"}
            if etape == 3 and not self.incident_stopat:
                return {
                    "success": False,
                    "error": "Aucun incident déclenché : point de restauration (STOPAT) inconnu.",
                }

            script = SQL_DIR / STEP_FILES[etape]
            if not script.exists():
                return {"success": False, "error": f"Script introuvable : {script}"}

            if etape == 1:
                self._verifier_fichier(self.config["sauvegardes"]["full"], "de sauvegarde FULL")
            elif etape == 2:
                self._verifier_fichier(self.config["sauvegardes"]["diff"], "de sauvegarde DIFF")

            sql_final = self._substituer(script.read_text(encoding="utf-8"))

            debut = time.perf_counter()
            self._executer_script(sql_final)
            duree_ms = round((time.perf_counter() - debut) * 1000)

            self.etape_max_terminee = max(self.etape_max_terminee, etape)
            return {
                "success": True,
                "etape": etape,
                "duree_ms": duree_ms,
                "sql": sql_final,
            }
        except FileNotFoundError as e:
            return {"success": False, "error": str(e)}
        except pyodbc.Error as e:
            return {"success": False, "error": self._message_erreur(e)}
        except Exception as e:
            return {"success": False, "error": f"Erreur inattendue : {e}"}

    def reinitialiser(self):
        self.incident_stopat = None
        self.etape_max_terminee = 0
        erreur = self._verifier_pret()
        if erreur:
            return {"success": False, "error": erreur}
        try:
            total = self._get_count()
            return {"success": True, "total": total}
        except pyodbc.Error as e:
            msg = self._message_erreur(e)
            return {
                "success": False,
                "error": msg,
                "restauration_en_cours": "restor" in msg.lower(),
            }
        except Exception as e:
            return {"success": False, "error": f"Erreur inattendue : {e}"}


def main():
    api = Api()
    webview.create_window(
        "Démo SQL Server 2022 — Billetterie Cinéma",
        str(resource_dir() / "index.html"),
        js_api=api,
        width=1280,
        height=800,
        resizable=False,
    )
    webview.start()


if __name__ == "__main__":
    main()
