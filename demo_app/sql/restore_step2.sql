-- ETAPE 2/3 : restauration de la sauvegarde DIFFERENTIELLE (DIFF).
-- Elle ramène la base à l'état qu'elle avait juste avant que le journal
-- de transactions (restauré à l'étape 3) ne prenne le relais.
USE master;
GO

RESTORE DATABASE [{{DB_NAME}}]
FROM DISK = N'{{DIFF_BACKUP_PATH}}'
WITH NORECOVERY;
GO
