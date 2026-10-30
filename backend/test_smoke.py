# 自检脚本: 验证 FastAPI 路由 + Agent 对话能跑通
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
print("=== 路由 ===")
for r in app.routes:
    if hasattr(r, "path"):
        print(" ", r.path, [m for m in getattr(r, "methods", []) or []])

print("\n=== 跑一次 Agent 对话 ===")
from app.agent.graph import run_agent
out = run_agent("5000 元入门剪辑电脑, 重点 CPU 和内存")
print("答案:", out.get("answer")[:200])
print("工具:", list(out.get("tool_results", {}).keys()))
print("降级:", out.get("fallback_used"))
print("trace:", out.get("trace"))
