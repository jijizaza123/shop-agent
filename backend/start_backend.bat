@echo off
cd /d %~dp0
echo ==^> installing deps
pip install -r requirements.txt -q
echo ==^> seed
python -m app.db.seed
echo ==^> starting FastAPI on :8000
uvicorn app.main:app --reload --port 8000
