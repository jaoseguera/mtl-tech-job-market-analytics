import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import SKILLS

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS]):
    raise SystemExit(
        "DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASS must be defined in the .env file."
    )

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def load_data():
    # 1. Load the cleaned data
    csv_path = "data/jobs_clean.csv"
    if not os.path.exists(csv_path):
        print(f"Error: The file {csv_path} does not exist. Please run 'transform_jobs.py' first.")
        return

    df = pd.read_csv(csv_path)
    print(f"Loading {len(df)} job postings from {csv_path}...")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # STEP 1: PRE-POPULATE THE SKILLS DIMENSION (dim_skills)
        print("Populating dim_skills...")
        skill_keys = {} # To keep track of the {skill_name: skill_key} pairs in memory
        for skill in SKILLS:
            # Insert if it doesn't exist, and retrieve the skill_key
            cursor.execute(
                """
                INSERT INTO dim_skills (skill_name)
                VALUES (%s)
                ON CONFLICT (skill_name) DO UPDATE SET skill_name = EXCLUDED.skill_name
                RETURNING skill_key;
                """,
                (skill,)
            )
            skill_key = cursor.fetchone()[0]
            skill_keys[skill] = skill_key
        
        # STEP 2: RESOLVE DIMENSIONS FOR EACH POSTING
        # The dictionaries below prevent redundant SQL roundtrips for
        # a company/location/contract/date already processed in this run.
        print("Resolving dimensions (date, company, location, contract)...")
        seen_dates = set()
        company_keys = {}
        location_keys = {}
        contract_keys = {}

        # Separate postings with adzuna_id (deduplicatable) from those without
        # (always inserted) to batch both of them safely.
        rows_with_id = []
        rows_without_id = []

        for index, row in df.iterrows():
            # --- A. Handle the DATE dimension (dim_date) ---
            # Adzuna formats the date as an ISO timestamp (e.g., 2026-07-21T10:16:59Z)
            # We extract only the YYYY-MM-DD date part
            raw_date = str(row['created_date'])
            date_obj = pd.to_datetime(raw_date)

            # Generate the key as an integer format YYYYMMDD
            date_key = int(date_obj.strftime("%Y%m%d"))

            if date_key not in seen_dates:
                cursor.execute(
                    """
                    INSERT INTO dim_date (
                        date_key, full_date, year, month, month_name, day, quarter, day_of_week, day_of_week_name
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date_key) DO NOTHING;
                    """,
                    (
                        date_key,
                        date_obj.date(),
                        date_obj.year,
                        date_obj.month,
                        date_obj.strftime("%B"), # Month name in English (or based on locale)
                        date_obj.day,
                        (date_obj.month - 1) // 3 + 1, # Quarter
                        date_obj.isoweekday(), # 1 (Monday) to 7 (Sunday)
                        date_obj.strftime("%A") # Day name
                    )
                )
                seen_dates.add(date_key)

            # --- B. Handle the COMPANY dimension (dim_company) ---
            company_name = str(row['company']).strip() if pd.notna(row['company']) else "Unknown"
            company_sector = str(row['company_sector']).strip() if pd.notna(row['company_sector']) else "not_specified"
            if company_name not in company_keys:
                cursor.execute(
                    """
                    INSERT INTO dim_company (company_name, company_sector)
                    VALUES (%s, %s)
                    ON CONFLICT (company_name) DO UPDATE SET company_sector = EXCLUDED.company_sector
                    RETURNING company_key;
                    """,
                    (company_name, company_sector)
                )
                company_keys[company_name] = cursor.fetchone()[0]
            company_key = company_keys[company_name]

            # --- C. Handle the LOCATION dimension (dim_location) ---
            location_name = str(row['location']).strip() if pd.notna(row['location']) else "Montreal"
            if location_name not in location_keys:
                cursor.execute(
                    """
                    INSERT INTO dim_location (location_name)
                    VALUES (%s)
                    ON CONFLICT (location_name) DO UPDATE SET location_name = EXCLUDED.location_name
                    RETURNING location_key;
                    """,
                    (location_name,)
                )
                location_keys[location_name] = cursor.fetchone()[0]
            location_key = location_keys[location_name]

            # --- D. Handle the CONTRACT dimension (dim_contract) ---
            contract_time = str(row['contract_time']).strip() if pd.notna(row['contract_time']) else "unknown"
            contract_type = str(row['contract_type']).strip() if pd.notna(row['contract_type']) else "unknown"
            contract_combo = (contract_time, contract_type)
            if contract_combo not in contract_keys:
                cursor.execute(
                    """
                    INSERT INTO dim_contract (contract_time, contract_type)
                    VALUES (%s, %s)
                    ON CONFLICT (contract_time, contract_type) DO UPDATE
                        SET contract_time = EXCLUDED.contract_time -- trick to retrieve the existing ID
                    RETURNING contract_key;
                    """,
                    contract_combo
                )
                contract_keys[contract_combo] = cursor.fetchone()[0]
            contract_key = contract_keys[contract_combo]

            # --- E. Prepare row for the FACT TABLE (fact_job_postings) ---
            adzuna_id = str(row['adzuna_id']).strip() if pd.notna(row['adzuna_id']) else None
            salary_min = float(row['salary_min']) if pd.notna(row['salary_min']) else None
            salary_max = float(row['salary_max']) if pd.notna(row['salary_max']) else None
            salary_avg = float(row['salary_avg']) if pd.notna(row['salary_avg']) else None
            has_salary = bool(row['has_salary'])
            matched_skills = [skill for skill in SKILLS if bool(row[skill]) is True]

            # Extract new dimensions
            language = str(row['language']).strip() if pd.notna(row['language']) else 'not_specified'
            experience_level = str(row['experience_level']).strip() if pd.notna(row['experience_level']) else 'not_specified'
            work_model = str(row['work_model']).strip() if pd.notna(row['work_model']) else 'not_specified'
            latitude = float(row['latitude']) if pd.notna(row['latitude']) else None
            longitude = float(row['longitude']) if pd.notna(row['longitude']) else None
            neighborhood = str(row['neighborhood']).strip() if pd.notna(row['neighborhood']) else 'not_specified'

            fact_row = (
                adzuna_id, row['job_title'], row['description'], company_key, location_key,
                date_key, contract_key, salary_min, salary_max, salary_avg, has_salary,
                language, experience_level, work_model, latitude, longitude, neighborhood
            )

            if adzuna_id:
                rows_with_id.append((fact_row, matched_skills))
            else:
                rows_without_id.append((fact_row, matched_skills))

        # STEP 3: BULK INSERT JOB POSTINGS (fact_job_postings)
        print("Bulk inserting job postings...")
        inserted_jobs = 0
        skipped_jobs = 0
        job_skill_rows = []

        if rows_with_id:
            # UNIQUE constraint on adzuna_id handles deduplication: ON CONFLICT
            # DO UPDATE updates all descriptive and analytical columns
            fact_rows = [r for r, _ in rows_with_id]
            inserted = execute_values(
                cursor,
                """
                INSERT INTO fact_job_postings (
                    adzuna_id, job_title, description, company_key, location_key, date_key, contract_key,
                    salary_min, salary_max, salary_avg, has_salary,
                    language, experience_level, work_model, latitude, longitude, neighborhood
                )
                VALUES %s
                ON CONFLICT (adzuna_id) DO UPDATE SET 
                    description = EXCLUDED.description,
                    language = EXCLUDED.language,
                    experience_level = EXCLUDED.experience_level,
                    work_model = EXCLUDED.work_model,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    neighborhood = EXCLUDED.neighborhood
                RETURNING adzuna_id, job_key;
                """,
                fact_rows,
                fetch=True
            )
            job_key_by_adzuna_id = dict(inserted)
            inserted_jobs += len(job_key_by_adzuna_id)
            skipped_jobs += len(rows_with_id) - len(job_key_by_adzuna_id)

            for fact_row, matched_skills in rows_with_id:
                job_key = job_key_by_adzuna_id.get(fact_row[0])
                if job_key is None:
                    continue
                job_skill_rows.extend((job_key, skill_keys[skill]) for skill in matched_skills)

        if rows_without_id:
            # No adzuna_id: nothing to deduplicate
            fact_rows = [r for r, _ in rows_without_id]
            inserted = execute_values(
                cursor,
                """
                INSERT INTO fact_job_postings (
                    adzuna_id, job_title, description, company_key, location_key, date_key, contract_key,
                    salary_min, salary_max, salary_avg, has_salary,
                    language, experience_level, work_model, latitude, longitude, neighborhood
                )
                VALUES %s
                RETURNING job_key;
                """,
                fact_rows,
                fetch=True
            )
            inserted_jobs += len(inserted)

            for (job_key,), (_, matched_skills) in zip(inserted, rows_without_id):
                job_skill_rows.extend((job_key, skill_keys[skill]) for skill in matched_skills)

        # STEP 4: BULK INSERT OF ASSOCIATED SKILLS (fact_job_skills)
        if job_skill_rows:
            execute_values(
                cursor,
                """
                INSERT INTO fact_job_skills (job_key, skill_key)
                VALUES %s
                ON CONFLICT (job_key, skill_key) DO NOTHING;
                """,
                job_skill_rows
            )

        # Validate all transactions at the end if there were no errors
        conn.commit()
        print("\n==================================================")
        print("LOAD COMPLETED SUCCESSFULLY!")
        print(f"Postings inserted: {inserted_jobs}")
        print(f"Postings ignored (already existing): {skipped_jobs}")
        print("==================================================")

    except Exception as e:
        # In case of an error, rollback everything done in this transaction to keep the DB clean
        conn.rollback()
        print(f"\nAn error occurred during loading: {e}")
        print("All changes from this session have been rolled back (Rollback).")
    finally:
        # Properly close the connection
        cursor.close()
        conn.close()

if __name__ == "__main__":
    load_data()
