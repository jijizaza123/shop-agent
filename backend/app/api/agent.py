# Agent 对话端点(主战场)
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.graph import run_agent
from app.db.database import get_session, AgentTrace

router = APIRouter()


class ChatIn(BaseModel):
    message: str
    history: list = []   # 可选: 带历史对话(当前简化,只用最后一轮)


@router.post("/agent/chat")
def chat(payload: ChatIn):
    """跑一次 Agent 对话。返回:
    { answer, tool_results, fallback_used, trace, latency_ms, tokens_in, tokens_out }
    """
    out = run_agent(payload.message)

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
        "tokens_in": out.get("tokens_in", 0),
        "tokens_out": out.get("tokens_out", 0),
        "session_id": out.get("session_id", ""),
    }
