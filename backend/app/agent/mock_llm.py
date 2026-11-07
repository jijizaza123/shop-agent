# ============================================================================
#  mock_llm.py —— 确定性"伪 LLM"层, 用于不依赖 Agnes 的可重复评测
#
#  为什么需要(面试重点):
#   真实 LLM 评测有两个致命问题:
#     1. 非确定性(同样输入答案不一样) -> 没法回归, 改了 prompt 不知道是好是坏
#     2. 外部依赖(限流/超时/额度) -> 评测报告被污染(就像 429 把成功率打到 10%)
#   解法: 把"评测目标"拆成两层
#     - 工具/降级链路(mock 层测): 输入->该调哪个工具->结果是否回填->降级是否正确
#       用确定性规则替代 LLM 的"决定调哪个工具", 永远可复现
#     - LLM 真实能力(real 层测): 自然语言理解/答案质量 -> 打真实 Agnes, 小样本
#   简历上放的是 mock 层数字("评测框架正确性 + 工具链路"), 不是被限流污染的 real 层。
#
#  接口: 仿 OpenAI 的 resp.choices[0].message(.content/.tool_calls/.usage),
#        让 graph.py 的 router/fallback 节点不用改就能挂上 mock。
# ============================================================================
import json
import re
import time


class _Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Usage:
    def __init__(self, pin=0, pout=0):
        self.prompt_tokens = pin
        self.completion_tokens = pout


class _Resp:
    def __init__(self, content=None, tool_calls=None, usage=None):
        self.choices = [type("C", (), {"message": _Msg(content, tool_calls)})]
        self.usage = usage or _Usage()


# --------------------------------------------------------------------------
# 确定性"决策规则": 看用户话里有什么关键词 -> 决定调哪个工具(模拟 LLM 的 tool 选择)
# --------------------------------------------------------------------------
def _pick_tool(user_input: str, prev_tool: str = "") -> tuple:
    """返回 (工具名, 参数dict) 或 (None, None)。
    这是"模拟 LLM 的 function-calling 决策"的部分 —— 用规则替代模型, 保证可复现。
    关键词覆盖 dataset 里 20 个 case 的意图。"""
    t = user_input.lower()
    has_order = any(k in user_input for k in ("下单", "购买", "买"))

    # 下单意图: 先算价再下单。mock 里简化: 下单直接调 create_order
    if has_order:
        items = _find_product_ids(user_input, limit=2)
        return ("create_order", {"items_json": json.dumps(
            [{"product_id": pid, "qty": 1} for pid in items], ensure_ascii=False)})

    # 库存/价格类: 提到具体商品名 -> check_stock(带真实 product_id)
    if any(k in t for k in ("库存", "还有货", "有货", "缺货")):
        pid = _find_product_ids(user_input, limit=1)
        pid = pid[0] if pid else 0
        return ("check_stock", {"product_id": pid})

    # 算价意图(多商品明确算总价): -> calculate_total
    # 注意: 单商品"XX 多少钱/价格"应走 search_products(查价+库存), 不算价
    m_multi = re.search(r"(\d{3,5})\s*元", user_input)
    budget = int(m_multi.group(1)) if m_multi else 0
    if any(k in t for k in ("总价", "算价", "算下")):
        items = _find_product_ids(user_input, limit=3)
        if items:
            return ("calculate_total", {"items_json": json.dumps(
                [{"product_id": pid, "qty": 1} for pid in items], ensure_ascii=False)})

    # 单商品问价/查详情(多少钱/价格/查一下): -> search_products(返回价格+库存)
    if any(k in t for k in ("多少钱", "价格", "查一下", "查下")):
        kw = _extract_keyword(user_input)
        return ("search_products", {"keyword": kw, "max_price": 0})

    # 预算/推荐/配置类 -> search_products(按关键词+预算)
    m = re.search(r"(\d{3,5})\s*元", user_input)
    budget = int(m.group(1)) if m else 0
    if any(k in t for k in ("推荐", "配置", "配一套", "配一台", "怎么配", "有哪些", "有什么", "便宜")):
        kw = _extract_keyword(user_input)
        return ("search_products", {"keyword": kw, "max_price": budget})

    # RAG 意图(纯知识型: 怎么选/保修/参数/哪个好): 放到商品意图之后, 避免抢"推荐 XX 商品"
    if any(k in t for k in ("怎么选", "怎么选", "哪个参数", "参数", "保修", "售后",
                            "哪个好", "什么好", "注意", "搭配")):
        return ("search_knowledge", {"query": user_input.strip()[:30], "top_k": 3})

    # 默认: 兜底, 让模型(这里直接)给个答案
    return (None, None)


def _find_product_ids(text: str, limit: int = 3) -> list:
    """从自然语言里粗匹配真实商品 id(mock 用, 真实 LLM 会语义理解)。
    查数据库按关键词模糊匹配, 保证返回的是存在的 id。"""
    try:
        from app.db.database import get_session, Product
        kw_map = [("rtx 4060", "rtx 4060"), ("rtx 4070", "rtx 4070"),
                   ("i5-14600k", "i5-14600k"), ("i7-14700k", "i7-14700k"),
                   ("32g", "32g"), ("2t", "2t"), ("1t", "1t"),
                   ("850w", "850w"), ("1000w", "1000w"), ("240", "240"),
                   ("ssd", "ssd"), ("ddr5", "ddr5"),
                   ("amd", "amd"), ("intel", "intel"), ("radeon", "radeon"),
                   ("rx", "rx"), ("nvidia", "nvidia")]
        low = text.lower()
        s = get_session()
        ids = []
        for _k, real in kw_map:
            if _k in low:
                p = s.query(Product).filter(Product.name.ilike(f"%{real}%")).first()
                if p:
                    ids.append(p.id)
        s.close()
        return ids[:limit]
    except Exception:
        return []


def _extract_keyword(text: str) -> str:
    """从自然语言里粗提商品关键词(演示级, 真实 LLM 会做语义理解)。"""
    kw_map = [
        ("显卡", "显卡"), ("cpu", "cpu"), ("内存", "内存"), ("硬盘", "硬盘"),
        ("机箱", "机箱"), ("电源", "电源"), ("散热", "散热"), ("ssd", "ssd"),
        ("rtx", "rtx"), ("剪辑", "剪辑"), ("电竞", "电竞"), ("amd", "amd"),
        ("intel", "intel"), ("ddr5", "ddr5"),
    ]
    low = text.lower()
    for k, v in kw_map:
        if k in low:
            return v
    return ""


# --------------------------------------------------------------------------
# MockLLMClient —— 接口对齐 llm_client.llm, graph.py 换掉这一行就能切 mock
# --------------------------------------------------------------------------
class MockLLMClient:
    """确定性 LLM 替身。
    第一轮: 按规则返回 tool_call(模拟 LLM 决定调工具);
    第二轮(已回填 tool 结果): 基于工具结果生成最终答案(模拟 LLM 总结)。
    不做真实推理, 只验证"工具链路 + 降级"是否正确。"""

    def chat(self, messages, tools=None, **kwargs):
        # 判断是否已经回填过工具结果 -> 该给最终答案了
        has_tool_result = any(m.get("role") == "tool" for m in messages)
        user_input = next((m["content"] for m in messages if m.get("role") == "user"), "")

        if has_tool_result:
            # 第二轮: 基于最近一条 tool 结果拼一个"最终答案"
            last_tool = next((m["content"] for m in reversed(messages) if m.get("role") == "tool"), "")
            answer = f"基于查询结果: {last_tool[:80]}"
            return _Resp(content=answer, usage=_Usage(500, 100))

        # 第一轮: 按规则决定调哪个工具
        tool_name, args = _pick_tool(user_input)
        if tool_name is None:
            return _Resp(content="我理解您的需求, 但没有找到合适的工具处理。", usage=_Usage(200, 50))

        # 构造 OpenAI 风格的 tool_calls
        import json
        tool_call = [type("TC", (), {
            "id": "call_mock_1",
            "type": "function",
            "function": type("F", (), {"name": tool_name, "arguments": json.dumps(args, ensure_ascii=False)}),
        })]
        return _Resp(content=None, tool_calls=tool_call, usage=_Usage(400, 80))


# 默认 mock 实例(供 graph.run_agent(mock=True) 注入)
mock_llm = MockLLMClient()
