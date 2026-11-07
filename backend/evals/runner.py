# ============================================================================
#  evals/runner.py —— Agent 评测: 跑 dataset.json 里所有 case, 输出 report.json
#  维度: 任务成功率 / 工具调用准确率 / Token 成本 / 延迟 / 降级率
#  模式:
#    --mock  (默认)  确定性 MockLLM, 不依赖 Agnes, 永远可复现, 测工具/降级链路
#    --real          打真实 Agnes, 测自然语言理解/答案质量(会受限流影响)
#  跑法: python -m evals.runner --mock | --real   (在 backend/ 下)
# ============================================================================
import json
import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import run_agent

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset.json")
REPORT_MOCK = os.path.join(HERE, "report.mock.json")
REPORT_REAL = os.path.join(HERE, "report.json")


def evaluate_one(case: dict, mock: bool) -> dict:
    """跑一个 case, 返回结构化结果。
    mock=True 时用确定性 MockLLM(隔离外部依赖, 测工具/降级链路)。
    工具匹配: 命中 expect_tools 中任意一个即算"调用正确"(避免 1 个 case 要调多个工具的假阴性)。"""
    t0 = time.perf_counter()
    try:
        out = run_agent(case["input"], mock=mock)
        answer = out.get("answer", "")
        tools_called = list(out.get("tool_results", {}).keys())
        fallback = out.get("fallback_used", False)
        tokens_in = out.get("tokens_in", 0)
        tokens_out = out.get("tokens_out", 0)
        latency = out.get("latency_ms", int((time.perf_counter() - t0) * 1000))

        # 工具调用准确率: expect_tools 里任一命中即算 1.0, 一个都没命中算 0.0
        # (有工具调用但全错也按 0 算; 完全没该调工具的 case, 全对)
        expect_tools = case.get("expect_tools", [])
        if not expect_tools:
            tool_acc = 1.0
        else:
            hit = any(t in tools_called for t in expect_tools)
            tool_acc = 1.0 if hit else 0.0

        # 答案关键词命中率(模糊: 任一关键词命中即 1.0, 否则按比例)
        kw = case.get("expect_answer_keywords", [])
        if not kw:
            kw_acc = 1.0
        else:
            kw_hit = sum(1 for k in kw if k in answer)
            kw_acc = kw_hit / len(kw)

        success = (not fallback) and (tool_acc >= 0.5 if expect_tools else True)
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


def run_all(mock: bool) -> dict:
    with open(DATASET, "r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data["cases"]
    mode = "mock(确定性)" if mock else "real(Agnes)"
    print(f"=== 评测 {len(cases)} 个 case [{mode}] ===\n")

    results = []
    for i, c in enumerate(cases, 1):
        r = evaluate_one(c, mock=mock)
        results.append(r)
        mark = "OK " if r["success"] else "FAIL"
        print(f"[{mark}] #{i:02d} {r['input'][:30]}")
        print(f"       工具 {r['tools_called']} acc {r['tool_acc']} 延迟 {r['latency_ms']}ms token {r['tokens']}")
        if r.get("error"):
            print(f"       异常: {r['error']}")

    n = len(results)
    success_rate = sum(1 for r in results if r["success"]) / n
    avg_tool_acc = sum(r["tool_acc"] for r in results) / n
    avg_kw_acc = sum(r["kw_acc"] for r in results) / n
    total_tokens = sum(r["tokens"] for r in results)
    avg_latency = sum(r["latency_ms"] for r in results) / n
    fallback_rate = sum(1 for r in results if r["fallback_used"]) / n

    report = {
        "mode": "mock" if mock else "real",
        "total_cases": n,
        "success_rate": round(success_rate, 4),
        "avg_tool_acc": round(avg_tool_acc, 4),
        "avg_kw_acc": round(avg_kw_acc, 4),
        "total_tokens": total_tokens,
        "avg_latency_ms": round(avg_latency, 1),
        "fallback_rate": round(fallback_rate, 4),
        "results": results,
    }
    out_path = REPORT_MOCK if mock else REPORT_REAL
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n=== 汇总 [{mode}] ===")
    print(f"任务成功率: {success_rate:.2%}")
    print(f"工具调用准确率: {avg_tool_acc:.2%}")
    print(f"答案关键词命中率: {avg_kw_acc:.2%}")
    print(f"降级率: {fallback_rate:.2%}")
    print(f"总 Token: {total_tokens}, 平均延迟: {avg_latency:.0f}ms")
    print(f"报告已写入: {out_path}")
    return report


def main() -> dict:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="用确定性 MockLLM(默认)")
    parser.add_argument("--real", action="store_true", help="打真实 Agnes")
    args = parser.parse_args()
    # 默认 mock; 显式 --real 才走真实 LLM
    mock = not args.real
    return run_all(mock=mock)


if __name__ == "__main__":
    main()
