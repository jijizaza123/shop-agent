# 商品 CRUD + 购物车(加入购物车/改数量/结算下单)
import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.db.database import get_session, Product, Order

router = APIRouter()


class AddToCartIn(BaseModel):
    product_id: int
    qty: int = 1


# ---------------------------------------------------------------- 商品查询
@router.get("/products")
def list_products(keyword: str = "", category: str = "",
                  max_price: float = 0, limit: int = 50):
    s = get_session()
    q = s.query(Product)
    if keyword:
        q = q.filter(Product.name.ilike(f"%{keyword}%") | Product.spec.ilike(f"%{keyword}%"))
    if category:
        q = q.filter(Product.category == category)
    if max_price and max_price > 0:
        q = q.filter(Product.price <= max_price)
    rows = q.order_by(Product.price).limit(limit).all()
    s.close()
    return [p.to_dict() for p in rows]


@router.get("/products/categories")
def categories():
    s = get_session()
    rows = s.query(Product.category).distinct().all()
    s.close()
    return [r[0] for r in rows]


@router.get("/products/{pid}")
def get_product(pid: int):
    s = get_session()
    p = s.query(Product).filter(Product.id == pid).first()
    s.close()
    return p.to_dict() if p else {"error": "not found"}


# ---------------------------------------------------------------- 购物车
@router.get("/cart")
def get_cart():
    """当前购物车(演示用全局, 真实项目按 user_id 隔离)。"""
    s = get_session()
    rows = s.query(Order).filter(Order.status == "cart").order_by(Order.id.desc()).all()
    s.close()
    # cart 存的是 items JSON; 取最近一条"购物车"状态的记录作为当前车
    if not rows:
        return {"items": [], "total": 0.0}
    cart = rows[0]
    return {"items": json.loads(cart.items) if cart.items else [], "total": cart.total}


@router.post("/cart/add")
def add_to_cart(payload: AddToCartIn):
    s = get_session()
    p = s.query(Product).filter(Product.id == payload.product_id).first()
    if not p:
        s.close()
        raise HTTPException(404, f"商品 {payload.product_id} 不存在")
    if p.stock < payload.qty:
        s.close()
        raise HTTPException(400, f"{p.name} 库存不足(需 {payload.qty}, 现有 {p.stock})")

    # 取/建当前购物车(一条 status=cart 的 Order)
    cart = s.query(Order).filter(Order.status == "cart").order_by(Order.id.desc()).first()
    if cart is None:
        cart = Order(items="[]", total=0.0, status="cart")
        s.add(cart)
    items = json.loads(cart.items) if cart.items else []
    # 同商品累加数量
    merged = False
    for it in items:
        if it.get("product_id") == payload.product_id:
            it["qty"] = it.get("qty", 0) + payload.qty
            merged = True
            break
    if not merged:
        items.append({"product_id": payload.product_id, "qty": payload.qty})
    cart.items = json.dumps(items, ensure_ascii=False)
    cart.total = _calc_total(s, items)
    s.commit()
    total = cart.total          # 在 close 之前取出来, 避免 DetachedInstanceError
    s.close()
    return {"items": items, "total": total}


@router.post("/cart/qty")
def update_qty(payload: dict):
    """payload: {product_id, qty}  改某商品数量(0=移除)"""
    s = get_session()
    cart = s.query(Order).filter(Order.status == "cart").order_by(Order.id.desc()).first()
    if cart is None:
        s.close()
        return {"items": [], "total": 0.0}
    items = json.loads(cart.items) if cart.items else []
    pid = payload.get("product_id")
    qty = int(payload.get("qty", 0))
    new_items = [it for it in items if it.get("product_id") != pid]
    if qty > 0:
        new_items.append({"product_id": pid, "qty": qty})
    cart.items = json.dumps(new_items, ensure_ascii=False)
    cart.total = _calc_total(s, new_items)
    s.commit()
    total = cart.total
    s.close()
    return {"items": new_items, "total": total}


@router.post("/cart/checkout")
def checkout():
    """结算: 校验库存 -> 扣库存 -> 生成正式订单(status=pending) -> 清空购物车。"""
    s = get_session()
    cart = s.query(Order).filter(Order.status == "cart").order_by(Order.id.desc()).first()
    if cart is None or not (json.loads(cart.items) if cart.items else []):
        s.close()
        raise HTTPException(400, "购物车为空")
    items = json.loads(cart.items)

    # 库存校验
    for it in items:
        p = s.query(Product).filter(Product.id == it.get("product_id")).first()
        if not p:
            s.close()
            raise HTTPException(400, f"商品 {it.get('product_id')} 不存在")
        if p.stock < it.get("qty", 1):
            s.close()
            raise HTTPException(400, f"{p.name} 库存不足(需 {it.get('qty')}, 现有 {p.stock})")

    total = _calc_total(s, items)
    # 扣库存
    for it in items:
        p = s.query(Product).filter(Product.id == it.get("product_id")).first()
        p.stock -= it.get("qty", 1)
    # 正式订单
    order = Order(items=cart.items, total=total, status="pending")
    s.add(order)
    s.delete(cart)
    s.commit()
    oid = order.id
    s.close()
    return {"order_id": oid, "total": total, "status": "pending",
            "msg": f"订单 #{oid} 已创建, 合计 {total:.2f} 元"}


def _calc_total(s, items: list) -> float:
    total = 0.0
    for it in items:
        p = s.query(Product).filter(Product.id == it.get("product_id")).first()
        if p:
            total += p.price * it.get("qty", 1)
    return total
