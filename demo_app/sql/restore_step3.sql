-- ETAPE 3/3 : restauration du journal de transactions (tail-log) jusqu'à
-- juste avant l'incident (STOPAT), puis remise en ligne de la base.
USE master;
GO

RESTORE LOG [{{DB_NAME}}]
FROM DISK = N'{{TAIL_LOG_PATH}}'
WITH RECOVERY, STOPAT = N'{{STOPAT}}';
GO

ALTER DATABASE [{{DB_NAME}}] SET MULTI_USER;
GO
