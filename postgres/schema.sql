-- ==============================================================================
-- DIMENSIONAL SCHEMA (STAR SCHEMA) - TECH JOB MARKET IN MONTREAL
-- Course: MTI820-01 Data Warehousing and Business Intelligence
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. DATE DIMENSION
-- In a data warehouse, a standard DATE type is generally not used as a primary key.
-- Instead, we use an integer in YYYYMMDD format (e.g., 20260721).
-- This speeds up temporal aggregation queries and facilitates partitioning.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT PRIMARY KEY,             -- Formatted Surrogate Key (e.g., 20260721)
    full_date DATE NOT NULL,               -- Standard full date
    year INT NOT NULL,                     -- Year (e.g., 2026)
    month INT NOT NULL,                    -- Month number (1 to 12)
    month_name VARCHAR(20) NOT NULL,       -- Month name (e.g., July)
    day INT NOT NULL,                      -- Day of the month (1 to 31)
    quarter INT NOT NULL,                  -- Quarter (1 to 4)
    day_of_week INT NOT NULL,              -- Day of the week (1 to 7)
    day_of_week_name VARCHAR(20) NOT NULL  -- Day name (e.g., Monday)
);

-- ------------------------------------------------------------------------------
-- 2. COMPANY DIMENSION
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_company (
    company_key SERIAL PRIMARY KEY,        -- Surrogate Key (sequential substitution key)
    company_name VARCHAR(255) UNIQUE NOT NULL, -- Natural Key (the unique company name)
    company_sector VARCHAR(100) DEFAULT 'not_specified' -- Business sector of the company
);

-- ------------------------------------------------------------------------------
-- 3. LOCATION DIMENSION
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_location (
    location_key SERIAL PRIMARY KEY,       -- Surrogate Key
    location_name VARCHAR(255) UNIQUE NOT NULL -- Natural Key (e.g., Montreal, Laval)
);

-- ------------------------------------------------------------------------------
-- 4. CONTRACT DIMENSION
-- Groups working terms (permanent, contract, full-time, part-time)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_contract (
    contract_key SERIAL PRIMARY KEY,       -- Surrogate Key
    contract_time VARCHAR(50),             -- permanent or contract
    contract_type VARCHAR(50),             -- full_time or part_time
    CONSTRAINT unique_contract_combination UNIQUE (contract_time, contract_type)
);

-- ------------------------------------------------------------------------------
-- 5. SKILLS DIMENSION
-- Contains the list of key skills being analyzed (e.g., Python, SQL)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_skills (
    skill_key SERIAL PRIMARY KEY,          -- Surrogate Key
    skill_name VARCHAR(50) UNIQUE NOT NULL -- Skill name (e.g., python, sql)
);

-- ------------------------------------------------------------------------------
-- 6. FACT TABLE: JOB POSTINGS
-- This is the core of our star schema. It contains the foreign keys
-- pointing to dimensions and measurable facts (salaries).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_job_postings (
    job_key SERIAL PRIMARY KEY,            -- Fact table Surrogate Key
    adzuna_id VARCHAR(50) UNIQUE,          -- Natural Key (Adzuna job posting unique ID)
    job_title VARCHAR(255) NOT NULL,       -- Job title
    description TEXT,                      -- Text description
    company_key INT REFERENCES dim_company(company_key),
    location_key INT REFERENCES dim_location(location_key),
    date_key INT REFERENCES dim_date(date_key),
    contract_key INT REFERENCES dim_contract(contract_key),
    salary_min NUMERIC(12, 2),             -- Minimum salary offered
    salary_max NUMERIC(12, 2),             -- Maximum salary offered
    salary_avg NUMERIC(12, 2),             -- Calculated average salary
    has_salary BOOLEAN NOT NULL DEFAULT FALSE, -- Indicator if salary is provided
    language VARCHAR(50) DEFAULT 'not_specified', -- Language of the posting (french, english, bilingual)
    experience_level VARCHAR(50) DEFAULT 'not_specified', -- Experience level (junior, intermediate, senior)
    work_model VARCHAR(50) DEFAULT 'not_specified', -- Work flexibility model (remote, hybrid, on_site)
    latitude NUMERIC(9, 6),                -- Geographic latitude
    longitude NUMERIC(9, 6),               -- Geographic longitude
    neighborhood VARCHAR(100) DEFAULT 'not_specified' -- Neighborhood / borough of Montreal
);

-- ------------------------------------------------------------------------------
-- 7. ASSOCIATION TABLE (BRIDGE): REQUIRED SKILLS
-- Models the many-to-many relationship between job postings and skills from dim_skills.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_job_skills (
    job_key INT REFERENCES fact_job_postings(job_key) ON DELETE CASCADE,
    skill_key INT REFERENCES dim_skills(skill_key) ON DELETE CASCADE,
    PRIMARY KEY (job_key, skill_key)
);
