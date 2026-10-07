/* 05 - INCIDENT (déclenché en silence par le clic « OK » du visiteur).
   1) sauvegarde du log (sans elle, pas de restauration à l'instant T)
   2) coupe les connexions et détache la base -> l'appli tombe en panne. */
USE master;
GO
BACKUP LOG LootTable
TO DISK = N'C:\LootTable\Backup\LootTable_LOG1.bak' WITH INIT, FORMAT, CHECKSUM;
GO
ALTER DATABASE LootTable SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
GO
EXEC master.dbo.sp_detach_db @dbname = N'LootTable', @skipchecks = N'true';
GO
