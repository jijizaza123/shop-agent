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
from app.agent.mock_llm import mock_llm


class AgentState(TypedDict, total=False):
    """LangGraph 状态。
    Annotated[..., add] = 累加器(节点返回的列表会被合并, 不覆盖)。
    其余字段默认覆盖语义(节点返回就更新, 不返回就保留)。"""
    session_id: str
    user_input: str
    user_key: str
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
    _t0: float                           # 总耗时起点(声明进 state, 供 answer 节点取, 修 undefinedms)
    _retry_count: int                   # 偷懒打回重跑次数(防无限循环)
    _llm_ms: int                        # 真实 LLM 往返耗时(区别于编排耗时, 可观测)


def _init_state(user_input: str, user_key: str = "user_demo",
                session_id: str = "") -> dict:
    from app.agent.memory import build_context
    if not session_id:
        session_id = str(uuid.uuid4())
    # 记忆块注入 system: 长期偏好 + 短期对话
    ctx = build_context(user_key, session_id)
    sys_parts = [SYSTEM_PROMPT]
    if ctx["preferences"]:
        sys_parts.append("[用户偏好] " + json.dumps(ctx["preferences"], ensure_ascii=False))
    if ctx["short_term"]:
        sys_parts.append("[最近对话] " + json.dumps(ctx["short_term"], ensure_ascii=False))
    system_text = "\n".join(sys_parts)
    return {
        "session_id": session_id,
        "user_input": user_input,
        "user_key": user_key,
        "messages": [
            {"role": "system", "content": system_text},
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
        "_t0": time.perf_counter(),
        "_retry_count": 0,
        "_llm_ms": 0,
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
    client = _active_llm()

    llm_t0 = time.perf_counter()
    resp = client.chat(state["messages"], tools=shop_tools.TOOL_SCHEMAS)
    llm_ms = int((time.perf_counter() - llm_t0) * 1000)          # 真实 LLM 往返
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
            "trace": [{"node": "router", "latency_ms": int((time.perf_counter()-t0)*1000),
                        "llm_ms": llm_ms}],
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "error_count": error_count, "fallback_used": fallback_used,
            "_llm_ms": state.get("_llm_ms", 0) + llm_ms,
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
                    "llm_ms": llm_ms,
                    "tools_called": [c.function.name for c in msg.tool_calls]}],
        "tokens_in": tokens_in, "tokens_out": tokens_out,
        "_llm_ms": state.get("_llm_ms", 0) + llm_ms,
        "_route": route,
    }


def fallback_node(state: dict) -> dict:
    """降级节点: 工具连续失败, 给友好提示 + 上次缓存。"""
    t0 = time.perf_counter()
    cached = json.dumps(state.get("tool_results", {}), ensure_ascii=False) if state.get("tool_results") else "(无缓存)"
    sys_note = {"role": "system",
                 "content": f"[系统] 工具连续失败, 请基于以下缓存结果给用户降级回复:\n{cached}"}
    resp = _active_llm().chat(state["messages"] + [sys_note])
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
    """答案节点: 记录总耗时 + 偷懒检测(硬约束)。
    偷懒判定: 模型'直接答'(没调工具) 但 该调工具(查询/下单类问题) 且 tool_results 空
              且 是第一次答 -> 打回 router 重跑(带强提示), 防止无限循环(最多 1 次)。"""
    t0 = state.get("_t0", time.perf_counter())
    answer = state.get("answer", "")
    tools_called = list(state.get("tool_results", {}).keys())
    retry = state.get("_retry_count", 0)

    need_tool = _needs_tool(state.get("user_input", ""))
    is_laziness = need_tool and not tools_called and not state.get("fallback_used")

    trace_entry = {"node": "answer", "fallback_used": state.get("fallback_used", False)}

    if is_laziness and retry < 1:
        # 打回 router: 加一条强提示, 逼模型这次真调工具
        state["messages"] = state.get("messages", []) + [{
            "role": "system",
            "content": "[强制] 你刚才没调任何工具就给答案。这是查询类问题, 必须先调 "
                       "search_products / check_stock / calculate_total 之一拿到真实数据, "
                       "再基于结果回答。现在重新来, 务必先调工具。",
        }]
        trace_entry["laziness_retry"] = True
        return {
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "trace": [trace_entry],
            "_retry_count": retry + 1,
            "_route": "router",
        }

    # 正常收尾
    trace_entry["laziness"] = is_laziness   # 记录: 最终仍是偷懒(打回也没救)就标出来
    return {
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "trace": [trace_entry],
        "_route": "answer",
    }


def _needs_tool(user_input: str) -> bool:
    """判断这个问题'该'调工具(查询/算价/下单)。闲聊/致谢不需要。
    偷懒检测的触发条件: 该调工具但一个都没调。"""
    kw = ("查", "库存", "多少钱", "价格", "推荐", "配", "下单", "买", "算",
          "显卡", "cpu", "内存", "硬盘", "电源", "散热", "机箱", "元")
    return any(k in user_input.lower() for k in kw)


def _route_decision(state: dict) -> str:
    return state.get("_route", "answer")


def _active_llm():
    """根据全局开关返回 真实 llm 或 mock llm(供评测隔离外部依赖)。"""
    return mock_llm if _USE_MOCK else llm


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
    # 答案节点: 偷懒则打回 router(最多 1 次), 否则收尾
    g.add_conditional_edges("answer", _answer_route,
                            {"router": "router", "end": END})
    return g.compile()


def _answer_route(state: dict) -> str:
    """answer 节点路由: 偷懒打回返回 'router'(重跑), 正常收尾返回 'end'。
    answer_node 设 _route='router' 表示要打回; 否则(_route='answer')收尾。"""
    return "router" if state.get("_route") == "router" else "end"


def run_agent(user_input: str, mock: bool = False,
              user_key: str = "user_demo", session_id: str = "") -> dict:
    """对外唯一入口: 跑一次 Agent 对话, 返回完整 state。
    mock=True 时用确定性 MockLLM(评测/CI 用, 不依赖 Agnes, 永远可复现)。
    user_key/session_id 用于记忆(短期会话 + 长期偏好)。"""
    global _USE_MOCK
    _USE_MOCK = mock
    state = _init_state(user_input, user_key, session_id)
    state["_t0"] = time.perf_counter()
    graph = build_graph()
    final = graph.invoke(state)

    # 对话结束存记忆(短期会话 + 抽取长期偏好)
    if not mock:   # mock 评测不污染记忆库
        from app.agent.memory import store_session, extract_and_store_preference
        store_session(user_key, final.get("session_id", session_id),
                      user_input, final.get("answer", ""))
        extract_and_store_preference(user_key, user_input, final.get("answer", ""))
    return final


if __name__ == "__main":
    print("=== 自检: '5000 元入门剪辑电脑配单' ===")
    out = run_agent("帮我配一套 5000 元以内的入门剪辑电脑, 重点 CPU 和内存")
    print("答案:", out.get("answer"))
    print("工具缓存:", out.get("tool_results"))
    print("降级:", out.get("fallback_used"))
    print("trace:", out.get("trace"))
