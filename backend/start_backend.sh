# ============================================================================
#  start_backend.sh —— 一键启动后端(FastAPI + 建表 + 种子)
#  用法: bash start_backend.sh   (在 backend/ 目录)
# ============================================================================
set -e
cd "$(dirname "$0")"

echo "==> 安装依赖"
pip install -r requirements.txt -q

echo "==> 建表 + 种子"
python -m app.db.seed

echo "==> 启动 FastAPI (http://localhost:8000)"
uvicorn app.main:app --reload --port 8000
