"""Régénère demo_hors_ligne.html : une page autonome (sans base de données).

Assemble index.html + style.css + app.js + mock_api.js (fausse API Python) dans un
seul fichier. Les jeux viennent de Script/02_generate_data.sql, les commandes SQL
affichées de main.py (SQL_AFFICHE) et des scripts de Script/ : rien n'est recopié
à la main.

    python build_hors_ligne.py
"""

import ast
import json
import re
from pathlib import Path

ICI = Path(__file__).resolve().parent
SCRIPTS = ICI.parent / "Script"


def lire(chemin):
    return Path(chemin).read_text(encoding="utf-8-sig")


def jeux():
    motif = re.compile(r"\(N'((?:[^']|'')*)', '(\w+)', N'([^']*)', ([\d.]+), N'((?:[^']|'')*)', (\d+)\)")
    return [
        {"jeux_id": i, "titre": m[1].replace("''", "'"), "plateforme": m[2], "genre": m[3],
         "prix": float(m[4]), "editeur": m[5].replace("''", "'"), "annee": int(m[6])}
        for i, m in enumerate(motif.finditer(lire(SCRIPTS / "02_generate_data.sql")), start=1)
    ]


def constante(arbre, nom):
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and getattr(noeud.targets[0], "id", None) == nom:
            return noeud.value
    raise KeyError(nom)


def commandes_sql():
    """SQL_AFFICHE + textes des scripts, comme le fait Api.get_sql()."""
    arbre = ast.parse(lire(ICI / "main.py"))
    consts = {n: ast.literal_eval(constante(arbre, n)) for n in
              ("SCRIPT_INDEX", "SCRIPT_BACKUP_DIFF", "SCRIPT_RESTORE", "SCRIPT_RESET")}
    sql = ast.literal_eval(constante(arbre, "SQL_AFFICHE"))
    scripts = {
        "index": [consts["SCRIPT_INDEX"], consts["SCRIPT_BACKUP_DIFF"]],
        "restauration": [consts["SCRIPT_RESTORE"]],
        "reset": [consts["SCRIPT_RESET"]],
    }
    for nom, fichiers in scripts.items():
        sql[nom] = "\n\n".join(lire(SCRIPTS / f).strip() for f in fichiers)
    return sql


def main():
    html = lire(ICI / "index.html")
    mock = lire(ICI / "mock_api.js").replace("__JEUX__", json.dumps(jeux(), ensure_ascii=False))
    mock = mock.replace("__SQL__", json.dumps(commandes_sql(), ensure_ascii=False))
    html = html.replace("<title>LootTable — Démo SQL Server 2022</title>", "<title>LootTable — Démo hors ligne</title>")
    html = html.replace('<link rel="stylesheet" href="style.css" />', "<style>\n" + lire(ICI / "style.css") + "</style>")
    html = html.replace(
        '<script src="app.js"></script>',
        "<!-- ===== MODE HORS LIGNE : fausse API Python, aucune base de données ===== -->\n"
        "  <script>\n" + mock + "  </script>\n  <script>\n" + lire(ICI / "app.js") + "</script>",
    )
    (ICI / "demo_hors_ligne.html").write_text(html, encoding="utf-8")
    print("demo_hors_ligne.html généré.")


if __name__ == "__main__":
    main()
