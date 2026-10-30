# ============================================================================
#  Agent 编排层 —— LangGraph 状态图
#  节点: plan -> router -> (router | fallback) -> answer
#  降级: 工具连续失败 3 次进 fallback 节点
#  state: 用 Annotated 累加器保留 messages, 节点返回局部更新
# ============================================================================
import json
import time
import uuid
from typing import TypedDict, Annotated

from operator import add
from langgraph.graph import StateGraph, END

from app.llm_client import llm, _TOOL_IMPLS
from app.agent import tools as shop_tools
from app.agent.prompts import SYSTEM_PROMPT


class AgentState(TypedDict, total=False):
    """LangGraph 状态。
    Annotated[..., add] = 累加器(节点返回的列表会被合并, 不覆盖)。
    其余字段默认覆盖语义(节点返回就更新, 不返回就保留)。"""
    session_id: str
    user_input: str
    messages: Annotated[list, add]      # 累加: 多轮对话不丢
    plan: Annotated[list, add]
    tool_results: dict                   # 覆盖语义(每个节点更新自己的部分)
    error_count: int
    fallback_used: bool
    answer: str
    trace: Annotated[list, add]
    tokens_in: int
    tokens_out: int
    latency_ms: int
    _route: str                          # 内部路由标记


def _init_state(user_input: str) -> dict:
    session_id = str(uuid.uuid4())
    return {
        "session_id": session_id,
        "user_input": user_input,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "plan": [],
        "tool_results": {},
        "error_count": 0,
        "fallback_used": False,
        "answer": "",
        "trace": [],
        "tokens_in": 0,
        "tokens_out": 0,
        "latency_ms": 0,
        "_route": "answer",
    }


# ============================================================================
#  节点定义 —— 每个节点只返回「它改的字段」, 别的字段由 LangGraph 保留
# ============================================================================

def plan_node(state: dict) -> dict:
    """规划节点: 当前先透传(留接口给 Plan-and-Execute)。"""
    t0 = time.perf_counter()
    return {"trace": [{"node": "plan", "latency_ms": int((time.perf_counter()-t0)*1000)}]}


def router_node(state: dict) -> dict:
    """路由节点: 调 LLM(带工具), 决定是调工具还是直接答。
    返回: messages(新增的 assistant/tool 消息) + trace + tokens + error_count
          + fallback_used + _route + (answer 如果模型直接答了)
    """
    t0 = time.perf_counter()
    new_messages = []
    error_count = state.get("error_count", 0)
    fallback_used = state.get("fallback_used", False)
    tool_results = dict(state.get("tool_results", {}))   # 浅拷贝, 不污染原 state
    tokens_in = state.get("tokens_in", 0)
    tokens_out = state.get("tokens_out", 0)

    resp = llm.chat(state["messages"], tools=shop_tools.TOOL_SCHEMAS)
    msg = resp.choices[0].message
    if resp.usage:
        tokens_in += resp.usage.prompt_tokens
        tokens_out += resp.usage.completion_tokens

    if not msg.tool_calls:
        # 模型直接给答案
        new_messages.append({"role": "assistant", "content": msg.content or ""})
        return {
            "messages": new_messages,
            "answer": msg.content or "",
            "trace": [{"node": "router", "latency_ms": int((time.perf_counter()-t0)*1000)}],
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "error_count": error_count, "fallback_used": fallback_used,
            "_route": "answer",
        }

    # 模型要调工具
    for call in msg.tool_calls:
        fn_name = call.function.name
        args = json.loads(call.function.arguments) if call.function.arguments else {}
        impl = _TOOL_IMPLS.get(fn_name)
        if impl is None:
            result = f"(未知工具 {fn_name})"
            error_count += 1
            fallback_used = True
        else:
            try:
                result = impl(**args)
                tool_results[fn_name] = result
            except Exception as e:
                result = f"(工具 {fn_name} 执行失败: {e})"
                error_count += 1
                fallback_used = True
        new_messages.append({"role": "assistant", "content": None, "tool_calls": msg.tool_calls})
        new_messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

    if error_count >= 3:
        route = "fallback"
    else:
        route = "router"
    return {
        "messages": new_messages,
        "tool_results": tool_results,
        "error_count": error_count,
        "fallback_used": fallback_used,
        "trace": [{"node": "router", "latency_ms": int((time.perf_counter()-t0)*1000),
                    "tools_called": [c.function.name for c in msg.tool_calls]}],
        "tokens_in": tokens_in, "tokens_out": tokens_out,
        "_route": route,
    }


def fallback_node(state: dict) -> dict:
    """降级节点: 工具连续失败, 给友好提示 + 上次缓存。"""
    t0 = time.perf_counter()
    cached = json.dumps(state.get("tool_results", {}), ensure_ascii=False) if state.get("tool_results") else "(无缓存)"
    sys_note = {"role": "system",
                 "content": f"[系统] 工具连续失败, 请基于以下缓存结果给用户降级回复:\n{cached}"}
    resp = llm.chat(state["messages"] + [sys_note])
    tokens_in = state.get("tokens_in", 0)
    tokens_out = state.get("tokens_out", 0)
    if resp.usage:
        tokens_in += resp.usage.prompt_tokens
        tokens_out += resp.usage.completion_tokens
    return {
        "messages": [sys_note, {"role": "assistant", "content": resp.choices[0].message.content or ""}],
        "answer": resp.choices[0].message.content or "(自动购物暂不可用, 请浏览商品列表)",
        "fallback_used": True,
        "trace": [{"node": "fallback", "latency_ms": int((time.perf_counter()-t0)*1000)}],
        "tokens_in": tokens_in, "tokens_out": tokens_out,
        "_route": "answer",
    }


def answer_node(state: dict) -> dict:
    """答案节点: 记录总耗时。"""
    t0 = state.get("_t0", time.perf_counter())
    return {
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "trace": [{"node": "answer", "fallback_used": state.get("fallback_used", False)}],
    }


def _route_decision(state: dict) -> str:
    return state.get("_route", "answer")


# ============================================================================
#  构建图
# ============================================================================
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", plan_node)
    g.add_node("router", router_node)
    g.add_node("fallback", fallback_node)
    g.add_node("answer", answer_node)
    g.set_entry_point("plan")
    g.add_edge("plan", "router")
    g.add_conditional_edges("router", _route_decision,
                            {"router": "router", "fallback": "fallback", "answer": "answer"})
    g.add_edge("fallback", "answer")
    g.add_edge("answer", END)
    return g.compile()


def run_agent(user_input: str) -> dict:
    """对外唯一入口: 跑一次 Agent 对话, 返回完整 state。"""
    state = _init_state(user_input)
    state["_t0"] = time.perf_counter()
    graph = build_graph()
    return graph.invoke(state)


if __name__ == "__main":
    print("=== 自检: '5000 元入门剪辑电脑配单' ===")
    out = run_agent("帮我配一套 5000 元以内的入门剪辑电脑, 重点 CPU 和内存")
    print("答案:", out.get("answer"))
    print("工具缓存:", out.get("tool_results"))
    print("降级:", out.get("fallback_used"))
    print("trace:", out.get("trace"))
