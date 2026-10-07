/* 07 - RESET entre deux visiteurs : restaure l'état GOLDEN puis recrée la base de la chaîne FULL.
   Durée : ~1-2 min (restore + backup full). À lancer pendant que le visiteur suivant est accueilli.
   Fonctionne que la base existe, soit en panne ou soit détachée. */
USE master;
GO
IF DB_ID(N'LootTable') IS NOT NULL
    ALTER DATABASE LootTable SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
GO
RESTORE DATABASE LootTable FROM DISK = N'C:\LootTable\Backup\LootTable_GOLDEN.bak'
    WITH FILE = 1, REPLACE, RECOVERY, STATS = 20;
GO
ALTER DATABASE LootTable SET MULTI_USER;
ALTER DATABASE LootTable SET RECOVERY FULL;
GO
-- Nouveau FULL : point de départ de la chaîne FULL/DIFF/LOG du prochain visiteur
BACKUP DATABASE LootTable
TO DISK = N'C:\LootTable\Backup\LootTable_FULL.bak' WITH INIT, FORMAT, COMPRESSION, CHECKSUM, STATS = 20;
GO
-- Contrôle : l'index doit être désactivé (is_disabled = 1) et t_achats vide
USE LootTable;
SELECT name, is_disabled FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.t_joueur') AND name = 'idx_pseudo';
SELECT COUNT(*) AS nb_achats FROM dbo.t_achats;
