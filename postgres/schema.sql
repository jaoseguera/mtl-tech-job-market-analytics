-- ==============================================================================
-- SCHÉMA DIMENSIONNEL (SCHÉMA EN ÉTOILE) - MARCHÉ DE L'EMPLOI TECH À MONTRÉAL
-- Cours : MTI820-01 Entrepôts de données et intelligence d'affaires
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. DIMENSION DATE
-- Dans un entrepôt de données, on n'utilise généralement pas le type DATE standard
-- comme clé primaire. On utilise un entier au format YYYYMMDD (ex: 20260721).
-- Cela permet d'accélérer les requêtes d'agrégation temporelle et facilite le partitionnement.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT PRIMARY KEY,             -- Surrogate Key formatée (ex: 20260721)
    full_date DATE NOT NULL,               -- Date complète standard
    year INT NOT NULL,                     -- Année (ex: 2026)
    month INT NOT NULL,                    -- Numéro du mois (1 à 12)
    month_name VARCHAR(20) NOT NULL,       -- Nom du mois (ex: Juillet)
    day INT NOT NULL,                      -- Jour du mois (1 à 31)
    quarter INT NOT NULL,                  -- Trimestre (1 à 4)
    day_of_week INT NOT NULL,              -- Jour de la semaine (1 à 7)
    day_of_week_name VARCHAR(20) NOT NULL  -- Nom du jour (ex: Lundi)
);

-- ------------------------------------------------------------------------------
-- 2. DIMENSION ENTREPRISE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_company (
    company_key SERIAL PRIMARY KEY,        -- Surrogate Key (clé de substitution séquentielle)
    company_name VARCHAR(255) UNIQUE NOT NULL -- Natural Key (le nom unique de la compagnie)
);

-- ------------------------------------------------------------------------------
-- 3. DIMENSION LOCALISATION
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_location (
    location_key SERIAL PRIMARY KEY,       -- Surrogate Key
    location_name VARCHAR(255) UNIQUE NOT NULL -- Natural Key (ex: Montréal, Laval)
);

-- ------------------------------------------------------------------------------
-- 4. DIMENSION CONTRAT
-- Regroupe les modalités de travail (permanent, temporaire, temps plein, temps partiel)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_contract (
    contract_key SERIAL PRIMARY KEY,       -- Surrogate Key
    contract_time VARCHAR(50),             -- permanent ou contract
    contract_type VARCHAR(50),             -- full_time ou part_time
    CONSTRAINT unique_contract_combination UNIQUE (contract_time, contract_type)
);

-- ------------------------------------------------------------------------------
-- 5. DIMENSION COMPÉTENCES
-- Contient la liste des compétences clés que l'on recherche (ex: Python, SQL)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_skills (
    skill_key SERIAL PRIMARY KEY,          -- Surrogate Key
    skill_name VARCHAR(50) UNIQUE NOT NULL -- Nom de la compétence (ex: python, sql)
);

-- ------------------------------------------------------------------------------
-- 6. TABLE DE FAITS : OFFRES D'EMPLOI
-- C'est le cœur de notre schéma en étoile. Elle contient les clés étrangères
-- pointant vers les dimensions et les faits mesurables (les salaires).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_job_postings (
    job_key SERIAL PRIMARY KEY,            -- Surrogate Key de la table de faits
    adzuna_id VARCHAR(50) UNIQUE,          -- Clé Naturelle (ID unique de l'offre d'emploi Adzuna)
    job_title VARCHAR(255) NOT NULL,       -- Titre de l'emploi
    description TEXT,                      -- Description textuelle
    company_key INT REFERENCES dim_company(company_key),
    location_key INT REFERENCES dim_location(location_key),
    date_key INT REFERENCES dim_date(date_key),
    contract_key INT REFERENCES dim_contract(contract_key),
    salary_min NUMERIC(12, 2),             -- Salaire minimum offert
    salary_max NUMERIC(12, 2),             -- Salaire maximum offert
    salary_avg NUMERIC(12, 2),             -- Salaire moyen calculé
    has_salary BOOLEAN NOT NULL DEFAULT FALSE -- Indicateur si le salaire est fourni
);

-- ------------------------------------------------------------------------------
-- 7. TABLE D'ASSOCIATION (PONT) : COMPÉTENCES REQUISES
-- Modélise la relation plusieurs-à-plusieurs (Many-to-Many) entre les offres d'emploi
-- et les compétences de la dimension dim_skills.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_job_skills (
    job_key INT REFERENCES fact_job_postings(job_key) ON DELETE CASCADE,
    skill_key INT REFERENCES dim_skills(skill_key) ON DELETE CASCADE,
    PRIMARY KEY (job_key, skill_key)
);
