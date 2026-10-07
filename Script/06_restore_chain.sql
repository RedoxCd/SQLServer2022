/* 06 - RESTAURATION EN DIRECT par l'animateur : FULL -> DIFF -> LOG (STOPAT).
   STOPAT = fin du dernier backup de log (lu dans msdb). On peut aussi saisir l'heure à la main. */
USE master;
GO
DECLARE @stopat DATETIME =
    (SELECT TOP (1) backup_finish_date FROM msdb.dbo.backupset
     WHERE database_name = N'LootTable' AND type = 'L'
     ORDER BY backup_finish_date DESC);
PRINT CONCAT('STOPAT = ', CONVERT(VARCHAR(23), @stopat, 121));

RESTORE DATABASE LootTable FROM DISK = N'C:\LootTable\Backup\LootTable_FULL.bak'
    WITH FILE = 1, NORECOVERY, REPLACE, STATS = 20;

RESTORE DATABASE LootTable FROM DISK = N'C:\LootTable\Backup\LootTable_DIFF.bak'
    WITH FILE = 1, NORECOVERY, STATS = 20;

RESTORE LOG LootTable FROM DISK = N'C:\LootTable\Backup\LootTable_LOG1.bak'
    WITH FILE = 1, STOPAT = @stopat, RECOVERY;
GO
-- Reveal : l'achat et le pseudo de l'ami sont revenus
USE LootTable;
SELECT TOP (5) a.achats_id, j.pseudo AS ami, g.titre, a.offertPar, a.dateAchat
FROM dbo.t_achats a
JOIN dbo.t_joueur j ON j.joueur_id = a.joueur_id
JOIN dbo.t_jeux   g ON g.jeux_id   = a.jeux_id
ORDER BY a.achats_id DESC;
