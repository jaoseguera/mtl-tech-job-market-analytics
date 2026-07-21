import re
import pandas as pd

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
    "id"
]

missing_columns = [col for col in columns_to_keep if col not in df.columns]
if missing_columns:
    raise SystemExit(
        f"Colonnes manquantes dans jobs_raw.csv: {missing_columns}. "
        "Le schéma de l'API Adzuna a peut-être changé."
    )

df = df[columns_to_keep]

df.columns = [
    "job_title",
    "company",
    "location",
    "description",
    "salary_min",
    "salary_max",
    "created_date",
    "contract_time",
    "contract_type",
    "adzuna_id"
]

df = df.dropna(subset=["job_title", "description"])

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

skills = [
    "python",
    "sql",
    "aws",
    "azure",
    "docker",
    "kubernetes",
    "java",
    "react",
    "power bi",
    "tableau",
    "spark"
]

for skill in skills:
    pattern = rf"\b{re.escape(skill)}\b"
    df[skill] = df["description"].str.contains(
        pattern,
        case=False,
        na=False,
        regex=True
    )

df.to_csv("data/jobs_clean.csv", index=False)