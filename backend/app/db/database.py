# ============================================================================
#  数据库层 —— SQLAlchemy 2.0 + Postgres
#  模型:Product / Order / AgentTrace
#  种子:run_seed.py(手动跑一次)
# ============================================================================
from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Integer, String, Float, Text, DateTime, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DB_URL = os.environ["DATABASE_URL"]
engine = create_engine(DB_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(64), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spec: Mapped[str] = mapped_column(Text, default="")   # 关键参数,给 LLM 看的

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "category": self.category,
            "brand": self.brand, "price": self.price, "stock": self.stock,
            "spec": self.spec,
        }


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    items: Mapped[str] = mapped_column(Text)   # JSON 字符串: [{product_id, qty}]
    total: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id, "created_at": str(self.created_at),
            "items": json.loads(self.items) if self.items else [],
            "total": self.total, "status": self.status,
        }


class AgentTrace(Base):
    """可观测:每次 Agent 对话把节点/工具/耗时/token 落表,前端展示用。"""
    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_input: Mapped[str] = mapped_column(Text)
    final_answer: Mapped[str] = mapped_column(Text, default="")
    tool_names: Mapped[str] = mapped_column(Text, default="")  # 逗号分隔
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[int] = mapped_column(Integer, default=0)
    trace: Mapped[str] = mapped_column(Text, default="")   # JSON: 节点级 trace


def get_session() -> Session:
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=engine)()


if __name__ == "__main__":
    # 自检:建表 + 打印
    Base.metadata.create_all(engine)
    with engine.connect() as c:
        print("已建表:", [Base.metadata.tables[k].name for k in Base.metadata.tables])
