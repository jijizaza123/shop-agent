# 评测报告端点 (real + mock 两份)
import os
import json
from fastapi import APIRouter, HTTPException

router = APIRouter()
EVALS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evals")
REPORT_REAL = os.path.join(EVALS_DIR, "report.json")
REPORT_MOCK = os.path.join(EVALS_DIR, "report.mock.json")


def _load(path: str, hint: str):
    if not os.path.exists(path):
        raise HTTPException(404, f"评测报告不存在, 先跑 {hint}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/evals/report")
def get_report():
    """real 报告(打 Agnes, 会受限流影响)。"""
    return _load(REPORT_REAL, "python -m evals.runner --real")


@router.get("/evals/report/mock")
def get_report_mock():
    """mock 报告(确定性, 可复现, 测工具/降级链路)。简历用这份。"""
    return _load(REPORT_MOCK, "python -m evals.runner --mock")
