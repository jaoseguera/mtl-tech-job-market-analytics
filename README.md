Commands:

python -m venv venv
venv\Scripts\activate
pip install requests pandas python-dotenv
pip install --upgrade pip
python scripts/extract_jobs.py
python .\scripts\transform_jobs.py