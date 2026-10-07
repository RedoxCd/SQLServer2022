# LootTable - ordre d'exécution

## Installation (une seule fois, ~15-30 min)
1. Créer `C:\LootTable\Data` et `C:\LootTable\Backup` (droits d'écriture pour le service SQL Server).
2. `01_create_database.sql` -> `02_generate_data.sql` -> vérifier `idx_pseudo` is_disabled = 1 -> `03_golden_backup.sql`.
3. `07_reset.sql` (crée le FULL de la chaîne). La base est prête.

## Déroulé de la démo
| Étape | Script / action |
|---|---|
| 1-2 Visiteur cherche un jeu, offre à un ami | App (t_jeux, t_joueur, t_achats) |
| 3 Recherche de l'ami (lente) | App (requête de `08_verification.sql`) |
| 4 Animateur active l'index | `04a_activer_index.sql` puis, tout de suite, `04b_backup_diff.sql` |
| 5 Même recherche (rapide) | App |
| 6 Clic « OK » | App écrit l'achat puis lance `05_incident.sql` (silencieux) |
| 7 Restauration en direct | `06_restore_chain.sql` |
| 8 Reveal | dernier SELECT de `06` |
| Visiteur suivant | `07_reset.sql` (~1-2 min) |

## À mesurer en répétition
- Durée de la recherche lente (cible : plusieurs secondes) et de la rapide (< 1 s).
- Durée du REBUILD (04a) : prévoir de quoi meubler.
- Durée de la restauration (06) et du reset (07).

## Migration Sébeillon
Copier `LootTable_GOLDEN.bak` sur le portable, créer les mêmes dossiers (ou adapter les chemins / ajouter MOVE), lancer `07_reset.sql`, puis tester la démo complète.
Garder une copie du .bak sur clé USB.
