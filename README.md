# SQLServer2022
This project is for the "Porte Ouverte de l'ETML", where people without any IT knowledge will discover the SQL Server 2022 software. The public will have an activity that is 5 to 7 minutes long to complete and have fun.

## Modeling
If you have any issues understanding how the database works and how the connections between tables are made, you can check **Porte_Ouverte.loo**. It will open Looping, which is the modeling software that I used. Both MCD and MLD (Merise method) can be checked.

## Script
### 1: 
In the folder "Script", create_data_base.txt is the script to create the database and the table, it has to be executed before any other script or operations.  

__*Disclaimer:*__ Since we are creating around 50 million records at once, the IDENTITY column of the t_billets table might be too small—even though it can hold up to 2.14 billion records. So don't forget to drop the table if you re-execute the script.
