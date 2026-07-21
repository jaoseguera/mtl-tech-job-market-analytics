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
        
        # ÉTAPE 2 : PARCOURIR LES OFFRES D'EMPLOI ET ALIMENTER LES TABLES
        print("Début de l'insertion des offres d'emploi (faits et dimensions)...")
        inserted_jobs = 0
        skipped_jobs = 0

        for index, row in df.iterrows():
            # --- A. Gestion de la dimension DATE (dim_date) ---
            # Adzuna formatte la date sous forme de timestamp ISO (ex: 2026-07-21T10:16:59Z)
            # On extrait uniquement la partie date YYYY-MM-DD
            raw_date = str(row['created_date'])
            date_obj = pd.to_datetime(raw_date)
            
            # Génération de la clé sous format entier YYYYMMDD
            date_key = int(date_obj.strftime("%Y%m%d"))
            
            # Insertion dans dim_date si elle n'existe pas déjà
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

            # --- B. Gestion de la dimension ENTREPRISE (dim_company) ---
            company_name = str(row['company']).strip() if pd.notna(row['company']) else "Inconnu"
            cursor.execute(
                """
                INSERT INTO dim_company (company_name)
                VALUES (%s)
                ON CONFLICT (company_name) DO UPDATE SET company_name = EXCLUDED.company_name
                RETURNING company_key;
                """,
                (company_name,)
            )
            company_key = cursor.fetchone()[0]

            # --- C. Gestion de la dimension LOCALISATION (dim_location) ---
            location_name = str(row['location']).strip() if pd.notna(row['location']) else "Montréal"
            cursor.execute(
                """
                INSERT INTO dim_location (location_name)
                VALUES (%s)
                ON CONFLICT (location_name) DO UPDATE SET location_name = EXCLUDED.location_name
                RETURNING location_key;
                """,
                (location_name,)
            )
            location_key = cursor.fetchone()[0]

            # --- D. Gestion de la dimension CONTRAT (dim_contract) ---
            contract_time = str(row['contract_time']).strip() if pd.notna(row['contract_time']) else "unknown"
            contract_type = str(row['contract_type']).strip() if pd.notna(row['contract_type']) else "unknown"
            cursor.execute(
                """
                INSERT INTO dim_contract (contract_time, contract_type)
                VALUES (%s, %s)
                ON CONFLICT (contract_time, contract_type) DO UPDATE 
                    SET contract_time = EXCLUDED.contract_time -- astuce pour récupérer l'ID existant
                RETURNING contract_key;
                """,
                (contract_time, contract_type)
            )
            contract_key = cursor.fetchone()[0]

            # --- E. Insertion dans la TABLE DE FAITS (fact_job_postings) ---
            adzuna_id = str(row['adzuna_id']).strip() if pd.notna(row['adzuna_id']) else None
            
            # Vérification de doublon sur la clé naturelle adzuna_id
            if adzuna_id:
                cursor.execute("SELECT job_key FROM fact_job_postings WHERE adzuna_id = %s;", (adzuna_id,))
                existing_job = cursor.fetchone()
                if existing_job:
                    skipped_jobs += 1
                    continue # On passe à la ligne suivante pour éviter d'insérer des doublons

            # Convertir les valeurs numériques pour les types SQL appropriés
            salary_min = float(row['salary_min']) if pd.notna(row['salary_min']) else None
            salary_max = float(row['salary_max']) if pd.notna(row['salary_max']) else None
            salary_avg = float(row['salary_avg']) if pd.notna(row['salary_avg']) else None
            has_salary = bool(row['has_salary'])

            cursor.execute(
                """
                INSERT INTO fact_job_postings (
                    adzuna_id, job_title, description, company_key, location_key, date_key, contract_key,
                    salary_min, salary_max, salary_avg, has_salary
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING job_key;
                """,
                (
                    adzuna_id,
                    row['job_title'],
                    row['description'],
                    company_key,
                    location_key,
                    date_key,
                    contract_key,
                    salary_min,
                    salary_max,
                    salary_avg,
                    has_salary
                )
            )
            job_key = cursor.fetchone()[0]
            inserted_jobs += 1

            # --- F. Association des compétences (fact_job_skills) ---
            for skill in SKILLS:
                # Si la colonne de compétence est True dans le CSV pour cette offre d'emploi
                if bool(row[skill]) is True:
                    skill_key = skill_keys[skill]
                    cursor.execute(
                        """
                        INSERT INTO fact_job_skills (job_key, skill_key)
                        VALUES (%s, %s)
                        ON CONFLICT (job_key, skill_key) DO NOTHING;
                        """,
                        (job_key, skill_key)
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
