/* 03 - Sauvegarde « GOLDEN » (état initial de la démo) - à faire UNE fois après le chargement.
   Vérifier avant : idx_pseudo est bien is_disabled = 1. */
USE master;
GO
ALTER DATABASE LootTable SET RECOVERY FULL;
GO
BACKUP DATABASE LootTable
TO DISK = N'C:\LootTable\Backup\LootTable_GOLDEN.bak'
WITH INIT, FORMAT, CHECKSUM, STATS = 10;
GO
RESTORE VERIFYONLY FROM DISK = N'C:\LootTable\Backup\LootTable_GOLDEN.bak' WITH CHECKSUM;
GO
