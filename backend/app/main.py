# ============================================================================
#  app/main.py —— FastAPI 入口
#  路由: /products /orders /agent/chat /evals/report /traces
#  启动: uvicorn app.main:app --reload --port 8000
# ============================================================================
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import products, orders, agent, evals, traces

app = FastAPI(title="极客配单", version="0.1.0")

# 允许前端(默认 http://localhost:5173)跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(products.router, prefix="/api", tags=["products"])
app.include_router(orders.router, prefix="/api", tags=["orders"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(evals.router, prefix="/api", tags=["evals"])
app.include_router(traces.router, prefix="/api", tags=["traces"])


@app.get("/")
def root():
    return {"msg": "极客配单 API", "endpoints": [
        "GET /api/products", "GET /api/products/{id}", "GET /api/orders",
        "POST /api/agent/chat", "GET /api/evals/report", "GET /api/traces",
    ]}


@app.get("/health")
def health():
    return {"ok": True}
