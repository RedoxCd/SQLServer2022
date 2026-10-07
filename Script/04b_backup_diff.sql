/* 04b - À lancer juste après le REBUILD (pendant que le visiteur relance sa recherche).
   Le LOG0 « jetable » évite que le log du REBUILD (très gros) se retrouve dans le LOG1 de l'incident. */
USE master;
GO
BACKUP LOG LootTable
TO DISK = N'C:\LootTable\Backup\LootTable_LOG0.bak' WITH INIT, FORMAT, CHECKSUM;
GO
BACKUP DATABASE LootTable
TO DISK = N'C:\LootTable\Backup\LootTable_DIFF.bak' WITH DIFFERENTIAL, INIT, FORMAT, CHECKSUM, STATS = 20;
GO
