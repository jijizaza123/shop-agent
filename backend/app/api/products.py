# 商品 CRUD
from fastapi import APIRouter
from app.db.database import get_session, Product

router = APIRouter()


@router.get("/products")
def list_products(keyword: str = "", category: str = "", max_price: float = 0, limit: int = 50):
    s = get_session()
    q = s.query(Product)
    if keyword:
        q = q.filter(Product.name.ilike(f"%{keyword}%") | Product.spec.ilike(f"%{keyword}%"))
    if category:
        q = q.filter(Product.category == category)
    if max_price and max_price > 0:
        q = q.filter(Product.price <= max_price)
    rows = q.limit(limit).all()
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
