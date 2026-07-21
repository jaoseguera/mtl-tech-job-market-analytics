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
        "DB_HOST, DB_PORT, DB_NAME, DB_USER et DB_PASS doivent être définis dans .env"
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
    # 1. Charger les données nettoyées
    csv_path = "data/jobs_clean.csv"
    if not os.path.exists(csv_path):
        print(f"Erreur : Le fichier {csv_path} n'existe pas. Veuillez lancer 'transform_jobs.py' d'abord.")
        return

    df = pd.read_csv(csv_path)
    print(f"Chargement de {len(df)} offres d'emploi depuis {csv_path}...")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # ÉTAPE 1 : PRÉ-ALIMENTER LA DIMENSION DES COMPÉTENCES (dim_skills)
        print("Alimentation de dim_skills...")
        skill_keys = {} # Pour garder en mémoire les couples {nom_competence: skill_key}
        for skill in SKILLS:
            # On insère si elle n'existe pas, et on récupère le skill_key
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
        
        # ÉTAPE 2 : RÉSOUDRE LES DIMENSIONS POUR CHAQUE OFFRE
        # Les dictionnaires ci-dessous évitent de refaire un aller-retour SQL pour
        # une entreprise/localisation/contrat/date déjà vue plus tôt dans ce run.
        print("Résolution des dimensions (date, entreprise, localisation, contrat)...")
        seen_dates = set()
        company_keys = {}
        location_keys = {}
        contract_keys = {}

        # On sépare les offres avec adzuna_id (dédoublonnables) de celles sans
        # (toujours insérées) pour pouvoir batcher les deux en toute sécurité.
        rows_with_id = []
        rows_without_id = []

        for index, row in df.iterrows():
            # --- A. Gestion de la dimension DATE (dim_date) ---
            # Adzuna formatte la date sous forme de timestamp ISO (ex: 2026-07-21T10:16:59Z)
            # On extrait uniquement la partie date YYYY-MM-DD
            raw_date = str(row['created_date'])
            date_obj = pd.to_datetime(raw_date)

            # Génération de la clé sous format entier YYYYMMDD
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
                        date_obj.strftime("%B"), # Nom du mois en anglais (ou selon la locale)
                        date_obj.day,
                        (date_obj.month - 1) // 3 + 1, # Trimestre
                        date_obj.isoweekday(), # 1 (Lundi) à 7 (Dimanche)
                        date_obj.strftime("%A") # Nom du jour
                    )
                )
                seen_dates.add(date_key)

            # --- B. Gestion de la dimension ENTREPRISE (dim_company) ---
            company_name = str(row['company']).strip() if pd.notna(row['company']) else "Inconnu"
            if company_name not in company_keys:
                cursor.execute(
                    """
                    INSERT INTO dim_company (company_name)
                    VALUES (%s)
                    ON CONFLICT (company_name) DO UPDATE SET company_name = EXCLUDED.company_name
                    RETURNING company_key;
                    """,
                    (company_name,)
                )
                company_keys[company_name] = cursor.fetchone()[0]
            company_key = company_keys[company_name]

            # --- C. Gestion de la dimension LOCALISATION (dim_location) ---
            location_name = str(row['location']).strip() if pd.notna(row['location']) else "Montréal"
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

            # --- D. Gestion de la dimension CONTRAT (dim_contract) ---
            contract_time = str(row['contract_time']).strip() if pd.notna(row['contract_time']) else "unknown"
            contract_type = str(row['contract_type']).strip() if pd.notna(row['contract_type']) else "unknown"
            contract_combo = (contract_time, contract_type)
            if contract_combo not in contract_keys:
                cursor.execute(
                    """
                    INSERT INTO dim_contract (contract_time, contract_type)
                    VALUES (%s, %s)
                    ON CONFLICT (contract_time, contract_type) DO UPDATE
                        SET contract_time = EXCLUDED.contract_time -- astuce pour récupérer l'ID existant
                    RETURNING contract_key;
                    """,
                    contract_combo
                )
                contract_keys[contract_combo] = cursor.fetchone()[0]
            contract_key = contract_keys[contract_combo]

            # --- E. Préparation de la ligne pour la TABLE DE FAITS (fact_job_postings) ---
            adzuna_id = str(row['adzuna_id']).strip() if pd.notna(row['adzuna_id']) else None
            salary_min = float(row['salary_min']) if pd.notna(row['salary_min']) else None
            salary_max = float(row['salary_max']) if pd.notna(row['salary_max']) else None
            salary_avg = float(row['salary_avg']) if pd.notna(row['salary_avg']) else None
            has_salary = bool(row['has_salary'])
            matched_skills = [skill for skill in SKILLS if bool(row[skill]) is True]

            fact_row = (
                adzuna_id, row['job_title'], row['description'], company_key, location_key,
                date_key, contract_key, salary_min, salary_max, salary_avg, has_salary
            )

            if adzuna_id:
                rows_with_id.append((fact_row, matched_skills))
            else:
                rows_without_id.append((fact_row, matched_skills))

        # ÉTAPE 3 : INSERTION EN LOT DES OFFRES (fact_job_postings)
        print("Insertion en lot des offres d'emploi...")
        inserted_jobs = 0
        skipped_jobs = 0
        job_skill_rows = []

        if rows_with_id:
            # La contrainte UNIQUE sur adzuna_id gère le dédoublonnage : ON CONFLICT
            # DO NOTHING ignore silencieusement les doublons (pas de ligne retournée
            # pour elles), donc on ne peut pas mapper les résultats par position —
            # on remappe par adzuna_id à la place.
            fact_rows = [r for r, _ in rows_with_id]
            inserted = execute_values(
                cursor,
                """
                INSERT INTO fact_job_postings (
                    adzuna_id, job_title, description, company_key, location_key, date_key, contract_key,
                    salary_min, salary_max, salary_avg, has_salary
                )
                VALUES %s
                ON CONFLICT (adzuna_id) DO NOTHING
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
            # Pas d'adzuna_id : rien à dédoublonner, donc pas de ON CONFLICT et les
            # lignes retournées suivent l'ordre d'insertion des VALUES fournies.
            fact_rows = [r for r, _ in rows_without_id]
            inserted = execute_values(
                cursor,
                """
                INSERT INTO fact_job_postings (
                    adzuna_id, job_title, description, company_key, location_key, date_key, contract_key,
                    salary_min, salary_max, salary_avg, has_salary
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

        # ÉTAPE 4 : INSERTION EN LOT DES COMPÉTENCES ASSOCIÉES (fact_job_skills)
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

        # Valider toutes les transactions à la fin s'il n'y a pas eu d'erreurs
        conn.commit()
        print("\n==================================================")
        print("ALIMENTATION TERMINÉE AVEC SUCCÈS !")
        print(f"Offres insérées : {inserted_jobs}")
        print(f"Offres ignorées (déjà existantes) : {skipped_jobs}")
        print("==================================================")

    except Exception as e:
        # En cas d'erreur, on annule tout ce qui a été fait dans cette transaction pour garder la BD propre
        conn.rollback()
        print(f"\nUne erreur est survenue lors du chargement : {e}")
        print("Toutes les modifications de cette session ont été annulées (Rollback).")
    finally:
        # Fermer la connexion proprement
        cursor.close()
        conn.close()

if __name__ == "__main__":
    load_data()
