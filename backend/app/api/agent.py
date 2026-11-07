# Agent 对话端点(主战场)
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.graph import run_agent
from app.db.database import get_session, AgentTrace

router = APIRouter()


class ChatIn(BaseModel):
    message: str
    session_id: str = ""     # 同一会话带同一个 id, 短期记忆才接得上
    user_key: str = "user_demo"


@router.post("/agent/chat")
def chat(payload: ChatIn):
    """跑一次 Agent 对话。返回:
    { answer, tool_results, fallback_used, trace, latency_ms, tokens_in, tokens_out, session_id }
    """
    out = run_agent(payload.message, user_key=payload.user_key,
                    session_id=payload.session_id)

    # 落 trace 表(可观测)
    s = get_session()
    trace = AgentTrace(
        session_id=out.get("session_id", ""),
        user_input=payload.message,
        final_answer=out.get("answer", ""),
        tool_names=",".join(out.get("tool_results", {}).keys()),
        latency_ms=out.get("latency_ms", 0),
        tokens_in=out.get("tokens_in", 0),
        tokens_out=out.get("tokens_out", 0),
        fallback_used=1 if out.get("fallback_used") else 0,
        trace=json.dumps(out.get("trace", []), ensure_ascii=False),
    )
    s.add(trace)
    s.commit()
    s.close()

    return {
        "answer": out.get("answer", ""),
        "tool_results": out.get("tool_results", {}),
        "fallback_used": out.get("fallback_used", False),
        "trace": out.get("trace", []),
        "latency_ms": out.get("latency_ms", 0),
        "llm_ms": out.get("_llm_ms", 0),          # 真实 LLM 往返耗时(区别于编排)
        "laziness": any(t.get("laziness") for t in out.get("trace", [])),   # 最终是否仍是偷懒
        "tokens_in": out.get("tokens_in", 0),
        "tokens_out": out.get("tokens_out", 0),
        "session_id": out.get("session_id", ""),
    }
