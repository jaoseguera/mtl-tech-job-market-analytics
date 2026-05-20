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
    "contract_type"
]

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
    "contract_type"
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
    df[skill] = df["description"].str.contains(
        skill,
        case=False,
        na=False
    )

df.to_csv("data/jobs_clean.csv", index=False)