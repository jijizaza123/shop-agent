# ============================================================================
#  记忆模块 —— Agent 两层记忆
#  短期(会话): 按 session_id 存最近 N 轮对话, 多轮上下文接得上
#  长期(偏好): 从对话抽取稳定偏好(预算/品类/品牌), 注入 system 做个性化推荐
#
#  面试重点:
#  - 短期=滑窗控上下文长度(只带最近 N 轮, 避免 token 爆炸)
#  - 长期=偏好抽取。这里用关键词启发式(预算/品类/品牌), 生产可换成 LLM
#    判断"这条值不值得长期记", 避免把闲聊全灌进永久库。
#  - 为什么落 Postgres 而不是内存: 服务重启/多实例不丢, 且偏好跨会话保留。
# ============================================================================
import json
import re
from app.db.database import get_session, AgentMemory

# 短期记忆只带最近几轮(控上下文长度)
SHORT_TERM_TURNS = 6


def build_context(user_key: str = "user_demo", session_id: str = "") -> dict:
    """给 graph 注入用: 返回要拼进 system prompt 的记忆块。
    { "short_term": [最近几轮对话], "preferences": [长期偏好 JSON] }"""
    s = get_session()
    # 短期: 最近 N 轮该会话
    short = (s.query(AgentMemory)
             .filter(AgentMemory.kind == "session",
                     AgentMemory.session_id == session_id)
             .order_by(AgentMemory.id.desc())
             .limit(SHORT_TERM_TURNS)
             .all())
    short_list = [{"kind": m.kind, "content": m.content} for m in reversed(short)]

    # 长期: 该用户所有偏好
    prefs = (s.query(AgentMemory)
             .filter(AgentMemory.kind == "preference",
                     AgentMemory.user_key == user_key)
             .order_by(AgentMemory.id.desc())
             .limit(10)
             .all())
    pref_list = []
    for p in prefs:
        try:
            pref_list.append(json.loads(p.content))
        except Exception:
            pref_list.append({"raw": p.content})
    s.close()
    return {"short_term": short_list, "preferences": pref_list}


def store_session(user_key: str, session_id: str, user_input: str, agent_answer: str) -> None:
    """对话结束存一条短期记忆(一问一答)。"""
    s = get_session()
    s.add(AgentMemory(user_key=user_key, session_id=session_id, kind="session",
                      content=json.dumps({"user": user_input, "assistant": agent_answer},
                                         ensure_ascii=False)))
    s.commit()
    s.close()


def extract_and_store_preference(user_key: str, user_input: str, agent_answer: str) -> None:
    """从对话里抽稳定偏好, 有就存(去重), 没有就跳过。
    关键词启发式: 预算(数字+元) / 品类(显卡/CPU/...) / 品牌(Intel/AMD/...)"""
    prefs = {}
    m = re.search(r"(\d{3,5})\s*元", user_input)
    if m:
        prefs["budget"] = int(m.group(1))
    for kw in ("显卡", "CPU", "内存", "硬盘", "机箱", "电源", "散热",
               "Intel", "AMD", "NVIDIA", "剪辑", "电竞"):
        if kw.lower() in user_input.lower() or kw.lower() in agent_answer.lower():
            cat = "显卡" if "显卡" in kw else ("CPU" if "CPU" in kw else kw)
            prefs.setdefault("categories", []).append(kw)
    if prefs:
        prefs_str = json.dumps(prefs, ensure_ascii=False)
        s = get_session()
        # 去重: 同 user_key 下完全相同的偏好不重复插
        dup = s.query(AgentMemory).filter(
            AgentMemory.kind == "preference",
            AgentMemory.user_key == user_key,
            AgentMemory.content == prefs_str,
        ).first()
        if not dup:
            s.add(AgentMemory(user_key=user_key, kind="preference", content=prefs_str))
            s.commit()
        s.close()


if __name__ == "__main__":
    # 自检: 存一条对话 + 抽偏好 + 读回上下文
    store_session("user_demo", "s-test", "帮我配 5000 元剪辑电脑, 喜欢 Intel", "已推荐 i5 + 32G")
    extract_and_store_preference("user_demo", "帮我配 5000 元剪辑电脑, 喜欢 Intel", "推荐 i5")
    ctx = build_context("user_demo", "s-test")
    print("短期记忆:", ctx["short_term"])
    print("长期偏好:", ctx["preferences"])
