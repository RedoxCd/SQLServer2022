/* 08 - Requêtes de contrôle / de démo */
USE LootTable;
SET STATISTICS TIME ON;
-- Recherche d'un ami (lente index désactivé, rapide après REBUILD)
SELECT joueur_id, pseudo, dateCreation FROM dbo.t_joueur WHERE pseudo = 'Lucas';
-- Etat de l'index
SELECT name, type_desc, is_disabled FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.t_joueur');
-- Historique des sauvegardes de la chaîne
SELECT type, backup_start_date, backup_finish_date, CAST(compressed_backup_size/1048576.0 AS DECIMAL(10,1)) AS Mo
FROM msdb.dbo.backupset WHERE database_name = 'LootTable' ORDER BY backup_start_date DESC;
