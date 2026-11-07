# ============================================================================
#  工具定义 —— 选购场景的 4 个工具
#  每个工具: schema(给模型看的菜单) + impl(真正干活的函数) + 注册
#  工具失败不抛异常,翻译成文本喂回给模型(降级)
# ============================================================================
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.llm_client import register_tool, make_tool_schemas

# 共享 DB session(每个工具调用现开现关,避免跨请求污染)
from app.db.database import get_session, Product, Order


# --------------------------------------------------------------------------
# 工具 ① search_products:按关键词/类别/预算筛选商品
# --------------------------------------------------------------------------
def search_products(keyword: str = "", category: str = "", max_price: float = 0, limit: int = 10) -> str:
    s = get_session()
    q = s.query(Product)
    if keyword:
        q = q.filter(Product.name.ilike(f"%{keyword}%") | Product.spec.ilike(f"%{keyword}%"))
    if category:
        q = q.filter(Product.category == category)
    if max_price and max_price > 0:
        q = q.filter(Product.price <= max_price)
    rows = q.limit(limit).all()
    if not rows:
        return "(没找到符合条件的商品)"
    out = []
    for p in rows:
        out.append({
            "id": p.id, "name": p.name, "category": p.category,
            "brand": p.brand, "price": p.price, "stock": p.stock, "spec": p.spec,
        })
    s.close()
    return json.dumps(out, ensure_ascii=False)


# --------------------------------------------------------------------------
# 工具 ② check_stock:查某商品库存
# --------------------------------------------------------------------------
def check_stock(product_id: int) -> str:
    s = get_session()
    p = s.query(Product).filter(Product.id == product_id).first()
    s.close()
    if not p:
        return f"(商品 id={product_id} 不存在)"
    return f"{p.name} 库存 {p.stock} 件"


# --------------------------------------------------------------------------
# 工具 ③ calculate_total:算一组商品总价(购物车/订单用)
# --------------------------------------------------------------------------
def calculate_total(items_json: str) -> str:
    """items_json: '[{"product_id": 1, "qty": 2}, ...]'"""
    try:
        items = json.loads(items_json)
    except Exception as e:
        return f"(items 解析失败: {e})"
    s = get_session()
    total = 0.0
    lines = []
    for it in items:
        pid, qty = it.get("product_id"), it.get("qty", 1)
        p = s.query(Product).filter(Product.id == pid).first()
        if not p:
            lines.append(f"  {pid} -> 商品不存在")
            continue
        if p.stock < qty:
            lines.append(f"  {p.name} 库存不足(需 {qty},现有 {p.stock})")
        sub = p.price * qty
        total += sub
        lines.append(f"  {p.name} x{qty} = {sub:.2f}")
    s.close()
    lines.append(f"  合计: {total:.2f}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 工具 ④ create_order:下单(写 Order 表)
# --------------------------------------------------------------------------
def create_order(items_json: str, note: str = "") -> str:
    """items_json: '[{"product_id": 1, "qty": 2}, ...]'"""
    try:
        items = json.loads(items_json)
    except Exception as e:
        return f"(items 解析失败: {e})"
    s = get_session()
    total = 0.0
    for it in items:
        p = s.query(Product).filter(Product.id == it.get("product_id")).first()
        if not p:
            s.close()
            return f"(商品 {it.get('product_id')} 不存在,无法下单)"
        total += p.price * it.get("qty", 1)
    order = Order(items=json.dumps(items, ensure_ascii=False), total=total,
                  status="pending" + (f" note={note}" if note else ""))
    s.add(order)
    s.commit()
    oid = order.id
    s.close()
    return f"订单 #{oid} 已创建,合计 {total:.2f} 元,状态 {order.status}"


# ============================================================================
#  工具 schema(给模型的菜单)
# ============================================================================
SCHEMAS = {
    "search_products": {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "按关键词/类别/预算筛选商品,返回 JSON 列表。用户问'有什么显卡/5000 元内的 CPU'时用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "名称或参数关键词,如 'RTX 4060'"},
                    "category": {"type": "string", "description": "类别:显卡/CPU/内存/硬盘/机箱/电源/散热"},
                    "max_price": {"type": "number", "description": "预算上限,0 表示不限"},
                    "limit": {"type": "integer", "description": "最多返回几条,默认 10"},
                },
            },
        },
    },
    "check_stock": {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "查某商品库存。用户问'还有货吗'时用。",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    "calculate_total": {
        "type": "function",
        "function": {
            "name": "calculate_total",
            "description": "算一组商品总价。用户给了多个商品要下单/购物车时用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "items_json": {"type": "string",
                                    "description": '[{"product_id":1,"qty":2}, ...] 的 JSON 字符串'},
                },
                "required": ["items_json"],
            },
        },
    },
    "create_order": {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "下单,写 Order 表。用户明确说'下单/购买/买'时才用,别擅自下单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "items_json": {"type": "string",
                                    "description": '[{"product_id":1,"qty":2}, ...]'},
                    "note": {"type": "string", "description": "备注,可空"},
                },
                "required": ["items_json"],
            },
        },
    },
}

# 注册
for _name, _sch in SCHEMAS.items():
    register_tool(_name, globals()[_name], _sch)

# ============================================================================
# 工具 ⑤ search_knowledge: RAG 检索选购知识库(领域知识/搭配建议/售后)
# 区别于 search_products: 那个查"商品数据", 这个查"选购经验知识"。
# 面试点: 这是 Agentic RAG —— Agent 自己决定"什么时候该查知识库", 而非固定 RAG 管道。
# ============================================================================
from app.agent.rag import retriever


def search_knowledge(query: str = "", top_k: int = 3) -> str:
    """在选购知识库里检索, 返回带来源的 chunk(供 LLM 基于知识回答 + 引用溯源)。"""
    if not query:
        return "(请提供检索问题)"
    hits = retriever.search(query, top_k=top_k)
    if not hits:
        return "(知识库里没检索到相关内容)"
    lines = []
    for i, h in enumerate(hits, 1):
        lines.append(f"[{i}] ({h['source']}/{h['section']}) {h['text']}")
    lines.append("(回答时请基于以上内容, 并标注引用 [n])")
    return "\n".join(lines)


SCHEMAS["search_knowledge"] = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": "在选购知识库中检索领域知识/搭配建议/售后政策。用户问'怎么选/什么参数好/保修多久/5000 怎么配'这类经验性问题时用, 别用它查具体商品价格(那个用 search_products)。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题, 如 '入门剪辑显卡怎么选'"},
                "top_k": {"type": "integer", "description": "返回几条, 默认 3"},
            },
            "required": ["query"],
        },
    },
}
register_tool("search_knowledge", search_knowledge, SCHEMAS["search_knowledge"])

# 便捷索引(含新工具)
TOOL_SCHEMAS = make_tool_schemas(list(SCHEMAS.keys()))


if __name__ == "__main__":
    # 自检:工具能跑通
    print("=== 自检 1:search_products ===")
    print(search_products(category="显卡", max_price=3000))
    print("\n=== 自检 2:calculate_total ===")
    print(calculate_total('[{"product_id":1,"qty":1},{"product_id":5,"qty":1}]'))
    print("\n=== 自检 3:create_order ===")
    print(create_order('[{"product_id":1,"qty":1}]', note="自测"))
    print("\n工具自检通过 OK")
