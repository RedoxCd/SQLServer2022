-- INCIDENT : suppression massive et accidentelle de tous les billets vendus.
-- Scénario : un opérateur exécute un DELETE sans clause WHERE sur t_billets.
USE [{{DB_NAME}}];
GO

DELETE FROM t_billets;
GO
