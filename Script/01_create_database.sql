/* 01 - Création de la base LootTable (à exécuter UNE fois)
   Prérequis : dossiers C:\LootTable\Data et C:\LootTable\Backup créés, avec droits en écriture
   pour le compte de service SQL Server. */
USE master;
GO
IF DB_ID(N'LootTable') IS NOT NULL
BEGIN
    ALTER DATABASE LootTable SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE LootTable;
END
GO
CREATE DATABASE LootTable
ON PRIMARY (NAME = LootTable_data, FILENAME = N'C:\LootTable\Data\LootTable.mdf', SIZE = 8GB, FILEGROWTH = 1GB)
LOG ON     (NAME = LootTable_log,  FILENAME = N'C:\LootTable\Data\LootTable_log.ldf', SIZE = 4GB, FILEGROWTH = 512MB)
COLLATE Latin1_General_CI_AS;
GO
ALTER DATABASE LootTable SET RECOVERY SIMPLE;   -- chargement rapide, repassé en FULL au script 03
GO
USE LootTable;
GO
CREATE TABLE dbo.t_jeux (
    jeux_id      INT IDENTITY,
    titre        VARCHAR(200) NOT NULL,
    plateforme   VARCHAR(50)  NOT NULL,
    genre        VARCHAR(50)  NOT NULL,
    prix         DECIMAL(5,2) NOT NULL,
    editeur      VARCHAR(100) NOT NULL,
    anneeSortie  INT NOT NULL,
    PRIMARY KEY (jeux_id)
);
CREATE TABLE dbo.t_joueur (
    joueur_id      INT IDENTITY,
    pseudo         VARCHAR(50) NOT NULL,
    dateCreation   DATETIME2 NOT NULL,
    PRIMARY KEY (joueur_id)
);
CREATE TABLE dbo.t_achats (
    achats_id   INT IDENTITY,
    jeux_id     INT NOT NULL,
    joueur_id   INT NOT NULL,
    prixPaye    DECIMAL(5,2) NOT NULL,
    dateAchat   DATETIME2 NOT NULL,
    offertPar   VARCHAR(50) NULL,
    PRIMARY KEY (achats_id),
    FOREIGN KEY (jeux_id)   REFERENCES dbo.t_jeux(jeux_id),
    FOREIGN KEY (joueur_id) REFERENCES dbo.t_joueur(joueur_id)
);
GO
