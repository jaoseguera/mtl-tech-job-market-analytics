import os
import re
import glob
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import requests

# Load config and DB parameters
sys_path = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.append(sys_path)
from config import SKILLS

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

CACHE_PATH = "data/scraped_descriptions.csv"

# ------------------------------------------------------------------------------
# 1. Scraper and Caching logic
# ------------------------------------------------------------------------------
def scrape_full_description(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            return None
        soup = BeautifulSoup(response.content, "html.parser")
        job_body = soup.find(class_="adp-body") or soup.find(class_="ui-foreign-click-description")
        return job_body.get_text(separator="\n", strip=True) if job_body else None
    except Exception:
        return None

def fetch_and_cache_descriptions(df):
    os.makedirs("data", exist_ok=True)
    scraped_cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            cache_df = pd.read_csv(CACHE_PATH)
            cache_df["adzuna_id"] = cache_df["adzuna_id"].astype(str)
            scraped_cache = dict(zip(cache_df["adzuna_id"], cache_df["full_description"]))
            print(f"Loaded {len(scraped_cache)} cached full descriptions.")
        except Exception as e:
            print(f"Error loading cache: {e}")
            
    df["adzuna_id"] = df["adzuna_id"].astype(str)
    unique_jobs = df[["adzuna_id", "redirect_url"]].drop_duplicates()
    to_scrape = unique_jobs[
        (~unique_jobs["adzuna_id"].isin(scraped_cache)) & 
        (unique_jobs["redirect_url"].notna()) & 
        (unique_jobs["redirect_url"] != "")
    ]
    
    total_to_scrape = len(to_scrape)
    if total_to_scrape > 0:
        print(f"Historical Processor: Found {total_to_scrape} uncached historical job(s) to scrape.")
        scraped_count = 0
        failed_count = 0
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {
                executor.submit(scrape_full_description, row["redirect_url"]): row["adzuna_id"] 
                for _, row in to_scrape.iterrows()
            }
            for future in as_completed(futures):
                adzuna_id = futures[future]
                try:
                    full_desc = future.result()
                    if full_desc:
                        scraped_cache[adzuna_id] = full_desc
                        scraped_count += 1
                    else:
                        failed_count += 1
                except Exception:
                    failed_count += 1
                
                total_processed = scraped_count + failed_count
                if total_processed % 20 == 0 or total_processed == total_to_scrape:
                    print(f"Progress: {total_processed}/{total_to_scrape} processed ({scraped_count} success)")
                    cache_df = pd.DataFrame(list(scraped_cache.items()), columns=["adzuna_id", "full_description"])
                    cache_df.to_csv(CACHE_PATH, index=False)
                    
        cache_df = pd.DataFrame(list(scraped_cache.items()), columns=["adzuna_id", "full_description"])
        cache_df.to_csv(CACHE_PATH, index=False)
    else:
        print("All historical jobs are already cached locally!")
    return scraped_cache

# ------------------------------------------------------------------------------
# 2. Classification Heuristics
# ------------------------------------------------------------------------------
def classify_language(description):
    text = str(description).lower()
    en_stops = ["the", "with", "from", "this", "your", "requirements", "responsibilities"]
    fr_stops = ["les", "dans", "avec", "pour", "vous", "requis", "responsabilités"]
    
    en_count = sum(1 for stop in en_stops if re.search(rf"\b{re.escape(stop)}\b", text))
    fr_count = sum(1 for stop in fr_stops if re.search(rf"\b{re.escape(stop)}\b", text))
    
    bilingual_patterns = [r"\bbilingue\b", r"\bbilinguisme\b", r"\bbilingual\b"]
    is_bilingual_mentioned = any(re.search(pat, text) for pat in bilingual_patterns)
    
    if (en_count >= 3 and fr_count >= 3) or is_bilingual_mentioned:
        return "bilingual"
    elif fr_count > en_count:
        return "french"
    else:
        return "english"

def classify_experience(description):
    text = str(description).lower()
    jr_patterns = [
        r"\bjunior\b", r"\bdébutant\b", r"\bentry[- ]level\b", r"\bsans expérience\b",
        r"\b0[- ]2\s*(ans|years)\b", r"\b1[- ]2\s*(ans|years)\b", r"\b0\s*à\s*2\s*ans\b", r"\b1\s*à\s*2\s*ans\b"
    ]
    sr_patterns = [
        r"\bsenior\b", r"\bsénior\b", r"\blead\b", r"\bprincipal\b", r"\barchitecte\b", r"\barchitect\b",
        r"\bdirecteur\b", r"\bdirector\b", r"\b5\+?\s*(ans|years)\b", r"\b5\s*ans\s*et\s*plus\b"
    ]
    mid_patterns = [
        r"\bintermediate\b", r"\bintermédiaire\b", r"\b3\+?\s*(ans|years)\b", r"\b3\s*ans\b", r"\b3\s*à\s*5\s*ans\b"
    ]
    is_jr = any(re.search(pat, text) for pat in jr_patterns)
    is_sr = any(re.search(pat, text) for pat in sr_patterns)
    is_mid = any(re.search(pat, text) for pat in mid_patterns)
    
    if is_sr: return "senior"
    elif is_mid: return "intermediate"
    elif is_jr: return "junior"
    return "not_specified"

def classify_work_model(description):
    text = str(description).lower()
    remote_patterns = [r"\bremote\b", r"\btélétravail\s*à\s*100%\b", r"\btélétravail\s*complet\b", r"\bà\s*distance\b"]
    hybrid_patterns = [r"\bhybrid\b", r"\bhybride\b", r"\btélétravail\s*hybride\b", r"\b2\s*jours\s*au\s*bureau\b"]
    onsite_patterns = [r"\bon-site\b", r"\bsur\s*site\b", r"\bprésentiel\b", r"\bau\s*bureau\b"]
    
    if any(re.search(pat, text) for pat in hybrid_patterns): return "hybrid"
    elif any(re.search(pat, text) for pat in remote_patterns): return "remote"
    elif any(re.search(pat, text) for pat in onsite_patterns): return "on_site"
    return "not_specified"

def classify_neighborhood(location, lat, lon):
    loc_str = str(location).lower()
    if "saint-laurent" in loc_str: return "Saint-Laurent"
    elif "plateau" in loc_str or "mile end" in loc_str or "mile-end" in loc_str: return "Plateau Mont-Royal / Mile End"
    elif "centre-ville" in loc_str or "downtown" in loc_str or "ville-marie" in loc_str: return "Downtown / Ville-Marie"
    elif "laval" in loc_str: return "Laval"
    elif "longueuil" in loc_str: return "Longueuil"
    elif "westmount" in loc_str: return "Westmount"
    elif "brossard" in loc_str: return "Brossard"
    elif "verdun" in loc_str: return "Verdun"
    elif "anjou" in loc_str: return "Anjou"
    elif "lasalle" in loc_str: return "LaSalle"
    elif "mont-royal" in loc_str: return "Mont-Royal"
    
    if pd.notna(lat) and pd.notna(lon):
        if 45.49 <= lat <= 45.52 and -73.59 <= lon <= -73.54: return "Downtown / Ville-Marie"
        elif 45.51 <= lat <= 45.54 and -73.61 <= lon <= -73.57: return "Plateau Mont-Royal / Mile End"
        elif 45.48 <= lat <= 45.53 and -73.74 <= lon <= -73.67: return "Saint-Laurent"
    return "Montreal / Other" if "montreal" in loc_str or "montréal" in loc_str else "Not Specified"

def classify_sector(company):
    comp_str = str(company).lower()
    
    # 1. Finance / Banking
    fin_substrings = ["desjardins", "morgan stanley", "national bank", "banque nationale", "rbc", "bmo", "scotia", "intact", "sun life", "cdpq", "moneris", "fundica", "wtw", "wealthsimple", "manulife", "ia financial"]
    fin_exact = [r"\btd\b"]
    
    if any(s in comp_str for s in fin_substrings) or any(re.search(pat, comp_str) for pat in fin_exact):
        return "Finance / Banking"
        
    # 2. IT Consulting / Services
    consult_substrings = ["cgi", "alithya", "accenture", "cognizant", "tata", "deloitte", "pwc", "kpmg", "lgs", "adviso", "expleo", "adga", "valtech", "s3 technologies", "astek", "pomerol", "alphanumeric systems", "fivesky", "indigo consulting", "era inc", "milan", "infotek", "procom", "teksystems", "amaris"]
    consult_exact = [r"\bey\b"]
    
    if any(s in comp_str for s in consult_substrings) or any(re.search(pat, comp_str) for pat in consult_exact):
        return "IT Consulting / Services"
        
    # 3. Gaming / Entertainment
    gaming_substrings = ["ubisoft", "electronic arts", "eidos", "behaviour", "gameloft", "ludia", "square enix", "people can fly", "virtuos", "ticketmaster", "unity", "epic games", "warner bros"]
    gaming_exact = [r"\bea\b"]
    
    if any(s in comp_str for s in gaming_substrings) or any(re.search(pat, comp_str) for pat in gaming_exact):
        return "Gaming / Entertainment"
        
    # 4. Telecom / Hardware
    telecom_substrings = ["ericsson", "bell", "rogers", "telus", "videotron", "sogetel", "bellatrx", "cogeco", "quebecor"]
    
    if any(s in comp_str for s in telecom_substrings):
        return "Telecom / Hardware"
        
    # 5. Aerospace
    aero_substrings = ["bombardier", "pratt", "aerospace", "bell flight", "l3harris", "harris geospatial", "altitude aerospace", "rtx"]
    aero_exact = [r"\bcae\b"]
    
    if any(s in comp_str for s in aero_substrings) or any(re.search(pat, comp_str) for pat in aero_exact):
        return "Aerospace"
        
    # 6. Software / SaaS
    software_substrings = ["coveo", "canonical", "maintainx", "lyft", "newforma", "secureops", "quadbridge", "confluent", "snowflake", "salesforce", "shopify", "optimyze", "atlassian", "hilo tech", "loc software", "safe fleet"]
    software_exact = [r"\bmeta\b", r"\baws\b", r"\bapple\b", r"\bgoogle\b", r"\bamazon\b", r"\bjira\b", r"\bslack\b", r"\bzoom\b"]
    
    if any(s in comp_str for s in software_substrings) or any(re.search(pat, comp_str) for pat in software_exact):
        return "Software / SaaS"
        
    # 7. Staffing & Recruiting
    staffing_substrings = ["manpower", "bedard", "randstad", "adecco", "robert half", "staffing", "grizzlytrek", "1840 staffing", "recruitment"]
    
    if any(s in comp_str for s in staffing_substrings):
        return "Staffing & Recruiting"
        
    # 8. Retail / Commerce
    retail_substrings = ["reitmans", "browns shoes", "rw&co", "walmart", "costco", "canadian tire", "loblaw", "sobeys", "metro"]
    
    if any(s in comp_str for s in retail_substrings):
        return "Retail / Commerce"
        
    # 9. Manufacturing / Engineering
    mfg_substrings = ["annexair", "tornatech", "canam", "trévi", "g.n. johnston", "safe fleet", "ge vernova", "fives", "air liquide", "walter surface", "construction virtuelle", "simple solutions", "tarkett", "emballage", "innoplex", "gmining", "techo-bloc"]
    
    if any(s in comp_str for s in mfg_substrings):
        return "Manufacturing / Engineering"
        
    return "Other / Not Specified"


# ------------------------------------------------------------------------------
# 3. Master Processing of Historical and Current Raw CSVs
# ------------------------------------------------------------------------------
def process_all():
    print("Gathering all raw job postings...")
    files = glob.glob("data/history/jobs_raw_*.csv")
    if os.path.exists("data/jobs_raw.csv"):
        files.append("data/jobs_raw.csv")
    
    print(f"Found {len(files)} raw file(s) to compile.")
    
    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_csv(f))
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not dfs:
        print("No raw files found!")
        return
        
    master_df = pd.concat(dfs, ignore_index=True)
    print(f"Merged total records before deduplication: {len(master_df)}")
    
    columns_to_keep = [
        "title", "company.display_name", "location.display_name", "description",
        "salary_min", "salary_max", "created", "contract_time", "contract_type",
        "id", "redirect_url", "latitude", "longitude"
    ]
    
    # Filter and rename
    master_df = master_df[[col for col in columns_to_keep if col in master_df.columns]]
    
    rename_map = {
        "title": "job_title", "company.display_name": "company", "location.display_name": "location",
        "description": "description", "salary_min": "salary_min", "salary_max": "salary_max",
        "created": "created_date", "contract_time": "contract_time", "contract_type": "contract_type",
        "id": "adzuna_id", "redirect_url": "redirect_url", "latitude": "latitude", "longitude": "longitude"
    }
    master_df = master_df.rename(columns=rename_map)
    
    master_df = master_df.dropna(subset=["job_title", "description", "adzuna_id"])
    master_df["adzuna_id"] = master_df["adzuna_id"].astype(str)
    
    # Deduplicate early
    master_df = master_df.drop_duplicates(subset=["adzuna_id"])
    print(f"Unique historical postings to process: {len(master_df)}")
    
    # Get descriptions from cache/scraper
    scraped_cache = fetch_and_cache_descriptions(master_df)
    
    def get_full_description(row):
        jid = str(row["adzuna_id"])
        return scraped_cache.get(jid, row["description"])
        
    master_df["description"] = master_df.apply(get_full_description, axis=1)
    master_df = master_df.drop(columns=["redirect_url"])
    
    master_df["description"] = master_df["description"].str.replace("\n", " ").str.replace("\r", " ").str.strip().str.lower()
    master_df["job_title"] = master_df["job_title"].str.lower()
    
    master_df = master_df.drop_duplicates(subset=["job_title", "company", "description"])
    master_df["has_salary"] = master_df["salary_min"].notna() & master_df["salary_max"].notna()
    master_df["salary_avg"] = (master_df["salary_min"] + master_df["salary_max"]) / 2
    
    # Apply classifications
    print("Classifying historical postings across all 5 dimensions...")
    master_df["language"] = master_df["description"].apply(classify_language)
    master_df["experience_level"] = master_df["description"].apply(classify_experience)
    master_df["work_model"] = master_df["description"].apply(classify_work_model)
    master_df["company_sector"] = master_df["company"].apply(classify_sector)
    master_df["neighborhood"] = master_df.apply(
        lambda row: classify_neighborhood(row["location"], row["latitude"], row["longitude"]), axis=1
    )
    
    # Skill matching
    print("Matching all 26 technical skills...")
    for skill in SKILLS:
        pattern = rf"\b{re.escape(skill)}\b"
        master_df[skill] = master_df["description"].str.contains(pattern, case=False, na=False, regex=True)
        
    # Write master clean dataset
    master_df.to_csv("data/jobs_clean.csv", index=False)
    print(f"Master dataset written with {len(master_df)} rows to data/jobs_clean.csv")
    
    # ------------------------------------------------------------------------------
    # 4. Sync with PostgreSQL (Upsert updates all new dimensions)
    # ------------------------------------------------------------------------------
    print("\nSyncing master dataset into PostgreSQL...")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cursor = conn.cursor()
    
    try:
        # Pre-feed dim_skills
        skill_keys = {}
        for skill in SKILLS:
            cursor.execute(
                "INSERT INTO dim_skills (skill_name) VALUES (%s) ON CONFLICT (skill_name) DO UPDATE SET skill_name = EXCLUDED.skill_name RETURNING skill_key;",
                (skill,)
            )
            skill_keys[skill] = cursor.fetchone()[0]
            
        seen_dates = set()
        company_keys = {}
        location_keys = {}
        contract_keys = {}
        
        rows_with_id = []
        
        print("Resolving dimensions and preparing fact rows...")
        for _, row in master_df.iterrows():
            # Date
            date_obj = pd.to_datetime(row['created_date'])
            date_key = int(date_obj.strftime("%Y%m%d"))
            if date_key not in seen_dates:
                cursor.execute(
                    "INSERT INTO dim_date (date_key, full_date, year, month, month_name, day, quarter, day_of_week, day_of_week_name) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (date_key) DO NOTHING;",
                    (date_key, date_obj.date(), date_obj.year, date_obj.month, date_obj.strftime("%B"), date_obj.day, (date_obj.month - 1) // 3 + 1, date_obj.isoweekday(), date_obj.strftime("%A"))
                )
                seen_dates.add(date_key)
                
            # Company
            company_name = str(row['company']).strip() if pd.notna(row['company']) else "Unknown"
            company_sector = str(row['company_sector']).strip() if pd.notna(row['company_sector']) else "not_specified"
            if company_name not in company_keys:
                cursor.execute(
                    "INSERT INTO dim_company (company_name, company_sector) VALUES (%s, %s) ON CONFLICT (company_name) DO UPDATE SET company_sector = EXCLUDED.company_sector RETURNING company_key;",
                    (company_name, company_sector)
                )
                company_keys[company_name] = cursor.fetchone()[0]
            company_key = company_keys[company_name]
            
            # Location
            location_name = str(row['location']).strip() if pd.notna(row['location']) else "Montreal"
            if location_name not in location_keys:
                cursor.execute(
                    "INSERT INTO dim_location (location_name) VALUES (%s) ON CONFLICT (location_name) DO UPDATE SET location_name = EXCLUDED.location_name RETURNING location_key;",
                    (location_name,)
                )
                location_keys[location_name] = cursor.fetchone()[0]
            location_key = location_keys[location_name]
            
            # Contract
            contract_time = str(row['contract_time']).strip() if pd.notna(row['contract_time']) else "unknown"
            contract_type = str(row['contract_type']).strip() if pd.notna(row['contract_type']) else "unknown"
            contract_combo = (contract_time, contract_type)
            if contract_combo not in contract_keys:
                cursor.execute(
                    "INSERT INTO dim_contract (contract_time, contract_type) VALUES (%s, %s) ON CONFLICT (contract_time, contract_type) DO UPDATE SET contract_time = EXCLUDED.contract_time RETURNING contract_key;",
                    contract_combo
                )
                contract_keys[contract_combo] = cursor.fetchone()[0]
            contract_key = contract_keys[contract_combo]
            
            # Fact preparation
            adzuna_id = str(row['adzuna_id']).strip()
            salary_min = float(row['salary_min']) if pd.notna(row['salary_min']) else None
            salary_max = float(row['salary_max']) if pd.notna(row['salary_max']) else None
            salary_avg = float(row['salary_avg']) if pd.notna(row['salary_avg']) else None
            has_salary = bool(row['has_salary'])
            matched_skills = [skill for skill in SKILLS if bool(row[skill])]
            
            language = str(row['language']).strip()
            experience_level = str(row['experience_level']).strip()
            work_model = str(row['work_model']).strip()
            latitude = float(row['latitude']) if pd.notna(row['latitude']) else None
            longitude = float(row['longitude']) if pd.notna(row['longitude']) else None
            neighborhood = str(row['neighborhood']).strip()
            
            fact_row = (
                adzuna_id, row['job_title'], row['description'], company_key, location_key,
                date_key, contract_key, salary_min, salary_max, salary_avg, has_salary,
                language, experience_level, work_model, latitude, longitude, neighborhood
            )
            rows_with_id.append((fact_row, matched_skills))
            
        print("Executing PostgreSQL upserts...")
        from psycopg2.extras import execute_values
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
        
        job_skill_rows = []
        for fact_row, matched_skills in rows_with_id:
            job_key = job_key_by_adzuna_id.get(fact_row[0])
            if job_key:
                job_skill_rows.extend((job_key, skill_keys[skill]) for skill in matched_skills)
                
        if job_skill_rows:
            execute_values(
                cursor,
                "INSERT INTO fact_job_skills (job_key, skill_key) VALUES %s ON CONFLICT (job_key, skill_key) DO NOTHING;",
                job_skill_rows
            )
            
        conn.commit()
        print("\n==================================================")
        print("MASTER HISTORICAL SYNC COMPLETE!")
        print(f"Total Unique Database Listings Synced: {len(job_key_by_adzuna_id)}")
        print("==================================================")
        
    except Exception as e:
        conn.rollback()
        print(f"Error during master historical loading: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    process_all()
