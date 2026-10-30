# ============================================================================
#  evals/runner.py —— Agent 评测: 跑 dataset.json 里所有 case, 输出 report.json
#  维度: 任务成功率 / 工具调用准确率 / Token 成本 / 延迟 / 降级率
#  跑法: python -m evals.runner  (在 backend/ 下)
# ============================================================================
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import run_agent

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset.json")
REPORT = os.path.join(HERE, "report.json")


def evaluate_one(case: dict) -> dict:
    """跑一个 case, 返回结构化结果。"""
    t0 = time.perf_counter()
    try:
        out = run_agent(case["input"])
        answer = out.get("answer", "")
        tools_called = list(out.get("tool_results", {}).keys())
        fallback = out.get("fallback_used", False)
        tokens_in = out.get("tokens_in", 0)
        tokens_out = out.get("tokens_out", 0)
        latency = out.get("latency_ms", int((time.perf_counter() - t0) * 1000))

        # 工具调用准确率: 期望的工具是否都调了
        expect_tools = case.get("expect_tools", [])
        tool_hit = sum(1 for t in expect_tools if t in tools_called)
        tool_acc = (tool_hit / len(expect_tools)) if expect_tools else 1.0

        # 答案关键词命中率
        kw = case.get("expect_answer_keywords", [])
        kw_hit = sum(1 for k in kw if k in answer)
        kw_acc = (kw_hit / len(kw)) if kw else 1.0

        success = (not fallback) and (tool_acc == 1.0 if expect_tools else True)
        return {
            "input": case["input"],
            "answer": answer,
            "tools_called": tools_called,
            "expect_tools": expect_tools,
            "tool_acc": round(tool_acc, 3),
            "kw_acc": round(kw_acc, 3),
            "fallback_used": fallback,
            "success": success,
            "tokens": tokens_in + tokens_out,
            "latency_ms": latency,
        }
    except Exception as e:
        return {
            "input": case["input"], "answer": f"(异常: {e})",
            "tools_called": [], "expect_tools": case.get("expect_tools", []),
            "tool_acc": 0.0, "kw_acc": 0.0, "fallback_used": True,
            "success": False, "tokens": 0,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error": str(e),
        }


def main() -> dict:
    with open(DATASET, "r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data["cases"]
    print(f"=== 评测 {len(cases)} 个 case ===\n")

    results = []
    for i, c in enumerate(cases, 1):
        r = evaluate_one(c)
        results.append(r)
        mark = "OK " if r["success"] else "FAIL"
        print(f"[{mark}] #{i:02d} {r['input'][:30]}")
        print(f"       工具 {r['tools_called']} 准确率 {r['tool_acc']} 延迟 {r['latency_ms']}ms token {r['tokens']}")
        if r.get("error"):
            print(f"       异常: {r['error']}")

    # 汇总
    n = len(results)
    success_rate = sum(1 for r in results if r["success"]) / n
    avg_tool_acc = sum(r["tool_acc"] for r in results) / n
    avg_kw_acc = sum(r["kw_acc"] for r in results) / n
    total_tokens = sum(r["tokens"] for r in results)
    avg_latency = sum(r["latency_ms"] for r in results) / n
    fallback_rate = sum(1 for r in results if r["fallback_used"]) / n

    report = {
        "total_cases": n,
        "success_rate": round(success_rate, 4),
        "avg_tool_acc": round(avg_tool_acc, 4),
        "avg_kw_acc": round(avg_kw_acc, 4),
        "total_tokens": total_tokens,
        "avg_latency_ms": round(avg_latency, 1),
        "fallback_rate": round(fallback_rate, 4),
        "results": results,
    }
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n=== 汇总 ===")
    print(f"任务成功率: {success_rate:.2%}")
    print(f"工具调用准确率: {avg_tool_acc:.2%}")
    print(f"答案关键词命中率: {avg_kw_acc:.2%}")
    print(f"降级率: {fallback_rate:.2%}")
    print(f"总 Token: {total_tokens}, 平均延迟: {avg_latency:.0f}ms")
    print(f"报告已写入: {REPORT}")
    return report


if __name__ == "__main__":
    main()
