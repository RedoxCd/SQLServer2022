/* 02 - Données : 42 jeux + 10 000 000 joueurs (GENERATE_SERIES, SQL Server 2022)
   Durée indicative : quelques minutes. Base en RECOVERY SIMPLE (script 01). */
USE LootTable;
SET NOCOUNT ON;
GO
INSERT INTO dbo.t_jeux (titre, plateforme, genre, prix, editeur, anneeSortie) VALUES
    (N'The Legend of Zelda: Breath of the Wild', 'Switch', N'Aventure', 59.90, N'Nintendo', 2017),
    (N'Super Mario Odyssey', 'Switch', N'Plateforme', 59.90, N'Nintendo', 2017),
    (N'Mario Kart 8 Deluxe', 'Switch', N'Course', 59.90, N'Nintendo', 2017),
    (N'Animal Crossing: New Horizons', 'Switch', N'Simulation', 59.90, N'Nintendo', 2020),
    (N'Splatoon 3', 'Switch', N'Tir', 59.90, N'Nintendo', 2022),
    (N'Super Smash Bros. Ultimate', 'Switch', N'Combat', 59.90, N'Nintendo', 2018),
    (N'Metroid Dread', 'Switch', N'Metroidvania', 49.90, N'Nintendo', 2021),
    (N'Pokémon Écarlate', 'Switch', N'RPG', 59.90, N'Game Freak', 2022),
    (N'Minecraft', 'PC', N'Bac à sable', 29.90, N'Mojang', 2011),
    (N'Hollow Knight', 'PC', N'Metroidvania', 14.99, N'Team Cherry', 2017),
    (N'Celeste', 'PC', N'Plateforme', 19.99, N'Maddy Makes Games', 2018),
    (N'Hades', 'PC', N'Roguelike', 24.99, N'Supergiant Games', 2020),
    (N'Stardew Valley', 'PC', N'Simulation', 13.99, N'ConcernedApe', 2016),
    (N'The Witcher 3: Wild Hunt', 'PC', N'RPG', 39.99, N'CD Projekt Red', 2015),
    (N'Cyberpunk 2077', 'PC', N'RPG', 59.99, N'CD Projekt Red', 2020),
    (N'Elden Ring', 'PC', N'RPG', 59.99, N'FromSoftware', 2022),
    (N'Dark Souls III', 'PC', N'RPG', 39.99, N'FromSoftware', 2016),
    (N'Baldur''s Gate 3', 'PC', N'RPG', 59.99, N'Larian Studios', 2023),
    (N'Hogwarts Legacy', 'PC', N'RPG', 59.99, N'Avalanche Software', 2023),
    (N'Red Dead Redemption 2', 'PC', N'Action-aventure', 59.99, N'Rockstar Games', 2018),
    (N'Grand Theft Auto V', 'PC', N'Action-aventure', 29.99, N'Rockstar Games', 2015),
    (N'Portal 2', 'PC', N'Puzzle', 9.99, N'Valve', 2011),
    (N'Half-Life: Alyx', 'PC', N'Tir', 49.99, N'Valve', 2020),
    (N'Rocket League', 'PC', N'Sport', 19.99, N'Psyonix', 2015),
    (N'Tetris Effect', 'PC', N'Puzzle', 29.99, N'Enhance', 2018),
    (N'Cuphead', 'PC', N'Run and gun', 19.99, N'Studio MDHR', 2017),
    (N'Undertale', 'PC', N'RPG', 9.99, N'Toby Fox', 2015),
    (N'Subnautica', 'PC', N'Survie', 29.99, N'Unknown Worlds', 2018),
    (N'Street Fighter 6', 'PC', N'Combat', 49.99, N'Capcom', 2023),
    (N'Alan Wake 2', 'PC', N'Horreur', 59.99, N'Remedy', 2023),
    (N'God of War', 'PS4', N'Action-aventure', 49.99, N'Santa Monica Studio', 2018),
    (N'Horizon Zero Dawn', 'PS4', N'Action-aventure', 19.99, N'Guerrilla Games', 2017),
    (N'Marvel''s Spider-Man', 'PS4', N'Action-aventure', 39.99, N'Insomniac Games', 2018),
    (N'The Last of Us Part II', 'PS4', N'Action-aventure', 39.99, N'Naughty Dog', 2020),
    (N'Gran Turismo 7', 'PS5', N'Course', 69.99, N'Polyphony Digital', 2022),
    (N'Astro Bot', 'PS5', N'Plateforme', 59.99, N'Team Asobi', 2024),
    (N'Ghost of Tsushima', 'PS5', N'Action-aventure', 59.99, N'Sucker Punch', 2020),
    (N'Resident Evil 4', 'PS5', N'Horreur', 39.99, N'Capcom', 2023),
    (N'EA Sports FC 25', 'PS5', N'Sport', 69.99, N'EA Sports', 2024),
    (N'Forza Horizon 5', 'Xbox', N'Course', 59.99, N'Playground Games', 2021),
    (N'Halo Infinite', 'Xbox', N'Tir', 59.99, N'343 Industries', 2021),
    (N'Gears 5', 'Xbox', N'Tir', 39.99, N'The Coalition', 2019);
GO
DECLARE @total BIGINT = 10000000, @batch BIGINT = 1000000, @start BIGINT = 1;
WHILE @start <= @total
BEGIN
    INSERT INTO dbo.t_joueur WITH (TABLOCK) (pseudo, dateCreation)
    SELECT CONCAT(CHOOSE(CAST(value % 16 AS INT) + 1, 'Shadow', 'Pixel', 'Turbo', 'Ninja', 'Dragon', 'Cyber', 'Frost', 'Blaze', 'Nova', 'Ghost', 'Storm', 'Viper', 'Rogue', 'Alpha', 'Lunar', 'Titan'), '_', value),
           DATEADD(MINUTE, -CAST(value % 2600000 AS INT), SYSDATETIME())
    FROM GENERATE_SERIES(@start, @start + @batch - 1);

    SET @start += @batch;
    CHECKPOINT;
    PRINT CONCAT(CAST(@start - 1 AS VARCHAR(20)), ' lignes - ', CONVERT(VARCHAR(8), GETDATE(), 108));
END
GO
-- Index sur le pseudo : créé puis DÉSACTIVÉ (la définition reste, les données disparaissent)
CREATE UNIQUE INDEX idx_pseudo ON dbo.t_joueur(pseudo);
ALTER INDEX idx_pseudo ON dbo.t_joueur DISABLE;
GO
SELECT (SELECT COUNT_BIG(*) FROM dbo.t_joueur) AS nb_joueurs, (SELECT COUNT(*) FROM dbo.t_jeux) AS nb_jeux;
SELECT name, is_disabled FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.t_joueur');
