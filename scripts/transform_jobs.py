import re
import pandas as pd
from datetime import datetime
import sys
import os
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import SKILLS

# ------------------------------------------------------------------------------
# Core Scraper and Caching Logic
# ------------------------------------------------------------------------------
CACHE_PATH = "data/scraped_descriptions.csv"

def scrape_full_description(url):
    """
    Scrapes the full job description from an Adzuna redirect URL.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if not response.ok:
            return None
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Try to find class "adp-body" (main content)
        job_body = soup.find(class_="adp-body")
        if job_body:
            return job_body.get_text(separator="\n", strip=True)
            
        # Fallback to class "ui-foreign-click-description"
        job_body = soup.find(class_="ui-foreign-click-description")
        if job_body:
            return job_body.get_text(separator="\n", strip=True)
            
        return None
    except Exception:
        return None

def fetch_and_cache_descriptions(df):
    """
    Identifies jobs without cached full descriptions, scrapes them concurrently,
    and updates the persistent cache.
    """
    # Create data dir if not exists
    os.makedirs("data", exist_ok=True)
    
    # 1. Load existing cache
    if os.path.exists(CACHE_PATH):
        try:
            cache_df = pd.read_csv(CACHE_PATH)
            # Ensure keys are treated as strings
            cache_df["adzuna_id"] = cache_df["adzuna_id"].astype(str)
            scraped_cache = dict(zip(cache_df["adzuna_id"], cache_df["full_description"]))
            print(f"Loaded {len(scraped_cache)} cached full descriptions.")
        except Exception as e:
            print(f"Error loading cache file: {e}. Starting with an empty cache.")
            scraped_cache = {}
    else:
        scraped_cache = {}
        print("No existing scraper cache found. Creating a new one.")

    # 2. Identify jobs that need to be scraped
    df["adzuna_id"] = df["adzuna_id"].astype(str)
    unique_jobs = df[["adzuna_id", "redirect_url"]].drop_duplicates()
    
    to_scrape = unique_jobs[
        (~unique_jobs["adzuna_id"].isin(scraped_cache)) & 
        (unique_jobs["redirect_url"].notna()) & 
        (unique_jobs["redirect_url"] != "")
    ]
    
    total_to_scrape = len(to_scrape)
    if total_to_scrape > 0:
        print(f"Scraper: Found {total_to_scrape} new job(s) to scrape for full descriptions.")
        print("Starting concurrent scraping (this may take a few minutes on the first run)...")
        
        scraped_count = 0
        failed_count = 0
        
        # Scrape concurrently using ThreadPoolExecutor
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
                    print(f"Progress: {total_processed}/{total_to_scrape} processed ({scraped_count} success, {failed_count} failed)")
                    # Periodically save cache to disk
                    cache_df = pd.DataFrame(list(scraped_cache.items()), columns=["adzuna_id", "full_description"])
                    cache_df.to_csv(CACHE_PATH, index=False)
                    
        # Final cache write
        cache_df = pd.DataFrame(list(scraped_cache.items()), columns=["adzuna_id", "full_description"])
        cache_df.to_csv(CACHE_PATH, index=False)
        print(f"Scraping completed. Cache now contains {len(scraped_cache)} descriptions.")
    else:
        print("All jobs are already present in the scraper cache. No web scraping required!")
        
    return scraped_cache

# ------------------------------------------------------------------------------
# ETL Transformation Pipeline
# ------------------------------------------------------------------------------

df = pd.read_csv("data/jobs_raw.csv")

columns_to_keep = [
    "title",
    "company.display_name",
    "location.display_name",
    "description",
    "salary_min",
    "salary_max",
    "created",
    "contract_time",
    "contract_type",
    "id",
    "redirect_url",
    "latitude",
    "longitude"
]

missing_columns = [col for col in columns_to_keep if col not in df.columns]
if missing_columns:
    raise SystemExit(
        f"Missing columns in jobs_raw.csv: {missing_columns}. "
        "API Adzuna's scheme may have changed."
    )

df = df[columns_to_keep]

df.columns = [
    "job_title",
    "company",
    "location",
    "description",  # Truncated description
    "salary_min",
    "salary_max",
    "created_date",
    "contract_time",
    "contract_type",
    "adzuna_id",
    "redirect_url",
    "latitude",
    "longitude"
]

df = df.dropna(subset=["job_title", "description"])

# --- Caching and Full Description Merging ---
scraped_cache = fetch_and_cache_descriptions(df)

# Replace truncated descriptions with full ones from cache if available
def get_full_description(row):
    jid = str(row["adzuna_id"])
    if jid in scraped_cache:
        return scraped_cache[jid]
    return row["description"]  # fallback to API description if scrape failed or was skipped

df["description"] = df.apply(get_full_description, axis=1)

# Drop redirect_url column before clean saving
df = df.drop(columns=["redirect_url"])

# Format description text (remove excessive whitespaces)
df["description"] = (
    df["description"]
    .str.replace("\n", " ")
    .str.replace("\r", " ")
    .str.strip()
)

df["description"] = df["description"].str.lower()
df["job_title"] = df["job_title"].str.lower()

df = df.drop_duplicates(subset=["job_title", "company", "description"])

df["has_salary"] = df["salary_min"].notna() & df["salary_max"].notna()

df["salary_avg"] = (
    df["salary_min"] + df["salary_max"]
) / 2

# ------------------------------------------------------------------------------
# Classification Heuristics for the 5 New Dimensions
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
    
    if is_sr:
        return "senior"
    elif is_mid:
        return "intermediate"
    elif is_jr:
        return "junior"
    else:
        return "not_specified"

def classify_work_model(description):
    text = str(description).lower()
    remote_patterns = [
        r"\bremote\b", r"\btélétravail\s*à\s*100%\b", r"\btélétravail\s*complet\b",
        r"\bwork\s*from\s*home\s*full[- ]time\b", r"\bà\s*distance\b"
    ]
    hybrid_patterns = [
        r"\bhybrid\b", r"\bhybride\b", r"\bwork\s*from\s*home\s*part[- ]time\b",
        r"\btélétravail\s*hybride\b", r"\b2\s*(jours|days)\s*au\s*bureau\b", r"\b3\s*(jours|days)\s*au\s*bureau\b"
    ]
    onsite_patterns = [
        r"\bon-site\b", r"\bsur\s*site\b", r"\bprésentiel\b", r"\bau\s*bureau\b"
    ]
    
    is_remote = any(re.search(pat, text) for pat in remote_patterns)
    is_hybrid = any(re.search(pat, text) for pat in hybrid_patterns)
    is_onsite = any(re.search(pat, text) for pat in onsite_patterns)
    
    if is_hybrid:
        return "hybrid"
    elif is_remote:
        return "remote"
    elif is_onsite:
        return "on_site"
    else:
        return "not_specified"

def classify_neighborhood(location, lat, lon):
    loc_str = str(location).lower()
    if "saint-laurent" in loc_str:
        return "Saint-Laurent"
    elif "plateau" in loc_str or "mile end" in loc_str or "mile-end" in loc_str:
        return "Plateau Mont-Royal / Mile End"
    elif "centre-ville" in loc_str or "downtown" in loc_str or "ville-marie" in loc_str:
        return "Downtown / Ville-Marie"
    elif "laval" in loc_str:
        return "Laval"
    elif "longueuil" in loc_str:
        return "Longueuil"
    elif "westmount" in loc_str:
        return "Westmount"
    elif "brossard" in loc_str:
        return "Brossard"
    elif "verdun" in loc_str or "nun's island" in loc_str or "île des soeurs" in loc_str:
        return "Verdun"
    elif "anjou" in loc_str:
        return "Anjou"
    elif "lasalle" in loc_str:
        return "LaSalle"
    elif "mont-royal" in loc_str or "mount royal" in loc_str:
        return "Mont-Royal"
        
    if pd.notna(lat) and pd.notna(lon):
        if 45.49 <= lat <= 45.52 and -73.59 <= lon <= -73.54:
            return "Downtown / Ville-Marie"
        elif 45.51 <= lat <= 45.54 and -73.61 <= lon <= -73.57:
            return "Plateau Mont-Royal / Mile End"
        elif 45.48 <= lat <= 45.53 and -73.74 <= lon <= -73.67:
            return "Saint-Laurent"
            
    if "montreal" in loc_str or "montréal" in loc_str:
        return "Montreal / Other"
    return "Not Specified"

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

# Extract extended analytical dimensions
print("Extracting extended analytical dimensions...")
df["language"] = df["description"].apply(classify_language)
df["experience_level"] = df["description"].apply(classify_experience)
df["work_model"] = df["description"].apply(classify_work_model)
df["company_sector"] = df["company"].apply(classify_sector)
df["neighborhood"] = df.apply(lambda row: classify_neighborhood(row["location"], row["latitude"], row["longitude"]), axis=1)

# Apply technology skill patterns on the full text
for skill in SKILLS:
    pattern = rf"\b{re.escape(skill)}\b"
    df[skill] = df["description"].str.contains(
        pattern,
        case=False,
        na=False,
        regex=True
    )

df.to_csv("data/jobs_clean.csv", index=False)
print(f"Successfully cleaned and saved {len(df)} jobs to data/jobs_clean.csv")