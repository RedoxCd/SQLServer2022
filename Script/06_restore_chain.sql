/* 06 - RESTAURATION EN DIRECT par l'animateur : FULL -> DIFF -> LOG.
   Le log est rejoué jusqu'au bout (sans STOPAT) : l'incident 05 est une panne (base détachée),
   pas une suppression de données, donc il n'y a aucun point « avant l'incident » à retrouver. */
USE master;
GO
RESTORE DATABASE LootTable FROM DISK = N'C:\LootTable\Backup\LootTable_FULL.bak'
    WITH FILE = 1, NORECOVERY, REPLACE, STATS = 20;

RESTORE DATABASE LootTable FROM DISK = N'C:\LootTable\Backup\LootTable_DIFF.bak'
    WITH FILE = 1, NORECOVERY, STATS = 20;

RESTORE LOG LootTable FROM DISK = N'C:\LootTable\Backup\LootTable_LOG1.bak'
    WITH FILE = 1, RECOVERY;
GO
-- Reveal : l'achat et le pseudo de l'ami sont revenus
USE LootTable;
SELECT TOP (5) a.achats_id, j.pseudo AS ami, g.titre, a.offertPar, a.dateAchat
FROM dbo.t_achats a
JOIN dbo.t_joueur j ON j.joueur_id = a.joueur_id
JOIN dbo.t_jeux   g ON g.jeux_id   = a.jeux_id
ORDER BY a.achats_id DESC;
