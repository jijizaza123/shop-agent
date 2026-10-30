# Agent 可观测(Trace 历史)
from fastapi import APIRouter
from app.db.database import get_session, AgentTrace

router = APIRouter()


@router.get("/traces")
def list_traces(limit: int = 50):
    s = get_session()
    rows = s.query(AgentTrace).order_by(AgentTrace.id.desc()).limit(limit).all()
    out = []
    for r in rows:
        import json
        out.append({
            "id": r.id, "created_at": str(r.created_at),
            "session_id": r.session_id, "user_input": r.user_input,
            "final_answer": r.final_answer[:200],
            "tool_names": r.tool_names, "latency_ms": r.latency_ms,
            "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
            "fallback_used": bool(r.fallback_used),
            "trace": json.loads(r.trace) if r.trace else [],
        })
    s.close()
    return out
