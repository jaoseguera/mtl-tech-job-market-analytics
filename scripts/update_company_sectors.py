import os
import psycopg2
import re
import sys
from dotenv import load_dotenv

# Ensure standard output supports UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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

def main():
    print("Connecting to the database...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"Database connection error: {e}")
        sys.exit(1)

    print("Fetching companies...")
    try:
        cursor.execute("SELECT company_key, company_name, company_sector FROM dim_company;")
        companies = cursor.fetchall()
        print(f"Found {len(companies)} companies in dim_company.")
    except Exception as e:
        print(f"Error fetching companies: {e}")
        cursor.close()
        conn.close()
        sys.exit(1)

    updated_count = 0
    unchanged_count = 0

    print("Re-classifying and updating companies...")
    for key, name, old_sector in companies:
        new_sector = classify_sector(name)
        if new_sector != old_sector:
            try:
                cursor.execute(
                    "UPDATE dim_company SET company_sector = %s WHERE company_key = %s;",
                    (new_sector, key)
                )
                updated_count += 1
                print(f"Updated: '{name}' [{old_sector} -> {new_sector}]")
            except Exception as e:
                print(f"Error updating company '{name}': {e}")
        else:
            unchanged_count += 1

    try:
        conn.commit()
        print("\n==================================================")
        print("DATABASE SYNCHRONIZATION COMPLETED SUCCESSFULLY!")
        print(f"Total Companies processed: {len(companies)}")
        print(f"Sectors updated: {updated_count}")
        print(f"Sectors unchanged: {unchanged_count}")
        print("==================================================")
    except Exception as e:
        conn.rollback()
        print(f"Error committing transaction: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
