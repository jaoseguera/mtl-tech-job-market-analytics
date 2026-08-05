## Script Overview

### 1. `config.py`
- **What it is for**: Shared configuration file.
- **Details**: Defines the global list of technological keywords (`SKILLS`) such as programming languages, cloud platforms, databases, and frameworks. These are used in the transformation steps to identify and analyze required skills from job descriptions.
- **How to use**: Imported as a module. Not intended to be executed directly.
  ```python
  from config import SKILLS
  ```

---

### 2. `extract_jobs.py`
- **What it is for**: Raw data extraction from the Adzuna API.
- **Details**: Queries the Adzuna API for tech job postings in the Montreal area. Handles pagination (up to 500 pages) and retries on retryable status codes (e.g., rate limits `429` or server errors `500+`). Saves the extracted raw data in two formats:
  1. A timestamped CSV file in `data/history/` for historical archives (e.g., `jobs_raw_20260805_120000.csv`).
  2. A single raw CSV file in `data/jobs_raw.csv` representing the most recent raw batch.
- **How to use**:
  Ensure `.env` contains `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`, then run:
  ```bash
  python scripts/extract_jobs.py
  ```

---

### 3. `transform_jobs.py`
- **What it is for**: Data cleaning, concurrent web scraping, and analytical enrichment.
- **Details**:
  - Identifies jobs from `data/jobs_raw.csv` that do not have their full descriptions cached.
  - Concurrently scrapes full descriptions from Adzuna's redirect links and caches them locally in `data/scraped_descriptions.csv` (optimizing API usage and network bandwidth).
  - Classifies five custom analytical dimensions using robust heuristics:
    - **Language**: French, English, or Bilingual.
    - **Experience Level**: Junior, Intermediate, or Senior.
    - **Work Model**: Remote, Hybrid, or On-site.
    - **Neighborhood**: Localizes latitude/longitude to specific Montreal neighborhoods (e.g., Downtown, Plateau, Saint-Laurent).
    - **Company Sector**: Robust industry-level grouping (e.g., Aerospace, Finance, Software, IT Consulting, Retail).
  - Analyzes tech skills using patterns defined in `config.py`.
  - Saves the cleaned, enriched dataset to `data/jobs_clean.csv`.
- **How to use**:
  ```bash
  python scripts/transform_jobs.py
  ```

---

### 4. `process_history.py`
- **What it is for**: Historical raw data compilation and consolidation.
- **Details**: Gathers all archived raw files (`data/history/jobs_raw_*.csv`) along with any immediate raw data (`data/jobs_raw.csv`), merges them, deduplicates records on their unique Adzuna ID, cleans them, applies the exact same dimension and sector classification heuristics as `transform_jobs.py`, and creates a compiled clean historical master file.
- **How to use**:
  ```bash
  python scripts/process_history.py
  ```

---

### 5. `load_jobs.py`
- **What it is for**: Loading cleaned data into the PostgreSQL star-schema database.
- **Details**: Populates the data warehouse dimensions and facts sequentially:
  1. Maps and loads date-based entries into `dim_date`.
  2. Resolves company profiles and upserts them into `dim_company` (using an `ON CONFLICT DO UPDATE` clause to keep company sectors up to date).
  3. Resolves locations into `dim_location`.
  4. Resolves contract/job listings into `dim_contract`.
  5. Populates `dim_skills` with the technological skills.
  6. Bulk inserts job records into the main `fact_postings` table.
  7. Populates the `bridge_postings_skills` association table to link job facts with their respective tech skills.
- **How to use**:
  Ensure PostgreSQL environment variables are configured in `.env`, then run:
  ```bash
  python scripts/load_jobs.py
  ```

---

### 6. `update_company_sectors.py`
- **What it is for**: Database sector synchronization and maintenance.
- **Details**: Connects to the active database, fetches all existing entries from the `dim_company` table, re-classifies their industry sectors using the updated whole-word regex classification heuristics to prevent false-positive overlaps (like "Whitney" matching "ey"), and updates the records directly in the DB in-place.
- **How to use**:
  ```bash
  python scripts/update_company_sectors.py
  ```

---

## Standard Run Workflow

To fetch, transform, and load a fresh set of job postings:

1. **Extract raw postings**:
   ```bash
   python scripts/extract_jobs.py
   ```
2. **Clean, scrape, and enrich listings**:
   ```bash
   python scripts/transform_jobs.py
   ```
3. **Load enriched listings to Database**:
   ```bash
   python scripts/load_jobs.py
   ```