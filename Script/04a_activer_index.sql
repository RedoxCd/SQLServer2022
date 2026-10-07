/* 04a - ÉTAPE 4 de la démo : l'animateur active l'index.
   À mesurer en répétition : la durée du REBUILD sur 50 M de lignes (prévoir un discours d'attente). */
USE LootTable;
GO
ALTER INDEX idx_pseudo ON dbo.t_joueur REBUILD WITH (SORT_IN_TEMPDB = ON, MAXDOP = 0);
GO
