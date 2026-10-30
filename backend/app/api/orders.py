# 订单查询/下单
import json
from fastapi import APIRouter, HTTPException
from app.db.database import get_session, Order, Product

router = APIRouter()


@router.get("/orders")
def list_orders(limit: int = 20):
    s = get_session()
    rows = s.query(Order).order_by(Order.id.desc()).limit(limit).all()
    s.close()
    return [o.to_dict() for o in rows]


@router.get("/orders/{oid}")
def get_order(oid: int):
    s = get_session()
    o = s.query(Order).filter(Order.id == oid).first()
    s.close()
    if not o:
        raise HTTPException(404, "订单不存在")
    return o.to_dict()


@router.post("/orders")
def create_order(payload: dict):
    """payload: {"items": [{"product_id":1,"qty":2}], "note": ""}"""
    items = payload.get("items", [])
    note = payload.get("note", "")
    s = get_session()
    total = 0.0
    for it in items:
        p = s.query(Product).filter(Product.id == it.get("product_id")).first()
        if not p:
            s.close()
            raise HTTPException(400, f"商品 {it.get('product_id')} 不存在")
        total += p.price * it.get("qty", 1)
    o = Order(items=json.dumps(items, ensure_ascii=False), total=total,
              status="pending" + (f" note={note}" if note else ""))
    s.add(o)
    s.commit()
    oid = o.id
    s.close()
    return {"id": oid, "total": total}
