Commands:

python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python scripts/extract_jobs.py
python .\scripts\transform_jobs.py