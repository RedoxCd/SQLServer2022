"""Vérifications de l'installateur LootTable, SANS RIEN CRÉER.

Contrôle (lecture seule) : connexion à SQL Server, version/édition, présence et
découpage des 4 scripts, dossiers et espace disque, existence de la base, noms
des .bak attendus et, si la base existe, le contrôle final de l'installation.
Ne crée aucun dossier et n'exécute aucun script.

    python smoke_test.py
"""

import sys

import main
from main import ETAPES, Api

ICONES = {"ok": "✔", "avert": "⚠", "erreur": "✘", "ignore": "—"}


def afficher(lignes, cle_libelle="libelle"):
    for ligne in lignes:
        icone = ICONES.get(ligne["etat"], "?")
        detail = f" — {ligne['detail']}" if ligne.get("detail") else ""
        print(f"  {icone} {ligne[cle_libelle]}{detail}")


def main_test():
    api = Api()
    if api.erreur_config:
        print(f"✘ {api.erreur_config}")
        return 1
    code = 0

    print("\n[1] Prérequis (aucun dossier créé)")
    v = api._verifications(creer_dossiers=False)
    afficher(v["verifications"])
    if v["confirmation"]:
        print(f"  Confirmation demandée avant écrasement : {v['confirmation']}")
    if v["bloquant"]:
        code = 1

    print("\n[2] Scripts de l'installation (lecture et découpage GO, rien n'est exécuté)")
    for e in ETAPES:
        try:
            lots = Api._decouper(api._lire_script(e["script"]))
            requetes = sum(1 for _, q in lots if q)
            print(f"  ✔ {e['script']} — {len(lots)} lot(s), {requetes} requête(s)")
        except Exception as err:  # noqa: BLE001
            print(f"  ✘ {e['script']} — {err}")
            code = 1

    print("\n[3] Sauvegardes attendues")
    for script in (main.SCRIPT_GOLDEN, main.SCRIPT_FULL):
        try:
            print(f"  ✔ {script} écrit {api._nom_sauvegarde(script)}")
        except Exception as err:  # noqa: BLE001
            print(f"  ✘ {script} — {err}")
            code = 1

    print("\n[4] Contrôle de l'installation (lecture seule)")
    try:
        conn = api._nouvelle_connexion()
    except Exception as err:  # noqa: BLE001
        print(f"  — ignoré : SQL Server injoignable ({main.message_erreur(err)})")
    else:
        try:
            controle = api._controler(conn)
            afficher(controle["controles"])
            print("  => " + ("Prêt pour l'activité." if controle["ok"] else "Installation absente ou incomplète (normal avant la première installation)."))
        finally:
            api._fermer(conn)

    print("\nTerminé : " + ("des prérequis bloquent l'installation." if code else "aucun prérequis bloquant."))
    return code


if __name__ == "__main__":
    sys.exit(main_test())
