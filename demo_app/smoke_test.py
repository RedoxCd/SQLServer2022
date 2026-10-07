"""Test de bout en bout de la démo LootTable (sans interface).

Rejoue le scénario complet via la classe Api de main.py (donc avec exactement
le même code que l'appli) : catalogue, cadeau, recherche lente, activation de
l'index, recherche rapide, OK + incident, restauration, reveal, reset.
Affiche la durée de chaque étape.

ATTENTION : ce script exécute vraiment les scripts 04a, 04b, 05, 06 et 07 sur le
serveur SQL de config.json (détache puis restaure la base LootTable, reset de
1 à 2 min). À lancer uniquement sur la base de démo, appli fermée.

    python smoke_test.py            # demande une confirmation
    python smoke_test.py --yes      # sans confirmation
    python smoke_test.py --sans-reset   # s'arrête après le reveal
"""

import argparse
import sys
import time

from main import Api

etapes_resumees = []


def echec(message):
    print(f"\nÉCHEC : {message}")
    afficher_resume()
    sys.exit(1)


def afficher_resume():
    if not etapes_resumees:
        return
    print("\n" + "=" * 62)
    print(f"{'Étape':<44}{'Mesuré (SQL)':>10}{'Total':>8}")
    print("-" * 62)
    for nom, sql_ms, total_s in etapes_resumees:
        sql = f"{sql_ms} ms" if sql_ms is not None else "—"
        print(f"{nom:<44}{sql:>10}{total_s:>7.1f}s")
    print("=" * 62)


def etape(nom, appel, *args):
    """Appelle une méthode de l'API, vérifie success et mémorise la durée."""
    print(f"\n[{nom}] …", flush=True)
    debut = time.perf_counter()
    rep = appel(*args)
    total = time.perf_counter() - debut
    if not rep.get("success"):
        etapes_resumees.append((nom + " (échec)", None, total))
        echec(f"{nom} : {rep.get('error')}")
    etapes_resumees.append((nom, rep.get("duree_ms"), total))
    return rep


def verifier(condition, message):
    if not condition:
        echec(message)
    print(f"  OK : {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="ne pas demander de confirmation")
    parser.add_argument("--sans-reset", action="store_true", help="ne pas exécuter 07_reset.sql à la fin")
    args = parser.parse_args()

    if not args.yes and input("Ce test détache/restaure la base de démo. Taper OUI pour continuer : ") != "OUI":
        print("Annulé.")
        return

    api = Api()
    if api.erreur_demarrage:
        echec(f"connexion impossible : {api.erreur_demarrage}")

    statut = api.get_status()
    verifier(statut.get("etat") == "en_ligne", f"base en ligne au départ (état : {statut.get('etat')})")
    verifier(statut.get("index_desactive") is True, "idx_pseudo désactivé au départ (lancer 07_reset.sql sinon)")

    # 1. Le visiteur cherche un jeu
    rep = etape("1. Recherche d'un jeu (t_jeux)", api.rechercher_jeux, "")
    verifier(len(rep["jeux"]) > 0, f"{len(rep['jeux'])} jeu(x) dans le catalogue")
    filtre = etape("1b. Recherche filtrée « a »", api.rechercher_jeux, "a")
    verifier(len(filtre["jeux"]) > 0, f"{len(filtre['jeux'])} jeu(x) pour « a »")
    jeu = rep["jeux"][0]

    # 2. Cadeau à un ami : INSERT t_joueur + t_achats en transaction
    pseudo_ami = f"Smoke_{int(time.time())}"
    achat = etape("2. Offrir le jeu (INSERT en transaction)", api.offrir_jeu, jeu["jeux_id"], pseudo_ami, "TestVisiteur")
    verifier(abs(achat["prix_paye"] - jeu["prix"]) < 0.001, f"prixPaye = prix du jeu ({jeu['prix']})")

    # 3. Recherche lente (index désactivé)
    avant = etape("3. Recherche de l'ami SANS index", api.rechercher_joueur, pseudo_ami)
    verifier(avant["trouve"], f"« {pseudo_ami} » trouvé")
    verifier(avant["index_desactive"] is True, "index désactivé pendant la recherche lente")

    # 4. Animateur : 04a (mesuré) + 04b en arrière-plan
    idx = etape("4. Activer l'index (04a REBUILD)", api.activer_index)
    verifier(idx["backup_lance"], "04b lancé en arrière-plan")

    # 5. Recherche rapide pendant que 04b tourne
    apres = etape("5. Recherche de l'ami AVEC index", api.rechercher_joueur, pseudo_ami)
    verifier(apres["trouve"], f"« {pseudo_ami} » trouvé")
    verifier(apres["index_desactive"] is False, "index actif pendant la recherche rapide")
    facteur = avant["duree_ms"] / max(1, apres["duree_ms"])
    print(f"  Avant : {avant['duree_ms']} ms — Après : {apres['duree_ms']} ms (×{facteur:.0f})")

    # 6. OK du visiteur : écriture + 05 (attend la fin de 04b)
    inc = etape("6. OK : validation + incident (05)", api.valider_achat)
    verifier(inc["panne"], "incident déclenché")
    sauvegarde = api.get_status()["sauvegarde"]
    verifier(sauvegarde["etat"] == "ok", f"sauvegarde DIFF terminée ({sauvegarde['duree_ms']} ms)")
    etapes_resumees.append(("   dont sauvegarde LOG0 + DIFF (04b)", sauvegarde["duree_ms"], 0.0))
    verifier(api.get_status().get("etat") == "absente", "base détachée : l'appli est « en panne »")

    # 7-8. Restauration et reveal
    resto = etape("7. Restaurer (06 : FULL, DIFF, LOG)", api.restaurer)
    for e in resto["etapes"]:
        print(f"  {e['nom']:<5}: {e['duree_ms']} ms")
        etapes_resumees.append((f"   dont restauration {e['nom']}", e["duree_ms"], 0.0))
    verifier(len(resto["reveal"]) > 0, "reveal : des achats sont revenus")
    dernier = resto["reveal"][0]
    verifier(dernier["ami"] == pseudo_ami, f"reveal : le pseudo de l'ami est revenu ({dernier['ami']})")
    verifier(dernier["offertPar"] == "TestVisiteur", "reveal : offertPar = pseudo du visiteur")
    verifier(api.get_status().get("etat") == "en_ligne", "base de nouveau en ligne")

    # 9. Reset
    if args.sans_reset:
        print("\nReset ignoré (--sans-reset) : lancer 07_reset.sql avant la prochaine démo.")
    else:
        rst = etape("9. Reset (07)", api.reset)
        verifier(rst.get("index_desactive") is True, "idx_pseudo de nouveau désactivé")
        verifier(api.get_status().get("etat") == "en_ligne", "base en ligne après reset")

    afficher_resume()
    print("\nScénario complet terminé sans erreur.")


if __name__ == "__main__":
    main()
