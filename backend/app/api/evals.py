# 评测报告端点
import os
import json
from fastapi import APIRouter, HTTPException

router = APIRouter()
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evals", "report.json")


@router.get("/evals/report")
def get_report():
    if not os.path.exists(REPORT_PATH):
        raise HTTPException(404, "评测报告不存在, 先跑 python -m evals.runner")
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
