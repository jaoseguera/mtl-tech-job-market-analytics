Commands:

python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python scripts/extract_jobs.py
python .\scripts\transform_jobs.py

# Database Export
docker exec -t mti820_postgres pg_dump -U admin -d job_market_dw > postgres/backup.sql

# Database Import
docker exec -i mti820_postgres psql -U admin -d job_market_dw < postgres/backup.sql