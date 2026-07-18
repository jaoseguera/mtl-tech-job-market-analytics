import requests
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

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

if(os.path.exists("data/jobs_raw.csv")):
    os.remove("data/jobs_raw.csv")

page = 1
all_jobs = []
while page <= 50:
    url=f"https://api.adzuna.com/v1/api/jobs/ca/search/{page}"
    response = requests.get(url, params=params)

    if not response.ok:
        print(f"Error fetching data: {response.status_code}")
        print(f"Response content: {response.reason}")
        print(f"Response text: {response.text}")
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
final_df.to_csv("data/jobs_raw.csv", index=False)