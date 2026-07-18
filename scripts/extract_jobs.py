import requests
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

if not APP_ID or not APP_KEY:
    raise SystemExit(
        "ADZUNA_APP_ID et ADZUNA_APP_KEY doivent être définis dans .env"
    )

params = {
    "app_id": APP_ID,
    "app_key": APP_KEY,
    "results_per_page": 100,
    "where": "Montreal",
    "distance": 100,
    "content-type": "application/json",
    "category": "it-jobs",
    "sort_by": "date"
}

os.makedirs("data/history", exist_ok=True)
run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

page = 1
all_jobs = []
while page <= 50:
    url=f"https://api.adzuna.com/v1/api/jobs/ca/search/{page}"

    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(url, params=params)
        if response.ok:
            break
        if response.status_code not in RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES:
            print(f"Error fetching data: {response.status_code}")
            print(f"Response content: {response.reason}")
            print(f"Response text: {response.text}")
            break
        wait = 2 ** attempt
        print(f"Retryable error {response.status_code}, retry {attempt}/{MAX_RETRIES} in {wait}s...")
        time.sleep(wait)

    if not response.ok:
        break

    data = response.json()
    jobs = data["results"]

    if not jobs:
        break

    df = pd.json_normalize(jobs)
    all_jobs.append(df)

    print(f"Page {page} extracted with {len(jobs)} jobs.")
    page += 1

final_df = pd.concat(all_jobs, ignore_index=True)
final_df.to_csv(f"data/history/jobs_raw_{run_timestamp}.csv", index=False)
final_df.to_csv("data/jobs_raw.csv", index=False)