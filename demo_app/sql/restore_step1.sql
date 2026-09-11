-- ETAPE 1/3 : bascule en mode restauration + restauration de la sauvegarde
-- COMPLETE (FULL), prise avant l'incident.
--
-- On sauvegarde d'abord la "fin" du journal de transactions (tail-log backup) :
-- cela capture l'incident (le DELETE) et permettra, à l'étape 3, de revenir
-- juste avant lui grâce à STOPAT.
--
-- Pendant les étapes 1 et 2, la base est dans l'état RESTORING : elle est
-- normalement inaccessible aux utilisateurs, c'est attendu.
USE master;
GO

ALTER DATABASE [{{DB_NAME}}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
GO

BACKUP LOG [{{DB_NAME}}]
TO DISK = N'{{TAIL_LOG_PATH}}'
WITH NORECOVERY, INIT;
GO

RESTORE DATABASE [{{DB_NAME}}]
FROM DISK = N'{{FULL_BACKUP_PATH}}'
WITH NORECOVERY, REPLACE{{MOVE_CLAUSE}};
GO
